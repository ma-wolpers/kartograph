from __future__ import annotations

import json

from app.infrastructure.symbol_config_loader import load_symbol_definitions


def test_symbol_loader_defaults_to_diagnostic_role(tmp_path) -> None:
    path = tmp_path / "symbols.json"
    path.write_text(
        json.dumps(
            {
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
