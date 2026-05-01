from __future__ import annotations

from pathlib import Path

from app.core.domain.models import Desk, SeatingPlan
from app.infrastructure.repositories.json_plan_repository import JsonSeatingPlanRepository


def _plan() -> SeatingPlan:
    return SeatingPlan(
        version=3,
        plan_id="backup-test",
        name="Backup",
        desks=[Desk(x=0, y=0, desk_type="teacher")],
    )


def test_save_writes_backup_and_rotates_to_limit(tmp_path, monkeypatch) -> None:
    repo = JsonSeatingPlanRepository()
    monkeypatch.setattr(repo, "_backup_root_dir", lambda: tmp_path / "appdata" / "Kartograph" / "backups")
    plan_path = tmp_path / "plans" / "klasse-7a.json"

    for index in range(25):
        plan = _plan()
        plan.name = f"Backup {index}"
        repo.save_plan(plan, plan_path)

    backup_dir = (tmp_path / "appdata" / "Kartograph" / "backups" / "klasse-7a")
    backups = sorted(backup_dir.glob("*.json"))
    assert len(backups) == 20
    assert backups[-1].is_file()
