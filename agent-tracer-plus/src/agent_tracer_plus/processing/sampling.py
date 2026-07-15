"""Sampling engine for traces."""

import random
from typing import Callable, Optional

from agent_tracer_plus.core.models import Trace
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("processing.sampling")


class Sampler:
    """Determines whether a trace should be captured or dropped."""

    def __init__(self, rate: float = 1.0, conditional: Optional[Callable[[Trace], bool]] = None):
        """
        Args:
            rate: The base head-based sampling rate (0.0 to 1.0).
            conditional: A function that takes a trace and returns True to ALWAYS sample it
                         (e.g., always sample errors).
        """
        self.rate = max(0.0, min(1.0, rate))
        self.conditional = conditional

    def should_sample(self, trace: Trace) -> bool:
        """Evaluate if the trace should be sampled."""

        # 1. Conditional sampling (e.g. keep all errors) overrides the base rate
        if self.conditional and self.conditional(trace):
            return True

        # 2. Head-based sampling
        if self.rate >= 1.0:
            return True
        if self.rate <= 0.0:
            return False

        return random.random() < self.rate
