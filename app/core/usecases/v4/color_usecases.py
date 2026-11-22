"""Usecases für Farbmarkierungen (Color-Tags) an Schülern und Ja/Nein-Spalten.

Color-Tags sind kurze Schlüssel wie ``"gelb"`` aus ``COLOR_MARKER_PALETTE``
(oder farblose ``flag_…``-Schlüssel, s. ``flag_columns``); ``plan.color_palette``
hält die planweite Bedeutung je Farbe -- in der Datenansicht ist jeder Eintrag
eine Ja/Nein-Spalte mit der Bedeutung als Titel.
Übergangsregel (``drop_abandoned_palette_entries``): Wird eine Markierung bei
der letzten Person entfernt, verschwindet ihr Eintrag; eine von Anfang an
leere Spalte bleibt (Entscheidung der Nutzerin 2026-11-17, ersetzt die
zustandsbasierte Regel "Palette nur getragene Farben" vom 2026-10-28).
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.flag_columns import new_colorless_key
from app.core.domain.models_v4 import PaletteEntry, SeatingPlan
from app.core.domain.permanent_absence import accepts_entries
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

    Einzige Definition von "im Plan vergebene Farben": genutzt für die
    Übergangsregel der Palette (``drop_abandoned_palette_entries``), die
    Ja/Nein-Spalten der Datenansicht und die Farbauswahl im
    Sitzplan-Vorschau-Dialog (nur vergebene Farben wählbar).

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
    if student is None or not accepts_entries(student):
        return next_plan

    tags = student.diagnostic.color_tags
    if color_key in tags:
        student.diagnostic.color_tags = [t for t in tags if t != color_key]
    else:
        student.diagnostic.color_tags = tags + [color_key]

    return next_plan


def add_flag_column(plan: SeatingPlan, title: str, color_key: str | None) -> tuple[SeatingPlan, str]:
    """Legt eine Ja/Nein-Spalte an: Paletteneintrag mit *title* als Bedeutung, noch ohne Markierungen.

    Args:
        plan: Ausgangsplan.
        title: Spaltentitel (= Bedeutung der Farbe).
        color_key: Freie Farbe oder ``None`` für eine farblose Spalte
            (dann wird ein neuer ``flag_…``-Schlüssel erzeugt).

    Returns:
        ``(neuer Plan, Schlüssel der Spalte)``.

    Raises:
        ValueError: *color_key* ist schon eine Spalte oder wird getragen.
    """
    in_use = set(plan.color_palette) | used_color_tags(plan)
    key = color_key if color_key is not None else new_colorless_key(in_use)
    if key in in_use:
        raise ValueError(f"Farbe {key!r} ist bereits vergeben")
    next_plan = deepcopy(plan)
    next_plan.color_palette[key] = PaletteEntry(meaning=title.strip())
    return next_plan, key


def delete_flag_column(plan: SeatingPlan, key: str) -> SeatingPlan:
    """Löscht eine Ja/Nein-Spalte: nimmt allen die Markierung *key* ab und entfernt den Eintrag.

    Bewusst auch bei dauerhaft Abwesenden (Löschen einer Spalte ist keine
    Eintragung bei einer Person).

    Args:
        plan: Ausgangsplan.
        key: Schlüssel der Spalte (Farbe oder ``flag_…``).

    Returns:
        Neuer Plan ohne die Spalte.
    """
    next_plan = deepcopy(plan)
    for student in next_plan.classroom.students:
        student.diagnostic.color_tags = [tag for tag in student.diagnostic.color_tags if tag != key]
    next_plan.color_palette.pop(key, None)
    return next_plan


def drop_abandoned_palette_entries(previous: SeatingPlan | None, plan: SeatingPlan) -> None:
    """Entfernt in-place die Einträge, deren letzte Markierung mit diesem Schritt wegfiel.

    Übergangsregel statt Zustandsregel: Gelöscht wird nur, was in *previous*
    noch jemand trug und in *plan* niemand mehr -- eine von Anfang an leere
    Ja/Nein-Spalte bleibt, ebenso jede Spalte beim Öffnen einer Datei
    (*previous* ``None``). Einzige Stelle der Regel; aufgerufen beim Übernehmen
    jedes neuen Planzustands (``handlers/_shared.py::_apply_plan_invariants``),
    deckt damit jeden Weg ab, auf dem eine Markierung verschwindet (Farbpunkt
    aus, Tisch löschen, Ausschneiden, Name gelöscht, ...).

    GRENZE: Wird der einzige Träger einer Farbe ausgeschnitten und wieder
    eingefügt, ist die Bedeutung nach dem Ausschneiden verworfen; der
    eingefügte Tisch zeigt den Farbpunkt dann mit dem Hinweis "keine
    Bedeutung hinterlegt" (bewusst so seit 2026-10-28).

    Nur für Pläne aufrufen, die der Aufrufer gerade selbst erzeugt hat
    (frische Kopie bzw. frisch deserialisiert), weil der Plan verändert wird.

    Args:
        previous: Bisher angezeigter Stand (``state.current_plan``) oder ``None``.
        plan: Neuer Stand (wird verändert).
    """
    if previous is None:
        return
    abandoned = used_color_tags(previous) - used_color_tags(plan)
    plan.color_palette = {key: entry for key, entry in plan.color_palette.items() if key not in abandoned}
