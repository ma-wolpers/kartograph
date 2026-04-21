from __future__ import annotations


class RectSelection:
    def __init__(self, x: int = 0, y: int = 0):
        self.anchor_x = x
        self.anchor_y = y
        self.focus_x = x
        self.focus_y = y

    def set_single(self, x: int, y: int) -> None:
        self.anchor_x = x
        self.anchor_y = y
        self.focus_x = x
        self.focus_y = y

    def set_focus(self, x: int, y: int) -> None:
        self.focus_x = x
        self.focus_y = y

    def collapse_to_anchor(self) -> None:
        self.focus_x = self.anchor_x
        self.focus_y = self.anchor_y

    def is_single(self) -> bool:
        return self.anchor_x == self.focus_x and self.anchor_y == self.focus_y

    def active_cell(self) -> tuple[int, int]:
        return self.focus_x, self.focus_y

    def anchor_cell(self) -> tuple[int, int]:
        return self.anchor_x, self.anchor_y

    def bounds(self) -> tuple[int, int, int, int]:
        min_x = min(self.anchor_x, self.focus_x)
        max_x = max(self.anchor_x, self.focus_x)
        min_y = min(self.anchor_y, self.focus_y)
        max_y = max(self.anchor_y, self.focus_y)
        return min_x, min_y, max_x, max_y

    def cells(self) -> list[tuple[int, int]]:
        min_x, min_y, max_x, max_y = self.bounds()
        values: list[tuple[int, int]] = []
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                values.append((x, y))
        return values
