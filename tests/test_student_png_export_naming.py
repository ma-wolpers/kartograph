"""Tests für die Dateinamens-Auflösung des PNG-ZIP-Exports (Sanitizing + Dedup).

Reine Domain-Logik ohne Pillow-Abhängigkeit -- in eigener Testdatei, damit
``tests/test_student_png_zip_export.py`` (Rendering + ZIP-Orchestrierung,
inkl. Pillow-Nutzung) nicht zu groß wird.
"""

from __future__ import annotations

from app.core.domain.student_naming import compute_display_names
from app.core.domain.student_png_export import (
    build_student_png_filenames,
    sanitize_windows_filename_component,
)
from tests.conftest import make_student


class TestSanitizeWindowsFilenameComponent:
    def test_forbidden_characters_are_replaced(self):
        assert sanitize_windows_filename_component('A\\B/C:D*E?F"G<H>I|J') == "A_B_C_D_E_F_G_H_I_J"

    def test_control_characters_are_removed(self):
        assert sanitize_windows_filename_component("Anna\x01\x7fGold") == "AnnaGold"

    def test_leading_and_trailing_dots_and_spaces_are_stripped(self):
        assert sanitize_windows_filename_component(" .Anna. ") == "Anna"

    def test_input_that_becomes_empty_after_stripping_falls_back_to_placeholder(self):
        """Nur aus Punkten/Leerzeichen bestehende Namen werden durch
        strip(" .") vollstaendig entfernt (nicht durch die Ersetzung
        verbotener Zeichen wie '*'/'?', die zu '_' werden und daher NICHT
        leer sind)."""
        assert sanitize_windows_filename_component(" . . . ") == "Schueler"

    def test_unicode_names_are_preserved_unchanged(self):
        assert sanitize_windows_filename_component("Müller") == "Müller"

    def test_reserved_device_name_gets_suffix(self):
        assert sanitize_windows_filename_component("CON") == "CON_"

    def test_reserved_device_name_with_extension_gets_suffix(self):
        """Windows prueft nur den Teil vor dem ersten Punkt -- 'CON.txt' ist
        ebenso reserviert wie 'CON' selbst."""
        assert sanitize_windows_filename_component("CON.txt") == "CON.txt_"

    def test_reserved_device_name_is_case_insensitive(self):
        assert sanitize_windows_filename_component("com1") == "com1_"

    def test_non_reserved_name_starting_like_device_name_is_untouched(self):
        assert sanitize_windows_filename_component("Constantin") == "Constantin"


class TestBuildStudentPngFilenames:
    def test_single_student_without_namesake(self):
        s1 = make_student(x=0, y=0, first_name="Emil", last_name="Meier")
        result = build_student_png_filenames([s1])
        assert result == {s1.student_id: "Emil.png"}

    def test_nickname_overrides_official_first_name(self):
        s1 = make_student(x=0, y=0, first_name="Emilian", last_name="Gold", nickname="Emil")
        result = build_student_png_filenames([s1])
        assert result == {s1.student_id: "Emil.png"}

    def test_namesakes_get_growing_last_name_prefix(self):
        s1 = make_student(x=0, y=0, first_name="Gustav", last_name="Maier")
        s2 = make_student(x=1, y=0, first_name="Gustav", last_name="Muster")
        result = build_student_png_filenames([s1, s2])
        assert result == {s1.student_id: "Gustav Ma.png", s2.student_id: "Gustav Mu.png"}

    def test_exact_name_collision_gets_numeric_suffix_instead_of_failing(self):
        """Zwillings-Randfall: identischer Vor- UND Nachname bleibt auch nach
        compute_display_names() kollidierend -- der PNG-Export bricht dafuer
        (anders als der CSV-Export) nicht ab, sondern haengt einen
        numerischen Suffix an."""
        s1 = make_student(x=0, y=0, first_name="Anna", last_name="Gold")
        s2 = make_student(x=1, y=0, first_name="Anna", last_name="Gold")

        result = build_student_png_filenames([s1, s2])

        assert result[s1.student_id] == "Anna Gold.png"
        assert result[s2.student_id] == "Anna Gold (2).png"

    def test_collision_introduced_only_by_sanitizing_is_still_deduplicated(self):
        """Zwei nach compute_display_names() unterschiedliche Namen, die
        sich nur durch ein auf Windows verbotenes Zeichen unterscheiden,
        werden nach dem Sanitizing identisch -- der Dedup-Schritt muss
        danach laufen, sonst bliebe diese Kollision unerkannt."""
        s1 = make_student(x=0, y=0, first_name="A/B", last_name="Meier")
        s2 = make_student(x=1, y=0, first_name="A?B", last_name="Muster")
        # Beide sind nach compute_display_names() eindeutig (unterschiedliche
        # Vornamen "A/B" vs "A?B"), sanitizen aber beide auf Basisname "A_B".
        assert compute_display_names([s1, s2], "Vorname", disambiguate=True) == {
            s1.student_id: "A/B",
            s2.student_id: "A?B",
        }

        result = build_student_png_filenames([s1, s2])

        assert result[s1.student_id] == "A_B.png"
        assert result[s2.student_id] == "A_B (2).png"

    def test_unnamed_students_must_be_filtered_by_caller(self):
        """build_student_png_filenames() filtert nicht selbst auf is_named()
        -- das ist Aufgabe des Aufrufers (export_student_pngs_zip()), analog
        zu build_namenfit_rows(). Ein unbenannter Schueler wuerde sonst
        einen Platzhalter-Dateinamen bekommen."""
        blank = make_student(x=0, y=0, first_name="", last_name="")
        result = build_student_png_filenames([blank])
        assert result[blank.student_id] == "Schueler.png"
