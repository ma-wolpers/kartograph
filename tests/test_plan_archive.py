"""Tests für Archivieren/Wiederherstellen von Sitzplänen (ALT-Unterordner).

Deckt ``JsonSeatingPlanRepositoryV4.archive_plan``/``restore_plan``/
``list_archived_plans`` gegen ein echtes temporäres Dateisystem ab.
"""

from __future__ import annotations

import pytest

from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4


@pytest.fixture
def repo(tmp_path, monkeypatch) -> JsonSeatingPlanRepositoryV4:
    """Repository mit Backup-Ziel innerhalb von tmp_path (kein Zugriff auf echtes APPDATA)."""
    instance = JsonSeatingPlanRepositoryV4()
    monkeypatch.setattr(instance, "_backup_root_dir", lambda: tmp_path / "appdata" / "backups")
    return instance


def test_archive_plan_moves_file_to_alt_subfolder(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")

    target_path = repo.archive_plan(path)

    assert target_path == plans_dir / "ALT" / "klasse-5a.json"
    assert target_path.exists()
    assert not path.exists()


def test_archive_plan_does_not_change_json_content(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")
    original_content = path.read_text(encoding="utf-8")

    target_path = repo.archive_plan(path)

    assert target_path.read_text(encoding="utf-8") == original_content


def test_list_plans_excludes_archived(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")
    repo.archive_plan(path)

    assert repo.list_plans(plans_dir) == []


def test_list_archived_plans_finds_moved_file(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, plan = repo.create_new_plan(plans_dir, "Klasse 5a")
    target_path = repo.archive_plan(path)

    archived = repo.list_archived_plans(plans_dir)

    assert archived == [(target_path, plan)]


def test_list_archived_plans_empty_when_no_archive_dir(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir(parents=True)

    assert repo.list_archived_plans(plans_dir) == []
    assert not (plans_dir / "ALT").exists()


def test_list_archived_plans_sorted_like_list_plans(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    for name in ["Zebra", "Anton", "Mitte"]:
        path, _plan = repo.create_new_plan(plans_dir, name)
        repo.archive_plan(path)

    archived_names = [plan.meta.name for _p, plan in repo.list_archived_plans(plans_dir)]
    assert archived_names == sorted(archived_names, key=lambda n: n.lower())


def test_archive_plan_collision_raises_file_exists_error(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")
    archive_dir = plans_dir / "ALT"
    archive_dir.mkdir(parents=True)
    (archive_dir / path.name).write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        repo.archive_plan(path)


def test_archive_plan_already_archived_raises_value_error(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")
    archived_path = repo.archive_plan(path)

    with pytest.raises(ValueError):
        repo.archive_plan(archived_path)


def test_restore_plan_moves_file_back(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")
    archived_path = repo.archive_plan(path)

    restored_path = repo.restore_plan(archived_path)

    assert restored_path == path
    assert restored_path.exists()
    assert not archived_path.exists()


def test_restore_plan_collision_raises_file_exists_error(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")
    archived_path = repo.archive_plan(path)
    repo.create_new_plan(plans_dir, "Klasse 5a", overwrite=True)

    with pytest.raises(FileExistsError):
        repo.restore_plan(archived_path)


def test_restore_plan_wrong_location_raises_value_error(repo, tmp_path) -> None:
    plans_dir = tmp_path / "plans"
    path, _plan = repo.create_new_plan(plans_dir, "Klasse 5a")

    with pytest.raises(ValueError):
        repo.restore_plan(path)
