from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SymbolDefinition:
    meaning: str
    glyph: str
    legend_one: str
    legend_two: str
    legend_three: str

    def legend_for_count(self, count: int) -> str:
        if count >= 3:
            return self.legend_three
        if count == 2:
            return self.legend_two
        return self.legend_one


_DEFAULT_SYMBOLS_PAYLOAD = {
    "symbols": [
        {
            "codepoint": "1F4BB",
            "meaning": "Laptop",
            "legend": {
                "three": "arbeitet durchgaengig digital",
                "two": "arbeitet phasenweise digital",
                "one": "braucht digitales Material",
            },
        },
        {
            "codepoint": "1F4F1",
            "meaning": "Tablet",
            "legend": {
                "three": "arbeitet sicher am Tablet",
                "two": "arbeitet meist sicher am Tablet",
                "one": "braucht Unterstuetzung am Tablet",
            },
        },
        {
            "codepoint": "2757",
            "meaning": "Beteiligung",
            "legend": {
                "three": "meldet sich sehr haeufig",
                "two": "meldet sich regelmaessig",
                "one": "meldet sich gelegentlich",
            },
        },
    ]
}


def _write_default_payload(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_DEFAULT_SYMBOLS_PAYLOAD, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_codepoint(raw_value: object) -> str | None:
    text = str(raw_value or "").strip().upper()
    if text.startswith("U+"):
        text = text[2:]
    if not text:
        return None
    try:
        return chr(int(text, 16))
    except (TypeError, ValueError):
        return None


def load_symbol_definitions(path: Path) -> tuple[list[SymbolDefinition], str | None]:
    if not path.exists():
        _write_default_payload(path)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _write_default_payload(path)
        payload = _DEFAULT_SYMBOLS_PAYLOAD
        warning = f"Symbol-Konfiguration ist ungueltig; Standardwerte wurden nach {path} geschrieben."
    else:
        warning = None

    symbols_raw = payload.get("symbols") if isinstance(payload, dict) else None
    if not isinstance(symbols_raw, list):
        _write_default_payload(path)
        symbols_raw = _DEFAULT_SYMBOLS_PAYLOAD["symbols"]
        warning = f"Symbol-Konfiguration hat kein gueltiges 'symbols'-Array; Standardwerte wurden nach {path} geschrieben."

    definitions: list[SymbolDefinition] = []
    for item in symbols_raw:
        if not isinstance(item, dict):
            continue

        meaning = str(item.get("meaning") or "").strip()
        glyph = _parse_codepoint(item.get("codepoint"))
        legend = item.get("legend")
        if not meaning or glyph is None or not isinstance(legend, dict):
            continue

        one = str(legend.get("one") or "").strip()
        two = str(legend.get("two") or "").strip()
        three = str(legend.get("three") or "").strip()
        if not one or not two or not three:
            continue

        definitions.append(
            SymbolDefinition(
                meaning=meaning,
                glyph=glyph,
                legend_one=one,
                legend_two=two,
                legend_three=three,
            )
        )

    if not definitions:
        _write_default_payload(path)
        fallback_defs, _ = load_symbol_definitions(path)
        return fallback_defs, f"Keine gueltigen Symbole gefunden; Standardwerte wurden nach {path} geschrieben."

    return definitions, warning
