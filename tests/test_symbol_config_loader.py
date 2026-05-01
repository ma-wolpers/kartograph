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
