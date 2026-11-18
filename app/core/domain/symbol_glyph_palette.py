# line-limit: data-only
"""Kuratierte Glyph-Auswahl für neue programmweite Symbole (Dialog „Symbole und Kompetenzen“).

Jedes Zeichen steckt in Segoe UI Symbol (``seguisym.ttf``) — der einzigen
Symbolschrift des PDF-Exports — und ist disjunkt zu allen eingebauten
Standardsymbolen (sonst könnte ein selbst angelegtes Symbol ein später
mitgeliefertes blockieren, weil der Katalog-Abgleich über den Codepoint läuft).
Beides prüft ``tests/test_default_catalog_integrity.py``.
"""

from __future__ import annotations

GLYPH_PALETTE: tuple[tuple[str, str], ...] = (
    ("2605", "Stern"),
    ("1F31F", "Leuchtender Stern"),
    ("1F3C6", "Pokal"),
    ("1F44D", "Daumen hoch"),
    ("1F4AA", "Bizeps"),
    ("270B", "Hand"),
    ("1F440", "Augen"),
    ("1F4AC", "Sprechblase"),
    ("1F4A1", "Glühbirne"),
    ("1F50D", "Lupe"),
    ("1F4D6", "Offenes Buch"),
    ("1F4DD", "Notiz"),
    ("270E", "Bleistift"),
    ("2702", "Schere"),
    ("1F3A8", "Farbpalette"),
    ("1F3B5", "Note"),
    ("1F3C3", "Läufer"),
    ("1F422", "Schildkröte"),
    ("1F680", "Rakete"),
    ("1F331", "Keimling"),
    ("1F308", "Regenbogen"),
    ("2600", "Sonne"),
    ("2601", "Wolke"),
    ("2744", "Schneeflocke"),
    ("2665", "Herz"),
    ("2663", "Kreuz"),
    ("2660", "Pik"),
    ("1F3B2", "Würfel"),
    ("2691", "Fahne"),
    ("1F4CC", "Pinnnadel"),
    ("1F514", "Glocke"),
    ("23F0", "Wecker"),
    ("231B", "Sanduhr"),
    ("2699", "Zahnrad"),
    ("26A0", "Warnung"),
    ("2615", "Tasse"),
    ("260E", "Telefon"),
    ("2708", "Flugzeug"),
    ("2709", "Brief"),
)
"""``(Codepoint in Hex, Beschriftung)`` in Anzeigereihenfolge."""
