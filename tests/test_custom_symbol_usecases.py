"""Tests für die Verwaltungs-Usecases eigener Doku-Symbole."""

from __future__ import annotations

import pytest

from app.core.domain.custom_symbol_validation import InvalidGlyphError, InvalidMeaningError, InvalidShortcutError
from app.core.domain.models_v4 import CustomSymbolDefinition
from app.core.usecases.v4.custom_symbol_usecases import (
    add_custom_symbol,
    delete_custom_symbol,
    resolve_custom_symbol_shortcut,
    update_custom_symbol,
)
from app.core.usecases.v4.symbol_usecases import record_symbol
from tests.conftest import make_plan, make_student


class TestAddCustomSymbol:
    def test_adds_symbol_with_generated_id(self):
        plan = make_plan()

        next_plan, symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")

        assert symbol_id in next_plan.custom_symbols
        symbol = next_plan.custom_symbols[symbol_id]
        assert symbol.glyph == "☕"
        assert symbol.meaning == "Kaffee vergessen"
        assert symbol.shortcut == "K"
        assert symbol.id == symbol_id

    def test_original_plan_is_not_mutated(self):
        plan = make_plan()
        add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")
        assert plan.custom_symbols == {}

    def test_two_symbols_can_share_glyph_and_similar_meaning(self):
        """Keine Bedeutungs-/Glyph-Eindeutigkeitsprüfung mehr -- Identität läuft über die ID."""
        plan = make_plan()
        plan, _id1 = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")
        plan, id2 = add_custom_symbol(plan, "☕", "Kaffee vergessen", "L")
        assert id2 in plan.custom_symbols

    def test_invalid_glyph_raises(self):
        plan = make_plan()
        with pytest.raises(InvalidGlyphError):
            add_custom_symbol(plan, "ab", "Ungueltig", "K")

    def test_invalid_shortcut_raises(self):
        plan = make_plan()
        with pytest.raises(InvalidShortcutError):
            add_custom_symbol(plan, "☕", "Ungueltig", "Ctrl+K")

    def test_shortcut_collision_with_existing_custom_symbol_raises(self):
        plan = make_plan()
        plan, _id1 = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")
        with pytest.raises(InvalidShortcutError):
            add_custom_symbol(plan, "💻", "Laptop vergessen", "K")

    def test_empty_meaning_raises(self):
        plan = make_plan()
        with pytest.raises(InvalidMeaningError):
            add_custom_symbol(plan, "☕", "   ", "K")

    def test_reserved_letter_raises(self):
        """reserved_letters wird nur durchgereicht -- die eigentliche Sperrliste
        wird zentral von reserved_symbol_letters() gebildet (siehe deren Tests)."""
        plan = make_plan()
        with pytest.raises(InvalidShortcutError):
            add_custom_symbol(plan, "☕", "Ungueltig", "K", reserved_letters=frozenset({"K"}))

    def test_old_ctrl_shift_format_is_rejected_not_reinterpreted(self):
        plan = make_plan()
        with pytest.raises(InvalidShortcutError):
            add_custom_symbol(plan, "☕", "Ungueltig", "Ctrl+Shift+K")


class TestUpdateCustomSymbol:
    def test_changes_glyph_meaning_and_shortcut(self):
        plan = make_plan()
        plan, symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")

        next_plan = update_custom_symbol(plan, symbol_id, "🍪", "Keks vergessen", "L")

        symbol = next_plan.custom_symbols[symbol_id]
        assert symbol.id == symbol_id
        assert symbol.glyph == "🍪"
        assert symbol.meaning == "Keks vergessen"
        assert symbol.shortcut == "L"

    def test_keeping_the_same_shortcut_does_not_collide_with_itself(self):
        plan = make_plan()
        plan, symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")

        next_plan = update_custom_symbol(plan, symbol_id, "☕", "Kaffee vergessen (neu)", "K")

        assert next_plan.custom_symbols[symbol_id].shortcut == "K"

    def test_shortcut_collision_with_a_different_custom_symbol_still_raises(self):
        plan = make_plan()
        plan, _id1 = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")
        plan, id2 = add_custom_symbol(plan, "💻", "Laptop vergessen", "L")
        with pytest.raises(InvalidShortcutError):
            update_custom_symbol(plan, id2, "💻", "Laptop vergessen", "K")

    def test_unknown_symbol_id_returns_plan_unchanged(self):
        plan = make_plan()
        next_plan = update_custom_symbol(plan, "does-not-exist", "☕", "X", "K")
        assert next_plan.custom_symbols == {}

    def test_empty_meaning_raises(self):
        plan = make_plan()
        plan, symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")
        with pytest.raises(InvalidMeaningError):
            update_custom_symbol(plan, symbol_id, "☕", "   ", "K")

    def test_referencing_history_survives_a_meaning_change(self):
        """Beweis, dass die Referenz ueber die ID laeuft: eine Bedeutungsaenderung
        laesst einen bereits gesetzten SessionEntry nicht verwaisen."""
        student = make_student(x=0, y=0, first_name="Anna")
        plan = make_plan(students=[student])
        plan, symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")
        plan = record_symbol(plan, student.student_id, "2026-01-15", symbol_id, 1)

        plan = update_custom_symbol(plan, symbol_id, "☕", "Kaffeetasse vergessen", "K")

        session = plan.documentation.session_for_date("2026-01-15")
        assert session is not None
        entry = session.entry_for(student.student_id)
        assert entry is not None
        assert entry.symbols[symbol_id] == 1
        assert plan.custom_symbols[symbol_id].meaning == "Kaffeetasse vergessen"


