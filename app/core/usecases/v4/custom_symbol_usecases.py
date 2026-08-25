"""Usecases für eigene, pro-Plan definierte Doku-Symbole (CRUD + Shortcut-Lookup).

Der eigentliche Toggle-Mechanismus (Symbol an einem Tag setzen/löschen) wird
NICHT hier neu gebaut, sondern unverändert von
``app/core/usecases/v4/symbol_usecases.py::record_symbol()`` übernommen —
die ist bereits vollständig generisch über beliebige ``symbol: str``-Schlüssel
und kennt weder eingebaute noch eigene Symbole. Dieses Modul kümmert sich
ausschließlich um die Verwaltung des Katalogs selbst.
"""

from __future__ import annotations

import uuid
from copy import deepcopy

from app.core.domain.custom_symbol_validation import (
    validate_custom_symbol_glyph,
    validate_custom_symbol_shortcut,
)
from app.core.domain.models_v4 import CustomSymbolDefinition, SeatingPlan


def add_custom_symbol(plan: SeatingPlan, glyph: str, meaning: str, shortcut: str) -> tuple[SeatingPlan, str]:
    """Legt ein neues eigenes Doku-Symbol an.

    Validiert Glyph und Tastenkürzel hart (wirft bei Verstoß, s. Modul-
    Docstring der Validatoren) — anders als z. B. ``add_grade_column``, das
    eine ungültige Kategorie still ignoriert: der Nutzer verlangt explizit
    sofortiges Anschlagen bei ungültiger Eingabe, nicht stilles Verwerfen.

    Args:
        plan: Ausgangsplan.
        glyph: Rohes Glyph-Feld (wird über ``validate_custom_symbol_glyph``
            geprüft/getrimmt).
        meaning: Bedeutungstext (Freitext, keine Eindeutigkeitsprüfung —
            Identität läuft über die generierte ``id``, nicht über den Text).
        shortcut: Rohes Tastenkürzel-Feld (wird über
            ``validate_custom_symbol_shortcut`` geprüft/normalisiert; geprüft
            gegen die Shortcuts aller bereits vorhandenen eigenen Symbole
            dieses Plans).

    Returns:
        Tupel aus (neuer Plan, ``id`` des neu angelegten Symbols) — analog
        zur Signatur von ``add_grade_column()``.

    Raises:
        InvalidGlyphError: Bei ungültigem Glyph.
        InvalidShortcutError: Bei ungültigem oder bereits belegtem Shortcut.
    """
    clean_glyph = validate_custom_symbol_glyph(glyph)
    other_shortcuts = [cs.shortcut for cs in plan.custom_symbols.values()]
    clean_shortcut = validate_custom_symbol_shortcut(shortcut, other_shortcuts)
    clean_meaning = str(meaning or "").strip()

    next_plan = deepcopy(plan)
    symbol_id = uuid.uuid4().hex[:8]
    next_plan.custom_symbols[symbol_id] = CustomSymbolDefinition(
        id=symbol_id, glyph=clean_glyph, meaning=clean_meaning, shortcut=clean_shortcut
    )
    return next_plan, symbol_id


