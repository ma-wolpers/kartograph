"""Doku-Zellen über die Text-Zwischenablage kopieren (reines Python, kein Tk).

Die System-Zwischenablage kann nur Text. Eine Doku-Zelle (Tageseintrag mit
Symbolen, Mitarbeit und Tagesnotiz) legt daher ihren Anzeigetext hinein und
merkt sich den Eintrag daneben (``CopiedDocEntry``). Beim Einfügen in eine
Doku-Zelle gilt der Eintrag nur, solange die Zwischenablage noch genau diesen
Text enthält und derselbe Sitzplan offen ist (``entry_to_paste``): wurde
inzwischen anderswo etwas kopiert, wird nichts Veraltetes eingefügt; eigene
Symbole gehören zu ihrem Plan und würden in einem anderen ins Leere zeigen.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.models_v4 import SessionEntry


@dataclass(frozen=True)
class CopiedDocEntry:
    """Zuletzt kopierte Doku-Zelle.

    Attributes:
        plan_id: Sitzplan, aus dem kopiert wurde.
        text: Text, der dabei in die Zwischenablage ging (Anzeigetext der Zelle).
        entry: Kopie des Tageseintrags (leer, wenn die Zelle leer war).
    """

    plan_id: str
    text: str
    entry: SessionEntry


def entry_to_paste(copied: CopiedDocEntry | None, plan_id: str, clipboard_text: str | None) -> SessionEntry | None:
    """Tageseintrag, den Einfügen in eine Doku-Zelle schreiben darf, sonst ``None``.

    Args:
        copied: Zuletzt kopierte Doku-Zelle oder ``None``.
        plan_id: ID des offenen Sitzplans.
        clipboard_text: Aktueller Text der Zwischenablage (``None`` = kein Text;
            zählt wie ``""``, weil eine leere Zelle leeren Text kopiert).

    Returns:
        Der gemerkte Eintrag, wenn Plan und Zwischenablage-Text noch passen.
    """
    if copied is None or copied.plan_id != plan_id or (clipboard_text or "") != copied.text:
        return None
    return copied.entry
