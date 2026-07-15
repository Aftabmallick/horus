"""Fault injection types for Chaos Engineering."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


class Fault:
    """Base class for chaos engineering faults."""
    def __init__(self, target: str, probability: float):
        self.target = target
        self.probability = probability


class LatencyFault(Fault):
    """Injects an artificial delay before execution."""
    def __init__(self, target: str, probability: float, delay_ms: int):
        super().__init__(target, probability)
        self.delay_ms = delay_ms


class ErrorFault(Fault):
    """Raises a configurable exception to simulate failures."""
    def __init__(self, target: str, probability: float, exception_type: str = "RuntimeError", message: str = "Injected by ChaosMonkey"):
        super().__init__(target, probability)
        self.exception_type = exception_type
        self.message = message


class TokenExhaustionFault(Fault):
    """Simulate LLM returning a max_tokens truncated response."""
    def __init__(self, target: str, probability: float):
        super().__init__(target, probability)


class NetworkPartitionFault(Fault):
    """Simulate a complete network partition — raises ConnectionError."""
    def __init__(self, target: str, probability: float):
        super().__init__(target, probability)


class HallucinationFault(Fault):
    """Replaces the LLM response with a plausible-but-wrong answer.
    
    Used to verify that hallucination detection pipelines catch it.
    The injected exception carries the fake response payload.
    """

    class HallucinationInjected(Exception):
        """Raised to signal that the response should be replaced."""
        def __init__(self, fake_response: str):
            self.fake_response = fake_response
            super().__init__(f"[ChaosMonkey] Hallucination injected: {fake_response[:100]}...")

    def __init__(self, target: str, probability: float, fake_response: str = "The capital of France is Berlin."):
        super().__init__(target, probability)
        self.fake_response = fake_response


def parse_faults(fault_configs: list) -> List[Fault]:
    """Parse a list of fault config dicts into Fault objects."""
    parsed = []
    for config in fault_configs:
        f_type = config.get("type")
        target = config.get("target", "*")
        prob = config.get("probability", 0.0)

        if f_type == "latency":
            parsed.append(LatencyFault(target, prob, config.get("delay_ms", 1000)))
        elif f_type == "error":
            parsed.append(ErrorFault(target, prob, config.get("exception_type", "RuntimeError"), config.get("message", "Chaos fault injected")))
        elif f_type == "token_exhaustion":
            parsed.append(TokenExhaustionFault(target, prob))
        elif f_type == "network_partition":
            parsed.append(NetworkPartitionFault(target, prob))
        elif f_type == "hallucination":
            parsed.append(HallucinationFault(target, prob, config.get("fake_response", "The capital of France is Berlin.")))

    return parsed

