"""Clipboard-Puffer für Schülertische.

Kapselt das Kopieren, Ausschneiden und Einfügen von Desk-Objekten innerhalb
eines SeatingPlan. Neue Felder in Desk werden automatisch übertragen, weil
intern deepcopy verwendet wird – kein manuelles Aufzählen von Attributen.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import Desk, SeatingPlan


class DeskClipboard:
    """Zwischenablage für Schülertisch-Blöcke.

    Speichert eine relative Kopie der markierten Tische (Ursprung = linke
    obere Ecke der Selektion) und kann sie an einer neuen Position wieder
    in einen Plan einsetzen.
    """

    def __init__(self) -> None:
        """Initialisiert einen leeren Clipboard-Puffer."""
        self._payload: dict[tuple[int, int], Desk] = {}
        self._width = 0
        self._height = 0

    def has_content(self) -> bool:
        """Gibt True zurück, wenn sich Tische im Puffer befinden."""
        return bool(self._payload)

    def copy_from_plan(self, plan: SeatingPlan, cells: list[tuple[int, int]]) -> int:
        """Kopiert alle Schülertische in *cells* in den Puffer.

        Die Positionen werden relativ zur linken oberen Ecke der Selektion
        gespeichert. Vorhandener Puffer-Inhalt wird ersetzt.

        Args:
            plan: Quellplan, aus dem gelesen wird.
            cells: Liste von (x, y)-Koordinaten der Selektion.

        Returns:
            Anzahl der kopierten Schülertische.
        """
        if not cells:
            self._payload = {}
            self._width = 0
            self._height = 0
            return 0

        xs = [x for x, _y in cells]
        ys = [y for _x, y in cells]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        self._payload = {}
        self._width = max_x - min_x + 1
        self._height = max_y - min_y + 1

        for x, y in cells:
            desk = plan.desk_at(x, y)
            if not desk or desk.desk_type != "student":
                continue
            rel = (x - min_x, y - min_y)
            # deepcopy statt manueller Konstruktion: neue Felder in Desk
            # werden automatisch übertragen, ohne hier Änderungen vornehmen
            # zu müssen.
            copied = deepcopy(desk)
            copied.x = rel[0]
            copied.y = rel[1]
            self._payload[rel] = copied

        return len(self._payload)

    def cut_from_plan(self, plan: SeatingPlan, cells: list[tuple[int, int]]) -> tuple[SeatingPlan, int, int]:
        """Kopiert Schülertische in den Puffer und entfernt sie aus dem Plan.

        Args:
            plan: Quellplan.
            cells: Liste von (x, y)-Koordinaten der Selektion.

        Returns:
            Tupel aus (aktualisierter Plan, Anzahl kopierter, Anzahl entfernter Tische).
        """
        copied = self.copy_from_plan(plan, cells)
        next_plan = deepcopy(plan)
        removed = 0
        for x, y in cells:
            desk = next_plan.desk_at(x, y)
            if not desk or desk.desk_type != "student":
                continue
            next_plan.without_desk_at(x, y)
            removed += 1
        return next_plan, copied, removed

    def paste_into_plan(
        self,
        plan: SeatingPlan,
        target_x: int,
        target_y: int,
        min_bound: int,
        max_bound: int,
    ) -> tuple[SeatingPlan, int, bool]:
        """Fügt den Puffer-Inhalt ab Position (*target_x*, *target_y*) ein.

        Bestehende Schülertische an Zielzellen werden überschrieben.
        Tische, die außerhalb von *min_bound*/*max_bound* fallen würden,
        werden übersprungen. Der Lehrertisch kann nie überschrieben werden.

        Args:
            plan: Zielplan.
            target_x: X-Koordinate der oberen linken Einfügeposition.
            target_y: Y-Koordinate der oberen linken Einfügeposition.
            min_bound: Minimale gültige Koordinate (x und y).
            max_bound: Maximale gültige Koordinate (x und y).

        Returns:
            Tupel aus (aktualisierter Plan, Anzahl eingefügter Tische,
            ob ein Lehrertisch-Konflikt aufgetreten ist).
        """
        next_plan = deepcopy(plan)
        if not self._payload:
            return next_plan, 0, False

        teacher_conflict = False
        pasted_count = 0

        for (dx, dy), source in self._payload.items():
            x = target_x + dx
            y = target_y + dy
            if x < min_bound or x > max_bound or y < min_bound or y > max_bound:
                continue

            existing = next_plan.desk_at(x, y)
            if existing and existing.desk_type == "teacher":
                teacher_conflict = True
                continue
            if existing and existing.desk_type == "student":
                next_plan.without_desk_at(x, y)

            # deepcopy statt manueller Konstruktion; nur Koordinaten anpassen.
            pasted = deepcopy(source)
            pasted.x = x
            pasted.y = y
            next_plan.desks.append(pasted)
            pasted_count += 1

        return next_plan, pasted_count, teacher_conflict
