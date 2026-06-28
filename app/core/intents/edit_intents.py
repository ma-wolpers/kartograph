from __future__ import annotations

from dataclasses import dataclass

from app.core.intents.base import Intent


@dataclass(frozen=True)
class UndoIntent(Intent):
    """Macht die letzte(n) aufgezeichnete(n) Planänderung(en) rückgängig.

    Args:
        steps: Anzahl der rückgängig zu machenden Schritte (>= 1).
    """

    steps: int = 1


@dataclass(frozen=True)
class RedoIntent(Intent):
    """Stellt die zuletzt rückgängig gemachte(n) Änderung(en) wieder her.

    Args:
        steps: Anzahl der wiederherzustellenden Schritte (>= 1).
    """

    steps: int = 1


@dataclass(frozen=True)
class CopySelectionIntent(Intent):
    """Kopiert alle Schüler in *cells* in die Zwischenablage (``StudentClipboard``).

    Verändert den Plan nicht. Schülerdaten (Name, Diagnoseprofil) werden erst
    beim nachfolgenden ``PasteSelectionIntent`` aus dem dann aktuellen Plan
    gelesen und unter einer frischen ``StudentId`` eingefügt — das Original
    bleibt unverändert an seinem Platz stehen, Dokumentationshistorie wird
    nicht mitkopiert (s. ``app/core/domain/student_clipboard.py``).

    Args:
        cells: Alle (x, y)-Rasterkoordinaten der aktuellen Selektion. Zellen
            ohne Schüler werden beim Einfügen ignoriert.
    """

    cells: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class CutSelectionIntent(Intent):
    """Markiert alle Schüler in *cells* zum Verschieben (``StudentClipboard``).

    Löscht beim Markieren **nichts** aus dem Plan — es wird nur vermerkt,
    welche Schüler ausgeschnitten wurden. Die tatsächliche Verschiebung
    (inkl. Beibehaltung von ``StudentId``, Diagnoseprofil, Tischgruppen-
    Mitgliedschaft und Dokumentationshistorie) passiert erst beim
    nachfolgenden ``PasteSelectionIntent``.

    Args:
        cells: Alle (x, y)-Rasterkoordinaten der aktuellen Selektion. Zellen
            ohne Schüler werden ignoriert.
    """

    cells: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class PasteSelectionIntent(Intent):
    """Fügt den Zwischenablage-Inhalt ab (*target_x*, *target_y*) in den Plan ein.

    Bezugspunkt ist die linke obere Ecke der ursprünglich kopierten/
    ausgeschnittenen Zellauswahl. Wirkungslos (keine Statusänderung außer der
    Statusmeldung), wenn die Zwischenablage leer ist.

    Args:
        target_x: X-Koordinate der Einfüge-Ankerzelle.
        target_y: Y-Koordinate der Einfüge-Ankerzelle.
    """

    target_x: int
    target_y: int
