from __future__ import annotations


class RectSelection:
    """Rechteckige Zellauswahl zwischen Anker- und Fokuszelle (wie bei Shift-Klick)."""

    def __init__(self, x: int = 0, y: int = 0):
        self.anchor_x = x
        self.anchor_y = y
        self.focus_x = x
        self.focus_y = y

    def set_single(self, x: int, y: int) -> None:
        """Setzt Anker und Fokus auf dieselbe Zelle (Auswahl aus genau einer Zelle).

        Args:
            x: X-Rasterkoordinate der neuen Auswahlzelle.
            y: Y-Rasterkoordinate der neuen Auswahlzelle.
        """
        self.anchor_x = x
        self.anchor_y = y
        self.focus_x = x
        self.focus_y = y

    def set_focus(self, x: int, y: int) -> None:
        """Verschiebt die Fokuszelle, ohne den Anker zu verändern (z. B. bei Shift-Klick).

        Args:
            x: X-Rasterkoordinate der neuen Fokuszelle.
            y: Y-Rasterkoordinate der neuen Fokuszelle.
        """
        self.focus_x = x
        self.focus_y = y

    def collapse_to_anchor(self) -> None:
        """Zieht den Fokus zurück auf den Anker und reduziert die Auswahl auf eine Zelle."""
        self.focus_x = self.anchor_x
        self.focus_y = self.anchor_y

    def is_single(self) -> bool:
        """Prüft, ob Anker und Fokus identisch sind (Auswahl aus genau einer Zelle)."""
        return self.anchor_x == self.focus_x and self.anchor_y == self.focus_y

    def active_cell(self) -> tuple[int, int]:
        """Gibt die Koordinaten der Fokuszelle zurück."""
        return self.focus_x, self.focus_y

    def anchor_cell(self) -> tuple[int, int]:
        """Gibt die Koordinaten der Ankerzelle zurück."""
        return self.anchor_x, self.anchor_y

    def bounds(self) -> tuple[int, int, int, int]:
        """Berechnet die Bounding-Box der Auswahl als (min_x, min_y, max_x, max_y)."""
        min_x = min(self.anchor_x, self.focus_x)
        max_x = max(self.anchor_x, self.focus_x)
        min_y = min(self.anchor_y, self.focus_y)
        max_y = max(self.anchor_y, self.focus_y)
        return min_x, min_y, max_x, max_y

    def cells(self) -> list[tuple[int, int]]:
        """Gibt alle (x, y)-Koordinaten innerhalb der Auswahl-Bounding-Box zurück."""
        min_x, min_y, max_x, max_y = self.bounds()
        values: list[tuple[int, int]] = []
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                values.append((x, y))
        return values
