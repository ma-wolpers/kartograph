"""Fachlogik für die Zielbelegung eines Ausschneiden-Einfügen-Vorgangs (v4).

Ein Cut-Paste-Vorgang verschiebt eine Menge von Schülern auf feste, vorgegebene
Zielplätze. Belegt ein *fremder* Schüler (nicht Teil der Auswahl) bereits einen
dieser Zielplätze, soll er nicht gelöscht werden, sondern auf den dadurch frei
werdenden Platz umziehen — verkettet über mehrere Stationen hinweg, falls auch
dieser Platz wiederum Ziel eines anderen ausgeschnittenen Schülers ist.

Dieses Modul bestimmt die vollständige Zielbelegung rein lesend aus dem
unveränderten Ausgangszustand. Die eigentliche Mutation (Sitzplätze setzen,
Tischgruppen-Koordinaten umschreiben) übernimmt der Aufrufer
(``StudentClipboard.paste_into_plan``).

Fachliche Herleitung, warum das immer eindeutig lösbar ist (kein Sonderfall
nötig): Jeder Cut-Paste-Eintrag hat einen eindeutigen Ausgangsplatz (aktueller
Sitzplatz) und einen eindeutigen Zielplatz. Da auf jedem Platz höchstens ein
Schüler sitzt, sind sowohl alle Ausgangsplätze als auch alle Zielplätze
paarweise verschieden. Bildet man daraus einen gerichteten Graphen mit einer
Kante *Ausgangsplatz → Zielplatz* pro Eintrag, hat jeder Knoten also höchstens
einen eingehenden und höchstens einen ausgehenden Pfeil — ein solcher Graph
zerfällt zwingend vollständig in disjunkte einfache Ketten und Kreise. Ein
Platz, der gleichzeitig Ausgangs- und Zielplatz ist ("innerer Kettenknoten"),
ist zu Beginn immer durch den Batch-Schüler besetzt, der von dort wegzieht —
dort kann kein Fremder sitzen. Ein Fremder kann folglich nur an einem
Kettenkopf sitzen (Zielplatz, der kein Ausgangsplatz eines anderen Eintrags
ist) und landet eindeutig am Kettenende (Ausgangsplatz, der kein Zielplatz
eines anderen Eintrags ist — garantiert frei, da Ketten disjunkt sind).
Kreise enthalten nie einen Fremden, da dort jeder Knoten ein Ausgangsplatz
eines Batch-Schülers ist. Die Verdrängung bleibt damit beweisbar auf die
Auswahl und ihre unmittelbaren Kettenenden begrenzt; unbeteiligte Schüler
außerhalb dieser Ketten werden nie berührt.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.models_v4 import Classroom
from app.core.domain.student_id import StudentId

Coordinate = tuple[int, int]


@dataclass(frozen=True)
class SeatMove:
    """Eine einzelne Platzänderung: betroffener Schüler, alter und neuer Platz."""

    student_id: StudentId
    from_seat: Coordinate
    to_seat: Coordinate


def resolve_cut_paste_moves(
    classroom: Classroom,
    batch_moves: list[tuple[StudentId, Coordinate, Coordinate]],
) -> list[SeatMove]:
    """Bestimmt die vollständige Zielbelegung für einen Ausschneiden-Einfügen-Vorgang.

    Liest den Belegungszustand ausschließlich aus *classroom* (unverändert,
    vor jeder Mutation) und mutiert nichts. Die zurückgegebene Liste enthält
    zuerst die Bewegungen der ausgeschnittenen Schüler selbst (in der
    Reihenfolge von *batch_moves*), danach — falls vorhanden — je eine
    zusätzliche Bewegung pro fremdem Schüler, der von einem Zielplatz
    verdrängt wird. Ein verdrängter Schüler landet auf dem Ausgangsplatz des
    Batch-Schülers, der ihn verdrängt; führt das wiederum auf einen Platz, der
    selbst Ziel eines anderen Batch-Eintrags ist, wird diese Kette so lange
    weiterverfolgt, bis ein tatsächlich frei werdender Platz erreicht ist
    (siehe Moduldocstring für die Begründung, warum das immer terminiert und
    eindeutig ist). Niemand wird gelöscht oder neu angelegt — ``StudentId``
    und damit Dokumentationshistorie und Tischgruppen-Mitgliedschaft bleiben
    für jeden Beteiligten erhalten.

    Args:
        classroom: Klassenraum, aus dem die aktuelle Belegung der Zielplätze
            gelesen wird (unveränderter Ausgangszustand).
        batch_moves: Die ausgeschnittenen Einträge als
            ``(student_id, ausgangsplatz, zielplatz)``-Tupel. Ausgangs- und
            Zielplätze müssen jeweils paarweise verschieden sein (siehe
            Moduldocstring) — das ist für echte, aus dem Plan gelesene
            Sitzplätze und Versätze stets der Fall.

    Returns:
        Die vollständige Liste der anzuwendenden ``SeatMove``s.
    """
    batch_ids = {student_id for student_id, _old, _new in batch_moves}
    old_seat_of_target: dict[Coordinate, Coordinate] = {
        new: old for _student_id, old, new in batch_moves
    }

    moves = [
        SeatMove(student_id=student_id, from_seat=old, to_seat=new)
        for student_id, old, new in batch_moves
    ]

    for _student_id, _old, new in batch_moves:
        existing = classroom.student_at(*new)
        if existing is None or existing.student_id in batch_ids:
            continue
        tail = old_seat_of_target[new]
        while tail in old_seat_of_target:
            tail = old_seat_of_target[tail]
        moves.append(SeatMove(student_id=existing.student_id, from_seat=new, to_seat=tail))

    return moves
