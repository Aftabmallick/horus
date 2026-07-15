# Module: `agent_tracer_plus.intelligence.anomaly`

Statistical anomaly detection for traces using Median Absolute Deviation (MAD).

## Function `_median(values)`
## Function `_calculate_mad(values)`
Calculate Median and Median Absolute Deviation (MAD).

## Class `AnomalyDetector`
Detects statistical anomalies using MAD for robust outlier detection.

### `def __init__(self, trace_history, spans_history, window_size)`
### `def detect(self, current, current_spans)`
Detect anomalies in the current trace based on history.

