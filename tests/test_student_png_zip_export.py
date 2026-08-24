"""Tests für Rendering und ZIP-Orchestrierung des PNG-Exports (ein Sitzkärtchen je Schüler).

Dateinamens-Auflösung ist separat in ``tests/test_student_png_export_naming.py``
getestet (reine Domain-Logik ohne Pillow-Abhängigkeit).
"""

from __future__ import annotations

import io
import zipfile

import pytest
from PIL import Image

from app.core.domain.student_id import StudentId
from app.core.domain.student_png_export import StudentPngExportError
from app.core.domain.table_groups import SeatGeometryV4
from app.infrastructure.exporters.student_png_renderer import (
    OWN_TABLE_FILL_COLOR,
    TABLE_FILL_COLOR,
    TEACHER_FILL_COLOR,
    build_geometry_transform,
    render_student_png,
)
from app.infrastructure.exporters.student_png_zip_exporter import export_student_pngs_zip
from tests.conftest import make_plan, make_student


def _square_polygon(x0: float, y0: float) -> tuple[tuple[float, float], ...]:
    """Baut ein unrotiertes 1x1-Tisch-Polygon mit Ecke oben-links bei (x0, y0)."""
    return ((x0, y0), (x0 + 1, y0), (x0 + 1, y0 + 1), (x0, y0 + 1))


def _fixed_geometries() -> tuple[list[SeatGeometryV4], StudentId, StudentId]:
    """Festes, handgebautes Geometrie-Fixture: 1 Lehrertisch + 2 weit auseinanderliegende,
    unrotierte Schülertische -- unabhängig von realen, ggf. komplexeren Plan-Geometrien."""
    student_a = make_student(x=3, y=0, first_name="Anna")
    student_b = make_student(x=7, y=0, first_name="Ben")
    geometries = [
        SeatGeometryV4(
            x=0, y=0, is_teacher=True, group_id=None,
            center_x=0.5, center_y=0.5, polygon=_square_polygon(0, 0), student=None,
        ),
        SeatGeometryV4(
            x=3, y=0, is_teacher=False, group_id=1,
            center_x=3.5, center_y=0.5, polygon=_square_polygon(3, 0), student=student_a,
        ),
        SeatGeometryV4(
            x=7, y=0, is_teacher=False, group_id=1,
            center_x=7.5, center_y=0.5, polygon=_square_polygon(7, 0), student=student_b,
        ),
    ]
    return geometries, student_a.student_id, student_b.student_id


def _rgba_at(png_bytes: bytes, wx: float, wy: float, transform) -> tuple[int, int, int, int]:
    """Dekodiert *png_bytes* und liest den Pixel an der zu *wx*/*wy* gehörenden Bildposition."""
    px, py = transform.to_pixel(wx, wy)
    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    return image.getpixel((int(round(px)), int(round(py))))


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


