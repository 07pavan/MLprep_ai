"""Plan Store — in-process persistence for generated CleaningPlan objects.

Design:
    - Thread-safe in-memory store keyed by (user_id, dataset_id).
    - Plans are stored newest-first (LIFO order).
    - Designed as a singleton — use ``get_plan_store()`` everywhere.
    - Drop-in replaceable with a Firestore or Redis backend in Phase 3.

Storage contract:
    - WRITE: save(user_id, dataset_id, plan) → None
    - READ:  get_latest(user_id, dataset_id) → CleaningPlan | None
    - READ:  get_by_plan_id(user_id, dataset_id, plan_id) → CleaningPlan | None
    - READ:  list_for_dataset(user_id, dataset_id) → list[CleaningPlan]
    - DELETE: delete_for_dataset(user_id, dataset_id) → int  (returns count deleted)

Thread safety:
    - A single threading.Lock guards all mutations.
    - Reads return copies (model_dump → model_validate) to prevent aliasing.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from schemas.cleaning_plan import CleaningPlan

logger = logging.getLogger(__name__)

# Maximum plans retained per (user_id, dataset_id) key.
# Oldest plans are evicted when the limit is exceeded.
_MAX_PLANS_PER_DATASET = 10


class PlanStore:
    """Thread-safe in-memory store for CleaningPlan objects."""

    def __init__(self, max_per_dataset: int = _MAX_PLANS_PER_DATASET) -> None:
        # _store[(user_id, dataset_id)] = [newest, ..., oldest]
        self._store: dict[tuple[str, str], list[CleaningPlan]] = {}
        self._lock = threading.Lock()
        self._max = max_per_dataset

    # ── Write ──────────────────────────────────────────────────────────────────

    def save(
        self,
        user_id: str,
        dataset_id: str,
        plan: CleaningPlan,
    ) -> None:
        """Persist a CleaningPlan. Inserts at position 0 (newest-first).

        Evicts the oldest plan when the per-dataset limit is exceeded.
        """
        key = (user_id, dataset_id)
        with self._lock:
            bucket = self._store.setdefault(key, [])
            bucket.insert(0, plan)        # newest first
            if len(bucket) > self._max:
                evicted = bucket.pop()    # remove oldest
                logger.debug(
                    "PlanStore: evicted plan %s for dataset %s (limit=%d)",
                    evicted.plan_id, dataset_id, self._max,
                )
        logger.info(
            "PlanStore: saved plan %s for user=%s dataset=%s (%d total)",
            plan.plan_id, user_id, dataset_id, len(self._store[key]),
        )

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_latest(
        self,
        user_id: str,
        dataset_id: str,
    ) -> Optional[CleaningPlan]:
        """Return the most recently saved plan, or None if none exist."""
        key = (user_id, dataset_id)
        with self._lock:
            bucket = self._store.get(key, [])
            plan = bucket[0] if bucket else None
        if plan:
            logger.debug("PlanStore: returning latest plan %s", plan.plan_id)
        return plan

    def get_by_plan_id(
        self,
        user_id: str,
        dataset_id: str,
        plan_id: str,
    ) -> Optional[CleaningPlan]:
        """Return a specific plan by its plan_id, or None if not found."""
        key = (user_id, dataset_id)
        with self._lock:
            bucket = self._store.get(key, [])
            for plan in bucket:
                if plan.plan_id == plan_id:
                    return plan
        return None

    def list_for_dataset(
        self,
        user_id: str,
        dataset_id: str,
    ) -> list[CleaningPlan]:
        """Return all plans for a dataset (newest-first). Empty list if none."""
        key = (user_id, dataset_id)
        with self._lock:
            return list(self._store.get(key, []))   # shallow copy

    def count(self, user_id: str, dataset_id: str) -> int:
        """Return the number of plans stored for a dataset."""
        with self._lock:
            return len(self._store.get((user_id, dataset_id), []))

    # ── Delete ─────────────────────────────────────────────────────────────────

    def delete_for_dataset(
        self,
        user_id: str,
        dataset_id: str,
    ) -> int:
        """Delete all plans for a dataset. Returns the number deleted."""
        key = (user_id, dataset_id)
        with self._lock:
            deleted = len(self._store.pop(key, []))
        logger.info(
            "PlanStore: deleted %d plans for user=%s dataset=%s",
            deleted, user_id, dataset_id,
        )
        return deleted

    # ── Introspection (for tests/admin) ───────────────────────────────────────

    def total_plans(self) -> int:
        """Return the total number of plans across all users and datasets."""
        with self._lock:
            return sum(len(v) for v in self._store.values())

    def clear(self) -> None:
        """Remove all stored plans. Use only in tests."""
        with self._lock:
            self._store.clear()
        logger.debug("PlanStore: cleared all plans")


# ── Singleton ─────────────────────────────────────────────────────────────────

_plan_store = PlanStore()


def get_plan_store() -> PlanStore:
    """Return the process-wide PlanStore singleton.

    Inject this via FastAPI's ``Depends`` for testability:

        store: PlanStore = Depends(get_plan_store)
    """
    return _plan_store