class TestDeleteCustomSymbol:
    def test_removes_symbol_from_catalog(self):
        plan = make_plan()
        plan, symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")

        next_plan = delete_custom_symbol(plan, symbol_id)

        assert symbol_id not in next_plan.custom_symbols

    def test_does_not_remove_historical_session_data(self):
        student = make_student(x=0, y=0, first_name="Anna")
        plan = make_plan(students=[student])
        plan, symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")
        plan = record_symbol(plan, student.student_id, "2026-01-15", symbol_id, 2)

        next_plan = delete_custom_symbol(plan, symbol_id)

        assert symbol_id not in next_plan.custom_symbols
        session = next_plan.documentation.session_for_date("2026-01-15")
        assert session is not None
        entry = session.entry_for(student.student_id)
        assert entry is not None
        assert entry.symbols[symbol_id] == 2

    def test_unknown_symbol_id_is_a_no_op(self):
        plan = make_plan()
        next_plan = delete_custom_symbol(plan, "does-not-exist")
        assert next_plan.custom_symbols == {}


class TestResolveCustomSymbolShortcut:
    def test_finds_matching_symbol(self):
        plan = make_plan()
        plan, symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")

        found = resolve_custom_symbol_shortcut(plan, "K")

        assert found is not None
        assert found.id == symbol_id

    def test_letter_case_is_normalized(self):
        plan = make_plan()
        plan, _symbol_id = add_custom_symbol(plan, "☕", "Kaffee vergessen", "K")
        assert resolve_custom_symbol_shortcut(plan, "k") is not None

    def test_no_match_returns_none(self):
        plan = make_plan()
        assert resolve_custom_symbol_shortcut(plan, "K") is None

    def test_none_plan_returns_none(self):
        assert resolve_custom_symbol_shortcut(None, "K") is None

    def test_old_ctrl_shift_value_never_matches_a_keypress(self):
        """Ein historischer Ctrl+Shift-Wert (z. B. aus einem alten/kaputten
        Plan-Datensatz) kann strukturell nie mit einem neuen Tastendruck
        matchen, ohne dass beim Laden re-validiert werden muss."""
        plan = make_plan()
        plan.custom_symbols["legacy-id"] = CustomSymbolDefinition(
            id="legacy-id", glyph="☕", meaning="Alt", shortcut="Ctrl+Shift+K"
        )

        assert resolve_custom_symbol_shortcut(plan, "K") is None

    def test_plan_isolation_same_letter_different_symbols(self):
        """Zwei Plaene mit je einem eigenen Symbol auf demselben Buchstaben
        liefern unabhaengige Ergebnisse -- kein Rebind, keine Vermischung
        zwischen Plaenen noetig."""
        plan_a = make_plan(name="Plan A")
        plan_a, id_a = add_custom_symbol(plan_a, "☕", "Kaffee vergessen", "K")

        plan_b = make_plan(name="Plan B")
        plan_b, id_b = add_custom_symbol(plan_b, "💻", "Laptop vergessen", "K")

        found_in_a = resolve_custom_symbol_shortcut(plan_a, "K")
        found_in_b = resolve_custom_symbol_shortcut(plan_b, "K")

        assert found_in_a is not None and found_in_a.id == id_a
        assert found_in_b is not None and found_in_b.id == id_b
        assert found_in_a.meaning == "Kaffee vergessen"
        assert found_in_b.meaning == "Laptop vergessen"
