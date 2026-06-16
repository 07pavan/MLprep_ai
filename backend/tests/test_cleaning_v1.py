"""Tests for Phase 2A v1 REST endpoints and supporting infrastructure.

Covers:
    - PlanStore: all CRUD operations, thread-safety, eviction
    - CleaningPlanMeta.from_plan() factory
    - New response schema fields (GeneratePlanResponse, PlanListResponse)
    - POST /api/v1/cleaning/plan/{dataset_id} — generate + store
    - GET  /api/v1/cleaning/plan/{dataset_id} — retrieve all / by plan_id
    - DELETE /api/v1/cleaning/plan/{dataset_id} — purge
    - Edge cases: no prior plans, wrong owner, missing dataset, empty file
"""
from __future__ import annotations

import os
import tempfile
import threading
import unittest
from unittest.mock import patch

import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from main import app
from schemas.cleaning_plan import (
    ActionType,
    CleaningAction,
    CleaningPlan,
    CleaningPlanMeta,
    CleaningSummary,
    GeneratePlanResponse,
    IssueType,
    PlanListResponse,
    PlanStatus,
    Severity,
)
from services.plan_store import PlanStore, get_plan_store
from utils.auth import verify_firebase_token
from services.dataset_service import get_dataset_service


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_summary(**kw) -> CleaningSummary:
    return CleaningSummary(
        total_issues=kw.get("total_issues", 3),
        critical_issues=kw.get("critical_issues", 0),
        high_risk_issues=kw.get("high_risk_issues", 1),
        medium_risk_issues=kw.get("medium_risk_issues", 1),
        low_risk_issues=kw.get("low_risk_issues", 1),
        auto_applicable_count=kw.get("auto_applicable_count", 2),
        overall_quality_score=kw.get("overall_quality_score", 65),
        quality_grade=kw.get("quality_grade", "C"),
        estimated_score_after_cleaning=kw.get("estimated_score_after_cleaning", 82),
    )


def _make_plan(dataset_id="ds-001", session_id=None, score=65, total_issues=3) -> CleaningPlan:
    return CleaningPlan(
        dataset_id=dataset_id,
        session_id=session_id,
        summary=_make_summary(overall_quality_score=score, total_issues=total_issues),
        actions=[
            CleaningAction(
                column_name="age",
                issue_type=IssueType.missing_values,
                severity=Severity.medium,
                current_state="5 missing (5.0%)",
                recommendation=ActionType.median_imputation,
                reason="test reason",
                confidence_score=0.9,
                auto_applicable=True,
            )
        ],
    )


def _register_dataset(service, dataset_id: str, user_id: str, parquet_path: str) -> None:
    service.create_dataset({
        "dataset_id": dataset_id,
        "user_id": user_id,
        "dataset_name": f"{dataset_id}.parquet",
        "original_file_type": "parquet",
        "source": "upload",
        "upload_timestamp": "2026-06-14T10:00:00Z",
        "row_count": 100,
        "column_count": 3,
        "memory_usage": 0.1,
        "parquet_path": parquet_path,
        "ml_readiness_score": 70,
        "dataset_version": 1,
        "status": "active",
    })


def _write_parquet(df: pd.DataFrame) -> str:
    """Write df to a temp parquet file. Caller is responsible for cleanup."""
    f = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    df.to_parquet(f.name)
    f.close()
    return f.name


