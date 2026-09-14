"""Tests für strukturierten Fehlertransport bei der Snapshot-Deserialisierung.

Deckt die Abgrenzung aus ``deserializer_v4.py::_deserialize_snapshots`` ab:
welche fehlerhaften Rohdaten ein ``SnapshotLoadIssue`` erzeugen und welche
still repariert/verworfen werden -- sowie das No-Cache-Design von
``JsonSeatingPlanRepositoryV4.load_snapshot_load_issues()`` (immer frisch von
der Festplatte gelesen, kein GUI-Cache, der veralten könnte).
"""

from __future__ import annotations

import pytest

from app.infrastructure.repositories.v4.deserializer_v4 import (
    deserialize_plan,
    deserialize_snapshot_load_issues,
)
from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from tests.conftest import make_plan, make_student


def _base_payload() -> dict:
    return serialize_plan(make_plan())


class TestSilentlyRepairedOrDropped:
    """Fehlerhafte Rohdaten, die KEIN SnapshotLoadIssue erzeugen (Tabelle in C.6)."""

    def test_missing_snapshot_id_drops_whole_entry_silently(self):
        payload = _base_payload()
        payload["snapshots"] = [{"name": "Kaputt", "teacher_seat": {"x": 0, "y": 0}, "seats": {}}]
        plan = deserialize_plan(payload)
        assert plan.snapshots == []
        assert deserialize_snapshot_load_issues(payload) == {}

    def test_duplicate_snapshot_id_drops_second_entry_silently(self):
        payload = _base_payload()
        entry = {"snapshot_id": "dup", "name": "Erster", "teacher_seat": {"x": 0, "y": 0}, "seats": {}}
        entry2 = {"snapshot_id": "dup", "name": "Zweiter", "teacher_seat": {"x": 0, "y": 0}, "seats": {}}
        payload["snapshots"] = [entry, entry2]
        plan = deserialize_plan(payload)
        assert len(plan.snapshots) == 1
        assert plan.snapshots[0].name == "Erster"
        assert deserialize_snapshot_load_issues(payload) == {}

    def test_missing_name_falls_back_to_default_no_issue(self):
        payload = _base_payload()
        payload["snapshots"] = [{"snapshot_id": "a", "teacher_seat": {"x": 0, "y": 0}, "seats": {}}]
        plan = deserialize_plan(payload)
        assert plan.snapshots[0].name == "Unbenannter Snapshot"
        assert deserialize_snapshot_load_issues(payload) == {}

    def test_invalid_teacher_seat_defaults_to_zero_no_issue(self):
        payload = _base_payload()
        payload["snapshots"] = [{"snapshot_id": "a", "name": "X", "teacher_seat": {"x": "kaputt"}, "seats": {}}]
        plan = deserialize_plan(payload)
        assert plan.snapshots[0].teacher_seat.x == 0
        assert plan.snapshots[0].teacher_seat.y == 0
        assert deserialize_snapshot_load_issues(payload) == {}


class TestStructuredIssues:
    """Fehlerhafte Rohdaten, die genau EIN SnapshotLoadIssue erzeugen."""

    def test_invalid_student_id_skips_entry_and_reports_issue(self):
        payload = _base_payload()
        payload["snapshots"] = [{
            "snapshot_id": "a",
            "name": "X",
            "teacher_seat": {"x": 0, "y": 0},
            "seats": {"not-a-valid-uuid": {"x": 1, "y": 1}},
        }]
        plan = deserialize_plan(payload)
        assert plan.snapshots[0].seats == {}

        issues = deserialize_snapshot_load_issues(payload)
        assert list(issues.keys()) == ["a"]
        assert len(issues["a"]) == 1
        assert issues["a"][0].reason == "invalid_student_id"

    def test_invalid_seat_coordinates_skips_entry_and_reports_issue(self):
        sid = "a" * 32
        payload = _base_payload()
        payload["snapshots"] = [{
            "snapshot_id": "a",
            "name": "X",
            "teacher_seat": {"x": 0, "y": 0},
            "seats": {sid: {"x": "kaputt", "y": 1}},
        }]
        plan = deserialize_plan(payload)
        assert plan.snapshots[0].seats == {}

        issues = deserialize_snapshot_load_issues(payload)
        assert issues["a"][0].reason == "invalid_seat"

    def test_snapshot_stays_usable_with_remaining_valid_entries(self):
        good_sid = "b" * 32
        payload = _base_payload()
        payload["snapshots"] = [{
            "snapshot_id": "a",
            "name": "X",
            "teacher_seat": {"x": 0, "y": 0},
            "seats": {
                "not-a-valid-uuid": {"x": 1, "y": 1},
                good_sid: {"x": 2, "y": 2},
            },
        }]
        plan = deserialize_plan(payload)
        assert len(plan.snapshots[0].seats) == 1

    def test_multiple_issues_in_different_snapshots_grouped_separately(self):
        payload = _base_payload()
        payload["snapshots"] = [
            {
                "snapshot_id": "a",
                "name": "X",
                "teacher_seat": {"x": 0, "y": 0},
                "seats": {"not-a-valid-uuid": {"x": 1, "y": 1}},
            },
            {
                "snapshot_id": "b",
                "name": "Y",
                "teacher_seat": {"x": 0, "y": 0},
                "seats": {"c" * 32: {"x": "kaputt"}},
            },
        ]
        issues = deserialize_snapshot_load_issues(payload)
        assert set(issues.keys()) == {"a", "b"}
        assert issues["a"][0].reason == "invalid_student_id"
        assert issues["b"][0].reason == "invalid_seat"


@pytest.fixture
def repo(tmp_path, monkeypatch) -> JsonSeatingPlanRepositoryV4:
    instance = JsonSeatingPlanRepositoryV4()
    monkeypatch.setattr(instance, "_backup_root_dir", lambda: tmp_path / "appdata" / "backups")
    return instance


class TestNoCacheFreshness:
    """Repository-Ebene: load_snapshot_load_issues() liest immer frisch von der Platte."""

    def test_issue_disappears_after_plan_is_saved_clean(self, repo, tmp_path):
        plans_dir = tmp_path / "plans"
        path, plan = repo.create_new_plan(plans_dir, "Klasse 5a")

        payload = serialize_plan(plan)
        payload["snapshots"] = [{
            "snapshot_id": "a",
            "name": "X",
            "teacher_seat": {"x": 0, "y": 0},
            "seats": {"not-a-valid-uuid": {"x": 1, "y": 1}},
        }]
        import json
        path.write_text(json.dumps(payload), encoding="utf-8")

        issues_before = repo.load_snapshot_load_issues(path)
        assert issues_before["a"][0].reason == "invalid_student_id"

        # Der Plan wird jetzt (unabhaengig vom betroffenen Snapshot) erneut
        # gespeichert -- serialize_plan() schreibt alle Snapshots aus den
        # sauberen In-Memory-Objekten neu, der kaputte Rohwert ist danach weg.
        clean_plan = repo.load_plan(path)
        repo.save_plan(clean_plan, path)

        issues_after = repo.load_snapshot_load_issues(path)
        assert issues_after == {}

    def test_no_issues_for_plan_without_snapshots(self, repo, tmp_path):
        plans_dir = tmp_path / "plans"
        path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")
        assert repo.load_snapshot_load_issues(path) == {}
