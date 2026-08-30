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
from typing import Iterable, Protocol


class CustomSymbolValidationError(Exception):
    """Basisklasse für alle Validierungsfehler eigener Doku-Symbole."""


class InvalidShortcutError(CustomSymbolValidationError):
    """Das angegebene Tastaturkürzel entspricht nicht der geforderten Form oder ist bereits belegt."""


class InvalidGlyphError(CustomSymbolValidationError):
    """Der angegebene Glyph ist kein einzelnes sichtbares Zeichen/Grapheme-Cluster."""


class InvalidMeaningError(CustomSymbolValidationError):
    """Die angegebene Bedeutung ist (nach dem Trimmen) leer."""


class _HasShortcut(Protocol):
    """Struktureller Vertrag für ``reserved_symbol_letters()`` — nur ``.shortcut`` wird gebraucht.

    Erfüllt sowohl von ``app.infrastructure.symbol_config_loader.SymbolDefinition``
    als auch von jedem anderen Objekt mit einem ``shortcut``-Attribut, ohne
    dass ``app/core`` von ``app/infrastructure`` importieren muss.
    """

    shortcut: str | None


# Fest verdrahtete Einzelbuchstaben-Shortcuts, die NICHT Teil des konfigurierbaren
# Symbolkatalogs sind (Mitarbeit-Bewertung "o"/"s", Tischsymbol-Dialog "d" — alle in
# app/adapters/gui/_mixin_shortcuts.py). Einzige Quelle der Wahrheit für diese drei
# Buchstaben; reserved_symbol_letters() vereinigt sie mit den (konfigurierbaren)
# eingebauten Symbol-Shortcuts aus config/symbols.json zur vollständigen Sperrliste.
RESERVED_SYMBOL_LETTERS = frozenset({"O", "S", "D"})

_SHORTCUT_PATTERN = re.compile(r"^[A-Za-z]$")


def reserved_symbol_letters(symbol_definitions: Iterable[_HasShortcut]) -> frozenset[str]:
    """Vereinigt konfigurierbare eingebaute Symbol-Shortcuts mit den festen System-Buchstaben.

    Einzige Stelle im gesamten Projekt, an der beide Quellen zusammengeführt
    werden — Validierung (über den ``reserved_letters``-Parameter unten),
    GUI-Bindung (``app/adapters/gui/_mixin_shortcuts.py::_bind_shortcuts()``)
    und das Anlage-/Bearbeiten-Formular
    (``app/adapters/gui/_mixin_symbol_management_form.py``) rufen
    ausschließlich diese Funktion auf, statt die Vereinigung jeweils selbst
    zu bilden. Da eingebaute Shortcuts über ``config/symbols.json``
    konfigurierbar sind, kann diese Menge nicht als feste Konstante
    vorgehalten werden — sie muss bei jedem Aufruf aus dem aktuellen Katalog
    neu gebildet werden.

    Berücksichtigt nur echte Einzelbuchstaben-Kürzel — ein eingebautes Symbol
    kann auch einen technischen Mehrzeichen-Shortcut wie ``"space"`` tragen
    (Sondertasten, s. ``main_window_constants.SPACE_SHORTCUT``); ein solcher
    String würde ohnehin nie mit dem Einzelbuchstaben-Regex eines eigenen
    Symbol-Kürzels kollidieren, soll aber erst gar nicht in einer als
    "gesperrte Buchstaben" dokumentierten Menge auftauchen.

    Args:
        symbol_definitions: Der aktuelle, app-weite Symbolkatalog (aus
            ``AppState.symbol_catalog``).

    Returns:
        Menge aller für eigene Symbol-Shortcuts gesperrten Großbuchstaben.
    """
    return frozenset(
        d.shortcut.upper() for d in symbol_definitions if d.shortcut and len(d.shortcut) == 1
    ) | RESERVED_SYMBOL_LETTERS


def validate_custom_symbol_shortcut(
    raw: str,
    other_shortcuts: Iterable[str] = (),
    reserved_letters: Iterable[str] = frozenset(),
) -> str:
    """Validiert und normalisiert *raw* auf einen einzelnen kanonischen Großbuchstaben.

    Bewusst sehr eng gefasst (Nutzerwunsch: lieber zu streng als zu lax) —
    erlaubt ausschließlich genau einen Buchstaben, unabhängig von
    Groß-/Kleinschreibung und umgebenden Leerzeichen (z. B. ``"l"``,
    ``" L "`` normalisieren beide zu ``"L"``). Ziffern, Sonderzeichen und
    mehrstellige Eingaben werden abgelehnt.

    Prüft danach gegen *reserved_letters* (typischerweise das Ergebnis von
    ``reserved_symbol_letters()`` — System- und eingebaute Symbol-Buchstaben)
    sowie gegen *other_shortcuts* (bereits vergebene Shortcuts anderer
    eigener Symbole desselben Plans, in kanonischer Form erwartet).

    Args:
        raw: Rohe Nutzereingabe.
        other_shortcuts: Bereits vergebene Shortcuts (kanonische Form), gegen
            die zusätzlich auf Kollision geprüft wird — beim Bearbeiten eines
            bestehenden Symbols schließt der Aufrufer dessen eigenen
            aktuellen Shortcut aus dieser Menge aus.
        reserved_letters: Aktuell gesperrte Buchstaben (System-Shortcuts plus
            eingebaute Symbol-Shortcuts), typischerweise via
            ``reserved_symbol_letters()`` ermittelt.

    Returns:
        Kanonische Form: ein einzelner Großbuchstabe, z. B. ``"L"``.

    Raises:
        InvalidShortcutError: Bei jeder Abweichung von der geforderten Form
            oder bei einer Kollision, mit einem konkreten Grund im Fehlertext.
    """
    normalized = re.sub(r"\s+", "", str(raw or "")).upper()
    match = _SHORTCUT_PATTERN.fullmatch(normalized)
    if match is None:
        raise InvalidShortcutError(
            f"Ungültiges Tastaturkürzel: '{raw}'. Erlaubt ist ausschließlich ein einzelner Buchstabe (z. B. 'L')."
        )

    letter = normalized
    reserved = frozenset(reserved_letters)
    if letter in reserved:
        raise InvalidShortcutError(f"'{letter}' ist bereits als Tastenkürzel belegt.")
    if letter in set(other_shortcuts):
        raise InvalidShortcutError(f"'{letter}' wird bereits von einem anderen eigenen Symbol dieses Plans verwendet.")

    return letter


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


def validate_custom_symbol_meaning(raw: str) -> str:
    """Prüft, dass *raw* nach dem Trimmen nicht leer ist.

    Bewusst minimal: keine Längenbeschränkung, keine Eindeutigkeitsprüfung
    gegen andere Symbole — die Identität eines eigenen Symbols ist seine
    ``id`` (siehe ``CustomSymbolDefinition``-Docstring), nicht der
    Bedeutungstext, daher müssen zwei Symbole nicht unterschiedlich heißen.
    Eine leere Bedeutung ist aber kein sinnvoll anzeigbares Symbol.

    Args:
        raw: Rohe Nutzereingabe für das Bedeutungsfeld.

    Returns:
        Die getrimmte Bedeutung.

    Raises:
        InvalidMeaningError: Wenn *raw* nach dem Trimmen leer ist.
    """
    text = str(raw or "").strip()
    if not text:
        raise InvalidMeaningError("Bitte eine Bedeutung angeben.")
    return text
