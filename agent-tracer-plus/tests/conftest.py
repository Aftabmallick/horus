import os
import shutil

import pytest


@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure tests run in a clean environment."""
    os.environ["AGENT_TRACER_PLUS_ENABLED"] = "1"
    os.environ["AGENT_TRACER_PLUS_LOG_LEVEL"] = "DEBUG"
    yield
    # Cleanup any stray test databases
    if os.path.exists("test_traces.db"):
        os.remove("test_traces.db")
    if os.path.exists("test_agent_traces"):
        shutil.rmtree("test_agent_traces")
