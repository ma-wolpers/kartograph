from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.domain.custom_symbol_validation import SPACE_SHORTCUT
from bw_libs.app_paths import atomic_write_json


SymbolRole = Literal["diagnostic", "documentation_only"]


@dataclass(frozen=True)
class SymbolDefinition:
    """Ein konfiguriertes Symbol aus ``config/symbols.json``: Glyph, Shortcut, Legenden-Stufentexte.

    ``role`` unterscheidet frei vergebbare diagnostische Symbole
    ("diagnostic") von Symbolen, die nur in der Dokumentation, nicht aber im
    Diagnoseprofil eines Schülers gesetzt werden können ("documentation_only",
    z. B. "Abwesend").
    """

    meaning: str
    glyph: str
    shortcut: str | None
    legend_one: str
    legend_two: str
    legend_three: str
    role: SymbolRole = "diagnostic"

    def legend_for_count(self, count: int) -> str:
        """Gibt den Legendentext für die Stärke *count* zurück (gestuft: 1, 2, 3+).

        Args:
            count: Symbolstärke, für die der passende Legendentext gesucht wird.
        """
        if count >= 3:
            return self.legend_three
        if count == 2:
            return self.legend_two
        return self.legend_one


_DEFAULT_SYMBOLS_PAYLOAD = {
    "symbols": [
        {
            "codepoint": "1F4BB",
            "meaning": "Laptop",
            "shortcut": "l",
            "legend": {
                "three": "arbeitet durchgaengig digital",
                "two": "arbeitet phasenweise digital",
                "one": "braucht digitales Material",
            },
        },
        {
            "codepoint": "1F4F1",
            "meaning": "Tablet",
            "shortcut": "t",
            "legend": {
                "three": "arbeitet sicher am Tablet",
                "two": "arbeitet meist sicher am Tablet",
                "one": "braucht Unterstuetzung am Tablet",
            },
        },
        {
            "codepoint": "2757",
            "meaning": "Beteiligung",
            "shortcut": "b",
            "legend": {
                "three": "meldet sich sehr haeufig",
                "two": "meldet sich regelmaessig",
                "one": "meldet sich gelegentlich",
            },
        },
        {
            "codepoint": "0058",
            "meaning": "Nicht abgegeben / verweigert",
            "shortcut": "x",
            "role": "documentation_only",
            "legend": {
                "three": "wiederholt nicht abgegeben oder Arbeitsverweigerung",
                "two": "mehrfach nicht abgegeben oder verweigert",
                "one": "einmalig nicht abgegeben oder verweigert",
            },
        },
        {
            "codepoint": "2205",
            "meaning": "Abwesend",
            "shortcut": "space",
            "role": "documentation_only",
            "legend": {
                "three": "an mehreren Terminen abwesend",
                "two": "wiederholt abwesend",
                "one": "am Termin abwesend",
            },
        },
    ]
}


def _write_default_payload(path: Path) -> None:
    """Schreibt das eingebaute Standard-Symbolset nach *path* (atomar).

    Args:
        path: Zielpfad der ``symbols.json``.
    """
    atomic_write_json(path, _DEFAULT_SYMBOLS_PAYLOAD)


def _parse_codepoint(raw_value: object) -> str | None:
    """Wandelt einen Codepoint-String (z. B. "1F4BB" oder "U+1F4BB") in das tatsächliche Unicode-Zeichen um.

    Gibt ``None`` zurück, wenn *raw_value* leer oder kein gültiger Hex-Codepoint ist.

    Args:
        raw_value: Roher Codepoint-Wert aus der Konfigurationsdatei.
    """
    text = str(raw_value or "").strip().upper()
    if text.startswith("U+"):
        text = text[2:]
    if not text:
        return None
    try:
        return chr(int(text, 16))
    except (TypeError, ValueError):
        return None


