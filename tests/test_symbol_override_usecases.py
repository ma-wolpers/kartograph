"""Tests für planbezogene Symbol-Anpassungen (Usecase, Symbolsicht, Undo)."""

from __future__ import annotations

import pytest

from app.core.domain.catalog_validation import CatalogValidationError
from app.core.domain.models_v4 import SymbolOverride
from app.core.domain.symbol_catalog import Competence, SymbolDefinition
from app.core.domain.symbol_view import build_symbol_view
from app.core.usecases.v4.symbol_override_usecases import set_symbol_override
from tests.conftest import make_plan

LEVELS = ("eins", "zwei", "drei")
COMPETENCES = (Competence("k.a", "A", "K", LEVELS), Competence("k.b", "B", "K", LEVELS))
FOCUS = SymbolDefinition(key="Konzentration", name="Konzentration", glyph="🎯", shortcut="z", competence_ids=("k.a",))
OTHER = SymbolDefinition(key="Beteiligung", name="Beteiligung", glyph="👆", shortcut="b", competence_ids=("k.b",))
ABSENT = SymbolDefinition(key="Abwesend", name="Abwesend", glyph="∅", shortcut="space", role="documentation_only",
                          frequency_legend=LEVELS)
CATALOG = (FOCUS, OTHER, ABSENT)


def _set(plan, key, name, ids):
    return set_symbol_override(plan, CATALOG, COMPETENCES, key, name, ids)


def test_local_name_and_competences_are_stored_and_applied() -> None:
    plan = _set(make_plan(), "Konzentration", " Fokus ", ["k.b", "k.a"])

    assert plan.symbol_overrides == {"Konzentration": SymbolOverride(name="Fokus", competence_ids=("k.b", "k.a"))}
    effective = build_symbol_view(CATALOG, COMPETENCES, plan).by_key["Konzentration"]
    assert (effective.name, effective.competence_ids, effective.shortcut) == ("Fokus", ("k.b", "k.a"), "z")


def test_values_equal_to_the_program_default_are_not_stored() -> None:
    plan = _set(make_plan(), "Konzentration", "Konzentration", ["k.a"])
    assert plan.symbol_overrides == {}


def test_reset_removes_the_entry_and_leaves_the_input_plan_untouched() -> None:
    original = _set(make_plan(), "Konzentration", "Fokus", None)
    reset = _set(original, "Konzentration", None, None)
    assert reset.symbol_overrides == {} and original.symbol_overrides != {}


def test_local_names_must_stay_unique_against_effective_names() -> None:
    plan = _set(make_plan(), "Beteiligung", "Fokus", None)
    with pytest.raises(CatalogValidationError, match="heißt schon"):
        _set(plan, "Konzentration", "fokus", None)


@pytest.mark.parametrize(
    ("key", "ids", "message"),
    [("Konzentration", [], "mindestens eine"), ("Konzentration", ["fehlt"], "Unbekannte"),
     ("Abwesend", ["k.a"], "keine Kompetenzen"), ("Gibtsnicht", None, "Unbekanntes Symbol")],
)
def test_invalid_overrides_are_rejected(key, ids, message) -> None:
    with pytest.raises(CatalogValidationError, match=message):
        _set(make_plan(), key, "Neu", ids)


def test_override_is_one_undo_step() -> None:
    """Plan-Anpassungen laufen über die Plan-History (anders als programmweite Änderungen)."""
    from dataclasses import replace

    from app.application.handlers.custom_symbol_handlers import handle_set_symbol_override
    from app.application.handlers.edit_handlers import handle_undo
    from app.core.intents import SetSymbolOverrideIntent, UndoIntent
    from tests.test_app_controller import PLANS_DIR, make_ctx, make_state_with_plan

    plan = make_plan()
    path = PLANS_DIR / "test.json"
    ctx = make_ctx({path: plan})
    ctx.history.reset(plan, path)
    state = replace(make_state_with_plan(plan, path), symbol_catalog=CATALOG, competence_catalog=COMPETENCES)

    changed = handle_set_symbol_override(SetSymbolOverrideIntent("Konzentration", "Fokus", ("k.b",)), state, ctx)
    undone = handle_undo(UndoIntent(), changed, ctx)

    assert changed.current_plan.symbol_overrides["Konzentration"].name == "Fokus"
    assert undone.current_plan.symbol_overrides == {}
