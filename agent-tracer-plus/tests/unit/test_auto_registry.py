"""Tests for the auto-instrumentation registry."""

import pytest

from agent_tracer_plus.auto.registry import InstrumentorRegistry, InstrumentorEntry, default_registry
from agent_tracer_plus.core.config import TracerConfig


class TestInstrumentorRegistry:
    def test_register_and_get(self):
        reg = InstrumentorRegistry()
        reg.register("test", "json", lambda: None, description="test instrumentor")
        entry = reg.get("test")
        assert entry is not None
        assert entry.name == "test"
        assert entry.target_module == "json"
        assert entry.description == "test instrumentor"

    def test_unregister(self):
        reg = InstrumentorRegistry()
        reg.register("test", "json", lambda: None)
        reg.unregister("test")
        assert reg.get("test") is None

    def test_unregister_nonexistent(self):
        reg = InstrumentorRegistry()
        reg.unregister("nonexistent")  # Should not raise

    def test_entries_sorted_by_priority(self):
        reg = InstrumentorRegistry()
        reg.register("low", "json", lambda: None, priority=100)
        reg.register("high", "json", lambda: None, priority=10)
        reg.register("mid", "json", lambda: None, priority=50)
        names = [e.name for e in reg.entries]
        assert names == ["high", "mid", "low"]

    def test_is_installed_stdlib(self):
        reg = InstrumentorRegistry()
        assert reg.is_installed("json") is True
        assert reg.is_installed("os") is True
        assert reg.is_installed("sys") is True

    def test_is_installed_nonexistent(self):
        reg = InstrumentorRegistry()
        assert reg.is_installed("totally_nonexistent_package_xyz") is False

    def test_apply_all_skips_uninstalled(self):
        reg = InstrumentorRegistry()
        called = []
        reg.register("missing", "nonexistent_pkg_abc", lambda: called.append("missing"))
        patched = reg.apply_all()
        assert patched == []
        assert called == []

    def test_apply_all_patches_installed(self):
        reg = InstrumentorRegistry()
        called = []
        reg.register("json_test", "json", lambda: called.append("json_patched"))
        patched = reg.apply_all()
        assert "json_test" in patched
        assert "json_patched" in called

    def test_apply_all_respects_config_flag(self):
        reg = InstrumentorRegistry()
        called = []
        reg.register("flagged", "json", lambda: called.append("flagged"), config_flag="instrument_openai")

        config = TracerConfig(instrument_openai=False)
        patched = reg.apply_all(config)
        assert patched == []
        assert called == []

    def test_apply_all_config_flag_enabled(self):
        reg = InstrumentorRegistry()
        called = []
        reg.register("flagged", "json", lambda: called.append("flagged"), config_flag="instrument_openai")

        config = TracerConfig(instrument_openai=True)
        patched = reg.apply_all(config)
        assert "flagged" in patched

    def test_apply_all_catches_patch_failure(self):
        reg = InstrumentorRegistry()

        def bad_patch():
            raise RuntimeError("patch exploded")

        reg.register("bad", "json", bad_patch)
        patched = reg.apply_all()
        assert patched == []  # Failed patches are not in the returned list

    def test_patched_flag_set(self):
        reg = InstrumentorRegistry()
        reg.register("test", "json", lambda: None)
        reg.apply_all()
        entry = reg.get("test")
        assert entry.patched is True


class TestDefaultRegistry:
    def test_has_openai(self):
        assert default_registry.get("openai") is not None

    def test_has_anthropic(self):
        assert default_registry.get("anthropic") is not None

    def test_has_httpx(self):
        assert default_registry.get("httpx") is not None

    def test_has_requests(self):
        assert default_registry.get("requests") is not None

    def test_has_langchain(self):
        assert default_registry.get("langchain") is not None

    def test_has_crewai(self):
        assert default_registry.get("crewai") is not None

    def test_has_agno(self):
        assert default_registry.get("agno") is not None

    def test_llm_providers_highest_priority(self):
        openai = default_registry.get("openai")
        httpx = default_registry.get("httpx")
        assert openai.priority < httpx.priority  # Lower = higher priority

    def test_total_registered_count(self):
        """Ensure we have all built-in instrumentors registered."""
        assert len(default_registry.entries) >= 12
