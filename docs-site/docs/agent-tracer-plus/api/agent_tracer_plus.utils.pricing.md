# Module: `agent_tracer_plus.utils.pricing`

Model pricing tables for automatic cost calculation.

Prices are in USD per 1 million tokens. Updated periodically.
Users can override with custom pricing via configuration.

## Class `ModelPricing`
Pricing for a single model.

### `def calculate_cost(self, input_tokens, output_tokens, cached_tokens)`
Calculate total cost in USD.

## Function `get_model_pricing(model, custom_pricing)`
Look up pricing for a model name.

Tries exact match first, then prefix match (e.g., "gpt-4o-2024-08-06" matches "gpt-4o").

Args:
    model: Model name/identifier.
    custom_pricing: Optional user-provided pricing overrides.

Returns:
    ModelPricing if found, None otherwise.

