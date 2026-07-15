# Module: `agent_tracer_plus.utils.serialization`

Safe JSON serialization that handles all Python types gracefully.

## Class `SafeEncoder`
JSON encoder that handles non-standard Python types.

Handles: datetime, date, UUID, Decimal, bytes, Path, set, frozenset,
dataclasses, enums, and objects with __dict__.

### `def default(self, obj)`
## Function `safe_serialize(obj, max_depth, max_str_len)`
Safely serialize any Python object to a JSON-compatible structure.

Args:
    obj: Any Python object.
    max_depth: Maximum nesting depth to prevent infinite recursion.
    max_str_len: Maximum string length (truncates with marker).

Returns:
    A JSON-serializable Python object (dict, list, str, int, float, bool, None).

## Function `_serialize_value(obj, depth, max_depth, max_str_len)`
Recursively serialize a value with depth limiting.

## Function `safe_deserialize(json_str)`
Safely deserialize a JSON string, returning None on failure.

## Function `to_json(obj, indent)`
Serialize object to JSON string using SafeEncoder.

