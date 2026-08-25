"""Validierung für pro-Plan eigene Doku-Symbole: Tastaturkürzel und Glyph.

Beide Prüfungen sind reine, GUI-unabhängige Funktionen — der einzige Ort, an
dem die jeweiligen Regeln definiert sind. Sowohl der GUI-Add/Edit-Dialog
(sofortige Fehlermeldung) als auch die Usecases
(``app/core/usecases/v4/custom_symbol_usecases.py``, verbindliche letzte
Instanz) rufen ausschließlich diese Funktionen auf — es gibt kein zweites,
abweichendes Regelwerk.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable


class CustomSymbolValidationError(Exception):
    """Basisklasse für alle Validierungsfehler eigener Doku-Symbole."""


class InvalidShortcutError(CustomSymbolValidationError):
    """Das angegebene Tastaturkürzel entspricht nicht der geforderten Form oder ist bereits belegt."""


class InvalidGlyphError(CustomSymbolValidationError):
    """Der angegebene Glyph ist kein einzelnes sichtbares Zeichen/Grapheme-Cluster."""


# Bereits in app/adapters/gui/_mixin_shortcuts.py fest gebundene
# Ctrl+Shift+<Buchstabe>-Systemshortcuts (Dokuansicht-Toggle [D], Runtime-Debug
# [R], Offline-Toggle [O], Doku-Symbol setzen [S], Dokudatum umbenennen [U],
# Notenspalte hinzufügen [N]). Einzige Quelle der Wahrheit für diese sechs
# Buchstaben -- _mixin_shortcuts.py importiert dieselbe Konstante, statt sie
# zu duplizieren, sowohl für die Validierung hier als auch um daraus den
# freien Buchstabenraum für die generische Custom-Symbol-Bindung abzuleiten.
RESERVED_CTRL_SHIFT_LETTERS = frozenset({"D", "R", "O", "S", "U", "N"})

_SHORTCUT_PATTERN = re.compile(r"^Ctrl\+Shift\+([A-Za-z])$")


def validate_custom_symbol_shortcut(raw: str, other_shortcuts: Iterable[str] = ()) -> str:
    """Validiert und normalisiert *raw* auf die kanonische Form ``"Ctrl+Shift+<GROSSBUCHSTABE>"``.

    Bewusst sehr eng gefasst (Nutzerwunsch: lieber zu streng als zu lax) —
    erlaubt ausschließlich exakt "Ctrl+Shift+" gefolgt von genau einem
    Buchstaben, unabhängig von Groß-/Kleinschreibung und umgebenden/inneren
    Leerzeichen (z. B. ``"ctrl+shift+t"``, ``"CTRL + SHIFT + T"`` und
    ``" Ctrl+Shift+T "`` normalisieren alle zu ``"Ctrl+Shift+T"``). Ctrl+Alt
    wird bewusst NICHT unterstützt, weil es auf deutschen Tastaturen physisch
    AltGr entspricht und dadurch konfliktanfällig ist (siehe
    ``docs/DEVELOPMENT_LOG.md``, Eintrag zum Symbolfilter-Shortcut). Ziffern,
    Sonderzeichen und mehrstellige Tastenfolgen werden ebenfalls abgelehnt.

    Prüft danach gegen ``RESERVED_CTRL_SHIFT_LETTERS`` (fest im Code
    gebundene System-Tastenkürzel) sowie gegen *other_shortcuts* (bereits
    vergebene Shortcuts anderer eigener Symbole desselben Plans, in
    kanonischer Form erwartet).

    Args:
        raw: Rohe Nutzereingabe.
        other_shortcuts: Bereits vergebene Shortcuts (kanonische Form), gegen
            die zusätzlich auf Kollision geprüft wird — beim Bearbeiten eines
            bestehenden Symbols schließt der Aufrufer dessen eigenen
            aktuellen Shortcut aus dieser Menge aus.

    Returns:
        Kanonische Form, z. B. ``"Ctrl+Shift+T"``.

    Raises:
        InvalidShortcutError: Bei jeder Abweichung von der geforderten Form
            oder bei einer Kollision, mit einem konkreten Grund im Fehlertext.
    """
    normalized = re.sub(r"\s+", "", str(raw or "")).title()
    match = _SHORTCUT_PATTERN.fullmatch(normalized)
    if match is None:
        raise InvalidShortcutError(
            f"Ungültiges Tastaturkürzel: '{raw}'. Erlaubt ist ausschließlich die Form "
            f"'Ctrl+Shift+<Buchstabe>' (z. B. 'Ctrl+Shift+T')."
        )

    letter = match.group(1).upper()
    canonical = f"Ctrl+Shift+{letter}"

    if letter in RESERVED_CTRL_SHIFT_LETTERS:
        raise InvalidShortcutError(f"'{canonical}' ist bereits als System-Tastenkürzel belegt.")
    if canonical in set(other_shortcuts):
        raise InvalidShortcutError(f"'{canonical}' wird bereits von einem anderen eigenen Symbol dieses Plans verwendet.")

    return canonical


_ZWJ = chr(0x200D)  # ZERO WIDTH JOINER
_VARIATION_SELECTORS = frozenset({chr(0xFE0E), chr(0xFE0F)})  # TEXT/EMOJI VARIATION SELECTOR
_SKIN_TONE_MODIFIERS = frozenset(chr(cp) for cp in range(0x1F3FB, 0x1F400))
_REGIONAL_INDICATORS = frozenset(chr(cp) for cp in range(0x1F1E6, 0x1F200))


def validate_custom_symbol_glyph(raw: str) -> str:
    """Prüft, dass *raw* nach dem Trimmen genau EIN sichtbares Zeichen bzw. Unicode-Grapheme-Cluster ist.

    Pragmatische, rein auf der Python-Standardbibliothek (``unicodedata``)
    basierende Heuristik — kein vollständiges UAX#29-Grapheme-Cluster-
    Segmentieren (dafür bräuchte es das Drittanbieter-Paket ``regex`` mit
    seinem ``\\X``-Muster, eine neue Laufzeitabhängigkeit für einen
    begrenzten Bedarf, die hier bewusst vermieden wird). Deckt den
    realistischen Eingabebereich ab:

    - ein einzelner Buchstabe/eine einzelne Ziffer/ein einzelnes Symbol,
    - ein Basiszeichen mit kombinierenden Akzentzeichen (``unicodedata.combining``),
    - ein Emoji mit Variationsselektor (``U+FE0E``/``U+FE0F``),
    - ein hautton-modifiziertes Emoji (``U+1F3FB``–``U+1F3FF``),
    - eine ZWJ-Sequenz wie Familien-Emoji (Basis, dann abwechselnd
      Zero-Width-Joiner + neues Basiszeichen),
    - ein Länderflaggen-Emoji (genau zwei Regional-Indicator-Symbole,
      ``U+1F1E6``–``U+1F1FF``).

    Lehnt ab: leere/nur-Leerzeichen-Eingabe, Steuerzeichen, mehrere
    unabhängige Zeichen hintereinander (z. B. zwei getrennte Emoji), sowie
    einen mit offenem ZWJ endenden String.

    Args:
        raw: Rohe Nutzereingabe für das Glyph-Feld.

    Returns:
        Die getrimmte Eingabe *raw*, unverändert (keine Normalisierung nötig
        — anders als beim Shortcut gibt es hier keine kanonische Groß-/
        Kleinschreibung).

    Raises:
        InvalidGlyphError: Bei jeder der oben genannten Ablehnungsbedingungen,
            mit einem konkreten Grund im Fehlertext.
    """
    text = str(raw or "").strip()
    if not text:
        raise InvalidGlyphError("Bitte ein Symbol (Zeichen oder Emoji) angeben.")
    if any(unicodedata.category(c) == "Cc" or c.isspace() for c in text):
        raise InvalidGlyphError(f"'{raw}' enthält Steuerzeichen oder Leerzeichen — das ist kein einzelnes Symbol.")

    chars = list(text)

    if len(chars) == 2 and all(c in _REGIONAL_INDICATORS for c in chars):
        return text

    first = chars[0]
    if (
        unicodedata.combining(first)
        or first in _VARIATION_SELECTORS
        or first == _ZWJ
        or first in _SKIN_TONE_MODIFIERS
        or first in _REGIONAL_INDICATORS
    ):
        raise InvalidGlyphError(f"'{raw}' beginnt nicht mit einem eigenständigen Basiszeichen.")

    index = 1
    pending_zwj = False
    while index < len(chars):
        c = chars[index]
        if pending_zwj:
            # Nach einem ZWJ muss ein neues Basiszeichen folgen; wird hier nicht
            # rekursiv erneut auf Modifier geprueft (pragmatische Heuristik).
            pending_zwj = False
            index += 1
            continue
        if unicodedata.combining(c) or c in _VARIATION_SELECTORS or c in _SKIN_TONE_MODIFIERS:
            index += 1
            continue
        if c == _ZWJ:
            pending_zwj = True
            index += 1
            continue
        raise InvalidGlyphError(f"'{raw}' enthält mehr als ein sichtbares Zeichen.")

    if pending_zwj:
        raise InvalidGlyphError(f"'{raw}' endet mit einem unvollständigen Zeichen-Verbund (offenes ZWJ).")

    return text