class TestRenderStudentPng:
    def test_own_table_is_filled_with_own_table_color(self):
        geometries, student_a_id, _student_b_id = _fixed_geometries()
        transform = build_geometry_transform(geometries)

        png_bytes = render_student_png(geometries, transform, student_a_id)

        r, g, b, a = _rgba_at(png_bytes, 3.5, 0.5, transform)
        assert (r, g, b) == _hex_to_rgb(OWN_TABLE_FILL_COLOR)
        assert a > 0

    def test_teacher_table_is_always_orange_regardless_of_target(self):
        geometries, student_a_id, student_b_id = _fixed_geometries()
        transform = build_geometry_transform(geometries)

        for target_id in (student_a_id, student_b_id):
            png_bytes = render_student_png(geometries, transform, target_id)
            r, g, b, _a = _rgba_at(png_bytes, 0.5, 0.5, transform)
            assert (r, g, b) == _hex_to_rgb(TEACHER_FILL_COLOR)

    def test_other_student_table_is_white(self):
        geometries, student_a_id, student_b_id = _fixed_geometries()
        transform = build_geometry_transform(geometries)

        png_bytes = render_student_png(geometries, transform, student_a_id)

        r, g, b, _a = _rgba_at(png_bytes, 7.5, 0.5, transform)
        assert (r, g, b) == _hex_to_rgb(TABLE_FILL_COLOR)

    def test_background_outside_tables_is_fully_transparent(self):
        geometries, student_a_id, _student_b_id = _fixed_geometries()
        transform = build_geometry_transform(geometries)

        png_bytes = render_student_png(geometries, transform, student_a_id)
        image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

        assert image.getpixel((0, 0))[3] == 0

    def test_table_interior_has_nonzero_alpha(self):
        """Ergaenzt den Transparenztest: ein Punkt AUSSERHALB (Alpha 0) und
        ein Punkt INNERHALB eines Tisches (Alpha > 0) werden getrennt
        geprueft, damit ein versehentlich komplett transparentes Bild nicht
        faelschlich als 'Transparenz vorhanden' durchgeht."""
        geometries, student_a_id, _student_b_id = _fixed_geometries()
        transform = build_geometry_transform(geometries)

        png_bytes = render_student_png(geometries, transform, student_a_id)

        _r, _g, _b, a = _rgba_at(png_bytes, 0.5, 0.5, transform)
        assert a > 0

    def test_two_renderings_differ_only_in_which_table_is_blue(self):
        """Fachlicher Vergleich der dekodierten Zentrumspixel statt Byte-
        Gleichheit der PNG-Kodierung (die waere wegen Metadaten/Encoding
        unnoetig fragil)."""
        geometries, student_a_id, student_b_id = _fixed_geometries()
        transform = build_geometry_transform(geometries)

        png_for_a = render_student_png(geometries, transform, student_a_id)
        png_for_b = render_student_png(geometries, transform, student_b_id)

        assert Image.open(io.BytesIO(png_for_a)).size == Image.open(io.BytesIO(png_for_b)).size

        teacher_in_a = _rgba_at(png_for_a, 0.5, 0.5, transform)[:3]
        teacher_in_b = _rgba_at(png_for_b, 0.5, 0.5, transform)[:3]
        assert teacher_in_a == teacher_in_b == _hex_to_rgb(TEACHER_FILL_COLOR)

        assert _rgba_at(png_for_a, 3.5, 0.5, transform)[:3] == _hex_to_rgb(OWN_TABLE_FILL_COLOR)
        assert _rgba_at(png_for_a, 7.5, 0.5, transform)[:3] == _hex_to_rgb(TABLE_FILL_COLOR)
        assert _rgba_at(png_for_b, 3.5, 0.5, transform)[:3] == _hex_to_rgb(TABLE_FILL_COLOR)
        assert _rgba_at(png_for_b, 7.5, 0.5, transform)[:3] == _hex_to_rgb(OWN_TABLE_FILL_COLOR)


class TestExportStudentPngsZip:
    def test_zip_contains_one_file_per_named_student(self, tmp_path):
        s1 = make_student(x=1, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=2, y=0, first_name="Ben", last_name="Meier")
        plan = make_plan(students=[s1, s2])
        output = tmp_path / "Testklasse.zip"

        count = export_student_pngs_zip(plan, output)

        assert count == 2
        with zipfile.ZipFile(output) as archive:
            assert sorted(archive.namelist()) == ["Anna.png", "Ben.png"]

    def test_each_zip_entry_is_a_valid_png_with_expected_size(self, tmp_path):
        s1 = make_student(x=1, y=0, first_name="Anna", last_name="Gold")
        plan = make_plan(students=[s1])
        output = tmp_path / "Testklasse.zip"

        export_student_pngs_zip(plan, output)

        with zipfile.ZipFile(output) as archive:
            png_bytes = archive.read("Anna.png")
        image = Image.open(io.BytesIO(png_bytes))
        assert image.format == "PNG"
        assert image.mode == "RGBA"
        assert image.width > 0 and image.height > 0

    def test_unnamed_students_are_skipped(self, tmp_path):
        named = make_student(x=1, y=0, first_name="Anna", last_name="Gold")
        blank = make_student(x=2, y=0, first_name="", last_name="")
        plan = make_plan(students=[named, blank])
        output = tmp_path / "Testklasse.zip"

        count = export_student_pngs_zip(plan, output)

        assert count == 1
        with zipfile.ZipFile(output) as archive:
            assert archive.namelist() == ["Anna.png"]

    def test_plan_without_named_students_raises_and_writes_nothing(self, tmp_path):
        blank = make_student(x=1, y=0, first_name="", last_name="")
        plan = make_plan(students=[blank])
        output = tmp_path / "Testklasse.zip"

        with pytest.raises(StudentPngExportError):
            export_student_pngs_zip(plan, output)

        assert not output.exists()
        assert list(tmp_path.iterdir()) == []

    def test_input_plan_is_not_mutated(self, tmp_path):
        s1 = make_student(x=1, y=0, first_name="Anna", last_name="Gold")
        plan = make_plan(students=[s1])
        tablegroups_before = list(plan.tablegroups)
        students_before = list(plan.classroom.students)
        output = tmp_path / "Testklasse.zip"

        export_student_pngs_zip(plan, output)

        assert plan.tablegroups == tablegroups_before
        assert plan.classroom.students == students_before
