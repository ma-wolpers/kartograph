"""Clipboard-Puffer für Schülerplätze (Format v4).

Ersetzt die alte v3-``DeskClipboard`` (``app/core/domain/desk_clipboard.py``),
die vollständige ``Desk``-Kopien speicherte. Da Schüler in v4 über eine
stabile :class:`~app.core.domain.student_id.StudentId` adressiert werden
(s. Architekturplan v2, Abschnitt 1), merkt sich dieser Puffer nur noch
**Referenzen** (``StudentId`` + relativer Versatz zur Selektion) statt
vollständiger Daten-Schnappschüsse. Die eigentlichen Schülerdaten werden erst
beim tatsächlichen Einfügen aus dem dann *aktuellen* Plan gelesen.

Zwei Modi, die sich in ihrer Semantik beim Einfügen unterscheiden:

- **Kopieren** (:meth:`StudentClipboard.copy_from_plan`): Das Original bleibt
  unverändert an seinem Platz. Jedes Einfügen erzeugt eine frische Kopie mit
  neuer ``StudentId`` (Name und Diagnoseprofil werden übernommen, die
  Dokumentationshistorie bleibt beim Original, da Sessions nach der
  *Original*-ID indiziert sind).
- **Ausschneiden** (:meth:`StudentClipboard.mark_for_cut`): Markiert Schüler
  nur zum Verschieben — löscht beim Markieren **nichts**. Erst das
  tatsächliche Einfügen (:meth:`StudentClipboard.paste_into_plan`) verschiebt
  sie, wobei ``StudentId`` und damit die gesamte Dokumentationshistorie
  erhalten bleiben. Wird ein markierter Schüler zwischen Markieren und
  Einfügen anderweitig aus dem Plan entfernt, wird sein Eintrag beim Einfügen
  übersprungen statt einen Fehler zu werfen.

Beide Modi erlauben mehrfaches Einfügen aus demselben Puffer: Kopieren
erzeugt dabei jedes Mal eine neue ID, Ausschneiden verschiebt dieselben
Schüler bei jedem weiteren Einfügen einfach erneut an die nächste Zielzelle.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from app.core.domain.models_v4 import Seat, SeatingPlan
from app.core.domain.student_id import StudentId
from app.core.usecases.v4.student_usecases import create_student, delete_student

ClipboardMode = Literal["copy", "cut"]


@dataclass(frozen=True)
class _ClipboardEntry:
    """Ein gemerkter Schüler im Puffer: Versatz zur Selektions-Ankerzelle plus ID.

    Der Versatz ist relativ zur linken oberen Ecke der ursprünglich
    kopierten/ausgeschnittenen Zellauswahl (analog zu ``DeskClipboard``).
    """

    offset_x: int
    offset_y: int
    student_id: StudentId


class StudentClipboard:
    """Zwischenablage für Schülerplätze, referenzbasiert über ``StudentId``.

    Eine Instanz lebt typischerweise in ``HandlerContext.clipboard`` und wird
    von den Edit-Handlern (``app/application/handlers/edit_handlers.py``)
    über mehrere Intent-Dispatches hinweg wiederverwendet — ähnlich wie
    ``HandlerContext.history`` für Undo/Redo.
    """

    def __init__(self) -> None:
        """Initialisiert einen leeren, modus-losen Puffer."""
        self._entries: list[_ClipboardEntry] = []
        self._mode: ClipboardMode | None = None

    def has_content(self) -> bool:
        """Gibt True zurück, wenn der Puffer mindestens einen Eintrag enthält."""
        return bool(self._entries)

    def clear(self) -> None:
        """Leert den Puffer und setzt den Modus zurück."""
        self._entries = []
        self._mode = None

    def copy_from_plan(self, plan: SeatingPlan, cells: list[tuple[int, int]]) -> int:
        """Merkt sich alle Schüler in *cells* zum Kopieren.

        Verändert *plan* nicht. Ein vorhandener Pufferinhalt wird ersetzt.

        Args:
            plan: Plan, aus dem die Selektion gelesen wird.
            cells: (x, y)-Koordinaten der Selektion; Zellen ohne Schüler
                werden ignoriert.

        Returns:
            Anzahl der gemerkten Schüler.
        """
        self._entries = self._collect_entries(plan, cells)
        self._mode = "copy"
        return len(self._entries)

    def mark_for_cut(self, plan: SeatingPlan, cells: list[tuple[int, int]]) -> int:
        """Markiert alle Schüler in *cells* zum Verschieben, ohne sie zu löschen.

        Verändert *plan* nicht — das eigentliche Verschieben passiert erst in
        :meth:`paste_into_plan`. Ein vorhandener Pufferinhalt wird ersetzt.

        Args:
            plan: Plan, aus dem die Selektion gelesen wird.
            cells: (x, y)-Koordinaten der Selektion; Zellen ohne Schüler
                werden ignoriert.

        Returns:
            Anzahl der markierten Schüler.
        """
        self._entries = self._collect_entries(plan, cells)
        self._mode = "cut"
        return len(self._entries)

    @staticmethod
    def _collect_entries(plan: SeatingPlan, cells: list[tuple[int, int]]) -> list[_ClipboardEntry]:
        """Baut die Eintragsliste (Versatz + StudentId) für *cells* auf.

        Args:
            plan: Plan, aus dem die Schüler an *cells* gelesen werden.
            cells: (x, y)-Koordinaten der Selektion; Zellen ohne Schüler
                werden ignoriert.
        """
        if not cells:
            return []
        xs = [x for x, _y in cells]
        ys = [y for _x, y in cells]
        min_x, min_y = min(xs), min(ys)

        entries: list[_ClipboardEntry] = []
        for x, y in cells:
            student = plan.classroom.student_at(x, y)
            if student is None:
                continue
            entries.append(
                _ClipboardEntry(offset_x=x - min_x, offset_y=y - min_y, student_id=student.student_id)
            )
        return entries

    def paste_into_plan(
        self, plan: SeatingPlan, target_x: int, target_y: int
    ) -> tuple[SeatingPlan, int, bool]:
        """Fügt den Pufferinhalt ab (*target_x*, *target_y*) in *plan* ein.

        Bestimmt für jeden Eintrag die Zielzelle relativ zu seinem
        gespeicherten Versatz. Schüler, die seit dem Kopieren/Ausschneiden
        aus dem Plan entfernt wurden, werden übersprungen. Belegt eine
        Zielzelle bereits ein *fremder* Schüler (nicht Teil dieses
        Puffer-Inhalts), wird dieser samt seiner Dokumentationshistorie
        entfernt (analog zum bisherigen ``DeskClipboard``-Verhalten).
        Der Lehrertisch kann nie überschrieben werden.

        Beim Ausschneiden bleiben ``StudentId`` und Tischgruppen-Mitgliedschaft
        erhalten (echte Verschiebung); beim Kopieren erhält jede eingefügte
        Kopie eine frische ``StudentId`` ohne Tischgruppen-Mitgliedschaft und
        ohne Dokumentationshistorie (analog zu ``create_student``). Trifft
        eine Kopie auf eine noch unverschobene andere Quelle aus derselben
        Auswahl (Selbstüberlappung beim Kopieren in den eigenen Auswahlbereich),
        wird dieser einzelne Eintrag übersprungen statt Daten zu überschreiben.

        Args:
            plan: Zielplan.
            target_x: X-Koordinate der Einfüge-Ankerzelle (Versatz 0, 0).
            target_y: Y-Koordinate der Einfüge-Ankerzelle (Versatz 0, 0).

        Returns:
            Tupel aus (aktualisierter Plan, Anzahl eingefügter Schüler,
            ob mindestens ein Eintrag am Lehrertisch blockiert wurde).
        """
        if not self._entries:
            return plan, 0, False

        next_plan = deepcopy(plan)
        batch_ids = {entry.student_id for entry in self._entries}
        teacher_conflict = False

        targets: list[tuple[_ClipboardEntry, int, int]] = []
        for entry in self._entries:
            if next_plan.classroom.student_by_id(entry.student_id) is None:
                continue  # zwischenzeitlich geloescht -> ueberspringen statt Fehler
            x, y = target_x + entry.offset_x, target_y + entry.offset_y
            ts = next_plan.classroom.teacher_seat
            if ts.x == x and ts.y == y:
                teacher_conflict = True
                continue
            targets.append((entry, x, y))

        # Fremde Belegungen an Zielzellen raeumen. Eigene Batch-Mitglieder
        # werden unten verschoben/dupliziert, nicht geloescht.
        for _entry, x, y in targets:
            existing = next_plan.classroom.student_at(x, y)
            if existing is not None and existing.student_id not in batch_ids:
                next_plan = delete_student(next_plan, existing.student_id)

        pasted = 0
        if self._mode == "cut":
            # Alt->Neu-Koordinaten zuerst vollstaendig einsammeln, erst danach
            # Tischgruppen-Sitze in einem Durchgang umschreiben. Vermeidet
            # Koordinaten-Aliasing, wenn zwei verschobene Schueler innerhalb
            # derselben Operation die Plaetze tauschen.
            coord_moves: dict[tuple[int, int], tuple[int, int]] = {}
            for entry, x, y in targets:
                student = next_plan.classroom.student_by_id(entry.student_id)
                coord_moves[(student.seat.x, student.seat.y)] = (x, y)
                student.seat = Seat(x=x, y=y)
                pasted += 1
            if coord_moves:
                for group in next_plan.tablegroups:
                    for seat in group.seats:
                        new_coords = coord_moves.get((seat.x, seat.y))
                        if new_coords is not None:
                            seat.x, seat.y = new_coords
        else:
            for entry, x, y in targets:
                if next_plan.classroom.student_at(x, y) is not None:
                    continue
                source = next_plan.classroom.student_by_id(entry.student_id)
                next_plan = create_student(next_plan, x, y)
                clone = next_plan.classroom.student_at(x, y)
                clone.first_name_official = source.first_name_official
                clone.nickname = source.nickname
                clone.last_name = source.last_name
                clone.diagnostic = deepcopy(source.diagnostic)
                pasted += 1

        return next_plan, pasted, teacher_conflict
