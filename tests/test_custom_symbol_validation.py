"""Tests für die Validierung eigener Doku-Symbole (Tastaturkürzel + Glyph).

Reine Domain-Logik ohne GUI-/Tk-Abhängigkeit.
"""

from __future__ import annotations

import pytest

from app.core.domain.custom_symbol_validation import (
    RESERVED_SYMBOL_LETTERS,
    InvalidGlyphError,
    InvalidMeaningError,
    InvalidShortcutError,
    reserved_symbol_letters,
    validate_custom_symbol_glyph,
    validate_custom_symbol_meaning,
    validate_custom_symbol_shortcut,
)


class _Definition:
    """Minimales Double für ``_HasShortcut`` -- nur ``.shortcut`` wird gebraucht."""

    def __init__(self, shortcut: str | None) -> None:
        self.shortcut = shortcut


class TestValidateCustomSymbolShortcut:
    @pytest.mark.parametrize("raw", ["l", "L", " L ", "l "])
    def test_valid_forms_normalize_to_canonical_uppercase_letter(self, raw):
        assert validate_custom_symbol_shortcut(raw) == "L"

    @pytest.mark.parametrize(
        "raw",
        [
            "Ctrl+Shift+T",
            "Ctrl+T",
            "12",
            "!",
            "LL",
            "",
            "   ",
        ],
    )
    def test_invalid_forms_are_rejected(self, raw):
        with pytest.raises(InvalidShortcutError):
            validate_custom_symbol_shortcut(raw)

    def test_old_ctrl_shift_format_is_rejected_not_reinterpreted(self):
        """Ein Wert im frueheren Ctrl+Shift+<Buchstabe>-Format darf nach der
        Umstellung nicht stillschweigend als neuer Einzelbuchstaben-Shortcut
        durchgehen."""
        with pytest.raises(InvalidShortcutError):
            validate_custom_symbol_shortcut("Ctrl+Shift+L")

    def test_reserved_letter_is_rejected(self):
        with pytest.raises(InvalidShortcutError):
            validate_custom_symbol_shortcut("K", reserved_letters=frozenset({"K"}))

    def test_free_letter_is_accepted(self):
        assert validate_custom_symbol_shortcut("K", reserved_letters=frozenset({"O", "S", "D"})) == "K"

    def test_collision_with_other_shortcut_is_rejected(self):
        with pytest.raises(InvalidShortcutError):
            validate_custom_symbol_shortcut("K", other_shortcuts=["K"])

    def test_no_collision_when_other_shortcuts_differ(self):
        assert validate_custom_symbol_shortcut("K", other_shortcuts=["L"]) == "K"


class TestReservedSymbolLetters:
    def test_fixed_system_letters_always_included(self):
        assert RESERVED_SYMBOL_LETTERS <= reserved_symbol_letters([])

    def test_builtin_symbol_shortcuts_are_included(self):
        letters = reserved_symbol_letters([_Definition("b"), _Definition("k")])
        assert "B" in letters
        assert "K" in letters

    def test_definitions_without_shortcut_are_ignored(self):
        letters = reserved_symbol_letters([_Definition(None), _Definition("")])
        assert letters == RESERVED_SYMBOL_LETTERS

    def test_letter_not_in_catalog_or_fixed_set_stays_free(self):
        letters = reserved_symbol_letters([_Definition("b")])
        assert "L" not in letters

    def test_multi_character_technical_shortcut_like_space_is_excluded(self):
        """Ein technischer Sondertasten-Shortcut wie "space" (main_window_constants.SPACE_SHORTCUT)
        ist kein Buchstabe und darf nicht in der Buchstaben-Sperrliste landen."""
        letters = reserved_symbol_letters([_Definition("space"), _Definition("b")])
        assert "SPACE" not in letters
        assert letters == RESERVED_SYMBOL_LETTERS | {"B"}


class TestValidateCustomSymbolGlyph:
    def test_single_letter_is_valid(self):
        assert validate_custom_symbol_glyph("A") == "A"

    def test_combining_accent_is_valid(self):
        text = "ä"  # a + combining diaeresis
        assert validate_custom_symbol_glyph(text) == text

    def test_simple_emoji_is_valid(self):
        text = "\U0001F44D"  # thumbs up
        assert validate_custom_symbol_glyph(text) == text

    def test_emoji_with_variation_selector_is_valid(self):
        text = "❤️"  # heart + variation selector
        assert validate_custom_symbol_glyph(text) == text

    def test_skin_tone_modified_emoji_is_valid(self):
        text = "\U0001F44D\U0001F3FD"  # thumbs up + skin tone modifier
        assert validate_custom_symbol_glyph(text) == text

    def test_zwj_family_emoji_sequence_is_valid(self):
        zwj = chr(0x200D)
        text = zwj.join(["\U0001F468", "\U0001F469", "\U0001F467", "\U0001F466"])
        assert validate_custom_symbol_glyph(text) == text

    def test_flag_pair_is_valid(self):
        text = "\U0001F1E9\U0001F1EA"  # regional indicators D + E -> German flag
        assert validate_custom_symbol_glyph(text) == text

    def test_surrounding_whitespace_is_trimmed(self):
        assert validate_custom_symbol_glyph("  A  ") == "A"

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_empty_input_is_rejected(self, raw):
        with pytest.raises(InvalidGlyphError):
            validate_custom_symbol_glyph(raw)

    def test_multiple_independent_letters_are_rejected(self):
        with pytest.raises(InvalidGlyphError):
            validate_custom_symbol_glyph("ab")

    def test_two_independent_emoji_are_rejected(self):
        with pytest.raises(InvalidGlyphError):
            validate_custom_symbol_glyph("\U0001F44D\U0001F44E")

    def test_dangling_zwj_is_rejected(self):
        with pytest.raises(InvalidGlyphError):
            validate_custom_symbol_glyph("A" + chr(0x200D))

    def test_single_regional_indicator_alone_is_rejected(self):
        with pytest.raises(InvalidGlyphError):
            validate_custom_symbol_glyph("\U0001F1E9")

    def test_control_character_is_rejected(self):
        with pytest.raises(InvalidGlyphError):
            validate_custom_symbol_glyph("A\x01")


class TestValidateCustomSymbolMeaning:
    def test_non_empty_meaning_is_trimmed(self):
        assert validate_custom_symbol_meaning("  Kaffee vergessen  ") == "Kaffee vergessen"

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_empty_meaning_is_rejected(self, raw):
        with pytest.raises(InvalidMeaningError):
            validate_custom_symbol_meaning(raw)

    def test_duplicate_meaning_across_symbols_is_not_rejected(self):
        """Keine Eindeutigkeitspruefung -- die Identitaet laeuft ueber die ID,
        nicht den Bedeutungstext (siehe CustomSymbolDefinition-Docstring)."""
        assert validate_custom_symbol_meaning("Kaffee vergessen") == "Kaffee vergessen"
