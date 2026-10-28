"""Notenskalen eines Plans (Schulnoten 1–6 / Punkte 0–15) und ihre Umrechnung.

Single Source of Truth für alles, was von der Skala abhängt: gültiger
Wertebereich, Anzeigeformat, Eingabehinweis, Menü-Label und die
Umrechnung zwischen Schulnoten und Punkten. GUI, Usecases und
Persistenz fragen ausschließlich diese Registry ab, statt Bereichs-
grenzen oder Labels selbst zu kodieren.

Die Skala-IDs sind bewusst identisch mit denen des Korrektors
(``schulnoten_1_6`` / ``punktnoten_0_15``), damit beide Werkzeuge
dieselbe Skala gleich benennen.

Umrechnungsregel (Ankertabelle :data:`POINTS_TO_GRADE`):

* Punkte → Note: glatte Punkte ergeben den Anker (15 → 0.7, 7 → 3.3),
  Zwischenpunkte werden linear interpoliert (7.5 → 3.15).
* Note → Punkte: liegt die Note *weniger als* 0.15 neben einem Anker,
  rastet sie auf dessen glatte Punktzahl ein (3.2 → 7). Grenzfälle
  (genau 0.15 Abstand) und Werte in größeren Lücken ergeben den halben
  Punkt zwischen den Nachbarankern (3.15 → 7.5, 2.5 → 9.5, 5.65 → 0.5).

Damit sind halbe Punkte verlustfrei hin- und zurückrechenbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

SCALE_SCHOOL_1_6 = "schulnoten_1_6"
SCALE_POINTS_0_15 = "punktnoten_0_15"


@dataclass(frozen=True, slots=True)
class GradeScale:
    """Beschreibung einer Notenskala.

    Attributes:
        scale_id: Persistierte ID (siehe Modul-Docstring).
        label: Anzeigetext für Menü und Warnungen.
        min_value: Kleinster gültiger Wert (inklusiv).
        max_value: Größter gültiger Wert (inklusiv).
        display_format: ``format()``-Spezifikation für Tabellenzellen —
            Schulnoten wie bisher mit zwei Nachkommastellen (``"2.30"``),
            Punkte ohne überflüssige Nullen (``"12"``, ``"7.5"``).
        input_hint: Statusmeldung bei ungültiger Eingabe.
    """

    scale_id: str
    label: str
    min_value: float
    max_value: float
    display_format: str
    input_hint: str

    def contains(self, value: float) -> bool:
        """Prüft, ob *value* im gültigen Bereich der Skala liegt.

        Args:
            value: Zu prüfender Wert.
        """
        return self.min_value <= float(value) <= self.max_value

    def clamp(self, value: float) -> float:
        """Begrenzt *value* auf den Skalenbereich.

        Letzte Sicherung in der Domain; die GUI lehnt ungültige Eingaben
        bereits vorher über :meth:`contains` ab.

        Args:
            value: Zu begrenzender Wert.
        """
        return max(self.min_value, min(self.max_value, float(value)))

    def format_value(self, value: float) -> str:
        """Formatiert *value* für die Anzeige in der Doku-Tabelle.

        Args:
            value: Gespeicherter Wert.

        Examples:
            Schulnoten: ``2.3 → "2.30"``; Punkte: ``12.0 → "12"``, ``7.5 → "7.5"``.
        """
        return format(float(value), self.display_format)

    def format_input(self, value: float) -> str:
        """Formatiert *value* als Vorbelegung des Inline-Editors (ohne überflüssige Nullen).

        Bewusst ``"g"`` statt ``"…".rstrip("0")``: Letzteres machte aus
        ``0.0`` einen leeren String, und ein leerer Editor löscht beim
        Bestätigen den Wert — fatal für 0 Punkte.

        Args:
            value: Gespeicherter Wert.

        Examples:
            ``2.3 → "2.3"``, ``3.15 → "3.15"``, ``0.0 → "0"``.
        """
        return format(float(value), "g")


# Schulnoten beginnen bei 0.7 ("1+"), damit 15 Punkte verlustfrei abbildbar sind.
GRADE_SCALES: dict[str, GradeScale] = {
    SCALE_SCHOOL_1_6: GradeScale(
        scale_id=SCALE_SCHOOL_1_6,
        label="Schulnoten (1–6)",
        min_value=0.7,
        max_value=6.0,
        display_format=".2f",
        input_hint="Ungültige Note: bitte Zahl zwischen 0,7 und 6 eingeben",
    ),
    SCALE_POINTS_0_15: GradeScale(
        scale_id=SCALE_POINTS_0_15,
        label="Punkte (0–15)",
        min_value=0.0,
        max_value=15.0,
        display_format="g",
        input_hint="Ungültige Punktzahl: bitte Zahl zwischen 0 und 15 eingeben",
    ),
}

DEFAULT_SCALE_ID = SCALE_SCHOOL_1_6


def scale_for(scale_id: str | None) -> GradeScale:
    """Liefert die Skala zu *scale_id*; unbekannte/leere IDs ergeben Schulnoten.

    Der Fallback hält Altpläne ohne ``grade_scale``-Feld unverändert.

    Args:
        scale_id: Persistierte Skala-ID.
    """
    return GRADE_SCALES.get(str(scale_id or "").strip(), GRADE_SCALES[DEFAULT_SCALE_ID])


# Ankertabelle: Punkte → Schulnote (Index = Punktzahl).
POINTS_TO_GRADE: tuple[Decimal, ...] = tuple(
    Decimal(v) for v in (
        "6.0", "5.3", "5.0", "4.7", "4.3", "4.0", "3.7", "3.3",
        "3.0", "2.7", "2.3", "2.0", "1.7", "1.3", "1.0", "0.7",
    )
)

_SNAP_DISTANCE = Decimal("0.15")
_CENT = Decimal("0.01")


def points_to_grade(points: float) -> float:
    """Rechnet eine Punktzahl in eine Schulnote um.

    Glatte Punkte ergeben den Anker, Zwischenwerte werden linear zwischen
    den Nachbarankern interpoliert und auf zwei Nachkommastellen gerundet.

    Args:
        points: Punktzahl; Werte außerhalb 0–15 werden begrenzt.

    Examples:
        ``15 → 0.7``, ``7 → 3.3``, ``7.5 → 3.15``, ``0.5 → 5.65``.
    """
    p = min(Decimal(15), max(Decimal(0), Decimal(str(points))))
    lower = int(p)
    if lower == 15:
        return float(POINTS_TO_GRADE[15])
    fraction = p - lower
    grade = POINTS_TO_GRADE[lower] + (POINTS_TO_GRADE[lower + 1] - POINTS_TO_GRADE[lower]) * fraction
    return float(grade.quantize(_CENT, rounding=ROUND_HALF_UP))


def grade_to_points(grade: float) -> float:
    """Rechnet eine Schulnote in Punkte um (Einrast-Regel, siehe Modul-Docstring).

    Gerechnet wird mit ``Decimal`` auf zwei Nachkommastellen, damit der
    Grenzfall "genau 0.15 Abstand" exakt erkannt wird (bei ``float`` wäre
    ``3.15 - 3.0`` nicht exakt 0.15).

    Args:
        grade: Schulnote; Werte außerhalb 0.7–6.0 werden begrenzt.

    Examples:
        ``3.2 → 7``, ``3.15 → 7.5``, ``2.5 → 9.5``, ``5.65 → 0.5``.
    """
    g = Decimal(str(grade)).quantize(_CENT, rounding=ROUND_HALF_UP)
    for points, anchor in enumerate(POINTS_TO_GRADE):
        if abs(g - anchor) < _SNAP_DISTANCE:
            return float(points)
    if g >= POINTS_TO_GRADE[0]:
        return 0.0
    if g <= POINTS_TO_GRADE[15]:
        return 15.0
    # Kein Anker in Reichweite: halber Punkt zwischen den Nachbarankern.
    for points in range(15):
        if POINTS_TO_GRADE[points + 1] < g < POINTS_TO_GRADE[points]:
            return points + 0.5
    raise AssertionError(f"Note {g} liegt zwischen keinen Ankern")  # pragma: no cover


def convert_value(value: float, from_scale_id: str, to_scale_id: str) -> float:
    """Rechnet *value* von einer Skala in eine andere um.

    Args:
        value: Gespeicherter Wert in der Ausgangsskala.
        from_scale_id: ID der Ausgangsskala.
        to_scale_id: ID der Zielskala.

    Returns:
        Wert in der Zielskala (unverändert bei gleicher Skala).
    """
    source = scale_for(from_scale_id).scale_id
    target = scale_for(to_scale_id).scale_id
    if source == target:
        return float(value)
    if target == SCALE_POINTS_0_15:
        return grade_to_points(value)
    return points_to_grade(value)
