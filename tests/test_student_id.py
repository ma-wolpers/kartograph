"""Tests für StudentId."""

import pytest

from app.core.domain.student_id import StudentId


def test_new_returns_32_hex_chars():
    sid = StudentId.new()
    assert len(sid) == 32
    assert all(c in "0123456789abcdef" for c in sid)


def test_new_is_unique():
    assert StudentId.new() != StudentId.new()


def test_of_accepts_valid_hex():
    raw = "a" * 32
    sid = StudentId.of(raw)
    assert sid == raw


def test_of_lowercases_input():
    raw = "A" * 32
    sid = StudentId.of(raw)
    assert sid == "a" * 32


def test_of_strips_whitespace():
    raw = "  " + "b" * 32 + "  "
    sid = StudentId.of(raw)
    assert sid == "b" * 32


def test_of_rejects_wrong_length():
    with pytest.raises(ValueError):
        StudentId.of("abc123")


def test_of_rejects_non_hex():
    with pytest.raises(ValueError):
        StudentId.of("g" * 32)


def test_student_id_is_str_subtype():
    sid = StudentId.new()
    assert isinstance(sid, str)


def test_student_id_usable_as_dict_key():
    sid = StudentId.new()
    d = {sid: "wert"}
    assert d[sid] == "wert"
