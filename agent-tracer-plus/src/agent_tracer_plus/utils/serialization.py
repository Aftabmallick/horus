"""Safe JSON serialization that handles all Python types gracefully."""

from __future__ import annotations

import dataclasses
import enum
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID


class SafeEncoder(json.JSONEncoder):
    """JSON encoder that handles non-standard Python types.

    Handles: datetime, date, UUID, Decimal, bytes, Path, set, frozenset,
    dataclasses, enums, and objects with __dict__.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return f"<bytes: {len(obj)} bytes>"
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if isinstance(obj, enum.Enum):
            return obj.value
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        # Last resort: string representation
        try:
            return str(obj)
        except Exception:
            return f"<unserializable: {type(obj).__name__}>"


def safe_serialize(
    obj: Any,
    max_depth: int = 10,
    max_str_len: int = 10_000,
    redact_pii: bool = False,
) -> Any:
    """Safely serialize any Python object to a JSON-compatible structure.

    Args:
        obj: Any Python object.
        max_depth: Maximum nesting depth to prevent infinite recursion.
        max_str_len: Maximum string length (truncates with marker).
        redact_pii: If True, applies PII redaction BEFORE serializing.
                    Pass True when capturing LLM inputs/outputs.
                    Can also be set globally via the tracer config (pii_redaction=True).

    Returns:
        A JSON-serializable Python object (dict, list, str, int, float, bool, None).
    """
    # Apply PII redaction early — before any data leaves memory as a string
    if redact_pii or _get_global_pii_flag():
        obj = _apply_pii_redaction(obj)

    return _serialize_value(obj, depth=0, max_depth=max_depth, max_str_len=max_str_len)


def _get_global_pii_flag() -> bool:
    """Check if PII redaction is globally enabled via the active tracer config."""
    try:
        from agent_tracer_plus.core.context import get_tracer
        tracer = get_tracer()
        if tracer and getattr(tracer, "pii_masker", None):
            return True
    except Exception:
        pass
    return False


def _apply_pii_redaction(obj: Any) -> Any:
    """Apply PII redaction to an object using the active tracer's PIIMasker.

    Falls back to the built-in regex masker if the tracer isn't available.
    This runs BEFORE safe_serialize so PII never enters the serialized form.
    """
    try:
        from agent_tracer_plus.core.context import get_tracer
        tracer = get_tracer()
        if tracer and tracer.pii_masker:
            # Convert to string, redact, return redacted string
            raw = str(obj) if not isinstance(obj, (dict, list)) else obj
            if isinstance(raw, str):
                return tracer.pii_masker.redact_text(raw)
            # For dicts/lists, recursively redact string values
            return _redact_nested(obj, tracer.pii_masker)
    except Exception:
        pass
    return obj


def _redact_nested(obj: Any, masker: Any) -> Any:
    """Recursively redact PII from nested dicts/lists."""
    if isinstance(obj, dict):
        return {k: _redact_nested(v, masker) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact_nested(v, masker) for v in obj]
    if isinstance(obj, str):
        try:
            return masker.redact_text(obj)
        except Exception:
            return obj
    return obj


def _serialize_value(obj: Any, depth: int, max_depth: int, max_str_len: int) -> Any:
    """Recursively serialize a value with depth limiting."""
    if depth > max_depth:
        return "<max_depth_exceeded>"

    if obj is None or isinstance(obj, (bool, int, float)):
        return obj

    if isinstance(obj, str):
        if len(obj) > max_str_len:
            return obj[:max_str_len] + f"... [truncated, {len(obj)} chars total]"
        return obj

    if isinstance(obj, bytes):
        try:
            decoded = obj.decode("utf-8")
            return _serialize_value(decoded, depth, max_depth, max_str_len)
        except UnicodeDecodeError:
            return f"<bytes: {len(obj)} bytes>"

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, enum.Enum):
        return obj.value

    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, (set, frozenset)):
        return [_serialize_value(v, depth + 1, max_depth, max_str_len) for v in obj]

    if isinstance(obj, (list, tuple)):
        return [_serialize_value(v, depth + 1, max_depth, max_str_len) for v in obj]

    if isinstance(obj, dict):
        return {
            str(k): _serialize_value(v, depth + 1, max_depth, max_str_len)
            for k, v in obj.items()
        }

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: _serialize_value(getattr(obj, f.name), depth + 1, max_depth, max_str_len)
            for f in dataclasses.fields(obj)
        }

    if hasattr(obj, "__dict__"):
        return {
            k: _serialize_value(v, depth + 1, max_depth, max_str_len)
            for k, v in obj.__dict__.items()
            if not k.startswith("_")
        }

    try:
        return str(obj)
    except Exception:
        return f"<unserializable: {type(obj).__name__}>"


def safe_deserialize(json_str: str) -> Any:
    """Safely deserialize a JSON string, returning None on failure."""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None


def to_json(obj: Any, indent: int | None = None) -> str:
    """Serialize object to JSON string using SafeEncoder."""
    return json.dumps(obj, cls=SafeEncoder, indent=indent, default=str)
