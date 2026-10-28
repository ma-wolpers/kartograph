"""Tests für Abgabestatus-Auflösung und die Usecases von "Abgaben zählen"."""

from types import SimpleNamespace

import pytest

from app.core.domain.submission_status import (
    ABSENT_CODEPOINT,
    CatalogSymbolMissing,
    SubmissionStatus,
    resolve_symbol_name,
    submission_symbol_names,
)
from app.core.usecases.v4.submission_usecases import apply_missing_submissions, rated_statuses, set_submission_status
from app.core.usecases.v4.symbol_usecases import record_symbol
from tests.conftest import make_plan, make_student

DATE = "2026-10-28"
CATALOG = (
    SimpleNamespace(glyph="✓", meaning="Abgabe vollständig"),
    SimpleNamespace(glyph="◐", meaning="Abgabe lückenhaft"),
    SimpleNamespace(glyph="X", meaning="Nicht abgegeben / verweigert"),
    SimpleNamespace(glyph="∅", meaning="Abwesend"),
)
NAMES = submission_symbol_names(CATALOG)
ABSENT = resolve_symbol_name(CATALOG, ABSENT_CODEPOINT)


def _symbols(plan, sid):
    session = plan.documentation.session_for_date(DATE)
    entry = session.entry_for(sid) if session else None
    return dict(entry.symbols) if entry else {}


def test_names_resolve_by_codepoint_not_text():
    renamed = (SimpleNamespace(glyph="✓", meaning="Fertig!"),) + CATALOG[1:]
    assert submission_symbol_names(renamed)[SubmissionStatus.COMPLETE] == "Fertig!"
    with pytest.raises(CatalogSymbolMissing):
        submission_symbol_names(CATALOG[1:])


def test_set_status_keeps_exactly_one_of_three():
    anna = make_student()
    plan = make_plan(students=[anna])
    plan = set_submission_status(plan, anna.student_id, DATE, SubmissionStatus.PARTIAL, NAMES)
    plan = set_submission_status(plan, anna.student_id, DATE, SubmissionStatus.COMPLETE, NAMES)
    assert _symbols(plan, anna.student_id) == {"Abgabe vollständig": 1}
    assert rated_statuses(plan, DATE, NAMES) == {anna.student_id: SubmissionStatus.COMPLETE}
    cleared = set_submission_status(plan, anna.student_id, DATE, None, NAMES)
    assert _symbols(cleared, anna.student_id) == {}


def _class_with_absent_ben():
    anna, ben, cem = make_student(first_name="Anna"), make_student(first_name="Ben", x=2), make_student(first_name="Cem", x=3)
    plan = record_symbol(make_plan(students=[anna, ben, cem]), ben.student_id, DATE, ABSENT, 1)
    return plan, anna, ben, cem


@pytest.mark.parametrize(("mark_absent", "ben_gets_x"), [(False, False), (True, True)])
def test_missing_get_x_and_absent_follow_the_choice(mark_absent, ben_gets_x):
    plan, anna, ben, cem = _class_with_absent_ben()
    result = apply_missing_submissions(
        plan, DATE, [anna.student_id], NAMES, absent_symbol=ABSENT, mark_absent=mark_absent, mode="replace"
    )
    assert _symbols(result, anna.student_id) == {}
    assert _symbols(result, cem.student_id) == {"Nicht abgegeben / verweigert": 1}
    assert ("Nicht abgegeben / verweigert" in _symbols(result, ben.student_id)) is ben_gets_x
    assert _symbols(result, ben.student_id)[ABSENT] == 1


def test_replace_clears_old_ratings_complement_keeps_them():
    plan, anna, ben, cem = _class_with_absent_ben()
    plan = set_submission_status(plan, cem.student_id, DATE, SubmissionStatus.COMPLETE, NAMES)
    kwargs = dict(absent_symbol=ABSENT, mark_absent=True)

    replaced = apply_missing_submissions(plan, DATE, [anna.student_id], NAMES, mode="replace", **kwargs)
    assert _symbols(replaced, cem.student_id) == {"Nicht abgegeben / verweigert": 1}

    complemented = apply_missing_submissions(plan, DATE, [anna.student_id], NAMES, mode="complement", **kwargs)
    assert _symbols(complemented, cem.student_id) == {"Abgabe vollständig": 1}
    assert "Nicht abgegeben / verweigert" in _symbols(complemented, ben.student_id)
