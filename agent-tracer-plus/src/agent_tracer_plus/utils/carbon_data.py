"""Static carbon intensity data for cloud datacenter regions.

Values in gCO2eq/kWh sourced from publicly available data:
  - US regions: EPA eGRID (https://www.epa.gov/egrid)
  - EU regions: European Environment Agency (https://www.eea.europa.eu)
  - APAC regions: IEA and regional grid operators
  - Cloud vendor disclosures (AWS, GCP, Azure sustainability reports)

Note: Values are annual averages and vary seasonally. For real-time data,
use ElectricityMapsProvider with an API key from electricitymap.org.
"""

from typing import Dict, List, Tuple

# Format: "provider-region": gCO2eq_per_kWh
CARBON_INTENSITY_BY_REGION: Dict[str, float] = {
    # ── AWS ─────────────────────────────────────────────────────────────
    "us-east-1":      384.0,   # N. Virginia (PJM grid)
    "us-east-2":      420.0,   # Ohio (MISO grid)
    "us-west-1":      210.0,   # N. California (CAISO — heavy renewables)
    "us-west-2":      139.0,   # Oregon (heavy hydro/wind)
    "ca-central-1":    25.0,   # Canada (Quebec hydro)
    "eu-west-1":      295.0,   # Ireland (high wind penetration)
    "eu-west-2":      228.0,   # London (UK grid)
    "eu-west-3":      58.0,    # Paris (nuclear-heavy French grid)
    "eu-central-1":   348.0,   # Frankfurt (German grid)
    "eu-north-1":     8.0,     # Stockholm (near-zero — Nordic hydro/nuclear)
    "eu-south-1":     233.0,   # Milan
    "ap-northeast-1": 496.0,   # Tokyo (Japan)
    "ap-northeast-2": 462.0,   # Seoul (South Korea)
    "ap-northeast-3": 496.0,   # Osaka
    "ap-southeast-1": 431.0,   # Singapore
    "ap-southeast-2": 790.0,   # Sydney (coal-heavy NEM)
    "ap-south-1":     708.0,   # Mumbai (India)
    "ap-east-1":      790.0,   # Hong Kong
    "sa-east-1":      96.0,    # Sao Paulo (Brazilian hydro)
    "me-south-1":     603.0,   # Bahrain
    "af-south-1":     928.0,   # Cape Town (South Africa — coal-heavy)

    # ── GCP ─────────────────────────────────────────────────────────────
    "us-central1":    411.0,   # Iowa
    "us-east4":       386.0,   # N. Virginia
    "us-west1":       115.0,   # Oregon (The Dalles — Columbia River hydro)
    "us-west2":       211.0,   # Los Angeles
    "europe-west1":   170.0,   # Belgium (St. Ghislain)
    "europe-west4":   390.0,   # Netherlands
    "europe-north1":  8.0,     # Finland
    "asia-east1":     790.0,   # Taiwan
    "asia-northeast1": 496.0,  # Tokyo
    "asia-southeast1": 431.0,  # Singapore
    "australia-southeast1": 790.0,  # Sydney

    # ── Azure ────────────────────────────────────────────────────────────
    "eastus":         386.0,
    "eastus2":        386.0,
    "westus":         210.0,
    "westus2":        139.0,
    "westeurope":     390.0,   # Netherlands
    "northeurope":    295.0,   # Ireland
    "uksouth":        228.0,
    "northcentralus": 448.0,   # Chicago
    "swedencentral":  8.0,     # Sweden
    "brazilsouth":    96.0,

    # ── Generic fallbacks ────────────────────────────────────────────────
    "default":        400.0,   # Conservative world average estimate
}

# PUE (Power Usage Effectiveness) by Cloud Provider/Region
# Measures data center efficiency: Total Facility Energy / IT Equipment Energy.
# 1.0 is perfect efficiency.
PUE_BY_REGION: Dict[str, float] = {
    "us-west-2": 1.12, # AWS Oregon
    "eu-north-1": 1.10, # AWS Stockholm
    "europe-north1": 1.09, # GCP Finland
    "us-central1": 1.11, # GCP Iowa
    "default": 1.15, # Industry average for hyperscalers
}

