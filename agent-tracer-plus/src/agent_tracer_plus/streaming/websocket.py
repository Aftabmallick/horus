"""Live tail WebSocket server with per-client filter subscriptions.

Features:
- URL query param filters: ws://host:8765/?filter=agent:MyAgent&filter=status:error
- Per-client subscription management (not broadcast-all)
- Optional token authentication
- Backpressure: slow consumers are disconnected gracefully
- Heartbeat ping/pong to detect stale connections
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    WebSocketServerProtocol = Any  # type: ignore[misc,assignment]


class _FilterPredicate:
    """Evaluates simple field=value filter expressions against trace dicts."""

    def __init__(self, filters: list[str]) -> None:
        """Parse filter strings like 'agent:MyAgent', 'status:error'."""
        self._rules: list[tuple[str, str]] = []
        for f in filters:
            if ":" in f:
                key, _, value = f.partition(":")
                self._rules.append((key.strip(), value.strip()))

    def matches(self, trace: Dict[str, Any]) -> bool:
        """Return True if the trace satisfies ALL filter rules."""
        for key, value in self._rules:
            trace_value = str(trace.get(key, "")).lower()
            if value.lower() not in trace_value:
                return False
        return True


class _ClientSession:
    """Represents a connected WebSocket client with its own filter."""

    def __init__(
        self,
        ws: Any,
        filters: list[str],
        auth_token: Optional[str] = None,
        send_queue_size: int = 100,
    ) -> None:
        self.ws = ws
        self.predicate = _FilterPredicate(filters)
        self.auth_token = auth_token
        self.send_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=send_queue_size)
        self.closed = False

    async def send_loop(self) -> None:
        """Drain the send queue. Disconnects if the queue is full (backpressure)."""
        try:
            while not self.closed:
                try:
                    message = await asyncio.wait_for(self.send_queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send a heartbeat ping
                    try:
                        await self.ws.ping()
                    except Exception:
                        break
                    continue
                try:
                    await self.ws.send(message)
                except Exception:
                    break
        finally:
            self.closed = True

    def enqueue(self, trace_data: Dict[str, Any]) -> None:
        """Enqueue trace data if it matches client filters. Drop if queue is full (backpressure)."""
        if self.closed:
            return
        if not self.predicate.matches(trace_data):
            return
        try:
            self.send_queue.put_nowait(json.dumps(trace_data))
        except asyncio.QueueFull:
            logger.warning("Live tail client queue full — dropping trace (backpressure)")


class TraceStreamServer:
    """WebSocket server for real-time trace streaming.

    Usage:
        server = TraceStreamServer(host="localhost", port=8765, auth_token="secret")
        await server.start()

        # In tracer:
        server.broadcast(trace.to_dict())

    Client connects with filters:
        ws://localhost:8765/?filter=agent:RecruitmentAgent&filter=status:error
        ws://localhost:8765/?filter=status:error  (auth via header or token param)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        auth_token: Optional[str] = None,
    ) -> None:
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets package required for live tail. "
                "Install with: pip install websockets"
            )
        self.host = host
        self.port = port
        self._auth_token = auth_token
        self._clients: Set[_ClientSession] = set()
        self._server: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def _authenticate(self, ws: Any, path: str) -> Optional[str]:
        """Validate auth token from query string or Authorization header.

        Returns the token if valid, None if auth is disabled.
        Closes connection and returns '__REJECTED__' if auth fails.
        """
        if not self._auth_token:
            return None  # Auth disabled

        # Parse query string
        parsed = urllib.parse.urlparse(path)
        params = urllib.parse.parse_qs(parsed.query)
        token_param = params.get("token", [None])[0]

        # Check Authorization header (websockets exposes request headers)
        auth_header = None
        try:
            auth_header = ws.request_headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                auth_header = auth_header[7:]
        except AttributeError:
            pass

        provided_token = token_param or auth_header
        if provided_token != self._auth_token:
            await ws.close(code=4001, reason="Unauthorized")
            return "__REJECTED__"

        return provided_token

    def _parse_filters(self, path: str) -> list[str]:
        """Extract filter query params from the WebSocket path."""
        parsed = urllib.parse.urlparse(path)
        params = urllib.parse.parse_qs(parsed.query)
        return params.get("filter", [])

    async def _handler(self, ws: Any, path: str = "/") -> None:
        """Handle a new WebSocket connection."""
        # Authenticate
        auth_result = await self._authenticate(ws, path)
        if auth_result == "__REJECTED__":
            return

        # Parse filters
        filters = self._parse_filters(path)
        session = _ClientSession(ws, filters)
        self._clients.add(session)

        filter_desc = ",".join(filters) if filters else "all"
        logger.info(
            f"Live tail client connected. filter=[{filter_desc}] "
            f"total={len(self._clients)}"
        )

        # Send welcome message
        try:
            await ws.send(json.dumps({
                "type": "connected",
                "filter": filters,
                "message": f"Live tail active. Streaming traces matching: {filter_desc}",
            }))
        except Exception:
            pass

        try:
            # Run send loop and keepalive concurrently
            send_task = asyncio.create_task(session.send_loop())
            # Wait for the connection to close
            async for _ in ws:
                pass  # Accept but ignore incoming messages
            send_task.cancel()
        except Exception:
            pass
        finally:
            session.closed = True
            self._clients.discard(session)
            logger.info(f"Live tail client disconnected. total={len(self._clients)}")

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._loop = asyncio.get_running_loop()
        self._server = await websockets.serve(  # type: ignore[attr-defined]
            self._handler, self.host, self.port
        )
        logger.info(f"Live tail server listening on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Live tail server stopped")

    def broadcast(self, trace_data: Dict[str, Any]) -> None:
        """Broadcast trace data to all clients whose filters match.

        Each client has its own filter predicate and send queue.
        Slow clients are dropped (backpressure) without affecting others.
        """
        if not self._clients or not self._loop:
            return

        dead = set()
        for session in self._clients:
            if session.closed:
                dead.add(session)
                continue
            session.enqueue(trace_data)

        # Clean up stale sessions
        self._clients -= dead

    @property
    def client_count(self) -> int:
        """Number of currently connected clients."""
        return len(self._clients)

    def get_client_stats(self) -> list[Dict[str, Any]]:
        """Return stats for all connected clients (for /metrics)."""
        return [
            {
                "filters": [f"{k}:{v}" for k, v in s.predicate._rules],
                "queue_depth": s.send_queue.qsize(),
                "closed": s.closed,
            }
            for s in self._clients
        ]
