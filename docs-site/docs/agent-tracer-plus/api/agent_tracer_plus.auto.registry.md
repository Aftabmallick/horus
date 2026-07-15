# Module: `agent_tracer_plus.auto.registry`

Instrumentor registry — dynamic discovery of installed packages for auto-instrumentation.

Each instrumentor registers itself with a target module name and a patch function.
The AutoPatcher queries this registry to apply only the patches for installed packages.

## Class `InstrumentorEntry`
A registered instrumentor.

## Class `InstrumentorRegistry`
Central registry for all auto-instrumentors.

Usage:
    registry = InstrumentorRegistry()
    registry.register("openai", "openai", patch_openai, config_flag="instrument_openai")
    registry.apply_all(config)

### `def __init__(self)`
### `def register(self, name, target_module, patch_fn, config_flag, priority, description)`
Register an instrumentor.

### `def unregister(self, name)`
Remove an instrumentor from the registry.

### `def get(self, name)`
Get an instrumentor entry by name.

### `def entries(self)`
Get all entries sorted by priority.

### `def is_installed(self, module_name)`
Check if a Python package is importable.

### `def apply_all(self, config)`
Apply all applicable patches.

Args:
    config: TracerConfig instance. If a config_flag is set on the entry,
            the corresponding config attribute must be True.

Returns:
    List of successfully patched module names.

## Function `_build_default_registry()`
Build the default registry with all built-in instrumentors.

