# Module: `agent_tracer_plus.core.profiler`

## Class `SysProfiler`
Hooks into the Python runtime to automatically trace specified modules.

### `def __init__(self)`
### `def start(self, target_modules)`
Start profiling specific module prefixes.

### `def stop(self)`
Stop profiling and remove hooks.

### `def _mon_py_start(self, code, instruction_offset)`
Callback for function entry in sys.monitoring.

### `def _mon_py_return(self, code, instruction_offset, retval)`
Callback for function exit in sys.monitoring.

### `def _profile_callback(self, frame, event, arg)`
Standard sys.setprofile callback.

