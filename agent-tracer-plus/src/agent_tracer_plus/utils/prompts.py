"""Dynamic Prompt Management."""

import json
import logging
import urllib.error
import urllib.request
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PromptManager:
    """Fetches and caches prompts dynamically from the Agent Tracer Platform."""

    def __init__(self, api_url: str = "http://localhost:3000", api_key: str = ""):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self._cache: Dict[str, str] = {}

    def get_prompt(self, name: str, fallback: str = "") -> str:
        """Fetch a prompt by name. Returns the fallback if the fetch fails."""
        if name in self._cache:
            return self._cache[name]

        url = f"{self.api_url}/api/prompts/{name}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    # Assuming the platform returns {"template": "..."}
                    prompt = data.get("template", fallback)
                    self._cache[name] = prompt
                    return prompt
        except Exception as e:
            logger.warning(f"Failed to fetch dynamic prompt '{name}': {e}. Using fallback.")

        return fallback

# Global singleton
_manager: Optional[PromptManager] = None

def init_prompt_manager(api_url: str, api_key: str) -> None:
    global _manager
    _manager = PromptManager(api_url, api_key)

def get_prompt(name: str, fallback: str = "") -> str:
    """Global helper to fetch a prompt."""
    if _manager is None:
        logger.warning("PromptManager not initialized. Using fallback.")
        return fallback
    return _manager.get_prompt(name, fallback)
