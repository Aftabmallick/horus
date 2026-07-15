"""Pytest plugin for agent-tracer-plus trace regression testing.

When enabled with --atp-regression <dir>, this plugin dynamically generates
test cases for every golden trace found in the directory.
"""

import pytest
from pathlib import Path

from agent_tracer_plus.testing.suite import TraceTestSuite


def pytest_addoption(parser):
    """Add custom command line options to pytest."""
    parser.addoption(
        "--atp-regression",
        action="store",
        default=None,
        help="Path to directory containing golden traces for regression testing.",
    )
    parser.addoption(
        "--atp-update-baselines",
        action="store_true",
        default=False,
        help="If set, overwrite golden traces and EvalSuite datasets with new results.",
    )


def pytest_generate_tests(metafunc):
    """Dynamically generate tests if the flag is provided and the fixture is requested."""
    regression_dir = metafunc.config.getoption("atp_regression")
    if regression_dir and "golden_trace" in metafunc.fixturenames:
        suite = TraceTestSuite(Path(regression_dir))

        # Parametrize the test with the loaded golden traces
        metafunc.parametrize(
            "golden_trace",
            suite.golden_traces,
            ids=[g.name for g in suite.golden_traces]
        )


@pytest.fixture
def atp_update_baselines(request) -> bool:
    """Fixture to check if the update flag was passed."""
    return request.config.getoption("--atp-update-baselines")


@pytest.fixture
def atp_eval_runner() -> "AsyncEvalRunner":
    """Fixture providing the concurrent AsyncEvalRunner for prompt testing."""
    from agent_tracer_plus.testing.runner import AsyncEvalRunner
    return AsyncEvalRunner(concurrency=5)
