import pytest

from agent_tracer_plus.experiments.analysis import _welchs_t_test


def test_welchs_t_test():
    control = [1.0, 1.2, 1.1, 1.3, 1.2]
    challenger = [0.5, 0.6, 0.5, 0.4, 0.5]

    try:
        res = _welchs_t_test(control, challenger)

        assert "t_stat" in res
        assert res["significant"] == True
        assert res["greater_mean"] == "control"

        res_tie = _welchs_t_test([1, 2, 3], [1, 2, 3])
        assert res_tie["significant"] == False
        assert res_tie["greater_mean"] == "tie"

        res_zero = _welchs_t_test([1, 1, 1], [2, 2, 2])
        assert "error" in res_zero
    except ImportError:
        pytest.skip("numpy not installed")
