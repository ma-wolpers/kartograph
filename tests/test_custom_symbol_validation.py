"""Tests für die Validierung eigener Doku-Symbole (Tastaturkürzel + Glyph).

Reine Domain-Logik ohne GUI-/Tk-Abhängigkeit.
"""

from __future__ import annotations

import pytest

from app.core.domain.custom_symbol_validation import (
    InvalidGlyphError,
    InvalidMeaningError,
    InvalidShortcutError,
    validate_custom_symbol_glyph,
    validate_custom_symbol_meaning,
    validate_custom_symbol_shortcut,
)


class TestValidateCustomSymbolShortcut:
    @pytest.mark.parametrize(
        "raw",
        ["ctrl+shift+t", "CTRL+SHIFT+T", "Ctrl+Shift+T", " Ctrl+Shift+T ", "Ctrl + Shift + T"],
    )
    def test_valid_forms_normalize_to_canonical(self, raw):
        assert validate_custom_symbol_shortcut(raw) == "Ctrl+Shift+T"

    @pytest.mark.parametrize(
        "raw",
        [
            "t",
            "Ctrl+T",
            "Ctrl+Alt+T",
            "Ctrl+Shift+12",
            "Ctrl+Shift+!",
            "Ctrl+Shift+Tt",
            "",
            "   ",
            "Shift+T",
        ],
    )
    def test_invalid_forms_are_rejected(self, raw):
        with pytest.raises(InvalidShortcutError):
            validate_custom_symbol_shortcut(raw)

    @pytest.mark.parametrize("letter", ["D", "R", "O", "S", "U", "N"])
    def test_reserved_system_letters_are_rejected(self, letter):
        with pytest.raises(InvalidShortcutError):
            validate_custom_symbol_shortcut(f"Ctrl+Shift+{letter}")

    def test_free_letter_is_accepted(self):
        assert validate_custom_symbol_shortcut("Ctrl+Shift+K") == "Ctrl+Shift+K"

    def test_collision_with_other_shortcut_is_rejected(self):
        with pytest.raises(InvalidShortcutError):
            validate_custom_symbol_shortcut("Ctrl+Shift+K", other_shortcuts=["Ctrl+Shift+K"])

    def test_no_collision_when_other_shortcuts_differ(self):
        assert validate_custom_symbol_shortcut("Ctrl+Shift+K", other_shortcuts=["Ctrl+Shift+L"]) == "Ctrl+Shift+K"


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
