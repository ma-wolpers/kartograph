from __future__ import annotations

import json

from app.infrastructure.symbol_config_loader import DEFAULT_SYMBOLS_PATH, load_symbol_definitions

# Testdateien, die alle eingebauten Symbole schon "kennen" -- sonst ergänzt der
# Loader sie (gewolltes Verhalten, eigens getestet in test_merge_*).
ALL_BUILTINS_KNOWN = sorted(
    f"{int(item['codepoint'], 16):04X}"
    for item in json.loads(DEFAULT_SYMBOLS_PATH.read_text(encoding="utf-8"))["symbols"]
)


def test_symbol_loader_defaults_to_diagnostic_role(tmp_path) -> None:
    path = tmp_path / "symbols.json"
    path.write_text(
        json.dumps(
            {
                "known_builtin_codepoints": ALL_BUILTINS_KNOWN,
                "symbols": [
                    {
                        "codepoint": "1F446",
                        "meaning": "Beteiligung",
                        "shortcut": "b",
                        "legend": {
                            "three": "a",
                            "two": "b",
                            "one": "c",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    symbols, warning = load_symbol_definitions(path)

    assert warning is None
    assert len(symbols) == 1
    assert symbols[0].role == "diagnostic"


def test_symbol_loader_reads_documentation_only_role(tmp_path) -> None:
    path = tmp_path / "symbols.json"
    path.write_text(
        json.dumps(
            {
                "known_builtin_codepoints": ALL_BUILTINS_KNOWN,
                "symbols": [
                    {
                        "codepoint": "2205",
                        "meaning": "Abwesend",
                        "shortcut": "u",
                        "role": "documentation_only",
                        "legend": {
                            "three": "a",
                            "two": "b",
                            "one": "c",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    symbols, warning = load_symbol_definitions(path)

    assert warning is None
    assert len(symbols) == 1
    assert symbols[0].role == "documentation_only"


def test_symbol_loader_preserves_space_shortcut_sentinel(tmp_path) -> None:
    """Regression: _parse_shortcut() verwarf frueher jeden Shortcut-Wert mit mehr
    als einem Zeichen -- damit ging "space" beim Laden auf None verloren und die
    Leertaste liess sich fuer kein Symbol mehr ausloesen (SPACE_SHORTCUT muss den
    Ladevorgang unveraendert ueberstehen)."""
    path = tmp_path / "symbols.json"
    path.write_text(
        json.dumps(
            {
                "known_builtin_codepoints": ALL_BUILTINS_KNOWN,
                "symbols": [
                    {
                        "codepoint": "2205",
                        "meaning": "Abwesend",
                        "shortcut": "space",
                        "role": "documentation_only",
                        "legend": {"three": "a", "two": "b", "one": "c"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    symbols, warning = load_symbol_definitions(path)

    assert warning is None
    assert len(symbols) == 1
    assert symbols[0].shortcut == "space"


def test_symbol_loader_rejects_other_multi_character_shortcuts(tmp_path) -> None:
    """Nur der bekannte Sentinel "space" ist als Mehrzeichen-Shortcut erlaubt --
    ein anderer mehrstelliger Wert wird weiterhin auf None normalisiert."""
    path = tmp_path / "symbols.json"
    path.write_text(
        json.dumps(
            {
                "known_builtin_codepoints": ALL_BUILTINS_KNOWN,
                "symbols": [
                    {
                        "codepoint": "1F446",
                        "meaning": "Beteiligung",
                        "shortcut": "xyz",
                        "legend": {"three": "a", "two": "b", "one": "c"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    symbols, _warning = load_symbol_definitions(path)

    assert symbols[0].shortcut is None


def _write(path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _entry(codepoint: str, meaning: str, shortcut: str | None) -> dict:
    return {"codepoint": codepoint, "meaning": meaning, "shortcut": shortcut, "legend": {"three": "a", "two": "b", "one": "c"}}


def test_missing_file_is_created_from_defaults_with_new_symbols(tmp_path) -> None:
    path = tmp_path / "symbols.json"
    symbols, warning = load_symbol_definitions(path)
    meanings = {s.meaning for s in symbols}
    assert {"Abgabe vollständig", "Abgabe lückenhaft", "Nicht abgegeben / verweigert"} <= meanings
    assert json.loads(path.read_text(encoding="utf-8"))["known_builtin_codepoints"] == ALL_BUILTINS_KNOWN


def test_merge_adds_new_builtins_without_touching_own_edits(tmp_path) -> None:
    """Alte Arbeitskopie ohne known-Liste: vorhandene Einträge bleiben, Neues wird ergänzt."""
    path = tmp_path / "symbols.json"
    own_x = _entry("0058", "Mein eigener Text für X", "x")
    _write(path, {"symbols": [own_x]})

    symbols, _warning = load_symbol_definitions(path)

    by_glyph = {s.glyph: s for s in symbols}
    assert by_glyph["X"].meaning == "Mein eigener Text für X"
    assert by_glyph["✓"].shortcut == "e"
    assert by_glyph["◐"].shortcut == "l"


def test_merge_does_not_resurrect_deleted_builtins(tmp_path) -> None:
    path = tmp_path / "symbols.json"
    _write(path, {"known_builtin_codepoints": ALL_BUILTINS_KNOWN, "symbols": [_entry("0058", "X", "x")]})

    symbols, _warning = load_symbol_definitions(path)

    assert [s.glyph for s in symbols] == ["X"]


def test_merge_drops_conflicting_shortcut_and_warns(tmp_path) -> None:
    path = tmp_path / "symbols.json"
    known = [c for c in ALL_BUILTINS_KNOWN if c != "2713"]
    _write(path, {"known_builtin_codepoints": known, "symbols": [_entry("1F600", "Eigenes", "e")]})

    symbols, warning = load_symbol_definitions(path)

    complete = next(s for s in symbols if s.glyph == "✓")
    assert complete.shortcut is None
    assert warning is not None and "Abgabe vollständig" in warning


def test_merge_is_idempotent(tmp_path) -> None:
    path = tmp_path / "symbols.json"
    load_symbol_definitions(path)
    before = path.read_text(encoding="utf-8")
    load_symbol_definitions(path)
    assert path.read_text(encoding="utf-8") == before


def test_defaults_file_is_never_used_as_working_copy() -> None:
    import pytest

    with pytest.raises(ValueError):
        load_symbol_definitions(DEFAULT_SYMBOLS_PATH)
