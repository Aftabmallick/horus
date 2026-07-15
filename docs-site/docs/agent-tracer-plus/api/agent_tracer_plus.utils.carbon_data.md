# Module: `agent_tracer_plus.utils.carbon_data`

Static carbon intensity data for cloud datacenter regions.

Values in gCO2eq/kWh sourced from publicly available data:
  - US regions: EPA eGRID (https://www.epa.gov/egrid)
  - EU regions: European Environment Agency (https://www.eea.europa.eu)
  - APAC regions: IEA and regional grid operators
  - Cloud vendor disclosures (AWS, GCP, Azure sustainability reports)

Note: Values are annual averages and vary seasonally. For real-time data,
use ElectricityMapsProvider with an API key from electricitymap.org.

## Class `PUEFetcher`
Dynamic fetcher for real-time PUE and Carbon Intensity.

## Function `get_carbon_intensity(region)`
Return the carbon intensity (gCO2eq/kWh) for a cloud region.

## Function `list_regions()`
Return the full region to intensity mapping.

## Function `get_model_energy(model)`
Return energy consumption (kWh per 1000 tokens) for a given model.

Uses exact match first, then heuristic (mini/haiku/flash = small tier).
Falls back to 0.005 for unknown models.

Args:
    model: Model identifier string.

Returns:
    kWh per 1000 tokens.

## Function `lowest_carbon_regions(top_n)`
Return the N regions with the lowest carbon intensity (Carbon-Aware Routing).

