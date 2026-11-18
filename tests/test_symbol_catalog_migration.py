"""Tests für die Migration alter ``symbols.json``-Arbeitskopien (``meaning`` + Legende → ``key`` + Kompetenzen)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.infrastructure.symbol_catalog_migration import local_competence_id, migrate_symbol_items
from app.infrastructure.symbol_config_loader import DEFAULT_SYMBOLS_PATH, load_catalog

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ITEMS = json.loads(DEFAULT_SYMBOLS_PATH.read_text(encoding="utf-8"))["symbols"]
CONCENTRATION_LINKS = next(item["competences"] for item in DEFAULT_ITEMS if item["codepoint"] == "1F3AF")
OWN_LEGEND = {"three": "eigen drei", "two": "eigen zwei", "one": "eigen eins"}


def _old_default_items() -> list[dict]:
    """Die Standardsymbole im Format vor der Umstellung (Stand vor 2026-11-18, aus der Git-Historie)."""
    raw = subprocess.run(
        ["git", "show", "84d0ba9:app/infrastructure/default_symbols.json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False,
    ).stdout
    if not raw:
        pytest.skip("Git-Historie nicht verfügbar")
    return json.loads(raw)["symbols"]


def test_unchanged_old_default_legends_get_default_links() -> None:
    items = _old_default_items()
    competences: list = []

    symbols_changed, competences_changed, adopted = migrate_symbol_items(items, DEFAULT_ITEMS, competences)

    assert symbols_changed and not competences_changed and adopted == []
    defaults = {item["codepoint"]: item for item in DEFAULT_ITEMS}
    for item in items:
        assert "meaning" not in item and item["key"]
        if item.get("role") == "documentation_only":
            assert "legend" in item and "competences" not in item
        else:
            assert "legend" not in item
            assert item["competences"] == defaults[item["codepoint"]]["competences"]


def test_edited_legend_becomes_local_competence() -> None:
    items = [{"codepoint": "1F3AF", "meaning": "Konzentration", "shortcut": "z", "legend": dict(OWN_LEGEND)}]
    competences: list = []

    _sym, competences_changed, adopted = migrate_symbol_items(items, DEFAULT_ITEMS, competences)

    assert competences_changed and adopted == ["Konzentration"]
    assert items[0]["competences"] == ["local.konzentration"]
    assert competences == [{"id": "local.konzentration", "name": "Konzentration", "group": "Eigene",
                            "levels": OWN_LEGEND}]


def test_own_symbol_with_legend_becomes_local_competence() -> None:
    items = [{"codepoint": "1F600", "meaning": "Umgang mit Ärger", "legend": dict(OWN_LEGEND)}]
    competences: list = []

    migrate_symbol_items(items, DEFAULT_ITEMS, competences)

    assert items[0]["competences"] == ["local.umgang_mit_aerger"]


def test_existing_local_competence_is_reused() -> None:
    existing = [{"id": "local.konzentration", "name": "Konzentration", "group": "Eigene", "levels": OWN_LEGEND}]
    items = [{"codepoint": "1F3AF", "key": "Konzentration", "legend": dict(OWN_LEGEND)}]

    _sym, competences_changed, _adopted = migrate_symbol_items(items, DEFAULT_ITEMS, existing)

    assert not competences_changed and len(existing) == 1
    assert items[0]["competences"] == ["local.konzentration"]


def test_missing_legend_falls_back_to_default_links() -> None:
    items = [{"codepoint": "1F3AF", "key": "Konzentration"}]
    migrate_symbol_items(items, DEFAULT_ITEMS, [])
    assert items[0]["competences"] == CONCENTRATION_LINKS


def test_explicit_empty_competences_are_kept() -> None:
    items = [{"codepoint": "1F3AF", "key": "Konzentration", "competences": []}]
    symbols_changed, _comp, _adopted = migrate_symbol_items(items, DEFAULT_ITEMS, [])
    assert not symbols_changed and items[0]["competences"] == []


def test_local_competence_id_is_ascii_and_deterministic() -> None:
    assert local_competence_id("Programmieren o.ä.") == "local.programmieren_o_ae"
    assert local_competence_id("Programmieren o.ä.") == local_competence_id("Programmieren o.ä.")


def test_loading_an_old_working_copy_migrates_once(tmp_path) -> None:
    symbols_path, competences_path = tmp_path / "symbols.json", tmp_path / "competences.json"
    old = _old_default_items() + [{"codepoint": "1F600", "meaning": "Eigenes", "legend": dict(OWN_LEGEND)}]
    known = sorted(f"{int(item['codepoint'], 16):04X}" for item in DEFAULT_ITEMS)
    symbols_path.write_text(json.dumps({"symbols": old, "known_builtin_codepoints": known}), encoding="utf-8")

    first = load_catalog(symbols_path, competences_path)
    snapshot = (symbols_path.read_text(encoding="utf-8"), competences_path.read_text(encoding="utf-8"))
    second = load_catalog(symbols_path, competences_path)

    assert "Eigenes" in first.warning and second.warning is None
    assert (symbols_path.read_text(encoding="utf-8"), competences_path.read_text(encoding="utf-8")) == snapshot
    by_key = {s.key: s for s in second.symbols}
    assert by_key["Konzentration"].competence_ids == tuple(CONCENTRATION_LINKS)
    assert by_key["Eigenes"].competence_ids == ("local.eigenes",)
    assert "local.eigenes" in {c.id for c in second.competences}


def test_crash_between_the_two_writes_is_harmless(tmp_path) -> None:
    """Kompetenzen schon geschrieben, Symbole noch alt: der nächste Lauf legt nichts doppelt an."""
    symbols_path, competences_path = tmp_path / "symbols.json", tmp_path / "competences.json"
    old_symbols = {"symbols": [{"codepoint": "1F600", "meaning": "Eigenes", "legend": dict(OWN_LEGEND)}]}
    symbols_path.write_text(json.dumps(old_symbols), encoding="utf-8")
    load_catalog(symbols_path, competences_path)
    symbols_path.write_text(json.dumps(old_symbols), encoding="utf-8")  # simulierter Abbruch vor dem Symbol-Schreiben

    result = load_catalog(symbols_path, competences_path)

    assert [c.id for c in result.competences].count("local.eigenes") == 1
