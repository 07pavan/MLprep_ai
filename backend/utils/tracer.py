"""Thread-safe, size-bounded trace collector for agent observability.

Isolates traces per user ID (uid) for multi-tenant SaaS safety.
"""
from __future__ import annotations
import time
import uuid
import threading
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class Tracer:
    """In-memory trace storage with auto-pruning, isolated by user ID (uid)."""

    MAX_TRACES = 200  # rolling window

    def __init__(self):
        self._traces: dict[str, dict] = {}
        self._order: deque[str] = deque(maxlen=self.MAX_TRACES)
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────

    def start_trace(self, session_id: str, question: str, uid: str = "") -> str:
        """Begin a new trace. Returns trace_id."""
        trace_id = str(uuid.uuid4())[:12]
        trace = {
            "trace_id": trace_id,
            "session_id": session_id,
            "uid": uid,
            "question": question,
            "started_at": time.time(),
            "ended_at": None,
            "duration_ms": None,
            "success": None,
            "events": [],
        }
        with self._lock:
            # Prune oldest if at capacity
            if len(self._order) >= self.MAX_TRACES:
                oldest = self._order[0]
                self._traces.pop(oldest, None)
            self._order.append(trace_id)
            self._traces[trace_id] = trace

        logger.debug("Trace %s started for user %s, question: %s", trace_id, uid, question[:60])
        return trace_id

    def end_trace(self, trace_id: str, success: bool) -> None:
        """Finalize a trace with success status and total duration."""
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace:
                trace["ended_at"] = time.time()
                trace["duration_ms"] = int((trace["ended_at"] - trace["started_at"]) * 1000)
                trace["success"] = success
                logger.debug(
                    "Trace %s ended: success=%s, duration=%dms",
                    trace_id, success, trace["duration_ms"],
                )

    # ── Event recording ───────────────────────────────────────────

    def add_event(
        self,
        trace_id: str,
        node: str,
        event_type: str,
        data: Optional[dict] = None,
    ) -> None:
        """Append a structured event to the trace."""
        event = {
            "timestamp": time.time(),
            "node": node,
            "type": event_type,
            "data": data or {},
        }
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace:
                trace["events"].append(event)

    # ── Query ─────────────────────────────────────────────────────

    def get_traces(self, limit: int = 50, uid: str = "") -> list[dict]:
        """Return recent trace summaries for a specific user, newest first."""
        with self._lock:
            trace_ids = list(reversed(self._order))
            result = []
            for tid in trace_ids:
                trace = self._traces.get(tid)
                if trace and trace.get("uid") == uid:
                    result.append({
                        "traceId": trace["trace_id"],
                        "sessionId": trace["session_id"],
                        "question": trace["question"],
                        "startedAt": trace["started_at"],
                        "durationMs": trace["duration_ms"],
                        "success": trace["success"],
                        "eventCount": len(trace["events"]),
                        "intent": _extract_intent(trace["events"]),
                        "model": _extract_model(trace["events"]),
                        "attempts": _extract_attempts(trace["events"]),
                    })
                    if len(result) >= limit:
                        break
            return result

    def get_trace_detail(self, trace_id: str, uid: str = "") -> Optional[dict]:
        """Return a full trace with all events if it belongs to the user."""
        with self._lock:
            trace = self._traces.get(trace_id)
            if not trace or trace.get("uid") != uid:
                return None
            return {
                "traceId": trace["trace_id"],
                "sessionId": trace["session_id"],
                "question": trace["question"],
                "startedAt": trace["started_at"],
                "endedAt": trace["ended_at"],
                "durationMs": trace["duration_ms"],
                "success": trace["success"],
                "events": trace["events"],
            }

    def clear(self, uid: str = "") -> int:
        """Wipe all stored traces for a specific user. Returns count cleared."""
        with self._lock:
            cleared_ids = []
            for tid, trace in list(self._traces.items()):
                if trace.get("uid") == uid:
                    self._traces.pop(tid)
                    cleared_ids.append(tid)
            
            # Rebuild order deque without the cleared traces
            new_order = deque(maxlen=self.MAX_TRACES)
            for tid in self._order:
                if tid not in cleared_ids:
                    new_order.append(tid)
            self._order = new_order
            
            return len(cleared_ids)

    def clear_all(self) -> int:
        """Wipe all stored traces for all users. Returns count cleared."""
        with self._lock:
            count = len(self._traces)
            self._traces.clear()
            self._order.clear()
            return count


# Helpers
def _extract_intent(events: list[dict]) -> str:
    for e in events:
        if e["type"] == "intent":
            return e["data"].get("intent", "")
    return ""


def _extract_model(events: list[dict]) -> str:
    for e in events:
        if e["type"] == "llm_call":
            return e["data"].get("model", "")
    return ""


def _extract_attempts(events: list[dict]) -> int:
    max_attempt = 0
    for e in events:
        if e["type"] == "code_exec":
            max_attempt = max(max_attempt, e["data"].get("attempt", 0))
    return max_attempt


# Singleton instance
tracer = Tracer()
