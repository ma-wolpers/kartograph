"""Tests für ``load_catalog``: Arbeitskopien von Symbolen und Kompetenzen laden, reparieren, ergänzen."""

from __future__ import annotations

import json

import pytest

from app.infrastructure.symbol_config_loader import DEFAULT_COMPETENCES_PATH, DEFAULT_SYMBOLS_PATH, load_catalog

# Testdateien, die alle eingebauten Einträge schon "kennen" -- sonst ergänzt der
# Loader sie (gewolltes Verhalten, eigens getestet in test_merge_*).
ALL_BUILTINS_KNOWN = sorted(
    f"{int(item['codepoint'], 16):04X}"
    for item in json.loads(DEFAULT_SYMBOLS_PATH.read_text(encoding="utf-8"))["symbols"]
)
ALL_COMPETENCES_KNOWN = sorted(
    item["id"] for item in json.loads(DEFAULT_COMPETENCES_PATH.read_text(encoding="utf-8"))["competences"]
)
LEVELS = {"three": "a", "two": "b", "one": "c"}


def _write(path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _symbols_file(tmp_path, items, known=ALL_BUILTINS_KNOWN):
    """Schreibt eine Symbol-Arbeitskopie und gibt ``(symbols_path, competences_path)`` zurück."""
    path = tmp_path / "symbols.json"
    _write(path, {"known_builtin_codepoints": known, "symbols": items})
    return path, tmp_path / "competences.json"


def _diagnostic(codepoint="1F446", key="Beteiligung", shortcut="b", competences=("beteiligung.lerngespraech",)):
    return {"codepoint": codepoint, "key": key, "shortcut": shortcut, "competences": list(competences)}


def _doc(codepoint="2205", key="Abwesend", shortcut="u"):
    return {"codepoint": codepoint, "key": key, "shortcut": shortcut, "role": "documentation_only", "legend": LEVELS}


def test_diagnostic_symbol_reads_key_name_and_competences(tmp_path) -> None:
    item = {**_diagnostic(), "name": "Mitarbeit im Gespräch"}
    result = load_catalog(*_symbols_file(tmp_path, [item]))

    assert result.warning is None
    symbol = result.symbols[0]
    assert (symbol.key, symbol.name, symbol.role) == ("Beteiligung", "Mitarbeit im Gespräch", "diagnostic")
    assert symbol.competence_ids == ("beteiligung.lerngespraech",)
    assert symbol.frequency_legend is None and symbol.active is True


def test_documentation_symbol_keeps_frequency_legend(tmp_path) -> None:
    result = load_catalog(*_symbols_file(tmp_path, [_doc()]))

    assert result.symbols[0].role == "documentation_only"
    assert result.symbols[0].frequency_legend == ("c", "b", "a")


def test_inactive_flag_is_read(tmp_path) -> None:
    result = load_catalog(*_symbols_file(tmp_path, [{**_diagnostic(), "active": False}]))
    assert result.symbols[0].active is False


def test_space_shortcut_sentinel_survives_loading(tmp_path) -> None:
    """Regression: ein Mehrzeichen-Kürzel ging früher verloren; der Sentinel "space" muss bleiben."""
    result = load_catalog(*_symbols_file(tmp_path, [_doc(shortcut="space")]))
    assert result.symbols[0].shortcut == "space"


def test_other_multi_character_shortcuts_are_dropped(tmp_path) -> None:
    result = load_catalog(*_symbols_file(tmp_path, [_diagnostic(shortcut="xyz")]))
    assert result.symbols[0].shortcut is None


def test_uppercase_shortcut_is_normalized(tmp_path) -> None:
    result = load_catalog(*_symbols_file(tmp_path, [_diagnostic(shortcut="P")]))
    assert result.symbols[0].shortcut == "p"


def test_missing_files_are_created_from_defaults(tmp_path) -> None:
    symbols_path, competences_path = tmp_path / "symbols.json", tmp_path / "competences.json"
    result = load_catalog(symbols_path, competences_path)

    assert {"Abgabe vollständig", "Konzentration"} <= {s.key for s in result.symbols}
    assert {c.id for c in result.competences} == set(ALL_COMPETENCES_KNOWN)
    assert json.loads(symbols_path.read_text(encoding="utf-8"))["known_builtin_codepoints"] == ALL_BUILTINS_KNOWN
    assert json.loads(competences_path.read_text(encoding="utf-8"))["known_builtin_competence_ids"] == ALL_COMPETENCES_KNOWN


def test_default_symbols_only_link_existing_competences(tmp_path) -> None:
    result = load_catalog(tmp_path / "symbols.json", tmp_path / "competences.json")
    known = {c.id for c in result.competences}
    for symbol in result.symbols:
        if symbol.role == "diagnostic":
            assert symbol.competence_ids and set(symbol.competence_ids) <= known, symbol.key


def test_merge_adds_new_builtins_without_touching_own_edits(tmp_path) -> None:
    """Alte Arbeitskopie ohne known-Liste: vorhandene Einträge bleiben, Neues wird ergänzt."""
    path = tmp_path / "symbols.json"
    _write(path, {"symbols": [_doc(codepoint="0058", key="Mein eigener Text für X", shortcut="x")]})

    result = load_catalog(path, tmp_path / "competences.json")

    by_glyph = {s.glyph: s for s in result.symbols}
    assert by_glyph["X"].key == "Mein eigener Text für X"
    assert by_glyph["✓"].shortcut == "e"
    assert by_glyph["◐"].shortcut == "l"


def test_merge_does_not_resurrect_deleted_builtins(tmp_path) -> None:
    result = load_catalog(*_symbols_file(tmp_path, [_doc(codepoint="0058", key="X", shortcut="x")]))
    assert [s.glyph for s in result.symbols] == ["X"]


def test_merge_drops_conflicting_shortcut_and_warns(tmp_path) -> None:
    known = [c for c in ALL_BUILTINS_KNOWN if c != "2713"]
    result = load_catalog(*_symbols_file(tmp_path, [_doc(codepoint="1F600", key="Eigenes", shortcut="e")], known))

    complete = next(s for s in result.symbols if s.glyph == "✓")
    assert complete.shortcut is None
    assert result.warning is not None and "Abgabe vollständig" in result.warning


def test_new_builtin_competences_are_merged_but_deleted_ones_stay_deleted(tmp_path) -> None:
    competences_path = tmp_path / "competences.json"
    own = {"id": "eigen.x", "name": "Eigene", "group": "G", "levels": LEVELS}
    known = [cid for cid in ALL_COMPETENCES_KNOWN if cid != "lernvoraussetzung.motivation"]
    _write(competences_path, {"competences": [own], "known_builtin_competence_ids": known})

    result = load_catalog(tmp_path / "symbols.json", competences_path)

    assert [c.id for c in result.competences] == ["eigen.x", "lernvoraussetzung.motivation"]


def test_loading_is_idempotent(tmp_path) -> None:
    symbols_path, competences_path = tmp_path / "symbols.json", tmp_path / "competences.json"
    load_catalog(symbols_path, competences_path)
    before = (symbols_path.read_text(encoding="utf-8"), competences_path.read_text(encoding="utf-8"))
    load_catalog(symbols_path, competences_path)
    assert (symbols_path.read_text(encoding="utf-8"), competences_path.read_text(encoding="utf-8")) == before


def test_broken_working_copies_are_repaired_with_warning(tmp_path) -> None:
    symbols_path, competences_path = tmp_path / "symbols.json", tmp_path / "competences.json"
    symbols_path.write_text("{kaputt", encoding="utf-8")
    _write(competences_path, {"competences": "keine Liste"})

    result = load_catalog(symbols_path, competences_path)

    assert result.symbols and result.competences
    assert "Symbol-Konfiguration" in result.warning and "Kompetenz-Konfiguration" in result.warning


@pytest.mark.parametrize("which", ["symbols", "competences"])
def test_defaults_file_is_never_used_as_working_copy(tmp_path, which: str) -> None:
    paths = {"symbols": tmp_path / "symbols.json", "competences": tmp_path / "competences.json"}
    paths[which] = DEFAULT_SYMBOLS_PATH if which == "symbols" else DEFAULT_COMPETENCES_PATH
    with pytest.raises(ValueError):
        load_catalog(paths["symbols"], paths["competences"])


def test_file_without_valid_entries_falls_back_to_defaults(tmp_path) -> None:
    competences_path = tmp_path / "competences.json"
    _write(competences_path, {"competences": [{"id": "ohne-stufen"}], "known_builtin_competence_ids": ALL_COMPETENCES_KNOWN})

    result = load_catalog(tmp_path / "symbols.json", competences_path)

    assert {c.id for c in result.competences} == set(ALL_COMPETENCES_KNOWN)
    assert "Kompetenz-Konfiguration ohne gültige Einträge" in result.warning
