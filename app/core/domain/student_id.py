"""Stabile Schüler-ID für Kartograph.

``StudentId`` ist ein unveränderlicher String-Subtyp, der eine UUID v4 (32 Hex-Zeichen,
ohne Bindestriche) kapselt. Er bleibt konstant, auch wenn ein Schüler den Sitzplatz
wechselt — im Gegensatz zur früheren Koordinaten-Adressierung ``(x, y)``.

Typisches Verwendungsmuster::

    sid = StudentId.new()          # neue ID erzeugen
    plan.student_by_id(sid)        # Schüler nachschlagen
    entry.entries[sid] = ...       # Session-Eintrag speichern
"""

from __future__ import annotations

import uuid


class StudentId(str):
    """Unveränderliche UUID-basierte Schüler-ID.

    Verhält sich in allen String-Kontexten wie ein gewöhnlicher ``str``
    (JSON-Serialisierung, Dict-Key, Vergleich), trägt aber explizit semantische
    Bedeutung und verhindert, dass beliebige Strings als IDs übergeben werden.
    """

    __slots__ = ()

    @classmethod
    def new(cls) -> StudentId:
        """Erzeugt eine neue, zufällige StudentId (UUID v4, 32 Hex-Zeichen)."""
        return cls(uuid.uuid4().hex)

    @classmethod
    def of(cls, raw: str) -> StudentId:
        """Konvertiert einen rohen String (z. B. aus JSON) in eine StudentId.

        Args:
            raw: 32-stelliger Hex-String einer UUID v4.

        Raises:
            ValueError: Wenn ``raw`` kein gültiger 32-stelliger Hex-String ist.
        """
        raw = raw.strip()
        if len(raw) != 32 or not all(c in "0123456789abcdef" for c in raw.lower()):
            raise ValueError(f"Ungültige StudentId: {raw!r} (erwartet 32 Hex-Zeichen)")
        return cls(raw.lower())

    def __repr__(self) -> str:
        return f"StudentId({str.__str__(self)!r})"
