"""Session analytics metrics over user sessions."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List

from agent_tracer_plus.core.context import get_tracer

logger = logging.getLogger(__name__)


class SessionAnalytics:
    """Calculates engagement, drop-off, and completion metrics over user sessions."""

    def __init__(self, time_range: str = "last_7d"):
        self.time_range = time_range

    async def _get_session_traces(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group traces by session_id."""
        tracer = get_tracer()
        if not tracer:
            return {}

        traces = await tracer.query(limit=10000)
        sessions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for t in traces:
            sid = t.get("session_id", "")
            if sid:
                sessions[sid].append(t)
        return sessions

    async def task_completion_rate(self) -> float:
        """Calculate % of sessions that ended in success (last trace is COMPLETED)."""
        sessions = await self._get_session_traces()
        if not sessions:
            return 0.0

        completed = 0
        for traces in sessions.values():
            sorted_traces = sorted(traces, key=lambda t: t.get("started_at", ""))
            if sorted_traces and sorted_traces[-1].get("status") == "COMPLETED":
                completed += 1

        return round(completed / len(sessions) * 100, 2) if sessions else 0.0

    async def avg_turns_per_session(self) -> float:
        """Calculate average number of trace invocations per session."""
        sessions = await self._get_session_traces()
        if not sessions:
            return 0.0

        total_turns = sum(len(traces) for traces in sessions.values())
        return round(total_turns / len(sessions), 2)

    async def drop_off_analysis(self) -> List[Dict[str, Any]]:
        """Analyze where sessions fail or users abandon.

        Returns the most common last spans before session ends with an error/abandonment.
        """
        tracer = get_tracer()
        if not tracer:
            return []

        sessions = await self._get_session_traces()
        drop_off_points: Dict[str, int] = defaultdict(int)

        for traces in sessions.values():
            sorted_traces = sorted(traces, key=lambda t: t.get("started_at", ""))
            if not sorted_traces:
                continue

            last_trace = sorted_traces[-1]
            if last_trace.get("status") in ("ERROR", "CANCELLED"):
                trace_id = last_trace.get("trace_id", "")
                if trace_id:
                    spans = await tracer.get_spans(trace_id)
                    if spans:
                        last_span = spans[-1]
                        drop_off_points[last_span.name] += 1

        results = []
        total_drop = sum(drop_off_points.values())
        for point, count in sorted(drop_off_points.items(), key=lambda x: -x[1]):
            pct = round(count / total_drop * 100, 1) if total_drop > 0 else 0
            results.append({
                "step": point,
                "drop_off_count": count,
                "percentage": pct,
            })

        return results

    async def funnel_analysis(self, required_steps: List[str]) -> Dict[str, Any]:
        """Strict multi-step funnel tracking (e.g., Prompt -> Search -> Tool -> Generation).
        
        Calculates conversion and drop-off rates at each defined step in the funnel.
        """
        tracer = get_tracer()
        if not tracer or not required_steps:
            return {"error": "Invalid tracer or steps"}
            
        sessions = await self._get_session_traces()
        funnel_counts = {step: 0 for step in required_steps}
        total_started = 0
        
        for traces in sessions.values():
            sorted_traces = sorted(traces, key=lambda t: t.get("started_at", ""))
            
            # Extract the sequence of span names executed in this session
            session_span_sequence = []
            for t in sorted_traces:
                trace_id = t.get("trace_id", "")
                if trace_id:
                    spans = await tracer.get_spans(trace_id)
                    # Sort spans chronologically within trace
                    sorted_spans = sorted(spans, key=lambda s: s.started_at)
                    session_span_sequence.extend([s.name for s in sorted_spans])
                    
            if not session_span_sequence:
                continue
                
            # Assume session started if it has traces
            total_started += 1
            
            # Check how deep into the funnel this session got
            current_step_idx = 0
            for span_name in session_span_sequence:
                if current_step_idx < len(required_steps) and span_name == required_steps[current_step_idx]:
                    funnel_counts[required_steps[current_step_idx]] += 1
                    current_step_idx += 1
                    
        # Calculate stats
        funnel_stats = []
        previous_count = total_started
        for step in required_steps:
            count = funnel_counts[step]
            conversion_rate = round((count / previous_count * 100) if previous_count > 0 else 0, 2)
            drop_off_rate = round(((previous_count - count) / previous_count * 100) if previous_count > 0 else 0, 2)
            
            funnel_stats.append({
                "step": step,
                "count": count,
                "conversion_from_previous": conversion_rate,
                "drop_off_from_previous": drop_off_rate,
                "overall_conversion": round((count / total_started * 100) if total_started > 0 else 0, 2)
            })
            previous_count = count
            
        return {
            "total_sessions": total_started,
            "funnel": funnel_stats
        }

    async def user_satisfaction_trend(self) -> List[Dict[str, Any]]:
        """Get time series of feedback scores grouped by day."""
        tracer = get_tracer()
        if not tracer:
            return []

        traces = await tracer.query(limit=10000)
        daily_scores: Dict[str, List[float]] = defaultdict(list)

        for t in traces:
            metadata = t.get("metadata", {})
            score = metadata.get("feedback_score")
            started = t.get("started_at", "")
            if score is not None and started:
                day = started[:10]  # YYYY-MM-DD
                daily_scores[day].append(float(score))

        trend = []
        for day in sorted(daily_scores.keys()):
            scores = daily_scores[day]
            trend.append({
                "date": day,
                "avg_score": round(sum(scores) / len(scores), 3),
                "count": len(scores),
            })

        return trend

    async def calculate_annotator_consensus(self) -> Dict[str, Any]:
        """Calculate multi-user consensus scoring (measuring inter-annotator agreement).
        
        Uses a simplified pairwise agreement ratio for multi-annotator setups.
        """
        tracer = get_tracer()
        if not tracer:
            return {}
            
        traces = await tracer.query(limit=10000)
        # trace_id -> annotator -> score
        annotations: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        for t in traces:
            meta = t.get("metadata", {})
            if "annotations" in meta:
                trace_id = t.get("trace_id", "")
                # Assuming metadata contains {"annotations": {"user_a": 1.0, "user_b": 0.5}}
                for user, score in meta["annotations"].items():
                    annotations[trace_id][user] = float(score)
                    
        total_pairs = 0
        agreed_pairs = 0
        
        for trace_id, user_scores in annotations.items():
            users = list(user_scores.keys())
            if len(users) < 2:
                continue
                
            # Check pairwise agreement (exact match or very close)
            for i in range(len(users)):
                for j in range(i + 1, len(users)):
                    total_pairs += 1
                    u1, u2 = users[i], users[j]
                    if abs(user_scores[u1] - user_scores[u2]) <= 0.2:
                        agreed_pairs += 1
                        
        agreement_ratio = agreed_pairs / total_pairs if total_pairs > 0 else 1.0
        
        return {
            "annotated_traces": len(annotations),
            "traces_with_multiple_annotators": sum(1 for v in annotations.values() if len(v) > 1),
            "pairwise_agreement_ratio": round(agreement_ratio, 3),
            "consensus_status": "High" if agreement_ratio > 0.8 else "Medium" if agreement_ratio > 0.5 else "Low"
        }

    async def summary(self) -> Dict[str, Any]:
        """Get a full session analytics summary."""
        return {
            "task_completion_rate": await self.task_completion_rate(),
            "avg_turns_per_session": await self.avg_turns_per_session(),
            "drop_off_points": await self.drop_off_analysis(),
            "satisfaction_trend": await self.user_satisfaction_trend(),
            "annotator_consensus": await self.calculate_annotator_consensus(),
        }
