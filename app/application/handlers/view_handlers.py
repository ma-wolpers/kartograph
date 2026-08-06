from __future__ import annotations

import dataclasses

from app.application.app_state import AppState, EditorSurface
from app.application.handler_context import HandlerContext
from app.core.domain.settings import KartographSettings
from app.core.intents.view_intents import (
    ExportPdfIntent,
    OpenSettingsIntent,
    OpenTablegroupSettingsIntent,
    ResetViewIntent,
    SetEditorSurfaceIntent,
    ToggleEditorSurfaceIntent,
    UpdateSettingsIntent,
    ZoomInIntent,
    ZoomOutIntent,
)

# Default/Grenzen als Literale dupliziert statt aus main_window_constants.py
# importiert (Core/Application darf nicht von der GUI abhaengen, s. settings.py).
DEFAULT_CELL_SIZE = 92
MIN_CELL_SIZE = 44
MAX_CELL_SIZE = 160
CELL_SIZE_STEP = 8


def handle_set_editor_surface(intent: SetEditorSurfaceIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Wechselt explizit zur Raster- oder Dokumentations-Oberfläche gemäß *intent.surface*.

    Args:
        intent: Zieloberfläche ("grid" oder "documentation").
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    surface = EditorSurface.DOCUMENTATION if intent.surface == "documentation" else EditorSurface.GRID
    return dataclasses.replace(state, editor_surface=surface)


def handle_toggle_editor_surface(intent: ToggleEditorSurfaceIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Schaltet zwischen Raster- und Dokumentations-Oberfläche um.

    Args:
        intent: Trägt keine Felder.
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    if state.editor_surface == EditorSurface.GRID:
        return dataclasses.replace(state, editor_surface=EditorSurface.DOCUMENTATION)
    return dataclasses.replace(state, editor_surface=EditorSurface.GRID)


def handle_zoom_in(intent: ZoomInIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Erhöht die Zellgröße um einen Schritt, geklemmt auf MAX_CELL_SIZE.

    Args:
        intent: Trägt keine Felder.
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    return dataclasses.replace(state, cell_size=min(MAX_CELL_SIZE, state.cell_size + CELL_SIZE_STEP))


def handle_zoom_out(intent: ZoomOutIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Verkleinert die Zellgröße um einen Schritt, geklemmt auf MIN_CELL_SIZE.

    Args:
        intent: Trägt keine Felder.
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    return dataclasses.replace(state, cell_size=max(MIN_CELL_SIZE, state.cell_size - CELL_SIZE_STEP))


def handle_reset_view(intent: ResetViewIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt die Zellgröße auf DEFAULT_CELL_SIZE zurück (Auswahl/Viewport-Zentrierung sind GUI-seitig).

    Args:
        intent: Trägt keine Felder.
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    return dataclasses.replace(state, cell_size=DEFAULT_CELL_SIZE)


# ExportPdfIntent/OpenTablegroupSettingsIntent sind bewusste No-Ops: PDF-Export
# (Dateidialog + Dateischreiben) und das Tischgruppen-Overlay (Toplevel-Fenster)
# sind reine Tk-/IO-Seiteneffekte ohne AppState-Wirkung. Dispatch dient hier nur
# der Konsistenz mit dem Intent-System (z. B. künftiges Makro-Recording, s.
# Architekturplan v2 Abschnitt 4.2) -- die GUI führt die eigentliche Aktion
# weiterhin selbst aus.

def handle_export_pdf(intent: ExportPdfIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """No-Op: PDF-Export hat keine AppState-Wirkung (s. Kommentar oben).

    Args:
        intent: Trägt keine Felder.
        state: Aktueller AppState (wird unverändert zurückgegeben).
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    return state


def handle_open_settings(intent: OpenSettingsIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Lädt die persistierten Einstellungen frisch aus dem Settings-Repository.

    Args:
        intent: Trägt keine Felder.
        state: Aktueller AppState.
        ctx: Handler-Kontext (liefert ``ctx.settings_repository``).
    """
    settings = KartographSettings.from_dict(ctx.settings_repository.load_settings())
    return dataclasses.replace(state, settings=settings)


def handle_update_settings(intent: UpdateSettingsIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Persistiert *intent.settings* und übernimmt sie in den AppState.

    Args:
        intent: Vollständige neue Einstellungen.
        state: Aktueller AppState.
        ctx: Handler-Kontext (liefert ``ctx.settings_repository``).
    """
    ctx.settings_repository.save_settings(intent.settings.to_dict())
    return dataclasses.replace(state, settings=intent.settings)


def handle_open_tablegroup_settings(
    intent: OpenTablegroupSettingsIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """No-Op: das Tischgruppen-Overlay hat keine AppState-Wirkung (s. Kommentar oben).

    Args:
        intent: Rasterkoordinaten der Zelle, auf die sich das Overlay bezieht.
        state: Aktueller AppState (wird unverändert zurückgegeben).
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    return state