def update_custom_symbol(plan: SeatingPlan, symbol_id: str, glyph: str, meaning: str, shortcut: str) -> SeatingPlan:
    """Ändert Glyph, Bedeutung und/oder Tastenkürzel eines bestehenden eigenen Symbols.

    Alle drei Felder sind änderbar — die ``id`` (nicht der Bedeutungstext)
    ist die stabile Referenz für bereits erfasste Dokumentationsdaten, ein
    Bearbeiten kann sie daher nicht verwaisen lassen.

    Args:
        plan: Ausgangsplan.
        symbol_id: ID des zu bearbeitenden Symbols. Unbekannte ID → Plan wird
            unverändert zurückgegeben (still, analog ``set_palette_meaning``
            bei unbekanntem ``color_key``).
        glyph: Neues rohes Glyph-Feld.
        meaning: Neuer Bedeutungstext.
        shortcut: Neues rohes Tastenkürzel-Feld. Der aktuelle Shortcut dieses
            Symbols wird von der Kollisionsprüfung ausgenommen (sonst würde
            ein unverändert übernommener Shortcut fälschlich als Kollision
            mit sich selbst gelten).

    Returns:
        Neuer Plan mit dem aktualisierten Symbol.

    Raises:
        InvalidGlyphError: Bei ungültigem Glyph.
        InvalidShortcutError: Bei ungültigem oder anderweitig bereits belegtem Shortcut.
    """
    if symbol_id not in plan.custom_symbols:
        return deepcopy(plan)

    clean_glyph = validate_custom_symbol_glyph(glyph)
    other_shortcuts = [cs.shortcut for sid, cs in plan.custom_symbols.items() if sid != symbol_id]
    clean_shortcut = validate_custom_symbol_shortcut(shortcut, other_shortcuts)
    clean_meaning = str(meaning or "").strip()

    next_plan = deepcopy(plan)
    next_plan.custom_symbols[symbol_id] = CustomSymbolDefinition(
        id=symbol_id, glyph=clean_glyph, meaning=clean_meaning, shortcut=clean_shortcut
    )
    return next_plan


def delete_custom_symbol(plan: SeatingPlan, symbol_id: str) -> SeatingPlan:
    """Entfernt ein eigenes Symbol aus dem aktuellen Katalog.

    Rührt ``SessionEntry.symbols`` bewusst NICHT an: historische
    Dokumentationsdaten, die dieses Symbol referenzieren, bleiben vollständig
    erhalten, auch wenn das Symbol danach nicht mehr im Katalog steht. Die
    Anzeige eines solchen "verwaisten" historischen Eintrags läuft über
    ``effective_symbol.py::resolve_symbol_display()``s Fallback.

    Args:
        plan: Ausgangsplan.
        symbol_id: ID des zu löschenden Symbols. Unbekannte ID → Plan wird
            unverändert zurückgegeben.

    Returns:
        Neuer Plan ohne den Katalogeintrag.
    """
    next_plan = deepcopy(plan)
    next_plan.custom_symbols.pop(symbol_id, None)
    return next_plan


def resolve_custom_symbol_shortcut(plan: SeatingPlan | None, letter: str) -> CustomSymbolDefinition | None:
    """Sucht das eigene Symbol von *plan*, dessen Tastenkürzel ``"Ctrl+Shift+<letter>"`` entspricht.

    Reine Lookup-Funktion ohne Seiteneffekt. Zentral für die GUI-
    Tastaturbindung (ein einziges, beim Start einmalig gebundenes
    ``Ctrl+Shift+<Buchstabe>``-Tastenraum-Binding pro Buchstabe löst pro
    Tastendruck über diese Funktion live auf, welches Symbol im *aktuell*
    offenen Plan gemeint ist — kein Rebind bei Planwechsel nötig) UND direkt
    unit-testbar für den Plan-Isolations-Nachweis: zwei verschiedene Pläne
    mit je einem eigenen Symbol auf demselben Buchstaben liefern
    unabhängige Ergebnisse.

    Args:
        plan: Der zu durchsuchende Plan, oder ``None`` (kein offener Plan).
        letter: Ein einzelner Großbuchstabe (z. B. ``"K"``); Groß-/
            Kleinschreibung wird intern normalisiert.

    Returns:
        Das gefundene ``CustomSymbolDefinition``, oder ``None`` wenn kein
        Plan offen ist oder kein eigenes Symbol diesen Shortcut trägt.
    """
    if plan is None:
        return None
    target = f"Ctrl+Shift+{letter.strip().upper()}"
    for custom in plan.custom_symbols.values():
        if custom.shortcut == target:
            return custom
    return None
