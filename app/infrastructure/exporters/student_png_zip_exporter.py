"""Schreibt das ZIP-Archiv mit den Sitzkärtchen-PNGs (ein Bild je Schüler).

Dünne I/O-Orchestrierung: holt Geometrien und Dateinamen aus der Domain-
Schicht, rendert pro benanntem Schüler ein PNG über
``student_png_renderer.py`` und schreibt das Ergebnis atomar ins ZIP.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.student_png_export import StudentPngExportError, build_student_png_filenames
from app.core.domain.table_groups import build_seat_geometries_v4
from app.core.usecases.v4.tablegroup_usecases import normalize_tablegroups
from app.infrastructure.exporters.student_png_renderer import build_geometry_transform, render_student_png


def export_student_pngs_zip(plan: SeatingPlan, output_path: Path) -> int:
    """Exportiert für jeden benannten Schüler eine transparente PNG-Miniaturkarte in ein ZIP-Archiv.

    Ablauf: ``normalize_tablegroups()`` -> ``build_seat_geometries_v4()`` ->
    Filter auf ``is_named()`` -> ``StudentPngExportError`` falls leer ->
    ``build_geometry_transform()`` (einmal für den ganzen Export) ->
    ``build_student_png_filenames()`` -> pro Schüler ``render_student_png()``
    -> Eintrag ins ZIP.

    ZIP-Einträge sind garantiert flache Dateinamen ohne Pfadanteile: Die
    Dateinamens-Auflösung (``sanitize_windows_filename_component()``) ersetzt
    ``\\`` und ``/`` immer durch ``_``, ein Eintrag kann daher nie als
    relativer/aufsteigender Pfad interpretiert werden.

    Atomarer Schreibvorgang: Das ZIP wird zunächst unter einem temporären
    Pfad im selben Verzeichnis wie *output_path* geschrieben; erst nach
    erfolgreichem Rendern und Schreiben aller Kärtchen wird per
    ``os.replace()`` an *output_path* verschoben. Schlägt ein einzelnes
    Rendering fehl, bleibt *output_path* unangetastet (kein halb
    geschriebenes ZIP), die temporäre Datei wird im Fehlerfall gelöscht.

    Args:
        plan: Zu exportierender Sitzplan. Wird intern über
            ``normalize_tablegroups()`` normalisiert; der übergebene Plan
            bleibt unverändert (gleiches Muster wie ``build_namenfit_rows()``).
        output_path: Zieldatei (``.zip``, wird überschrieben, falls vorhanden).

    Returns:
        Anzahl geschriebener PNG-Dateien (für die Statuszeile im Dialog).

    Raises:
        StudentPngExportError: Wenn der Plan keine benannten Schüler enthält.
        RuntimeError: Wenn Pillow nicht installiert ist (aus ``render_student_png()``).
        OSError: Bei Schreibfehlern.
    """
    export_plan = normalize_tablegroups(plan)
    geometries = build_seat_geometries_v4(export_plan)
    named_students = [g.student for g in geometries if g.student is not None and g.student.is_named()]
    if not named_students:
        raise StudentPngExportError("Plan enthaelt keine benannten Schueler, PNG-Export abgebrochen.")

    transform = build_geometry_transform(geometries)
    filenames = build_student_png_filenames(named_students)

    output_path = Path(output_path)
    fd, tmp_path_str = tempfile.mkstemp(suffix=".zip.tmp", dir=str(output_path.parent))
    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for student in named_students:
                png_bytes = render_student_png(geometries, transform, student.student_id)
                archive.writestr(filenames[student.student_id], png_bytes)
        os.replace(tmp_path, output_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    return len(named_students)