def _parse_shortcut(raw_value: object) -> str | None:
    """Validiert *raw_value* als Ein-Zeichen-Tastaturkürzel oder den Leertaste-Sentinel.

    Erlaubt genau zwei Formen: ein einzelnes Zeichen (normaler Buchstaben-
    Shortcut) oder den technischen Mehrzeichen-Sentinel ``SPACE_SHORTCUT``
    (``"space"``, s. ``custom_symbol_validation.py``) für Symbole, die über
    die Leertaste getoggelt werden. Alles andere (leer, mehrstellig und kein
    bekannter Sentinel) ergibt ``None``.

    Args:
        raw_value: Roher Shortcut-Wert aus der Konfigurationsdatei.
    """
    text = str(raw_value or "").strip().lower()
    if not text:
        return None
    if text == SPACE_SHORTCUT:
        return text
    if len(text) != 1:
        return None
    return text


def _parse_role(raw_value: object) -> SymbolRole:
    """Normalisiert *raw_value* auf eine gültige ``SymbolRole``; alles außer "documentation_only" wird "diagnostic".

    Args:
        raw_value: Roher Rollen-Wert aus der Konfigurationsdatei.
    """
    text = str(raw_value or "").strip().lower()
    if text == "documentation_only":
        return "documentation_only"
    return "diagnostic"


def load_symbol_definitions(path: Path) -> tuple[list[SymbolDefinition], str | None]:
    """Lädt die Symbol-Konfiguration aus *path*, repariert sie defensiv bei Problemen.

    Fehlt die Datei, ist ihr JSON ungültig, fehlt das ``symbols``-Array oder
    enthält es nach dem Parsen keinen einzigen vollständigen Eintrag (Pflicht-
    felder: ``meaning``, ein gültiger Codepoint, alle drei Legendenstufen),
    wird jeweils das eingebaute Standardset nach *path* zurückgeschrieben und
    von dort neu geladen — die Anwendung soll mit einer kaputten
    Konfigurationsdatei nie ganz ohne Symbole starten.

    Args:
        path: Pfad zur ``symbols.json``.

    Returns:
        Tupel aus (geladene Symbol-Definitionen, optionale Warnmeldung für
        den Fall, dass auf das Standardset zurückgefallen wurde).
    """
    if not path.exists():
        _write_default_payload(path)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _write_default_payload(path)
        payload = _DEFAULT_SYMBOLS_PAYLOAD
        warning = f"Symbol-Konfiguration ist ungueltig; Standardwerte wurden nach {path} geschrieben."
    else:
        warning = None

    symbols_raw = payload.get("symbols") if isinstance(payload, dict) else None
    if not isinstance(symbols_raw, list):
        _write_default_payload(path)
        symbols_raw = _DEFAULT_SYMBOLS_PAYLOAD["symbols"]
        warning = f"Symbol-Konfiguration hat kein gueltiges 'symbols'-Array; Standardwerte wurden nach {path} geschrieben."

    definitions: list[SymbolDefinition] = []
    for item in symbols_raw:
        if not isinstance(item, dict):
            continue

        meaning = str(item.get("meaning") or "").strip()
        glyph = _parse_codepoint(item.get("codepoint"))
        shortcut = _parse_shortcut(item.get("shortcut"))
        role = _parse_role(item.get("role"))
        legend = item.get("legend")
        if not meaning or glyph is None or not isinstance(legend, dict):
            continue

        one = str(legend.get("one") or "").strip()
        two = str(legend.get("two") or "").strip()
        three = str(legend.get("three") or "").strip()
        if not one or not two or not three:
            continue

        definitions.append(
            SymbolDefinition(
                meaning=meaning,
                glyph=glyph,
                shortcut=shortcut,
                role=role,
                legend_one=one,
                legend_two=two,
                legend_three=three,
            )
        )

    if not definitions:
        _write_default_payload(path)
        fallback_defs, _ = load_symbol_definitions(path)
        return fallback_defs, f"Keine gueltigen Symbole gefunden; Standardwerte wurden nach {path} geschrieben."

    return definitions, warning
