# Module: `agent_tracer_plus.plugins.base`

Base classes for plugins.

## Class `PluginBase`
Base class for all community plugins.

### `def setup(self, config)`
Initialize plugin.

## Class `InstrumentorPlugin`
Base class for auto-instrumentation plugins.

### `def patch(self)`
Apply monkey-patches.

## Class `ExporterPlugin`
Base class for export format plugins.

### `def export(self, traces, output_path)`
Export traces.

