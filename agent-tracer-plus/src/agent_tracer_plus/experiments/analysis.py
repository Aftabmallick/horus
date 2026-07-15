"""Statistical analysis."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Lazy loaded dependencies
_numpy = None
_scipy_stats = None


def _load_stats() -> None:
    global _numpy, _scipy_stats
    if _scipy_stats is None:
        try:
            import numpy as np
            import scipy.stats as stats
            _numpy = np
            _scipy_stats = stats
        except ImportError:
            logger.error("scipy is not installed. Please install with `pip install scipy numpy`")
            raise ImportError("scipy is required for experimental analysis")


def _welchs_t_test(control_data: List[float], challenger_data: List[float], min_sample_size: int = 100) -> Dict[str, Any]:
    """Perform Welch's t-test using scipy."""
    _load_stats()
    np = _numpy
    stats = _scipy_stats

    if not control_data or not challenger_data:
        return {"error": "Insufficient data"}

    if len(control_data) < min_sample_size or len(challenger_data) < min_sample_size:
        return {
            "error": "Peeking Problem Prevention", 
            "reason": f"Sample size must be at least {min_sample_size} to avoid statistical illusions. Currently {len(control_data)} (control) vs {len(challenger_data)} (challenger)."
        }

    control = np.array(control_data)
    challenger = np.array(challenger_data)

    mean_c = np.mean(control)
    mean_ch = np.mean(challenger)
    var_c = np.var(control, ddof=1)
    var_ch = np.var(challenger, ddof=1)

    if var_c == 0 and var_ch == 0:
        if mean_c == mean_ch:
            return {"t_stat": 0.0, "p_value": 1.0, "significant": False, "greater_mean": "tie"}
        else:
            return {"error": "Zero variance with different means"}

    # Exact Welch's t-test via scipy
    t_stat, p_value = stats.ttest_ind(control, challenger, equal_var=False)

    return {
        "t_stat": float(t_stat),
        "mean_control": float(mean_c),
        "mean_challenger": float(mean_ch),
        "p_value": float(p_value),
        "significant": bool(p_value < 0.05),
        "greater_mean": "control" if mean_c > mean_ch else ("challenger" if mean_ch > mean_c else "tie")
    }


def analyze_results(experiment_name: str, control_data: Dict[str, List[float]], challenger_data: Dict[str, List[float]], metrics: List[str]) -> Dict[str, Any]:
    """Analyze experimental results using Welch's t-test."""
    logger.info(f"Analyzing {experiment_name} on {metrics}...")

    results = {}
    for metric in metrics:
        c_data = control_data.get(metric, [])
        ch_data = challenger_data.get(metric, [])
        results[metric] = _welchs_t_test(c_data, ch_data)

    return {
        "status": "analyzed",
        "experiment": experiment_name,
        "metrics": results
    }
