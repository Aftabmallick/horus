"""Tests for TracerConfig — environment loading, dict creation, defaults."""

import os
import pytest

from agent_tracer_plus.core.config import TracerConfig


class TestTracerConfigDefaults:
    def test_default_values(self):
        config = TracerConfig()
        assert config.service_name == "default"
        assert config.enabled is True
        assert config.auto_instrument is True
        assert config.sampling_rate == 1.0
        assert config.batch_size == 100
        assert config.flush_interval_seconds == 5.0
        assert config.max_queue_size == 10_000
        assert config.capture_input is True
        assert config.capture_output is True
        assert config.pii_redaction is False
        assert config.storage is None
        assert config.budget is None

    def test_custom_values(self):
        config = TracerConfig(
            service_name="my-svc",
            sampling_rate=0.5,
            batch_size=50,
        )
        assert config.service_name == "my-svc"
        assert config.sampling_rate == 0.5
        assert config.batch_size == 50


class TestTracerConfigFromDict:
    def test_basic(self):
        config = TracerConfig.from_dict({"service_name": "test", "sampling_rate": 0.1})
        assert config.service_name == "test"
        assert config.sampling_rate == 0.1

    def test_ignores_unknown_keys(self):
        """from_dict should silently ignore keys that don't exist on the dataclass."""
        config = TracerConfig.from_dict({
            "service_name": "test",
            "nonexistent_key": "value",
            "another_bad_key": 42,
        })
        assert config.service_name == "test"
        assert not hasattr(config, "nonexistent_key")

    def test_empty_dict(self):
        config = TracerConfig.from_dict({})
        assert config.service_name == "default"


class TestTracerConfigFromEnv:
    def test_reads_service_name(self, monkeypatch):
        monkeypatch.setenv("AGENT_TRACER_PLUS_SERVICE_NAME", "env-svc")
        config = TracerConfig.from_env()
        assert config.service_name == "env-svc"

    def test_reads_sampling_rate(self, monkeypatch):
        monkeypatch.setenv("AGENT_TRACER_PLUS_SAMPLING_RATE", "0.25")
        config = TracerConfig.from_env()
        assert config.sampling_rate == 0.25

    def test_reads_boolean_enabled(self, monkeypatch):
        monkeypatch.setenv("AGENT_TRACER_PLUS_ENABLED", "false")
        config = TracerConfig.from_env()
        assert config.enabled is False

    def test_reads_boolean_true_variants(self, monkeypatch):
        for val in ("1", "true", "yes", "True", "YES"):
            monkeypatch.setenv("AGENT_TRACER_PLUS_ENABLED", val)
            config = TracerConfig.from_env()
            assert config.enabled is True

    def test_reads_debug(self, monkeypatch):
        monkeypatch.setenv("AGENT_TRACER_PLUS_DEBUG", "1")
        config = TracerConfig.from_env()
        assert config.debug is True

    def test_reads_tenant_id(self, monkeypatch):
        monkeypatch.setenv("AGENT_TRACER_PLUS_TENANT_ID", "tenant_abc")
        config = TracerConfig.from_env()
        assert config.tenant_id == "tenant_abc"

    def test_no_env_vars_uses_defaults(self):
        """With no env vars set, from_env returns defaults."""
        config = TracerConfig.from_env()
        assert config.service_name == "default"
        assert config.enabled is True

    def test_reads_storage_uri(self, monkeypatch):
        monkeypatch.setenv("AGENT_TRACER_PLUS_STORAGE", "postgresql://host/db")
        config = TracerConfig.from_env()
        assert config.storage == "postgresql://host/db"
