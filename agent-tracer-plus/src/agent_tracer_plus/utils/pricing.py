"""Model pricing tables for automatic cost calculation.

Prices are in USD per 1 million tokens. Updated periodically.
Users can override with custom pricing via configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ModelPricing:
    """Pricing for a single model."""

    input_per_million: float  # USD per 1M input tokens
    output_per_million: float  # USD per 1M output tokens
    cached_input_per_million: Optional[float] = None  # USD per 1M cached input tokens
    context_window: int = 128000  # Default context window limit

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> float:
        """Calculate total cost in USD."""
        input_cost = (input_tokens - cached_tokens) * self.input_per_million / 1_000_000
        output_cost = output_tokens * self.output_per_million / 1_000_000
        cached_cost = 0.0
        if cached_tokens > 0 and self.cached_input_per_million is not None:
            cached_cost = cached_tokens * self.cached_input_per_million / 1_000_000
        return input_cost + output_cost + cached_cost


# Default pricing table — updated as of 2026
# Users can override via AgentTracerPlus(custom_pricing={...})
DEFAULT_PRICING: Dict[str, ModelPricing] = {
    # OpenAI
    "gpt-4o": ModelPricing(2.50, 10.00, 1.25, 128000),
    "gpt-4o-mini": ModelPricing(0.15, 0.60, 0.075, 128000),
    "gpt-4-turbo": ModelPricing(10.00, 30.00, None, 128000),
    "gpt-4": ModelPricing(30.00, 60.00, None, 8192),
    "gpt-3.5-turbo": ModelPricing(0.50, 1.50, None, 16385),
    "o1": ModelPricing(15.00, 60.00, None, 200000),
    "o1-mini": ModelPricing(3.00, 12.00, None, 128000),
    "o3-mini": ModelPricing(1.10, 4.40, None, 200000),
    "o4-mini": ModelPricing(1.10, 4.40, None, 200000),
    "gpt-4o-mini-2024-07-18": ModelPricing(0.15, 0.60, 0.075, 128000),
    "gpt-4.1": ModelPricing(2.00, 8.00, 0.50, 1000000),
    "gpt-4.1-mini": ModelPricing(0.40, 1.60, 0.10, 1000000),
    "gpt-4.1-nano": ModelPricing(0.10, 0.40, None, 1000000),
    # Anthropic
    "claude-opus-4": ModelPricing(15.00, 75.00, None, 200000),
    "claude-opus-4-5": ModelPricing(15.00, 75.00, None, 200000),
    "claude-sonnet-4": ModelPricing(3.00, 15.00, None, 200000),
    "claude-3-5-sonnet": ModelPricing(3.00, 15.00, None, 200000),
    "claude-3-5-haiku": ModelPricing(0.80, 4.00, None, 200000),
    "claude-3-5-haiku-20241022": ModelPricing(0.80, 4.00, None, 200000),
    "claude-3-opus": ModelPricing(15.00, 75.00, None, 200000),
    "claude-3-haiku": ModelPricing(0.25, 1.25, None, 200000),
    # Google
    "gemini-2.5-pro": ModelPricing(1.25, 10.00, None, 2000000),
    "gemini-2.5-flash": ModelPricing(0.15, 0.60, None, 1000000),
    "gemini-2.0-flash": ModelPricing(0.10, 0.40, None, 1000000),
    "gemini-2.0-flash-lite": ModelPricing(0.075, 0.30, None, 1000000),
    "gemini-1.5-pro": ModelPricing(1.25, 5.00, None, 2000000),
    "gemini-1.5-flash": ModelPricing(0.075, 0.30, None, 1000000),
    # Meta (via providers)
    "llama-3.1-405b": ModelPricing(3.00, 3.00, None, 128000),
    "llama-3.1-70b": ModelPricing(0.80, 0.80, None, 128000),
    "llama-3.1-8b": ModelPricing(0.10, 0.10, None, 128000),
    # Mistral
    "mistral-large": ModelPricing(2.00, 6.00, None, 32000),
    "mistral-small": ModelPricing(0.20, 0.60, None, 32000),
    "mixtral-8x7b": ModelPricing(0.50, 0.50, None, 32000),
}


def get_model_pricing(model: str, custom_pricing: Dict[str, ModelPricing] | None = None) -> ModelPricing | None:
    """Look up pricing for a model name.

    Tries exact match first, then prefix match (e.g., "gpt-4o-2024-08-06" matches "gpt-4o").

    Args:
        model: Model name/identifier.
        custom_pricing: Optional user-provided pricing overrides.

    Returns:
        ModelPricing if found, None otherwise.
    """
    all_pricing = {**DEFAULT_PRICING, **(custom_pricing or {})}

    # Exact match
    if model in all_pricing:
        return all_pricing[model]

    # Prefix match (e.g., "gpt-4o-2024-08-06" → "gpt-4o")
    for known_model, pricing in sorted(all_pricing.items(), key=lambda x: -len(x[0])):
        if model.startswith(known_model):
            return pricing

    return None
