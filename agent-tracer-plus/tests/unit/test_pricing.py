"""Tests for model pricing tables and cost calculation."""

import pytest

from agent_tracer_plus.utils.pricing import (
    DEFAULT_PRICING,
    ModelPricing,
    get_model_pricing,
)


class TestModelPricing:
    def test_calculate_cost_basic(self):
        pricing = ModelPricing(input_per_million=2.50, output_per_million=10.00)
        # 1000 input + 500 output
        cost = pricing.calculate_cost(input_tokens=1000, output_tokens=500)
        expected = (1000 * 2.50 / 1_000_000) + (500 * 10.00 / 1_000_000)
        assert cost == pytest.approx(expected)

    def test_calculate_cost_with_cached(self):
        pricing = ModelPricing(
            input_per_million=2.50,
            output_per_million=10.00,
            cached_input_per_million=1.25,
        )
        cost = pricing.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            cached_tokens=200,
        )
        # (1000-200) * 2.50/1M + 500 * 10/1M + 200 * 1.25/1M
        input_cost = 800 * 2.50 / 1_000_000
        output_cost = 500 * 10.00 / 1_000_000
        cached_cost = 200 * 1.25 / 1_000_000
        assert cost == pytest.approx(input_cost + output_cost + cached_cost)

    def test_calculate_cost_zero_tokens(self):
        pricing = ModelPricing(input_per_million=2.50, output_per_million=10.00)
        assert pricing.calculate_cost(0, 0) == 0.0

    def test_immutable(self):
        """ModelPricing should be frozen (immutable)."""
        pricing = ModelPricing(input_per_million=1.0, output_per_million=2.0)
        with pytest.raises(AttributeError):
            pricing.input_per_million = 5.0


class TestGetModelPricing:
    def test_exact_match(self):
        pricing = get_model_pricing("gpt-4o")
        assert pricing is not None
        assert pricing.input_per_million == 2.50
        assert pricing.output_per_million == 10.00

    def test_exact_match_mini(self):
        pricing = get_model_pricing("gpt-4o-mini")
        assert pricing is not None
        assert pricing.input_per_million == 0.15

    def test_prefix_match(self):
        """gpt-4o-2024-08-06 should match gpt-4o."""
        pricing = get_model_pricing("gpt-4o-2024-08-06")
        assert pricing is not None
        assert pricing.input_per_million == 2.50

    def test_prefix_match_prefers_longer(self):
        """gpt-4o-mini-2024-07-18 should match gpt-4o-mini, not gpt-4o."""
        pricing = get_model_pricing("gpt-4o-mini-2024-07-18")
        assert pricing is not None
        assert pricing.input_per_million == 0.15  # gpt-4o-mini price

    def test_unknown_model(self):
        pricing = get_model_pricing("totally-unknown-model-xyz")
        assert pricing is None

    def test_custom_pricing_override(self):
        custom = {"my-model": ModelPricing(1.0, 2.0)}
        pricing = get_model_pricing("my-model", custom_pricing=custom)
        assert pricing is not None
        assert pricing.input_per_million == 1.0

    def test_custom_pricing_overrides_default(self):
        custom = {"gpt-4o": ModelPricing(99.0, 99.0)}
        pricing = get_model_pricing("gpt-4o", custom_pricing=custom)
        assert pricing.input_per_million == 99.0

    def test_anthropic_models_present(self):
        for model in ["claude-opus-4", "claude-sonnet-4", "claude-3-5-sonnet", "claude-3-haiku"]:
            assert get_model_pricing(model) is not None

    def test_google_models_present(self):
        for model in ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]:
            assert get_model_pricing(model) is not None

    def test_mistral_models_present(self):
        for model in ["mistral-large", "mistral-small", "mixtral-8x7b"]:
            assert get_model_pricing(model) is not None


class TestDefaultPricingTable:
    def test_minimum_models(self):
        """Default pricing table should have at least 20 models."""
        assert len(DEFAULT_PRICING) >= 20

    def test_all_prices_positive(self):
        for model, pricing in DEFAULT_PRICING.items():
            assert pricing.input_per_million > 0, f"{model} has zero input price"
            assert pricing.output_per_million > 0, f"{model} has zero output price"
