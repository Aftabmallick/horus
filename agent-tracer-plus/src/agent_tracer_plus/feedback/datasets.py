"""Dataset export for RLHF/SFT fine-tuning from annotated traces."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from agent_tracer_plus.core.context import get_tracer

logger = logging.getLogger(__name__)


async def export_training_data(
    filter_dict: Optional[Dict[str, Any]] = None,
    format: str = "jsonl",
    output: str = "training_data.jsonl",
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Export feedback-annotated traces as SFT/RLHF training datasets.

    Args:
        filter_dict: Optional filters for trace selection.
        format: Output format — "jsonl", "huggingface", "openai_finetune", or "dpo".
        output: Output file path.
        min_score: Minimum feedback score to include.
        max_score: Maximum feedback score to include.

    Returns:
        Summary of exported data.
    """
    tracer = get_tracer()
    if not tracer:
        logger.warning("Tracer not initialized, cannot export training data")
        return {"status": "error", "message": "Tracer not initialized", "count": 0}

    traces = await tracer.query(limit=10000)

    # Apply filters
    if filter_dict:
        status = filter_dict.get("status")
        if status:
            traces = [t for t in traces if t.get("status") == status]
        agent = filter_dict.get("agent_name")
        if agent:
            traces = [t for t in traces if t.get("agent_name") == agent]

    records = []
    for t in traces:
        trace_id = t.get("trace_id", "")
        if not trace_id:
            continue

        spans = await tracer.get_spans(trace_id)

        # Extract prompt/completion pairs from LLM spans
        for s in spans:
            if s.span_type.value != "LLM":
                continue

            prompt = str(s.input) if s.input else ""
            completion = str(s.output) if s.output else ""

            if not prompt or not completion:
                continue

            # Get feedback score from metadata if available
            score = t.get("metadata", {}).get("feedback_score")
            if score is not None:
                if min_score is not None and score < min_score:
                    continue
                if max_score is not None and score > max_score:
                    continue

            record = _format_record(prompt, completion, score, format, t, s)
            records.append(record)

    # DPO pairing logic
    if format == "dpo":
        # Group by prompt
        prompt_groups = {}
        for r in records:
            p = r["prompt"]
            if p not in prompt_groups:
                prompt_groups[p] = {"chosen": [], "rejected": []}
            score = r.get("score")
            if score is not None:
                if score >= 0.8: # high feedback
                    prompt_groups[p]["chosen"].append(r["completion"])
                elif score <= 0.4: # low feedback
                    prompt_groups[p]["rejected"].append(r["completion"])

        dpo_records = []
        for p, group in prompt_groups.items():
            if group["chosen"] and group["rejected"]:
                # Cartesian product of chosen and rejected for this prompt
                for c in group["chosen"]:
                    for rj in group["rejected"]:
                        dpo_records.append({
                            "prompt": p,
                            "chosen": c,
                            "rejected": rj
                        })
        records = dpo_records

    # Write output
    with open(output, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    summary = {
        "status": "success",
        "format": format,
        "output": output,
        "count": len(records),
        "traces_scanned": len(traces),
    }
    logger.info(f"Exported {len(records)} training records to {output}")
    return summary


def _format_record(
    prompt: str,
    completion: str,
    score: Optional[float],
    format: str,
    trace: Dict[str, Any],
    span: Any,
) -> Dict[str, Any]:
    """Format a single training record based on output format."""
    if format == "openai_finetune":
        return {
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": completion},
            ]
        }
    elif format == "huggingface":
        record: Dict[str, Any] = {
            "instruction": prompt,
            "output": completion,
        }
        if score is not None:
            record["score"] = score
        return record
    else:  # jsonl (default)
        record = {
            "prompt": prompt,
            "completion": completion,
            "trace_id": trace.get("trace_id", ""),
            "agent_name": trace.get("agent_name", ""),
            "model": getattr(span, "attributes", {}).get("model", ""),
        }
        if score is not None:
            record["score"] = score
        return record
