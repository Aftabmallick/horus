# Module: `agent_tracer_plus.auto.patcher`

Auto-patcher — monkey-patches installed libraries for zero-code tracing.

Uses the InstrumentorRegistry for dynamic discovery of installed packages
and applies only the patches for packages that are actually installed.

## Class `ChaosException`
Exception injected by the Chaos Engineering module.

## Class `AutoPatcher`
Detects installed packages and applies instrumentation patches.

### `def __init__(self, config)`
### `def patch_all(self)`
Apply all applicable patches based on config and installed packages.

Uses the global InstrumentorRegistry to discover and apply patches
for all installed packages.

## Function `wrap(target, method_name, wrapper)`
Replace a method on a target object with a wrapper and optional chaos fault injection.

