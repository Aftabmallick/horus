# Module: `agent_tracer_plus.storage.base`

Abstract base class for all storage backends.

## Class `StorageBackend`
Base class for trace/span storage.

All backends must implement these methods.
Methods are async to support both sync and async backends uniformly.

