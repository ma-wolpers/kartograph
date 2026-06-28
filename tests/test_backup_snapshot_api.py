from __future__ import annotations

from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4
from tests.conftest import make_plan


def test_backup_snapshot_writes_without_primary_save(tmp_path, monkeypatch) -> None:
    repo = JsonSeatingPlanRepositoryV4()
    monkeypatch.setattr(repo, "_backup_root_dir", lambda: tmp_path / "appdata" / "Kartograph" / "backups")

    plan = make_plan(name="Snapshot")
    plan_path = tmp_path / "plans" / "klasse-7a.json"

    repo.backup_plan_snapshot(plan, plan_path)

    backup_dir = tmp_path / "appdata" / "Kartograph" / "backups" / "klasse-7a"
    backups = list(backup_dir.glob("*.json"))
    assert len(backups) == 1
    assert not plan_path.exists()
