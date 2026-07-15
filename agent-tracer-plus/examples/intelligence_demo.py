"""
Example demonstrating Phase 2 Intelligence Layer capabilities:
- Time-Travel Replay
- Trace-to-Test Baseline generation
- AI Diagnosis

Run this with: `python examples/intelligence_demo.py`
"""

import asyncio
from pathlib import Path

from agent_tracer_plus.intelligence.anomaly import AnomalyDetector
from agent_tracer_plus.intelligence.diagnosis import TraceDiagnoser
from agent_tracer_plus.intelligence.replay import ReplayEngine
from agent_tracer_plus.storage.sqlite import SQLiteBackend
from agent_tracer_plus.testing.golden import GoldenTrace


async def main():
    print("--- Agent Tracer Plus: Intelligence Demo ---")
    storage = SQLiteBackend("./agent_traces.db")

    traces = await storage.query_traces(limit=5)
    if not traces:
        print("No traces found in database. Run examples/basic_usage.py first.")
        return

    trace_id = traces[0]["trace_id"]
    print("\n1. Time-Travel Replay Engine")
    print(f"Loading trace: {trace_id}")

    engine = ReplayEngine(trace_id, storage)
    await engine.load()

    print(f"Loaded {len(engine.spans)} spans for replay.")
    print("With `with engine.mock_context():`, all LLM/HTTP calls are mocked using these spans!")

    print("\n2. Trace-to-Test Pipeline")
    trace = await storage.get_trace(trace_id)
    golden = GoldenTrace(trace, engine.spans)
    golden_dir = Path("tests/golden_traces")
    golden.save(golden_dir)
    print(f"Saved golden baseline to {golden_dir}/{golden.name}.json")
    print("You can now run `pytest --atp-regression tests/golden_traces/` to prevent regressions!")

    print("\n3. AI Root Cause Analysis")
    diagnoser = TraceDiagnoser()
    # Since we don't have an API key set, it will raise an error if we actually hit the LLM,
    # but we can format the trace to show what it would send.
    prompt = diagnoser._format_trace_for_llm(trace, engine.spans)
    print("Formatted prompt for AI diagnosis:")
    print("-" * 40)
    print(prompt)
    print("-" * 40)

    print("\n4. Anomaly Detection")
    # Using the single trace as both history and current for demo purposes
    detector = AnomalyDetector(history=[trace])
    result = detector.detect(trace)
    print(f"Anomalies detected: {result['anomalies']}")

if __name__ == "__main__":
    asyncio.run(main())
