"""
Example demonstrating Phase 3 Production & Enterprise Layer capabilities:
- Budget Enforcement
- PII Redaction
- AES-256 Payload Encryption
- Trace Sampling
"""

import asyncio

from cryptography.fernet import Fernet

import agent_tracer_plus
from agent_tracer_plus.core.models import SpanStatus
from agent_tracer_plus.security.encryption import FieldEncryptor
from agent_tracer_plus.security.redaction import PIIRedactor


async def main():
    print("--- Agent Tracer Plus: Phase 3 Enterprise Demo ---")

    # Generate an encryption key (in reality, loaded from secure ENV)
    key = Fernet.generate_key()
    encryptor = FieldEncryptor(key)

    # Initialize PII Redactor
    redactor = PIIRedactor()

    # Initialize tracer with Phase 3 features
    agent_tracer_plus.init(
        service_name="enterprise-agent",
        storage="memory://", # Using memory for demo, could be postgresql:// or s3://
        sampling_rate=0.5,   # 50% head-based sampling
        budget={"max_tokens_per_trace": 100, "on_exceed": "alert"},
    )

    tracer = agent_tracer_plus.core.context.get_tracer()

    print("\n1. PII Redaction & Encryption")
    raw_payload = {
        "user_email": "ceo@company.com",
        "ssn": "123-45-6789",
        "secret_prompt": "You are a highly classified AI."
    }
    print(f"Raw Payload: {raw_payload}")

    # Step 1: Redact
    redacted_payload = redactor.redact_payload(raw_payload)
    print(f"Redacted Payload: {redacted_payload}")

    # Step 2: Encrypt specific fields
    encrypted_payload = encryptor.encrypt_payload(redacted_payload, fields=["secret_prompt"])
    print(f"Encrypted Payload (Ready for DB): {encrypted_payload}")

    print("\n2. Budget Enforcement")
    try:
        # Simulate a trace that blows the budget
        with agent_tracer_plus.core.context.TraceContext(agent_name="GreedyAgent"):
            with agent_tracer_plus.core.context.SpanContext(name="expensive_call") as span:
                span.token_usage = {"total_tokens": 150}
                trace = agent_tracer_plus.current_trace()
                trace.total_tokens = 150

                # Context manager exit will trigger budget check
                print("Closing span, triggering budget check...")
    except Exception as e:
        print(f"Budget Enforcer triggered: {e}")

    print("\n3. Trace Sampling")
    # Simulate sampling (50% chance, but 100% for errors)
    trace_ok = agent_tracer_plus.core.models.Trace(trace_id="ok", status=SpanStatus.OK)
    trace_err = agent_tracer_plus.core.models.Trace(trace_id="err", status=SpanStatus.ERROR)

    print(f"Sampling OK Trace (50% chance): {tracer.sampler.should_sample(trace_ok)}")
    print(f"Sampling ERROR Trace (100% chance): {tracer.sampler.should_sample(trace_err)}")

if __name__ == "__main__":
    asyncio.run(main())
