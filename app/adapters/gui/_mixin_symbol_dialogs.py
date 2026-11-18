"""Bündel der Symbol-Dialoge: programmweiter Katalog und Plan-Anpassung.

Fasst die Mixins des Fensters „Symbole und Kompetenzen“ und des Formulars
„Für diesen Plan anpassen“ zu einer Basisklasse zusammen, damit das
Hauptfenster (nahe am Zeilenlimit) nur eine Basis aufnimmt.
"""

from __future__ import annotations

from app.adapters.gui._mixin_catalog_competence_form import CatalogCompetenceFormMixin
from app.adapters.gui._mixin_catalog_dialog import CatalogDialogMixin
from app.adapters.gui._mixin_catalog_symbol_form import CatalogSymbolFormMixin
from app.adapters.gui._mixin_symbol_override_form import SymbolOverrideFormMixin


class SymbolDialogsMixin(CatalogDialogMixin, CatalogSymbolFormMixin, CatalogCompetenceFormMixin, SymbolOverrideFormMixin):
    """Mixin-Bündel: alle Dialoge rund um Symbole, Kompetenzen und Plan-Anpassungen."""
