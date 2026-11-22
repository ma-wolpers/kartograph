"""Notizen an Schülern: die einzige Normalisierungsregel (SSOT).

Notizen (``DiagnosticProfile.notes``) sind freie Textzeilen zu einer Person,
z. B. Absprachen oder Nachteilsausgleiche ("Zeitzuschlag 25 %"). Gespeichert
wird eine Liste von Zeilen. Wie eine Eingabe zu dieser Liste wird, entscheidet
ausschließlich ``normalize_note_lines`` -- der Usecase beim Schreiben, der
Deserializer beim Laden und das Details-Panel beim Vergleich "Feld zeigt schon
den gespeicherten Stand" nutzen dieselbe Funktion, damit Vergleichswert und
gespeicherter Wert nie auseinanderlaufen.

``LEGACY_NOTES_KEY`` ist der frühere JSON-Schlüssel (Feld hieß
"Nachteilsausgleiche"); Pläne mit diesem Schlüssel werden weiter gelesen und
beim nächsten Speichern unter ``notes`` geschrieben.
"""

from __future__ import annotations

from collections.abc import Iterable

NOTES_LABEL = "Notizen"
LEGACY_NOTES_KEY = "accommodations"
_INLINE_SEPARATOR = " · "


def notes_inline(lines: Iterable[str]) -> str:
    """Notizzeilen einzeilig, z. B. für eine Tabellenzelle der Datenansicht.

    Args:
        lines: Gespeicherte Notizzeilen (``DiagnosticProfile.notes``).

    Returns:
        Die Zeilen mit " · " verbunden, z. B. ``"braucht Zeit · sitzt vorne"``.
    """
    return _INLINE_SEPARATOR.join(lines)


def normalize_note_lines(lines: Iterable[object]) -> list[str]:
    """Bringt Notizzeilen in die gespeicherte Form.

    Jede Zeile wird zu Text, außen getrimmt; leere Zeilen entfallen. Die
    Reihenfolge bleibt erhalten, Duplikate bleiben bestehen (eine Notiz darf
    zweimal vorkommen).

    Args:
        lines: Rohzeilen (Feldinhalt, JSON-Liste oder Intent-Wert).

    Returns:
        Die normalisierte Zeilenliste.
    """
    normalized: list[str] = []
    for line in lines:
        text = str(line).strip()
        if text:
            normalized.append(text)
    return normalized
