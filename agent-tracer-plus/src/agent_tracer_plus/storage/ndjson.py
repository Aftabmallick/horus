"""NDJSON (Newline Delimited JSON) file storage backend.

Append-only .jsonl files — crash-safe, human-readable, great for debugging.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_tracer_plus.core.models import Span, Trace
from agent_tracer_plus.storage.base import StorageBackend
from agent_tracer_plus.utils.logger import get_logger
from agent_tracer_plus.utils.serialization import SafeEncoder

logger = get_logger("storage.ndjson")


class NDJSONBackend(StorageBackend):
    """Stores traces and spans as newline-delimited JSON files.

    Args:
        directory: Directory to store .jsonl files. Created if it doesn't exist.
    """

    def __init__(self, directory: str = "./agent_traces") -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._traces_file = self._dir / "traces.jsonl"
        self._spans_file = self._dir / "spans.jsonl"
        self._lock = asyncio.Lock()

    async def _append(self, filepath: Path, data: Dict[str, Any]) -> None:
        """Append a JSON line to a file."""
        line = json.dumps(data, cls=SafeEncoder, default=str) + "\n"
        async with self._lock:
            # Use sync I/O in thread to avoid aiofiles dependency
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_line, filepath, line)

    @staticmethod
    def _write_line(filepath: Path, line: str) -> None:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line)

    async def save_trace(self, trace: Trace) -> None:
        data = trace.to_dict()
        data["_type"] = "trace"
        await self._append(self._traces_file, data)

    async def save_span(self, span: Span) -> None:
        data = span.to_dict()
        data["_type"] = "span"
        await self._append(self._spans_file, data)

    async def save_spans_batch(self, spans: List[Span]) -> None:
        lines = []
        for span in spans:
            data = span.to_dict()
            data["_type"] = "span"
            lines.append(json.dumps(data, cls=SafeEncoder, default=str) + "\n")

        async with self._lock:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._write_lines, self._spans_file, lines
            )

    @staticmethod
    def _write_lines(filepath: Path, lines: List[str]) -> None:
        with open(filepath, "a", encoding="utf-8") as f:
            f.writelines(lines)

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Linear scan — not efficient for large datasets."""
        if not self._traces_file.exists():
            return None
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._find_trace, trace_id)
        return result

    def _find_trace(self, trace_id: str) -> Optional[Trace]:
        with open(self._traces_file, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("trace_id") == trace_id:
                        trace = Trace(trace_id=trace_id)
                        trace.agent_name = data.get("agent_name", "")
                        trace.duration_ms = data.get("duration_ms", 0.0)
                        return trace
                except json.JSONDecodeError:
                    continue
        return None

    async def get_spans(self, trace_id: str) -> List[Span]:
        if not self._spans_file.exists():
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._find_spans, trace_id)

    def _find_spans(self, trace_id: str) -> List[Span]:
        spans = []
        with open(self._spans_file, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("trace_id") == trace_id:
                        span = Span(name=data.get("name", ""), span_id=data.get("span_id", ""))
                        span.trace_id = trace_id
                        span.duration_ms = data.get("duration_ms", 0.0)
                        spans.append(span)
                except json.JSONDecodeError:
                    continue
        return spans

    async def query_traces(
        self,
        filters: Dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        if not self._traces_file.exists():
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._query, filters, limit, offset)

    def _query(
        self, filters: Dict[str, Any] | None, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        results = []
        with open(self._traces_file, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if filters:
                        if all(data.get(k) == v for k, v in filters.items()):
                            results.append(data)
                    else:
                        results.append(data)
                except json.JSONDecodeError:
                    continue
        return results[offset : offset + limit]

    async def delete_traces(self, before: datetime) -> int:
        # NDJSON doesn't support efficient deletion — would need file rewrite
        logger.warning("delete_traces not efficiently supported for NDJSON backend")
        return 0

    async def flush(self) -> None:
        pass  # Writes are flushed immediately

    async def close(self) -> None:
        pass  # No persistent connections
