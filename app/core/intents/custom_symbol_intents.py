from __future__ import annotations

from dataclasses import dataclass

from app.core.intents.base import Intent


@dataclass(frozen=True)
class AddCustomSymbolIntent(Intent):
    """Legt ein neues eigenes Doku-Symbol im aktuellen Plan an."""

    glyph: str
    meaning: str
    shortcut: str


@dataclass(frozen=True)
class UpdateCustomSymbolIntent(Intent):
    """Ändert Glyph, Bedeutung und/oder Tastenkürzel eines bestehenden eigenen Symbols."""

    symbol_id: str
    glyph: str
    meaning: str
    shortcut: str


@dataclass(frozen=True)
class DeleteCustomSymbolIntent(Intent):
    """Entfernt ein eigenes Symbol aus dem aktuellen Katalog (historische Dokudaten bleiben erhalten)."""

    symbol_id: str
