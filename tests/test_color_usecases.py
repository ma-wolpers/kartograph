"""Tests für v4 color_usecases (Farbpunkt-Bedeutungen in der Palette)."""

from app.core.domain.models_v4 import PaletteEntry
from app.core.usecases.v4.color_usecases import palette_meaning, set_palette_meaning
from tests.conftest import make_plan


class TestSetPaletteMeaning:
    def test_creates_missing_entry(self):
        # Regression: ohne Palette-Eintrag ging die abgefragte Bedeutung verloren.
        plan = make_plan()
        result = set_palette_meaning(plan, "gelb", "  Förderbedarf  ", label="Gelb", hex_color="#f4d35e")
        assert result.color_palette["gelb"] == PaletteEntry(label="Gelb", hex="#f4d35e", meaning="Förderbedarf")

    def test_updates_existing_entry_keeps_label_and_hex(self):
        plan = make_plan()
        plan.color_palette["gelb"] = PaletteEntry(label="Gelb", hex="#f4d35e", meaning="Alt")
        result = set_palette_meaning(plan, "gelb", "Neu", label="Anders", hex_color="#000000")
        assert result.color_palette["gelb"] == PaletteEntry(label="Gelb", hex="#f4d35e", meaning="Neu")

    def test_does_not_mutate_input(self):
        plan = make_plan()
        set_palette_meaning(plan, "gelb", "Förderbedarf", label="Gelb", hex_color="#f4d35e")
        assert plan.color_palette == {}


class TestPaletteMeaning:
    def test_missing_entry_is_empty(self):
        assert palette_meaning(make_plan(), "gelb") == ""

    def test_whitespace_only_is_empty(self):
        plan = make_plan()
        plan.color_palette["gelb"] = PaletteEntry(label="Gelb", hex="#f4d35e", meaning="   ")
        assert palette_meaning(plan, "gelb") == ""

    def test_returns_trimmed_meaning(self):
        plan = make_plan()
        plan.color_palette["gelb"] = PaletteEntry(label="Gelb", hex="#f4d35e", meaning=" Förderbedarf ")
        assert palette_meaning(plan, "gelb") == "Förderbedarf"
