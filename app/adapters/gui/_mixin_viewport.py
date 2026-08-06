"""Viewport-Mixin für das Kartograph-Hauptfenster.

Stellt alle Scroll-Handler für Canvas und Dokumentations-Treeviews bereit:
horizontale und vertikale Scrollbefehle, synchronisiertes Docs-Scrolling
sowie die Initialisierung des Docs-Splitters.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import DOCS_HORIZONTAL_SCROLLBAR_UNITS, DOCS_HORIZONTAL_WHEEL_UNITS


class ViewportMixin:
    """Mixin: Scroll-Handler für Canvas, Docs-Treeview und Splitter."""

    def _xview(self, *args) -> None:
        """Leitet horizontale Scroll-Befehle an den Canvas weiter und zeichnet das Raster neu.

        Args:
            *args: Tkinter-Scrollbar-Kommando-Argumente (z. B. ``"scroll", n, "units"``).
        """
        self.canvas.xview(*args)
        self.redraw_grid()

    def _yview(self, *args) -> None:
        """Leitet vertikale Scroll-Befehle an den Canvas weiter und zeichnet das Raster neu.

        Args:
            *args: Tkinter-Scrollbar-Kommando-Argumente (z. B. ``"scroll", n, "units"``).
        """
        self.canvas.yview(*args)
        self.redraw_grid()

    def _docs_yview(self, *args) -> None:
        """Synchronisiert vertikales Scrollen beider Docs-Treeviews.

        Args:
            *args: Tkinter-Scrollbar-Kommando-Argumente (z. B. ``"scroll", n, "units"``).
        """
        self.docs_tree.yview(*args)
        self.docs_right_tree.yview(*args)

    def _position_docs_splitter_initial(self) -> None:
        """Setzt die Splitter-Position beim ersten Configure-Ereignis auf 68 % links."""
        if self._docs_splitter_positioned:
            return
        if not hasattr(self, "docs_splitter") or not self.docs_splitter.winfo_exists():
            return
        total_width = self.docs_splitter.winfo_width()
        if total_width <= 1:
            return
        left_width = max(320, min(total_width - 240, int(total_width * 0.68)))
        try:
            self.docs_splitter.sash_place(0, left_width, 0)
        except Exception:
            return
        self._docs_splitter_positioned = True

    def _docs_main_xview(self, *args) -> None:
        """Horizontaler Scroll-Handler für den linken Docs-Treeview mit Schritt-Multiplikator.

        Args:
            *args: Tkinter-Scrollbar-Kommando-Argumente (z. B. ``"scroll", n, "units"``).
        """
        if len(args) >= 3 and args[0] == "scroll" and str(args[2]) == "units":
            try:
                amount = int(float(args[1]))
            except (TypeError, ValueError):
                self.docs_tree.xview(*args)
            else:
                self.docs_tree.xview_scroll(amount * DOCS_HORIZONTAL_SCROLLBAR_UNITS, "units")
        else:
            self.docs_tree.xview(*args)
        self.after_idle(self._update_docs_cell_highlight)

    def _docs_right_xview(self, *args) -> None:
        """Horizontaler Scroll-Handler für den rechten Docs-Treeview mit Schritt-Multiplikator.

        Args:
            *args: Tkinter-Scrollbar-Kommando-Argumente (z. B. ``"scroll", n, "units"``).
        """
        if len(args) >= 3 and args[0] == "scroll" and str(args[2]) == "units":
            try:
                amount = int(float(args[1]))
            except (TypeError, ValueError):
                self.docs_right_tree.xview(*args)
            else:
                self.docs_right_tree.xview_scroll(amount * DOCS_HORIZONTAL_SCROLLBAR_UNITS, "units")
        else:
            self.docs_right_tree.xview(*args)
        self.after_idle(self._update_docs_cell_highlight)

    def _docs_horizontal_wheel_units(self, delta: int) -> int:
        """Berechnet die Scroll-Einheitenzahl aus einem MouseWheel-Delta.

        Args:
            delta: MouseWheel-Delta-Wert.

        Returns:
            Vorzeichenbehaftete Scroll-Einheitenanzahl.
        """
        direction = -1 if delta > 0 else 1
        steps = max(1, abs(int(delta)) // 120) if delta else 1
        return direction * steps * DOCS_HORIZONTAL_WHEEL_UNITS

    def _on_docs_shift_mouse_wheel(self, event) -> str:
        """Handler für Shift+MouseWheel: horizontales Scrollen im aktiven Docs-Treeview.

        Args:
            event: Tkinter-MouseWheel-Ereignis mit Ziel-Widget und Delta.
        """
        target = self.docs_right_tree if event.widget == self.docs_right_tree else self.docs_tree
        target.xview_scroll(self._docs_horizontal_wheel_units(getattr(event, "delta", 0)), "units")
        self.after_idle(self._update_docs_cell_highlight)
        return "break"

    def _on_docs_main_yscroll(self, first: str, last: str) -> None:
        """Synchronisiert den rechten Treeview wenn der linke vertikal gescrollt wird.

        Args:
            first: Obere Scrollbar-Grenze.
            last: Untere Scrollbar-Grenze.
        """
        self.docs_y_scroll.set(first, last)
        if self._syncing_docs_scroll:
            return
        self._syncing_docs_scroll = True
        try:
            self.docs_right_tree.yview_moveto(float(first))
        finally:
            self._syncing_docs_scroll = False

    def _on_docs_right_yscroll(self, first: str, last: str) -> None:
        """Synchronisiert den linken Treeview wenn der rechte vertikal gescrollt wird.

        Args:
            first: Obere Scrollbar-Grenze.
            last: Untere Scrollbar-Grenze.
        """
        self.docs_y_scroll.set(first, last)
        if self._syncing_docs_scroll:
            return
        self._syncing_docs_scroll = True
        try:
            self.docs_tree.yview_moveto(float(first))
        finally:
            self._syncing_docs_scroll = False

    def _on_canvas_xscroll(self, first: str, last: str) -> None:
        """Aktualisiert die horizontale Scrollbar und zeichnet das Raster neu.

        Args:
            first: Obere Scrollbar-Grenze.
            last: Untere Scrollbar-Grenze.
        """
        self.x_scroll.set(first, last)
        self.redraw_grid()

    def _on_canvas_yscroll(self, first: str, last: str) -> None:
        """Aktualisiert die vertikale Scrollbar und zeichnet das Raster neu.

        Args:
            first: Obere Scrollbar-Grenze.
            last: Untere Scrollbar-Grenze.
        """
        self.y_scroll.set(first, last)
        self.redraw_grid()
