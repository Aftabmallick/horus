"""Team annotations and collaboration on traces."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_tracer_plus.utils.clock import now_utc
from agent_tracer_plus.utils.ids import generate_span_id

logger = logging.getLogger(__name__)


@dataclass
class Annotation:
    """A single annotation on a trace."""

    annotation_id: str = field(default_factory=generate_span_id)
    trace_id: str = ""
    author: str = ""
    comment: str = ""
    tags: List[str] = field(default_factory=list)
    status: str = "open"  # "open" | "investigating" | "resolved" | "wontfix"
    created_at: datetime = field(default_factory=now_utc)
    updated_at: datetime = field(default_factory=now_utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "trace_id": self.trace_id,
            "author": self.author,
            "comment": self.comment,
            "tags": self.tags,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AnnotationStore:
    """In-memory annotation storage with query support."""

    def __init__(self) -> None:
        self._annotations: Dict[str, List[Annotation]] = {}  # trace_id -> [annotations]

    def add(
        self,
        trace_id: str,
        author: str,
        comment: str,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> Annotation:
        """Add an annotation to a trace."""
        annotation = Annotation(
            trace_id=trace_id,
            author=author,
            comment=comment,
            tags=tags or [],
            status=status or "open",
        )
        if trace_id not in self._annotations:
            self._annotations[trace_id] = []
        self._annotations[trace_id].append(annotation)
        logger.info(f"Annotation added to trace {trace_id} by {author} [{status}]")
        return annotation

    def get_for_trace(self, trace_id: str) -> List[Annotation]:
        """Get all annotations for a trace."""
        return self._annotations.get(trace_id, [])

    def query(
        self,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        author: Optional[str] = None,
    ) -> List[Annotation]:
        """Query annotations across all traces."""
        results = []
        for trace_annotations in self._annotations.values():
            for ann in trace_annotations:
                if tags and not all(t in ann.tags for t in tags):
                    continue
                if status and ann.status != status:
                    continue
                if author and ann.author != author:
                    continue
                results.append(ann)
        return results

    def update_status(self, annotation_id: str, new_status: str) -> bool:
        """Update the status of an annotation."""
        for trace_annotations in self._annotations.values():
            for ann in trace_annotations:
                if ann.annotation_id == annotation_id:
                    ann.status = new_status
                    ann.updated_at = now_utc()
                    logger.info(f"Annotation {annotation_id} status updated to {new_status}")
                    return True
        return False

    def delete(self, annotation_id: str) -> bool:
        """Delete an annotation."""
        for trace_id, trace_annotations in self._annotations.items():
            for i, ann in enumerate(trace_annotations):
                if ann.annotation_id == annotation_id:
                    trace_annotations.pop(i)
                    logger.info(f"Annotation {annotation_id} deleted from trace {trace_id}")
                    return True
        return False

    @property
    def count(self) -> int:
        return sum(len(v) for v in self._annotations.values())


# Global store singleton
_store = AnnotationStore()


async def annotate(
    trace_id: str,
    author: str,
    comment: str,
    tags: Optional[List[str]] = None,
    status: Optional[str] = None,
) -> Annotation:
    """Annotate a trace with comments and tags for team collaboration."""
    return _store.add(trace_id, author, comment, tags=tags, status=status)


async def get_annotations(trace_id: str) -> List[Dict[str, Any]]:
    """Get all annotations for a trace."""
    return [a.to_dict() for a in _store.get_for_trace(trace_id)]


async def query_annotations(
    tags: Optional[List[str]] = None,
    status: Optional[str] = None,
    author: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query annotations across all traces."""
    return [a.to_dict() for a in _store.query(tags=tags, status=status, author=author)]
