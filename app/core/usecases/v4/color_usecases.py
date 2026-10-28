"""Usecases für Farbmarkierungen (Color-Tags) an Schülern.

Color-Tags sind kurze Schlüssel wie ``"gelb"`` aus ``COLOR_MARKER_PALETTE``;
``plan.color_palette`` hält nur die planweite Bedeutung je Farbe. Invariante:
Die Palette enthält nur Farben, die mindestens ein Schüler trägt
(``drop_unused_palette_entries``) -- wird eine Farbe beim letzten Schüler
entfernt, wird ihre Bedeutung verworfen und beim nächsten Setzen neu abgefragt.
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
    Bereinigen der Palette (``drop_unused_palette_entries``) und für die
    Farbauswahl im Sitzplan-Vorschau-Dialog (nur vergebene Farben wählbar).

    Args:
        plan: Plan, aus dem gelesen wird.

    Returns:
        Menge der getragenen Farbschlüssel (unsortiert; für eine
        Palettenreihenfolge ``color_order.order_color_keys`` verwenden).
    """
    return {tag for s in plan.classroom.students for tag in s.diagnostic.color_tags}


def set_palette_meaning(plan: SeatingPlan, color_key: str, meaning: str) -> SeatingPlan:
    """Weist *color_key* eine pädagogische Bedeutung zu oder entfernt sie.

    Fehlt der Palette-Eintrag noch (der Normalfall beim ersten Setzen einer
    Farbe in einem Plan), wird er angelegt. Früher kehrte die Funktion in
    diesem Fall still zurück -- die abgefragte Bedeutung ging verloren und
    die Farbpunkt-Legende blieb leer.
    Leeres *meaning* entfernt nur den Bedeutungstext; der Palette-Eintrag bleibt.

    Args:
        plan: Ausgangsplan.
        color_key: Farbschlüssel, z. B. ``"gelb"``.
        meaning: Textuelle Bedeutung; leer = löschen.

    Returns:
        Neuer Plan mit dem aktualisierten Bedeutungstext.
    """
    next_plan = deepcopy(plan)
    next_plan.color_palette.setdefault(color_key, PaletteEntry()).meaning = meaning.strip()
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


def drop_unused_palette_entries(plan: SeatingPlan) -> None:
    """Entfernt in-place die Palette-Einträge (Bedeutungen), die kein Schüler mehr trägt.

    Einzige Stelle, an der die Invariante "die Palette enthält nur getragene
    Farben" durchgesetzt wird: beim Übernehmen jedes neuen Planzustands
    (``handlers/_shared.py::_record_and_save``) und beim Öffnen einer
    Plandatei (``handlers/plan_handlers.py::handle_open_plan``), analog zu
    ``apply_normalized_tablegroups``. So deckt sie jeden Weg ab, auf dem eine
    Farbe verschwindet (Farbpunkt aus, Tisch löschen, Ausschneiden, ...).

    GRENZE: Wird der einzige Träger einer Farbe ausgeschnitten und wieder
    eingefügt, ist die Bedeutung nach dem Ausschneiden verworfen; der
    eingefügte Tisch zeigt den Farbpunkt dann mit dem Hinweis "keine
    Bedeutung hinterlegt". Bewusst so entschieden (2026-10-28): Bedeutungen
    ungenutzter Farben werden nicht aufbewahrt.

    Nur für Pläne aufrufen, die der Aufrufer gerade selbst erzeugt hat
    (frische Kopie bzw. frisch deserialisiert), weil der Plan verändert wird.

    Args:
        plan: Zu bereinigender Plan (wird verändert).
    """
    used = used_color_tags(plan)
    plan.color_palette = {key: entry for key, entry in plan.color_palette.items() if key in used}
