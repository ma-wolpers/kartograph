"""Viewport-Mixin für das Kartograph-Hauptfenster.

Stellt die Scroll-Handler des Sitzplan-Canvas bereit. Die Doku-Tabelle
(bw-gui ``DataGrid``) scrollt sich selbst.
"""

from __future__ import annotations


class ViewportMixin:
    """Mixin: Scroll-Handler für den Sitzplan-Canvas."""

    def _xview(self, *args) -> None:
        """Leitet horizontale Scroll-Befehle an den Canvas weiter und zeichnet das Raster neu.

        Args:
            *args: Tkinter-Scrollbar-Kommando-Argumente (z. B. ``"scroll", n, "units"``).
        """
        self.canvas.xview(*args)
        self._request_grid_redraw()

    def _yview(self, *args) -> None:
        """Leitet vertikale Scroll-Befehle an den Canvas weiter und zeichnet das Raster neu.

        Args:
            *args: Tkinter-Scrollbar-Kommando-Argumente (z. B. ``"scroll", n, "units"``).
        """
        self.canvas.yview(*args)
        self._request_grid_redraw()

    def _on_canvas_xscroll(self, first: str, last: str) -> None:
        """Aktualisiert die horizontale Scrollbar und zeichnet das Raster neu.

        Args:
            first: Obere Scrollbar-Grenze.
            last: Untere Scrollbar-Grenze.
        """
        self.x_scroll.set(first, last)
        self._request_grid_redraw()

    def _on_canvas_yscroll(self, first: str, last: str) -> None:
        """Aktualisiert die vertikale Scrollbar und zeichnet das Raster neu.

        Args:
            first: Obere Scrollbar-Grenze.
            last: Untere Scrollbar-Grenze.
        """
        self.y_scroll.set(first, last)
        self._request_grid_redraw()