# ══════════════════════════════════════════════════════════════════════════════
# 1. PlanStore Unit Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanStore(unittest.TestCase):

    def setUp(self):
        self.store = PlanStore(max_per_dataset=5)

    def test_save_and_get_latest(self):
        plan = _make_plan("ds-1")
        self.store.save("u1", "ds-1", plan)
        retrieved = self.store.get_latest("u1", "ds-1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.plan_id, plan.plan_id)

    def test_newest_first_ordering(self):
        p1 = _make_plan("ds-1", score=60)
        p2 = _make_plan("ds-1", score=70)
        self.store.save("u1", "ds-1", p1)
        self.store.save("u1", "ds-1", p2)
        latest = self.store.get_latest("u1", "ds-1")
        # p2 was saved last → it is newest
        self.assertEqual(latest.plan_id, p2.plan_id)

    def test_list_returns_newest_first(self):
        plans = [_make_plan("ds-1") for _ in range(3)]
        for p in plans:
            self.store.save("u1", "ds-1", p)
        listed = self.store.list_for_dataset("u1", "ds-1")
        # Third plan saved = newest = first in list
        self.assertEqual(listed[0].plan_id, plans[-1].plan_id)

    def test_get_by_plan_id(self):
        p1 = _make_plan("ds-1")
        p2 = _make_plan("ds-1")
        self.store.save("u1", "ds-1", p1)
        self.store.save("u1", "ds-1", p2)
        found = self.store.get_by_plan_id("u1", "ds-1", p1.plan_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.plan_id, p1.plan_id)

    def test_get_by_nonexistent_plan_id_returns_none(self):
        self.store.save("u1", "ds-1", _make_plan("ds-1"))
        self.assertIsNone(self.store.get_by_plan_id("u1", "ds-1", "fake-uuid"))

    def test_get_latest_empty_returns_none(self):
        self.assertIsNone(self.store.get_latest("u1", "nonexistent"))

    def test_list_empty_returns_empty_list(self):
        self.assertEqual(self.store.list_for_dataset("u1", "none"), [])

    def test_user_isolation(self):
        """Plans for user A must not be visible to user B."""
        plan_a = _make_plan("ds-1")
        self.store.save("user_a", "ds-1", plan_a)
        self.assertIsNone(self.store.get_latest("user_b", "ds-1"))

    def test_dataset_isolation(self):
        """Plans for ds-1 must not appear in ds-2's bucket."""
        self.store.save("u1", "ds-1", _make_plan("ds-1"))
        self.assertIsNone(self.store.get_latest("u1", "ds-2"))

    def test_eviction_at_max_capacity(self):
        """When max_per_dataset is exceeded, the oldest plan is evicted."""
        for i in range(6):   # max is 5
            self.store.save("u1", "ds-1", _make_plan("ds-1"))
        self.assertEqual(self.store.count("u1", "ds-1"), 5)

    def test_delete_for_dataset(self):
        for _ in range(3):
            self.store.save("u1", "ds-1", _make_plan("ds-1"))
        deleted = self.store.delete_for_dataset("u1", "ds-1")
        self.assertEqual(deleted, 3)
        self.assertEqual(self.store.count("u1", "ds-1"), 0)

    def test_delete_nonexistent_returns_zero(self):
        self.assertEqual(self.store.delete_for_dataset("u1", "none"), 0)

    def test_total_plans(self):
        self.store.save("u1", "ds-1", _make_plan("ds-1"))
        self.store.save("u1", "ds-2", _make_plan("ds-2"))
        self.store.save("u2", "ds-1", _make_plan("ds-1"))
        self.assertEqual(self.store.total_plans(), 3)

    def test_clear(self):
        for _ in range(3):
            self.store.save("u1", "ds-1", _make_plan("ds-1"))
        self.store.clear()
        self.assertEqual(self.store.total_plans(), 0)

    def test_thread_safety_concurrent_saves(self):
        """Concurrent saves from multiple threads must not corrupt the store."""
        errors = []

        def save_plans():
            try:
                for _ in range(10):
                    self.store.save("u1", "ds-shared", _make_plan("ds-shared"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=save_plans) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        # Count must not exceed max_per_dataset=5
        self.assertLessEqual(self.store.count("u1", "ds-shared"), 5)


# ══════════════════════════════════════════════════════════════════════════════
# 2. CleaningPlanMeta Schema Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCleaningPlanMeta(unittest.TestCase):

    def test_from_plan_factory(self):
        plan = _make_plan("ds-abc", score=72)
        meta = CleaningPlanMeta.from_plan(plan)
        self.assertEqual(meta.plan_id, plan.plan_id)
        self.assertEqual(meta.dataset_id, "ds-abc")
        self.assertEqual(meta.overall_quality_score, 72)
        self.assertEqual(meta.quality_grade, plan.summary.quality_grade)
        self.assertTrue(meta.readonly)

    def test_meta_has_no_actions_field(self):
        """CleaningPlanMeta must not expose the full actions list."""
        meta = CleaningPlanMeta.from_plan(_make_plan())
        self.assertFalse(hasattr(meta, "actions"))

    def test_meta_serialises_correctly(self):
        meta = CleaningPlanMeta.from_plan(_make_plan("ds-xyz", score=55))
        data = meta.model_dump()
        self.assertIn("plan_id", data)
        self.assertIn("total_issues", data)
        self.assertNotIn("actions", data)


# ══════════════════════════════════════════════════════════════════════════════
# 3. v1 API Endpoint Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCleaningV1Router(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides = {}
        # Clear the global plan store before each test
        get_plan_store().clear()

    def tearDown(self):
        app.dependency_overrides = {}
        get_plan_store().clear()

    def _auth(self, uid: str = "test_user") -> None:
        app.dependency_overrides[verify_firebase_token] = lambda: {"uid": uid}

    def _register(self, dataset_id: str, user_id: str, parquet_path: str) -> None:
        service = get_dataset_service()
        if hasattr(service, "store"):
            service.store = {
                k: v for k, v in service.store.items() if k != dataset_id
            }
        _register_dataset(get_dataset_service(), dataset_id, user_id, parquet_path)

    # ── POST /{dataset_id} ────────────────────────────────────────────────────

    def test_post_returns_201_with_plan(self):
        """POST should generate and return a CleaningPlan with HTTP 201."""
        df = pd.DataFrame({
            "salary": [50000, 60000, None, 80000, 100000] * 20,
            "category": ["A", "B", None, "C", "D"] * 20,
        })
        tmp = _write_parquet(df)
        try:
            self._register("ds-post-test", "test_user", tmp)
            self._auth("test_user")
            r = self.client.post("/api/v1/cleaning/plan/ds-post-test")
            self.assertEqual(r.status_code, 201)
            data = r.json()
            self.assertIn("plan", data)
            self.assertIn("message", data)
            self.assertIn("dataset_id", data)
            self.assertEqual(data["status"], "generated")
            self.assertEqual(data["dataset_id"], "ds-post-test")
            self.assertTrue(data["plan"]["readonly"])
            self.assertEqual(data["plan"]["phase"], "2A")
        finally:
            os.remove(tmp)

    def test_post_stores_plan_in_store(self):
        """A successful POST must persist the plan so it can be GETted later."""
        df = pd.DataFrame({"A": list(range(100)), "B": [None if i % 10 == 0 else i for i in range(100)]})
        tmp = _write_parquet(df)
        try:
            self._register("ds-store-test", "test_user", tmp)
            self._auth("test_user")
            r = self.client.post("/api/v1/cleaning/plan/ds-store-test")
            self.assertEqual(r.status_code, 201)
            plan_id = r.json()["plan"]["plan_id"]
            # Verify it is in the store
            stored = get_plan_store().get_by_plan_id("test_user", "ds-store-test", plan_id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored.plan_id, plan_id)
        finally:
            os.remove(tmp)

    def test_post_multiple_plans_accumulate(self):
        """Each POST must add a new plan (not overwrite the previous one)."""
        df = pd.DataFrame({"A": list(range(100))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-multi", "test_user", tmp)
            self._auth("test_user")
            self.client.post("/api/v1/cleaning/plan/ds-multi")
            self.client.post("/api/v1/cleaning/plan/ds-multi")
            count = get_plan_store().count("test_user", "ds-multi")
            self.assertEqual(count, 2)
        finally:
            os.remove(tmp)

    def test_post_returns_message_with_score_info(self):
        df = pd.DataFrame({"X": list(range(200))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-msg-test", "test_user", tmp)
            self._auth("test_user")
            r = self.client.post("/api/v1/cleaning/plan/ds-msg-test")
            self.assertIn("score", r.json()["message"].lower())
        finally:
            os.remove(tmp)

    def test_post_wrong_owner_403(self):
        df = pd.DataFrame({"A": [1, 2, 3]})
        tmp = _write_parquet(df)
        try:
            self._register("ds-owned", "real_owner", tmp)
            self._auth("attacker")
            r = self.client.post("/api/v1/cleaning/plan/ds-owned")
            self.assertEqual(r.status_code, 403)
        finally:
            os.remove(tmp)

    def test_post_nonexistent_dataset_404(self):
        self._auth("test_user")
        r = self.client.post("/api/v1/cleaning/plan/does-not-exist-uuid")
        self.assertEqual(r.status_code, 404)

    def test_post_no_auth_401_or_403(self):
        r = self.client.post("/api/v1/cleaning/plan/any-dataset")
        self.assertIn(r.status_code, (401, 403))

    def test_post_missing_parquet_file_404(self):
        """If the parquet file is gone from disk, expect HTTP 404."""
        service = get_dataset_service()
        if hasattr(service, "store"):
            service.store.pop("ds-deleted-file", None)
        service.create_dataset({
            "dataset_id": "ds-deleted-file",
            "user_id": "test_user",
            "dataset_name": "gone.parquet",
            "original_file_type": "parquet",
            "source": "upload",
            "upload_timestamp": "2026-06-14T00:00:00Z",
            "row_count": 10,
            "column_count": 2,
            "memory_usage": 0.01,
            "parquet_path": "/nonexistent/path/data.parquet",
            "ml_readiness_score": 0,
            "dataset_version": 1,
            "status": "active",
        })
        self._auth("test_user")
        r = self.client.post("/api/v1/cleaning/plan/ds-deleted-file")
        self.assertEqual(r.status_code, 404)

    # ── GET /{dataset_id} ─────────────────────────────────────────────────────

    def test_get_returns_200_with_plan_list(self):
        """GET after POST must return the stored plan."""
        df = pd.DataFrame({"A": list(range(100)), "B": list(range(100, 200))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-get-test", "test_user", tmp)
            self._auth("test_user")
            self.client.post("/api/v1/cleaning/plan/ds-get-test")
            r = self.client.get("/api/v1/cleaning/plan/ds-get-test")
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertEqual(data["dataset_id"], "ds-get-test")
            self.assertEqual(data["total_plans"], 1)
            self.assertEqual(len(data["plans"]), 1)
            self.assertIsNotNone(data["latest_plan"])
        finally:
            os.remove(tmp)

    def test_get_returns_200_no_plans_yet(self):
        """GET before any POST must return 200 with total_plans=0, latest_plan=null."""
        df = pd.DataFrame({"A": [1, 2, 3]})
        tmp = _write_parquet(df)
        try:
            self._register("ds-empty-get", "test_user", tmp)
            self._auth("test_user")
            r = self.client.get("/api/v1/cleaning/plan/ds-empty-get")
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertEqual(data["total_plans"], 0)
            self.assertEqual(data["plans"], [])
            self.assertIsNone(data["latest_plan"])
        finally:
            os.remove(tmp)

    def test_get_with_plan_id_returns_specific_plan(self):
        """GET ?plan_id=<uuid> should return that specific plan in latest_plan."""
        df = pd.DataFrame({"A": list(range(100))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-plan-id-test", "test_user", tmp)
            self._auth("test_user")
            r1 = self.client.post("/api/v1/cleaning/plan/ds-plan-id-test")
            plan_id_1 = r1.json()["plan"]["plan_id"]
            r2 = self.client.post("/api/v1/cleaning/plan/ds-plan-id-test")
            # Request plan 1 specifically
            r = self.client.get(
                "/api/v1/cleaning/plan/ds-plan-id-test",
                params={"plan_id": plan_id_1},
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["latest_plan"]["plan_id"], plan_id_1)
            self.assertEqual(r.json()["total_plans"], 2)
        finally:
            os.remove(tmp)

    def test_get_plans_list_contains_meta_not_actions(self):
        """plans[] in the GET response must be CleaningPlanMeta (no actions field)."""
        df = pd.DataFrame({"A": list(range(100))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-meta-check", "test_user", tmp)
            self._auth("test_user")
            self.client.post("/api/v1/cleaning/plan/ds-meta-check")
            r = self.client.get("/api/v1/cleaning/plan/ds-meta-check")
            meta_item = r.json()["plans"][0]
            self.assertIn("plan_id", meta_item)
            self.assertIn("overall_quality_score", meta_item)
            self.assertNotIn("actions", meta_item)   # lightweight meta only
        finally:
            os.remove(tmp)

    def test_get_multiple_plans_shows_correct_count(self):
        df = pd.DataFrame({"A": list(range(100))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-count-test", "test_user", tmp)
            self._auth("test_user")
            for _ in range(3):
                self.client.post("/api/v1/cleaning/plan/ds-count-test")
            r = self.client.get("/api/v1/cleaning/plan/ds-count-test")
            self.assertEqual(r.json()["total_plans"], 3)
            self.assertEqual(len(r.json()["plans"]), 3)
        finally:
            os.remove(tmp)

    def test_get_wrong_owner_403(self):
        df = pd.DataFrame({"A": [1, 2, 3]})
        tmp = _write_parquet(df)
        try:
            self._register("ds-get-owned", "real_owner", tmp)
            self._auth("attacker")
            r = self.client.get("/api/v1/cleaning/plan/ds-get-owned")
            self.assertEqual(r.status_code, 403)
        finally:
            os.remove(tmp)

    def test_get_nonexistent_dataset_404(self):
        self._auth("test_user")
        r = self.client.get("/api/v1/cleaning/plan/no-such-dataset")
        self.assertEqual(r.status_code, 404)

    def test_get_no_auth_rejected(self):
        r = self.client.get("/api/v1/cleaning/plan/any-id")
        self.assertIn(r.status_code, (401, 403))

    # ── DELETE /{dataset_id} ──────────────────────────────────────────────────

    def test_delete_purges_plans(self):
        df = pd.DataFrame({"A": list(range(100))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-delete-test", "test_user", tmp)
            self._auth("test_user")
            self.client.post("/api/v1/cleaning/plan/ds-delete-test")
            self.client.post("/api/v1/cleaning/plan/ds-delete-test")
            r = self.client.delete("/api/v1/cleaning/plan/ds-delete-test")
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertEqual(data["plans_deleted"], 2)
            self.assertEqual(data["dataset_id"], "ds-delete-test")
            # Verify store is now empty
            self.assertEqual(get_plan_store().count("test_user", "ds-delete-test"), 0)
        finally:
            os.remove(tmp)

    def test_delete_nonexistent_dataset_404(self):
        self._auth("test_user")
        r = self.client.delete("/api/v1/cleaning/plan/nonexistent-ds")
        self.assertEqual(r.status_code, 404)

    def test_delete_wrong_owner_403(self):
        df = pd.DataFrame({"A": [1, 2, 3]})
        tmp = _write_parquet(df)
        try:
            self._register("ds-del-owned", "real_owner", tmp)
            self._auth("attacker")
            r = self.client.delete("/api/v1/cleaning/plan/ds-del-owned")
            self.assertEqual(r.status_code, 403)
        finally:
            os.remove(tmp)

    # ── Response schema validation ────────────────────────────────────────────

    def test_generate_plan_response_schema_fields(self):
        """POST response must include all GeneratePlanResponse fields."""
        df = pd.DataFrame({"A": list(range(100)), "B": list(range(100))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-schema-test", "test_user", tmp)
            self._auth("test_user")
            r = self.client.post("/api/v1/cleaning/plan/ds-schema-test")
            data = r.json()
            for field in ("status", "message", "dataset_id", "plan"):
                self.assertIn(field, data, f"Missing field: {field}")
            for field in ("plan_id", "generated_at", "summary", "actions", "readonly", "phase"):
                self.assertIn(field, data["plan"], f"Missing plan field: {field}")
            for field in ("total_issues", "overall_quality_score", "quality_grade",
                          "estimated_score_after_cleaning", "auto_applicable_count"):
                self.assertIn(field, data["plan"]["summary"], f"Missing summary field: {field}")
        finally:
            os.remove(tmp)

    def test_plan_list_response_schema_fields(self):
        """GET response must include all PlanListResponse fields."""
        df = pd.DataFrame({"A": list(range(100))})
        tmp = _write_parquet(df)
        try:
            self._register("ds-list-schema", "test_user", tmp)
            self._auth("test_user")
            self.client.post("/api/v1/cleaning/plan/ds-list-schema")
            r = self.client.get("/api/v1/cleaning/plan/ds-list-schema")
            data = r.json()
            for field in ("dataset_id", "total_plans", "plans", "latest_plan"):
                self.assertIn(field, data, f"Missing field: {field}")
        finally:
            os.remove(tmp)

    def test_get_singleton_plan_store(self):
        """get_plan_store() must return the same instance each call."""
        from services.plan_store import get_plan_store as gps
        self.assertIs(gps(), gps())


if __name__ == "__main__":
    unittest.main()
