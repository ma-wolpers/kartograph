"""Tests für Regeln, Usecases, Repository und Handler programmweiter Katalogänderungen."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers.catalog_handlers import (
    handle_add_catalog_symbol,
    handle_add_competence,
    handle_update_catalog_symbol,
)
from app.core.domain.catalog_validation import (
    CatalogValidationError,
    custom_shortcut_conflicts,
    validate_catalog_shortcut,
)
from app.core.domain.models_v4 import CustomSymbolDefinition
from app.core.domain.plan_history import PlanHistory
from app.core.domain.symbol_catalog import Competence, SymbolDefinition
from app.core.domain.symbol_glyph_palette import GLYPH_PALETTE
from app.core.intents.catalog_intents import AddCatalogSymbolIntent, AddCompetenceIntent, UpdateCatalogSymbolIntent
from app.core.usecases.catalog_usecases import add_competence, add_symbol, new_symbol_key, update_symbol
from app.infrastructure.repositories.symbol_catalog_repository import JsonSymbolCatalogRepository
from app.infrastructure.symbol_config_loader import DEFAULT_SYMBOLS_PATH

LEVELS = ("eins", "zwei", "drei")
COMPETENCES = (Competence("k.a", "A", "K", LEVELS), Competence("k.b", "B", "K", LEVELS))
FOCUS = SymbolDefinition(key="Konzentration", name="Konzentration", glyph="🎯", shortcut="z", competence_ids=("k.a",))
OFF = SymbolDefinition(key="Alt", name="Alt", glyph="?", shortcut="q", active=False, competence_ids=("k.a",))
ABSENT = SymbolDefinition(key="Abwesend", name="Abwesend", glyph="∅", shortcut="space", role="documentation_only",
                          frequency_legend=LEVELS)
CATALOG = (FOCUS, OFF, ABSENT)


@pytest.mark.parametrize(
    ("raw", "message"),
    [("ab", "einzelner Buchstabe"), ("o", "fest vergeben"), ("q", "„Alt“"), ("1", "einzelner Buchstabe")],
)
def test_invalid_shortcuts_are_rejected(raw: str, message: str) -> None:
    with pytest.raises(CatalogValidationError, match=message):
        validate_catalog_shortcut(raw, "Konzentration", CATALOG)


def test_shortcut_rules_for_valid_cases() -> None:
    assert validate_catalog_shortcut(" Y ", "Konzentration", CATALOG) == "y"
    assert validate_catalog_shortcut("", "Konzentration", CATALOG) is None
    assert validate_catalog_shortcut("z", "Konzentration", CATALOG) == "z"
    assert validate_catalog_shortcut("space", "Abwesend", CATALOG) == "space"


def test_custom_shortcut_conflicts_are_only_reported() -> None:
    custom = {"c1": CustomSymbolDefinition(id="c1", glyph="★", meaning="Eigenes", shortcut="Y")}
    assert custom_shortcut_conflicts("y", custom) == ["Eigenes"]
    assert custom_shortcut_conflicts("space", custom) == []


def test_update_keeps_the_key_and_changes_name_shortcut_and_links() -> None:
    catalog = update_symbol(CATALOG, COMPETENCES, "Konzentration", "Fokus", "y", True, ["k.b", "k.a"])
    updated = catalog[0]
    assert (updated.key, updated.name, updated.shortcut, updated.competence_ids) == ("Konzentration", "Fokus", "y", ("k.b", "k.a"))
    assert catalog[1:] == CATALOG[1:]


def test_update_rejects_duplicate_names_missing_competences_and_required_deactivation() -> None:
    with pytest.raises(CatalogValidationError, match="heißt schon"):
        update_symbol(CATALOG, COMPETENCES, "Konzentration", "alt", "z", True, ["k.a"])
    with pytest.raises(CatalogValidationError, match="mindestens eine"):
        update_symbol(CATALOG, COMPETENCES, "Konzentration", "Fokus", "z", True, [])
    with pytest.raises(CatalogValidationError, match="Abgaben zählen"):
        update_symbol(CATALOG, COMPETENCES, "Abwesend", "Abwesend", "space", False, [])


def test_add_symbol_inserts_after_the_diagnostic_symbols_with_a_palette_glyph() -> None:
    codepoint = GLYPH_PALETTE[0][0]
    catalog, key = add_symbol(CATALOG, COMPETENCES, "Ausdauer", codepoint, "y", ["k.b"])
    assert key == "Ausdauer"
    assert [d.key for d in catalog] == ["Konzentration", "Alt", "Ausdauer", "Abwesend"]
    assert catalog[2].glyph == chr(int(codepoint, 16)) and catalog[2].competence_ids == ("k.b",)


def test_add_symbol_rejects_glyphs_outside_the_palette() -> None:
    with pytest.raises(CatalogValidationError, match="Auswahl"):
        add_symbol(CATALOG, COMPETENCES, "Neu", "1F3AF", "", ["k.a"])


def test_new_keys_avoid_existing_and_legacy_keys() -> None:
    renamed = (SymbolDefinition(key="Konzentration", name="Fokus", glyph="🎯", shortcut=None),)
    assert new_symbol_key("Konzentration", renamed) == "Konzentration (2)"
    assert new_symbol_key("Mathem. Fachkompetenz", ()) == "Mathem. Fachkompetenz (2)"


def test_add_competence_generates_a_stable_ascii_id() -> None:
    competences, first = add_competence(COMPETENCES, "Ausdauer zeigen", "Eigene", LEVELS)
    _competences, second = add_competence(competences, "Ausdauer zeigen", "Andere", LEVELS)
    assert (first, second) == ("eigen.ausdauer_zeigen", "eigen.ausdauer_zeigen_2")


def test_palette_is_disjoint_from_default_symbols() -> None:
    defaults = {item["codepoint"] for item in json.loads(DEFAULT_SYMBOLS_PATH.read_text(encoding="utf-8"))["symbols"]}
    assert defaults.isdisjoint(cp for cp, _label in GLYPH_PALETTE)
    assert len({cp for cp, _label in GLYPH_PALETTE}) == len(GLYPH_PALETTE)


def _repository(tmp_path: Path) -> JsonSymbolCatalogRepository:
    return JsonSymbolCatalogRepository(tmp_path / "symbols.json", tmp_path / "competences.json")


def test_repository_roundtrip_keeps_known_lists(tmp_path) -> None:
    repository = _repository(tmp_path)
    loaded = repository.load()
    known_before = json.loads(repository.symbols_path.read_text(encoding="utf-8"))["known_builtin_codepoints"]

    symbols = update_symbol(loaded.symbols, loaded.competences, "Konzentration", "Fokus", "", False, ["konzentration.arbeiten"])
    repository.save(symbols, loaded.competences)
    reloaded = repository.load()

    focus = next(s for s in reloaded.symbols if s.key == "Konzentration")
    assert (focus.name, focus.shortcut, focus.active, focus.competence_ids) == ("Fokus", None, False, ("konzentration.arbeiten",))
    assert reloaded.competences == loaded.competences and reloaded.warning is None
    assert json.loads(repository.symbols_path.read_text(encoding="utf-8"))["known_builtin_codepoints"] == known_before


def _ctx(tmp_path: Path) -> HandlerContext:
    return HandlerContext(plan_repository=None, settings_repository=None, history=PlanHistory(),
                          default_plans_dir=tmp_path, symbol_catalog_repository=_repository(tmp_path))


def test_handlers_persist_without_plan_history(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    loaded = ctx.symbol_catalog_repository.load()
    state = AppState(symbol_catalog=loaded.symbols, competence_catalog=loaded.competences)

    state = handle_add_competence(AddCompetenceIntent("Ausdauer", "Eigene", LEVELS), state, ctx)
    state = handle_add_catalog_symbol(AddCatalogSymbolIntent("Ausdauer", GLYPH_PALETTE[0][0], "y", ("eigen.ausdauer",)), state, ctx)
    state = handle_update_catalog_symbol(
        UpdateCatalogSymbolIntent("Konzentration", "Fokus", "z", True, ("konzentration.arbeiten",)), state, ctx
    )

    reloaded = ctx.symbol_catalog_repository.load()
    assert reloaded.symbols == state.symbol_catalog and reloaded.competences == state.competence_catalog
    assert "Fokus" in state.status_message and "alle Pläne" in state.status_message
    assert not ctx.history.can_undo
