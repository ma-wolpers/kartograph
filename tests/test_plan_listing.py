"""Tests für ``build_plan_list`` — die einzige Stelle, die normale und optional
archivierte Pläne zu einer PlanListEntry-Liste zusammenführt.
"""

from __future__ import annotations

import pytest

from app.application.plan_listing import build_plan_list
from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4


@pytest.fixture
def repo(tmp_path, monkeypatch) -> JsonSeatingPlanRepositoryV4:
    instance = JsonSeatingPlanRepositoryV4()
    monkeypatch.setattr(instance, "_backup_root_dir", lambda: tmp_path / "appdata" / "backups")
    return instance


def test_include_archived_false_excludes_archived(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    normal_path, _plan = repo.create_new_plan(plans_dir, "Normal")
    archived_path, _archived_plan = repo.create_new_plan(plans_dir, "Archiviert")
    repo.archive_plan(archived_path)

    entries = build_plan_list(repo, plans_dir, include_archived=False)

    assert [e.name for e in entries] == ["Normal"]
    assert entries[0].is_archived is False


def test_include_archived_true_includes_archived_with_flag(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    _normal_path, _plan = repo.create_new_plan(plans_dir, "Normal")
    archived_path, _archived_plan = repo.create_new_plan(plans_dir, "Archiviert")
    target_path = repo.archive_plan(archived_path)

    entries = build_plan_list(repo, plans_dir, include_archived=True)

    by_name = {e.name: e for e in entries}
    assert by_name["Normal"].is_archived is False
    assert by_name["Archiviert"].is_archived is True
    assert by_name["Archiviert"].path == target_path
