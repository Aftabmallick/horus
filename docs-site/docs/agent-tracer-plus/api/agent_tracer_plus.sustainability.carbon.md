# Module: `agent_tracer_plus.sustainability.carbon`

Carbon footprint calculation with comprehensive regional data.

## Function `_load_codecarbon()`
## Class `CarbonTracker`
Estimates carbon footprint of LLM queries based on region and tokens.

Uses a comprehensive 50+ region static table for carbon intensity.
Optionally fetches live data from the Electricity Maps API if configured.

### `def __init__(self, region, electricity_maps_api_key)`
## Class `ElectricityMapsProvider`
Stub provider for the Electricity Maps API (https://electricitymap.org).

To use real live data:
1. Get an API key at https://app.electricitymaps.com/
2. Pass api_key to CarbonTracker
3. This provider will fetch real-time grid carbon intensity

Without a key, it returns None and CarbonTracker falls back to static data.

### `def __init__(self, api_key)`
