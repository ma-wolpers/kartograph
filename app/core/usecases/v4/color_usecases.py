"""Usecases für Farbmarkierungen (Color-Tags) an Schülern.

Color-Tags sind kurze Schlüssel wie ``"gelb"`` aus der ``color_palette`` des Plans.
Das Palette-Dict wird bereinigt, wenn eine Farbe von keinem Schüler mehr getragen wird.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import PaletteEntry, SeatingPlan
from app.core.domain.student_id import StudentId


def palette_meaning(plan: SeatingPlan, color_key: str) -> str:
    """Gibt die hinterlegte pädagogische Bedeutung von *color_key* zurück.

    Einzige Stelle, die entscheidet, ob eine Farbe "eine Bedeutung hat":
    fehlender Palette-Eintrag und leerer/nur aus Leerraum bestehender Text
    gelten gleichermaßen als "keine Bedeutung".

    Args:
        plan: Plan, aus dem gelesen wird.
        color_key: Farbschlüssel, z. B. ``"gelb"``.

    Returns:
        Getrimmter Bedeutungstext oder ``""``, wenn keiner hinterlegt ist.
    """
    entry = plan.color_palette.get(color_key)
    return entry.meaning.strip() if entry else ""


def used_color_tags(plan: SeatingPlan) -> set[str]:
    """Gibt alle Farbschlüssel zurück, die mindestens ein Schüler trägt.

    Einzige Definition von "im Plan vergebene Farben": genutzt zum
    Bereinigen der Palette (``cleanup_unused_palette_entries``) und für die
    Farbauswahl im Sitzplan-Vorschau-Dialog (nur vergebene Farben wählbar).

    Args:
        plan: Plan, aus dem gelesen wird.

    Returns:
        Menge der getragenen Farbschlüssel (unsortiert; für eine
        Palettenreihenfolge ``color_order.order_color_keys`` verwenden).
    """
    return {tag for s in plan.classroom.students for tag in s.diagnostic.color_tags}


def set_palette_meaning(
    plan: SeatingPlan, color_key: str, meaning: str, *, label: str, hex_color: str
) -> SeatingPlan:
    """Weist *color_key* eine pädagogische Bedeutung zu oder entfernt sie.

    Fehlt der Palette-Eintrag noch (der Normalfall beim ersten Setzen einer
    Farbe in einem Plan), wird er mit *label*/*hex_color* angelegt. Früher
    kehrte die Funktion in diesem Fall still zurück -- die abgefragte
    Bedeutung ging verloren und die Farbpunkt-Legende blieb leer.
    Leeres *meaning* entfernt nur den Bedeutungstext; der Palette-Eintrag bleibt.

    Args:
        plan: Ausgangsplan.
        color_key: Farbschlüssel, z. B. ``"gelb"``.
        meaning: Textuelle Bedeutung; leer = löschen.
        label: Anzeigename der Farbe, falls der Eintrag neu angelegt wird.
        hex_color: Hex-Farbwert, falls der Eintrag neu angelegt wird.

    Returns:
        Neuer Plan mit dem aktualisierten Bedeutungstext.
    """
    next_plan = deepcopy(plan)
    entry = next_plan.color_palette.get(color_key)
    if entry is None:
        entry = PaletteEntry(label=label, hex=hex_color)
        next_plan.color_palette[color_key] = entry
    entry.meaning = meaning.strip()
    return next_plan


def toggle_color_tag(
    plan: SeatingPlan, student_id: StudentId, color_key: str
) -> SeatingPlan:
    """Schaltet *color_key* beim Schüler ein oder aus.

    War der Tag aktiv, wird er entfernt; andernfalls angehängt.

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        color_key: Zu toggelnder Farbschlüssel.

    Returns:
        Neuer Plan mit dem aktualisierten Color-Tag-Zustand.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan

    tags = student.diagnostic.color_tags
    if color_key in tags:
        student.diagnostic.color_tags = [t for t in tags if t != color_key]
    else:
        student.diagnostic.color_tags = tags + [color_key]

    return next_plan


def cleanup_unused_palette_entries(plan: SeatingPlan) -> SeatingPlan:
    """Entfernt Palette-Einträge, die kein Schüler mehr trägt.

    Wird typischerweise nach dem Entfernen eines Color-Tags aufgerufen.

    Args:
        plan: Ausgangsplan (kann bereits eine deepcopy sein).

    Returns:
        Neuer Plan ohne verwaiste Palette-Einträge.
    """
    next_plan = deepcopy(plan)
    used = used_color_tags(next_plan)
    next_plan.color_palette = {
        key: entry
        for key, entry in next_plan.color_palette.items()
        if key in used
    }
    return next_plan
