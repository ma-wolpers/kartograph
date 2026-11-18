"""Formale Regeln für die mitgelieferten Kataloge (``default_competences.json``).

Prüft, was sich maschinell prüfen lässt (``docs/SYMBOLE.md``): eindeutige,
stabile ASCII-IDs, nichtleere Namen/Gruppen, genau drei Stufentexte, Satzform
(klein, ohne Schlusspunkt) und keine doppelten Stufentexte. Inhaltliche Regeln
(Ressourcenorientierung, Signalwörter) prüft die Nutzerin im Review.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DEFAULT_COMPETENCES_PATH = Path(__file__).resolve().parents[1] / "app" / "infrastructure" / "default_competences.json"
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


def _competences() -> list[dict]:
    """Liest die Kompetenzliste direkt aus der Datendatei."""
    return json.loads(DEFAULT_COMPETENCES_PATH.read_text(encoding="utf-8"))["competences"]


def _level_texts() -> list[tuple[str, str, str]]:
    """``(id, Stufe, Text)`` für alle Stufentexte."""
    return [(item["id"], level, item["levels"][level]) for item in _competences() for level in ("one", "two", "three")]


def test_ids_are_unique_ascii_slugs() -> None:
    ids = [item["id"] for item in _competences()]
    assert len(ids) == len(set(ids))
    assert [i for i in ids if not _ID_PATTERN.match(i)] == []


def test_every_competence_has_name_group_and_three_levels() -> None:
    for item in _competences():
        assert item["name"].strip() and item["group"].strip(), item["id"]
        assert set(item["levels"]) == {"one", "two", "three"}, item["id"]


@pytest.mark.parametrize(("competence_id", "level", "text"), _level_texts())
def test_level_text_follows_sentence_form(competence_id: str, level: str, text: str) -> None:
    assert text == text.strip() and text, (competence_id, level)
    assert text[0].islower(), (competence_id, level)
    assert not text.endswith("."), (competence_id, level)


def test_levels_of_one_competence_differ() -> None:
    for item in _competences():
        assert len(set(item["levels"].values())) == 3, item["id"]


def test_names_are_unique_within_group() -> None:
    seen = [(item["group"], item["name"].lower()) for item in _competences()]
    assert len(seen) == len(set(seen))


DEFAULT_SYMBOLS_PATH = DEFAULT_COMPETENCES_PATH.with_name("default_symbols.json")
SEGOE_UI_SYMBOL = Path("C:/Windows/Fonts/seguisym.ttf")


def _symbols() -> list[dict]:
    """Liest die Symbolliste direkt aus der Datendatei."""
    return json.loads(DEFAULT_SYMBOLS_PATH.read_text(encoding="utf-8"))["symbols"]


def test_diagnostic_symbols_link_at_least_one_existing_competence() -> None:
    known = {item["id"] for item in _competences()}
    for item in _symbols():
        if item.get("role") == "documentation_only":
            assert "competences" not in item and set(item["legend"]) == {"one", "two", "three"}, item["key"]
        else:
            assert item["competences"] and set(item["competences"]) <= known, item["key"]


def test_symbol_keys_codepoints_and_shortcuts_are_unique() -> None:
    items = _symbols()
    for field in ("key", "codepoint"):
        values = [item[field] for item in items]
        assert len(values) == len(set(values)), field
    shortcuts = [item["shortcut"] for item in items if item.get("shortcut")]
    assert len(shortcuts) == len(set(shortcuts))
    assert all(s == s.lower() for s in shortcuts)


def test_every_default_glyph_is_in_segoe_ui_symbol() -> None:
    """Der PDF-Export registriert nur diese Symbolschrift (``docs/SYMBOLE.md``, Checkliste Punkt 2)."""
    ttfonts = pytest.importorskip("reportlab.pdfbase.ttfonts")
    if not SEGOE_UI_SYMBOL.exists():
        pytest.skip("Segoe UI Symbol nicht installiert")
    cmap = ttfonts.TTFontFile(str(SEGOE_UI_SYMBOL)).charToGlyph
    missing = [item["key"] for item in _symbols() if int(item["codepoint"], 16) not in cmap]
    assert missing == []
