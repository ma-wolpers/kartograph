"""Tests für die Symbolsicht (``build_symbol_view``) und ihre Kürzelregel."""

from __future__ import annotations

from app.core.domain.models_v4 import CustomSymbolDefinition
from app.core.domain.symbol_catalog import Competence, SymbolDefinition
from app.core.domain.symbol_view import build_symbol_view
from tests.conftest import make_plan

FOCUS = SymbolDefinition(key="Konzentration", name="Fokus", glyph="🎯", shortcut="z", competence_ids=("k.a",))
OLD = SymbolDefinition(key="Alt", name="Alt", glyph="?", shortcut="q", active=False, competence_ids=("k.a",))
DUPLICATE = SymbolDefinition(key="Doppelt", name="Doppelt", glyph="!", shortcut="z", competence_ids=("k.a",))
ABSENT = SymbolDefinition(key="Abwesend", name="Abwesend", glyph="∅", shortcut="space", role="documentation_only",
                          frequency_legend=("a", "b", "c"))
COMPETENCE = Competence("k.a", "A", "K", ("eins", "zwei", "drei"))


def _plan_with_custom(letter: str):
    plan = make_plan()
    plan.custom_symbols["c1"] = CustomSymbolDefinition(id="c1", glyph="★", meaning="Eigenes", shortcut=letter)
    return plan


def test_view_exposes_keys_roles_and_competences() -> None:
    view = build_symbol_view([FOCUS, OLD, ABSENT], [COMPETENCE], None)

    assert view.keys == ["Konzentration", "Alt", "Abwesend"]
    assert view.diagnostic_keys == ["Konzentration", "Alt"]
    assert view.by_key["Konzentration"].name == "Fokus"
    assert view.competences == {"k.a": COMPETENCE}
    assert [s.key for s in view.documentation_symbols] == ["Abwesend"]


def test_active_builtin_wins_and_first_duplicate_wins() -> None:
    view = build_symbol_view([FOCUS, DUPLICATE], [], _plan_with_custom("Z"))
    assert view.symbol_for_shortcut("Z") == "Konzentration"
    assert view.symbol_for_shortcut("z") == "Konzentration"


def test_inactive_builtin_frees_its_letter_for_custom_symbols() -> None:
    assert build_symbol_view([OLD], [], None).symbol_for_shortcut("q") is None
    assert build_symbol_view([OLD], [], _plan_with_custom("Q")).symbol_for_shortcut("q") == "c1"


def test_custom_symbols_of_the_plan_are_resolved_and_listed() -> None:
    view = build_symbol_view([FOCUS], [], _plan_with_custom("K"))
    assert view.symbol_for_shortcut("k") == "c1"
    assert [s.key for s in view.documentation_symbols if s.is_custom] == ["c1"]


def test_space_resolves_only_to_builtin_symbols() -> None:
    assert build_symbol_view([ABSENT], [], None).symbol_for_shortcut("space") == "Abwesend"
    assert build_symbol_view([FOCUS], [], None).symbol_for_shortcut("space") is None
