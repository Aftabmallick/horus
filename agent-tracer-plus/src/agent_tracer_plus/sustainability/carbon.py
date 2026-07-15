"""Carbon footprint calculation with comprehensive regional data."""

import logging
from typing import Dict, Optional

from agent_tracer_plus.utils.carbon_data import get_carbon_intensity, get_model_energy

logger = logging.getLogger(__name__)

_codecarbon = None

def _load_codecarbon():
    global _codecarbon
    if _codecarbon is None:
        try:
            import codecarbon
            _codecarbon = codecarbon
        except ImportError:
            _codecarbon = False

class CarbonTracker:
    """Estimates carbon footprint of LLM queries based on region and tokens.

    Uses a comprehensive 50+ region static table for carbon intensity.
    Optionally fetches live data from the Electricity Maps API if configured.
    """

    def __init__(self, region: str = "us-east-1", electricity_maps_api_key: Optional[str] = None):
        self.region = region
        self._api_key = electricity_maps_api_key
        self._live_provider = ElectricityMapsProvider(api_key=electricity_maps_api_key) if electricity_maps_api_key else None

    async def calculate_footprint(self, model: str, total_tokens: int, duration_seconds: float = 1.0) -> Dict[str, float]:
        """Estimate CO2 emissions for an LLM inference call.

        Args:
            model: The LLM model name (used to estimate energy per token).
            total_tokens: Total tokens processed.
            duration_seconds: Duration of the inference call.

        Returns:
            Dict with co2_grams, energy_kwh, region, intensity_g_per_kwh.
        """
        _load_codecarbon()

        # Use the centralized energy model from carbon_data for consistency with tests
        energy_kwh_per_1k_tokens = get_model_energy(model)
        total_energy_kwh = (total_tokens / 1000.0) * energy_kwh_per_1k_tokens

        # Get carbon intensity — live if API key provided, else static table
        intensity = get_carbon_intensity(self.region)
        if self._live_provider:
            try:
                live_intensity = await self._live_provider.fetch_intensity(self.region)
                if live_intensity is not None:
                    intensity = live_intensity
            except Exception as e:
                logger.debug(f"Live carbon intensity fetch failed, using static data: {e}")

        co2_grams = total_energy_kwh * intensity

        return {
            "co2_grams": round(co2_grams, 6),
            "energy_kwh": round(total_energy_kwh, 6),
            "region": self.region,
            "intensity_g_per_kwh": intensity,
            "intensity_source": "live" if self._live_provider else "static",
        }


class ElectricityMapsProvider:
    """Stub provider for the Electricity Maps API (https://electricitymap.org).

    To use real live data:
    1. Get an API key at https://app.electricitymaps.com/
    2. Pass api_key to CarbonTracker
    3. This provider will fetch real-time grid carbon intensity

    Without a key, it returns None and CarbonTracker falls back to static data.
    """

    _BASE_URL = "https://api.electricitymap.org/v3/carbon-intensity/latest"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    async def fetch_intensity(self, region: str) -> Optional[float]:
        """Fetch live carbon intensity for a region.

        Args:
            region: Cloud region identifier. Will be mapped to an electricity
                    map zone code (e.g., "us-east-1" -> "US-MIDA-PJM").

        Returns:
            Carbon intensity in gCO2eq/kWh, or None if fetch fails.
        """
        if not self.api_key:
            return None

        zone = _REGION_TO_ZONE.get(region.lower())
        if not zone:
            logger.debug(f"No Electricity Maps zone mapping for region '{region}'")
            return None

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._BASE_URL,
                    params={"zone": zone},
                    headers={"auth-token": self.api_key},
                    timeout=aiohttp.ClientTimeout(total=3.0),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("carbonIntensity")
        except ImportError:
            logger.debug("aiohttp not installed — cannot fetch live carbon intensity")
        except Exception as e:
            logger.debug(f"ElectricityMaps API error: {e}")

        return None


# Mapping of common cloud regions to Electricity Maps zone codes
_REGION_TO_ZONE: Dict[str, str] = {
    "us-east-1": "US-MIDA-PJM",
    "us-east-2": "US-MIDW-MISO",
    "us-west-1": "US-CAL-CISO",
    "us-west-2": "US-NW-BPAT",
    "eu-west-1": "IE",
    "eu-west-2": "GB",
    "eu-west-3": "FR",
    "eu-central-1": "DE",
    "eu-north-1": "SE",
    "ap-northeast-1": "JP-TK",
    "ap-southeast-1": "SG",
    "ap-southeast-2": "AU-NSW",
    "ap-south-1": "IN-WE",
    "sa-east-1": "BR-CS",
    "ca-central-1": "CA-QC",
}

