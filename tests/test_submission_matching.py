"""Tests für den Abgleich ZIP-Unterordner ↔ Schüler:innen (nur erfundene Namen)."""

from app.core.domain.submission_matching import match_submission_folders, normalize_name
from tests.conftest import make_student


def test_normalize_handles_umlauts_accents_separators_and_ids():
    assert normalize_name("Anna-Lena Müller_123") == ("anna", "lena", "mueller")
    assert normalize_name("Anna Lena Mueller") == ("anna", "lena", "mueller")
    assert normalize_name("José Núñez") == ("jose", "nunez")
    assert normalize_name("Jörg Groß") == ("joerg", "gross")


def test_second_names_and_double_surnames_match():
    anna = make_student(first_name="Anna", last_name="Müller")
    ben = make_student(first_name="Ben", last_name="von der Heide", x=2)
    result = match_submission_folders(["Anna Sophie Marie Mueller", "Ben Lukas von der Heide"], [anna, ben])
    assert result.matched == {"Anna Sophie Marie Mueller": anna.student_id, "Ben Lukas von der Heide": ben.student_id}
    assert result.ambiguous == {} and result.unknown == () and result.without_folder == ()


def test_nickname_counts_as_first_name():
    kim = make_student(first_name="Kimberly", nickname="Kim", last_name="Probe")
    assert match_submission_folders(["Kim Probe"], [kim]).matched == {"Kim Probe": kim.student_id}


def test_typo_is_unknown_and_student_without_folder_is_reported():
    anna = make_student(first_name="Anna", last_name="Müller")
    result = match_submission_folders(["Anna Müler"], [anna])
    assert result.unknown == ("Anna Müler",)
    assert result.without_folder == (anna.student_id,)


def test_two_candidates_are_ambiguous_never_guessed():
    a1 = make_student(first_name="Lea", last_name="Schmidt")
    a2 = make_student(first_name="Lea Marie", last_name="Schmidt", x=2)
    result = match_submission_folders(["Lea Schmidt"], [a1, a2])
    assert result.matched == {}
    assert set(result.ambiguous["Lea Schmidt"]) == {a1.student_id, a2.student_id}


def test_same_student_in_two_folders_is_ambiguous():
    anna = make_student(first_name="Anna", last_name="Müller")
    result = match_submission_folders(["Anna Müller", "Anna Maria Müller"], [anna])
    assert result.matched == {}
    assert set(result.ambiguous) == {"Anna Müller", "Anna Maria Müller"}


def test_last_name_alone_or_unnamed_seats_do_not_match():
    anna = make_student(first_name="Anna", last_name="Müller")
    empty = make_student(first_name="", last_name="", x=3)
    result = match_submission_folders(["Müller", "Anna"], [anna, empty])
    assert result.matched == {} and set(result.unknown) == {"Müller", "Anna"}
    assert result.without_folder == (anna.student_id,)
