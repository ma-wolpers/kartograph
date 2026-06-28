from __future__ import annotations

from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4
from tests.conftest import make_plan


def test_save_writes_backup_and_rotates_to_limit(tmp_path, monkeypatch) -> None:
    repo = JsonSeatingPlanRepositoryV4()
    monkeypatch.setattr(repo, "_backup_root_dir", lambda: tmp_path / "appdata" / "Kartograph" / "backups")
    plan_path = tmp_path / "plans" / "klasse-7a.json"

    for index in range(25):
        plan = make_plan(name=f"Backup {index}")
        repo.save_plan(plan, plan_path)

    backup_dir = (tmp_path / "appdata" / "Kartograph" / "backups" / "klasse-7a")
    backups = sorted(backup_dir.glob("*.json"))
    assert len(backups) == 20
    assert backups[-1].is_file()
