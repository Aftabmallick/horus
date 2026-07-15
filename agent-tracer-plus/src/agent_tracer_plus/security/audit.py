"""Audit logging framework for Agent Tracer Plus."""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Types of actions that can be audited."""
    VIEW_TRACE = "VIEW_TRACE"
    EXPORT_TRACES = "EXPORT_TRACES"
    DELETE_TRACES = "DELETE_TRACES"
    CONFIG_CHANGED = "CONFIG_CHANGED"
    POLICY_UPDATED = "POLICY_UPDATED"
    ACCESS_DENIED = "ACCESS_DENIED"
    CREATE_API_KEY = "CREATE_API_KEY"
    RBAC_ROLE_CHANGE = "RBAC_ROLE_CHANGE"


class AuditLogger:
    """Enterprise audit logger for security events."""

    def __init__(self, backend_url: Optional[str] = None):
        self.backend_url = backend_url
        self.logger = logging.getLogger("agent_tracer_plus.audit")

    def log_event(
        self,
        action: AuditAction | str,
        actor: str,
        target: str,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> None:
        """Log a security or access event."""
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action.value if isinstance(action, AuditAction) else action,
            "actor": actor,
            "target": target,
            "ip_address": ip_address or "unknown",
            "success": success,
            "metadata": metadata or {}
        }

        # In a real enterprise setting, this would send to a dedicated SIEM or audit log service
        # For now, we use structured logging
        self.logger.info(f"AUDIT EVENT: {event}")

        if self.backend_url:
            self._send_to_backend(event)

    def _send_to_backend(self, event: Dict[str, Any]) -> None:
        """Send the audit event to a remote backend (stub)."""
        # E.g., HTTP POST to a centralized SIEM
        pass

    def log_access_denied(self, actor: str, target: str, reason: str) -> None:
        """Helper to log access denied events."""
        self.log_event(
            action=AuditAction.ACCESS_DENIED,
            actor=actor,
            target=target,
            metadata={"reason": reason},
            success=False
        )

    def log_trace_view(self, actor: str, trace_id: str, ip_address: Optional[str] = None) -> None:
        """Helper to log when a user views a trace."""
        self.log_event(
            action=AuditAction.VIEW_TRACE,
            actor=actor,
            target=trace_id,
            ip_address=ip_address
        )


class S3WormAuditSink:
    """WORM-compliant audit sink that pushes events to an S3 bucket with Object Lock enabled."""
    
    def __init__(self, bucket: str, prefix: str = "audit-logs/"):
        self.bucket = bucket
        self.prefix = prefix
        self._s3 = None
        
    def _init_s3(self):
        if self._s3 is None:
            try:
                import boto3
                self._s3 = boto3.client("s3")
            except ImportError:
                raise ImportError("boto3 required for S3WormAuditSink")
                
    def send(self, event: Dict[str, Any]) -> None:
        self._init_s3()
        # Create a unique key per event to simulate append-only immutable storage
        key = f"{self.prefix}{event['timestamp']}_{event['actor']}_{event['action']}.json"
        
        # S3 Object Lock prevents deletion or overwriting
        try:
            self._s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(event).encode('utf-8'),
                ContentType="application/json"
            )
        except Exception as e:
            logger.error(f"Failed to push audit log to S3 WORM: {e}")

# Global audit logger instance
audit_logger = AuditLogger()
