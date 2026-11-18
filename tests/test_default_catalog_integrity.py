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
