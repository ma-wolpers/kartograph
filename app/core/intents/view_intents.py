from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.domain.settings import KartographSettings
from app.core.intents.base import Intent


@dataclass(frozen=True)
class SetEditorSurfaceIntent(Intent):
    """Wechselt im Editor explizit zur Raster- oder Dokumentations-Oberfläche (*surface*)."""

    surface: Literal["grid", "documentation"]


@dataclass(frozen=True)
class ToggleEditorSurfaceIntent(Intent):
    """Schaltet zwischen Raster- und Dokumentations-Oberfläche um."""


@dataclass(frozen=True)
class ZoomInIntent(Intent):
    """Vergrößert die Zellgröße im Raster um eine Stufe (geklemmt auf eine Obergrenze)."""


@dataclass(frozen=True)
class ZoomOutIntent(Intent):
    """Verkleinert die Zellgröße im Raster um eine Stufe (geklemmt auf eine Untergrenze)."""


@dataclass(frozen=True)
class ResetViewIntent(Intent):
    """Setzt die Zellgröße auf den Standardwert zurück (Auswahl/Viewport-Zentrierung sind GUI-seitig)."""


@dataclass(frozen=True)
class ExportPdfIntent(Intent):
    """Markiert einen abgeschlossenen PDF-Export.

    Reiner No-Op-Marker: Dateidialog und PDF-Schreiben sind Tk-/IO-
    Seiteneffekte ohne AppState-Wirkung; Dispatch dient nur der Konsistenz
    mit dem Intent-System (z. B. künftiges Makro-Recording).
    """


@dataclass(frozen=True)
class OpenSettingsIntent(Intent):
    """Lädt die persistierten Einstellungen frisch aus dem Settings-Repository in den AppState."""


@dataclass(frozen=True)
class UpdateSettingsIntent(Intent):
    """Ersetzt die persistierten Einstellungen vollständig durch *settings*."""

    settings: KartographSettings


@dataclass(frozen=True)
class OpenTablegroupSettingsIntent(Intent):
    """Markiert das Öffnen des Tischgruppen-Einstellungs-Overlays für Zelle (*x*, *y*).

    Reiner No-Op-Marker: das Overlay ist ein Tk-Toplevel-Seiteneffekt ohne
    AppState-Wirkung; Dispatch dient nur der Konsistenz mit dem
    Intent-System.
    """

    x: int
    y: int
