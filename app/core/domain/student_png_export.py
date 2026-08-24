"""Dateinamens-Auflösung für den PNG-ZIP-Export (ein Sitzkärtchen je Schüler).

Reine Domain-Logik ohne Datei-I/O und ohne Pillow-Abhängigkeit: baut auf der
bestehenden, spitznamen-bewussten Namensauflösung (``student_naming.py``) auf
und macht das Ergebnis Windows-dateisystem-sicher. Das eigentliche Rendering
liegt in ``app/infrastructure/exporters/student_png_renderer.py``, das
ZIP-Schreiben in ``app/infrastructure/exporters/student_png_zip_exporter.py``.
"""

from __future__ import annotations

from typing import Sequence

from app.core.domain.models_v4 import Student
from app.core.domain.student_id import StudentId
from app.core.domain.student_naming import compute_display_names

_FORBIDDEN_CHARS = '\\/:*?"<>|'
_RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
_EMPTY_NAME_FALLBACK = "Schueler"


class StudentPngExportError(Exception):
    """Export-Vorbedingung für den PNG-ZIP-Export verletzt (z. B. kein
    benannter Schüler im Plan).

    Lebt hier statt in einem separaten Fehler-Modul, weil dieses Modul die
    Domain-Schicht *dieses* Exports ist — exakt der Präzedenzfall von
    ``NamenfitExportError`` in ``namenfit_csv_export.py``, das ebenfalls im
    Domain-Modul des jeweiligen Exports lebt statt in einer generischen
    Fehlerhierarchie.
    """


def sanitize_windows_filename_component(name: str) -> str:
    """Macht *name* zu einem auf Windows gültigen Dateinamens-Bestandteil (ohne Endung).

    Reines Escaping, keine Transliteration: Unicode-Zeichen (z. B. Umlaute)
    bleiben unverändert erhalten, nur tatsächlich auf Windows verbotene
    Zeichen/Konstrukte werden angepasst. Die Schritte bauen aufeinander auf:

    1. Verbotene Zeichen ``\\ / : * ? " < > |`` werden durch ``_`` ersetzt
       (nicht ersatzlos gestrichen, damit zwei Namensteile nicht
       stillschweigend verschmelzen). Da ``\\`` und ``/`` dabei immer
       ersetzt werden, kann das Ergebnis strukturell nie einen
       Pfadseparator enthalten — Voraussetzung dafür, dass ein daraus
       gebauter ZIP-Eintrag garantiert ein flacher Dateiname bleibt.
    2. Steuerzeichen (``ord(c) < 0x20`` sowie ``0x7F``) werden ersatzlos
       entfernt.
    3. Führende/trailende Punkte und Leerzeichen werden entfernt
       (``str.strip(" .")``) — Windows verbietet trailende Punkte/
       Leerzeichen in Dateinamen, führende werden zusätzlich aus
       Lesbarkeitsgründen entfernt.
    4. Reservierte Gerätenamen (``CON``, ``PRN``, ``AUX``, ``NUL``,
       ``COM1``-``COM9``, ``LPT1``-``LPT9``) werden erkannt, indem nur der
       Teil vor dem ersten Punkt case-insensitiv verglichen wird — Windows
       prüft ebenfalls nur diesen Teil, wodurch z. B. auch ``"CON.txt"``
       als reserviert gilt. Bei einem Treffer wird ``_`` an die gesamte
       Zeichenkette angehängt.
    5. Bleibt nach den Schritten 1-4 nichts übrig (z. B. bestand *name* nur
       aus verbotenen Zeichen), wird auf den Platzhalter ``"Schueler"``
       zurückgefallen.

    Args:
        name: Roher Anzeigename (ohne Dateiendung), z. B. aus
            ``compute_display_names()``.
    """
    cleaned = "".join("_" if c in _FORBIDDEN_CHARS else c for c in name)
    cleaned = "".join(c for c in cleaned if ord(c) >= 0x20 and c != "\x7f")
    cleaned = cleaned.strip(" .")

    device_name = cleaned.split(".", 1)[0].upper()
    if device_name in _RESERVED_DEVICE_NAMES:
        cleaned = f"{cleaned}_"

    return cleaned or _EMPTY_NAME_FALLBACK


def _deduplicate_filenames(
    base_names_by_id: dict[StudentId, str], named_students: Sequence[Student]
) -> dict[StudentId, str]:
    """Hängt an real kollidierende, bereits sanitizte Basisnamen einen numerischen Suffix an.

    Iteriert *named_students* in der gegebenen Reihenfolge (deterministisch:
    der erste Treffer eines Basisnamens behält ihn unverändert, jeder
    weitere bekommt ``" (2)"``, ``" (3)"``, … angehängt). Läuft NACH dem
    Sanitizing, damit auch Kollisionen erkannt werden, die das Sanitizing
    selbst erst erzeugt hat (z. B. zwei unterschiedliche Anzeigenamen, die
    sich nur durch ein verbotenes Zeichen unterscheiden).

    Args:
        base_names_by_id: Sanitizte (aber noch potenziell kollidierende)
            Basisnamen je Schüler, ohne Dateiendung.
        named_students: Dieselben Schüler wie in *base_names_by_id*, in der
            Reihenfolge, in der Duplikat-Suffixe vergeben werden.
    """
    seen_counts: dict[str, int] = {}
    result: dict[StudentId, str] = {}
    for student in named_students:
        base_name = base_names_by_id[student.student_id]
        count = seen_counts.get(base_name, 0) + 1
        seen_counts[base_name] = count
        result[student.student_id] = base_name if count == 1 else f"{base_name} ({count})"
    return result


def build_student_png_filenames(named_students: Sequence[Student]) -> dict[StudentId, str]:
    """Berechnet für jeden Schüler in *named_students* den finalen, eindeutigen ZIP-Dateinamen.

    Feste Reihenfolge:

    1. ``compute_display_names(named_students, "Vorname", disambiguate=True)``
       — unverändertes, etabliertes Vornamens-/Spitzname-/Namensvetter-
       Verhalten, identisch zum Namenfit-CSV-Export: Spitzname überschreibt
       den offiziellen Vornamen, bei gleichem effektivem Vornamen wird so
       viel vom Nachnamen ergänzt, wie zur Eindeutigkeit innerhalb der
       Kollisionsgruppe nötig ist.
    2. ``sanitize_windows_filename_component()`` auf jedes Ergebnis anwenden.
    3. Erst danach deduplizieren (``_deduplicate_filenames``) — nicht davor,
       siehe dortige Begründung.
    4. ``.png`` anhängen.

    Eine nach Schritt 3 verbleibende Kollision (z. B. zwei Schüler mit
    exakt identischem Vor- und Nachnamen) blockiert — anders als beim
    CSV-Export (``DuplicateDisplayNamesError``, harter Abbruch) — den
    PNG-Export nicht: es sind unabhängige Einzeldateien, kein
    zusammenhängendes CSV-Format, daher genügt der numerische Suffix.

    Args:
        named_students: Bereits auf ``is_named()`` gefilterte Schülerliste.

    Returns:
        Dict von ``StudentId`` auf den finalen Dateinamen inkl. ``.png``.
    """
    display_names = compute_display_names(named_students, "Vorname", disambiguate=True)
    sanitized = {
        student_id: sanitize_windows_filename_component(name)
        for student_id, name in display_names.items()
    }
    unique_base_names = _deduplicate_filenames(sanitized, named_students)
    return {student_id: f"{base_name}.png" for student_id, base_name in unique_base_names.items()}
