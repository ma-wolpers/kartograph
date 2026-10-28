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


DEFAULT_SYMBOLS_PATH = Path(__file__).with_name("default_symbols.json")
"""Einzige Quelle der eingebauten Symbole (reine Datendatei, versioniert).

``config/symbols.json`` ist nur die lokale Arbeitskopie: daraus erzeugt, bei
Defekt daraus wiederhergestellt und beim Start um neu eingebaute Symbole
ergänzt (s. :func:`_merge_new_builtins`).
"""

_KNOWN_BUILTINS_KEY = "known_builtin_codepoints"


def _load_default_payload() -> dict:
    """Liest die mitgelieferten Standardsymbole aus :data:`DEFAULT_SYMBOLS_PATH`."""
    return json.loads(DEFAULT_SYMBOLS_PATH.read_text(encoding="utf-8"))


def _write_default_payload(path: Path) -> dict:
    """Schreibt die Standardsymbole nach *path* (atomar) und gibt sie zurück.

    Die Liste der bekannten eingebauten Codepoints wird mitgeschrieben, damit
    spätere Ergänzungen nur wirklich neue Symbole betreffen.

    Args:
        path: Zielpfad der ``symbols.json``.
    """
    payload = _load_default_payload()
    payload[_KNOWN_BUILTINS_KEY] = sorted(_codepoint_keys(payload["symbols"]))
    atomic_write_json(path, payload)
    return payload


def _codepoint_key(raw_value: object) -> str | None:
    """Normalisiert einen Codepoint-Wert auf Hex in Großbuchstaben (``"u+2713"`` → ``"2713"``).

    Identität eines eingebauten Symbols ist sein Codepoint, nicht sein Text.

    Args:
        raw_value: Roher Codepoint-Wert aus einer ``symbols.json``.
    """
    glyph = _parse_codepoint(raw_value)
    return None if glyph is None else f"{ord(glyph):04X}"


def _codepoint_keys(symbols: list) -> set[str]:
    """Gibt die normalisierten Codepoints aller gültigen Einträge in *symbols* zurück.

    Args:
        symbols: Rohliste aus einer ``symbols.json``.
    """
    keys = {_codepoint_key(item.get("codepoint")) for item in symbols if isinstance(item, dict)}
    return keys - {None}


def _merge_new_builtins(payload: dict, path: Path) -> str | None:
    """Ergänzt in *payload* eingebaute Symbole, die die Arbeitskopie noch nie gesehen hat.

    Robust gegen drei Fälle: (1) eigene Änderungen an vorhandenen Einträgen
    werden nie überschrieben; (2) ein bewusst gelöschtes eingebautes Symbol
    kommt nicht zurück, weil ``known_builtin_codepoints`` festhält, welche
    Standards schon angeboten wurden (fehlt die Liste, gelten die vorhandenen
    Einträge als bekannt); (3) ist das Kürzel eines neuen Symbols schon
    vergeben, wird es ohne Kürzel ergänzt und gemeldet. Bei Änderungen wird
    *path* atomar neu geschrieben.

    Args:
        payload: Geladener Inhalt der Arbeitskopie (wird verändert).
        path: Pfad der Arbeitskopie.

    Returns:
        Hinweistext bei Kürzelkonflikten, sonst ``None``.
    """
    symbols = payload["symbols"]
    present = _codepoint_keys(symbols)
    known_raw = payload.get(_KNOWN_BUILTINS_KEY)
    known = {c for c in known_raw if isinstance(c, str)} if isinstance(known_raw, list) else set(present)
    used_shortcuts = {_parse_shortcut(item.get("shortcut")) for item in symbols if isinstance(item, dict)} - {None}
    defaults = _load_default_payload()["symbols"]
    conflicts: list[str] = []
    changed = False
    for item in defaults:
        key = _codepoint_key(item.get("codepoint"))
        if key is None or key in known or key in present:
            continue
        added = dict(item)
        shortcut = _parse_shortcut(added.get("shortcut"))
        if shortcut in used_shortcuts:
            conflicts.append(f"{added.get('meaning')} ({shortcut})")
            added["shortcut"] = None
        elif shortcut is not None:
            used_shortcuts.add(shortcut)
        symbols.append(added)
        changed = True
    all_builtins = sorted(known | _codepoint_keys(defaults))
    if changed or payload.get(_KNOWN_BUILTINS_KEY) != all_builtins:
        payload[_KNOWN_BUILTINS_KEY] = all_builtins
        atomic_write_json(path, payload)
    if not conflicts:
        return None
    return "Neue Symbole ohne Kürzel ergänzt (Kürzel bereits vergeben): " + ", ".join(conflicts)


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

    *path* ist die lokale Arbeitskopie. Fehlt sie, ist ihr JSON ungültig, fehlt
    das ``symbols``-Array oder enthält es nach dem Parsen keinen einzigen
    vollständigen Eintrag (Pflichtfelder: ``meaning``, ein gültiger Codepoint,
    alle drei Legendenstufen), wird sie jeweils aus
    :data:`DEFAULT_SYMBOLS_PATH` neu geschrieben — die Anwendung soll mit
    einer kaputten Konfigurationsdatei nie ganz ohne Symbole starten. Neu
    eingebaute Symbole werden ergänzt, ohne eigene Änderungen anzutasten
    (:func:`_merge_new_builtins`).

    Args:
        path: Pfad zur ``symbols.json``.

    Returns:
        Tupel aus (geladene Symbol-Definitionen, optionale Warnmeldung für
        den Fall, dass auf das Standardset zurückgefallen wurde).
    """
    if path.resolve() == DEFAULT_SYMBOLS_PATH.resolve():
        # Invariante: die versionierte Standarddatei wird nie als Arbeitskopie beschrieben.
        raise ValueError(f"{path} ist die Standarddatei, nicht die Arbeitskopie")
    if not path.exists():
        _write_default_payload(path)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = _write_default_payload(path)
        warning = f"Symbol-Konfiguration ist ungueltig; Standardwerte wurden nach {path} geschrieben."
    else:
        warning = None

    if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
        payload = _write_default_payload(path)
        warning = f"Symbol-Konfiguration hat kein gueltiges 'symbols'-Array; Standardwerte wurden nach {path} geschrieben."
    warning = _merge_new_builtins(payload, path) or warning
    symbols_raw = payload["symbols"]

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