class PUEFetcher:
    """Dynamic fetcher for real-time PUE and Carbon Intensity."""
    
    @classmethod
    async def fetch_real_time_pue(cls, provider: str, region: str) -> float:
        """Fetch live PUE from cloud vendor APIs if available."""
        # Stub for future HTTP client implementation (e.g., WattTime, ElectricityMaps)
        # In a real enterprise system, this hits external sustainability APIs.
        return PUE_BY_REGION.get(region, PUE_BY_REGION["default"])
        
    @classmethod
    async def fetch_real_time_intensity(cls, region: str) -> float:
        """Fetch live gCO2eq/kWh."""
        return get_carbon_intensity(region)


def get_carbon_intensity(region: str) -> float:
    """Return the carbon intensity (gCO2eq/kWh) for a cloud region."""
    normalized = region.lower().strip()
    if normalized in CARBON_INTENSITY_BY_REGION:
        return CARBON_INTENSITY_BY_REGION[normalized]
    for key, value in CARBON_INTENSITY_BY_REGION.items():
        if key in normalized or normalized in key:
            return value
    return CARBON_INTENSITY_BY_REGION["default"]


def list_regions() -> Dict[str, float]:
    """Return the full region to intensity mapping."""
    return dict(CARBON_INTENSITY_BY_REGION)


# kWh per 1000 tokens for various model tiers
_MODEL_ENERGY_KWH_PER_1K_TOKENS: Dict[str, float] = {
    "gpt-4o-mini":   0.0015,
    "gpt-4o":        0.005,
    "claude-3-haiku": 0.001,
    "claude-3-5-sonnet": 0.005,
    "gemini-1.5-flash": 0.001,
    "gemini-1.5-pro": 0.010,
}


async def calculate_carbon_footprint(model: str, tokens: int, region: str) -> float:
    """Calculate the carbon footprint (gCO2eq) for a given LLM request.
    
    Applies the specific Data Center PUE multiplier to the IT load.
    """
    it_load_kwh = get_model_energy(model) * (tokens / 1000.0)
    pue = await PUEFetcher.fetch_real_time_pue("auto", region)
    total_facility_kwh = it_load_kwh * pue
    
    intensity = await PUEFetcher.fetch_real_time_intensity(region)
    return total_facility_kwh * intensity


def get_model_energy(model: str) -> float:
    """Return energy consumption (kWh per 1000 tokens) for a given model.

    Uses exact match first, then heuristic (mini/haiku/flash = small tier).
    Falls back to 0.005 for unknown models.

    Args:
        model: Model identifier string.

    Returns:
        kWh per 1000 tokens.
    """
    normalized = model.lower().strip()
    # Exact match
    if normalized in _MODEL_ENERGY_KWH_PER_1K_TOKENS:
        return _MODEL_ENERGY_KWH_PER_1K_TOKENS[normalized]
    # Heuristic: small/efficient models
    if any(x in normalized for x in ("mini", "haiku", "flash", "nano", "small")):
        return 0.001
    # Heuristic: large frontier models
    if any(x in normalized for x in ("gpt-4", "claude-3-5", "gemini-1.5-pro", "o1")):
        return 0.010
    # Default: mid-size
    return 0.005


def lowest_carbon_regions(top_n: int = 5) -> List[Tuple[str, float]]:
    """Return the N regions with the lowest carbon intensity (Carbon-Aware Routing)."""
    sorted_regions = sorted(
        [(k, v * PUE_BY_REGION.get(k, PUE_BY_REGION["default"])) for k, v in CARBON_INTENSITY_BY_REGION.items() if k != "default"],
        key=lambda x: x[1]
    )
    return sorted_regions[:top_n]
