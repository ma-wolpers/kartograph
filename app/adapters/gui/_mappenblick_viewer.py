"""Einzige Stelle in Kartograph, die Mappenblick importiert (Plattform-Isolation).

Kapselt beide Mappenblick-Nutzungen von "Abgaben zählen" hinter einer
kleinen, Kartograph-eigenen Schnittstelle:

* :class:`SubmissionArchive` öffnet eine Abgabe-ZIP und liefert ihre
  Unterordnernamen (für den Namensabgleich).
* :func:`open_viewer_window` zeigt dieselbe ZIP im eingebetteten
  Mappenblick-Viewer und meldet Bewertungen über ``on_rated`` zurück.

Beide teilen sich *dieselben* Mappenblick-Abhängigkeiten, weil das
ZIP-Repository den offenen Datei-Handle hält, aus dem der Viewer rendert.
Ändert sich Mappenblicks API, ist nur diese Datei betroffen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Mapping

from app.core.domain.submission_status import SubmissionStatus
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

# Vor den Mappenblick-Importen: dessen GUI-Module importieren bw_gui schon beim Laden.
ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.runtime import widgets as tui
from mappenblick.adapters.bootstrap.wiring import build_gui_dependencies
from mappenblick.adapters.gui.viewer_panel import ViewerPanel
from mappenblick.core.domain.models import ArchiveIndex
from mappenblick.core.domain.rating import Rating

# Einzige Zuordnung Mappenblick-Bewertung ↔ Kartograph-Abgabestatus.
STATUS_BY_RATING: dict[Rating, SubmissionStatus] = {
    Rating.COMPLETE: SubmissionStatus.COMPLETE,
    Rating.PARTIAL: SubmissionStatus.PARTIAL,
    Rating.NOT_DONE: SubmissionStatus.MISSING,
}
RATING_BY_STATUS: dict[SubmissionStatus, Rating] = {status: rating for rating, status in STATUS_BY_RATING.items()}


class SubmissionArchive:
    """Eine geöffnete Abgabe-ZIP: Ordnernamen für den Abgleich, Index für den Viewer."""

    def __init__(self, archive_path: Path) -> None:
        """Öffnet und indiziert *archive_path* (liest PDFs für die Seitenzahl).

        Args:
            archive_path: Gewählte ``.zip``-Datei.

        Raises:
            Exception: Jeder Lesefehler der ZIP; der Aufrufer zeigt ihn an.
        """
        self.path = archive_path
        self._deps = build_gui_dependencies()
        self._index: ArchiveIndex = self._deps.open_archive_usecase.execute(archive_path)

    @property
    def folder_names(self) -> tuple[str, ...]:
        """Alle Unterordner mit mindestens einer Datei (auch nur nicht anzeigbare)."""
        return tuple(group.name for group in self._index.subfolders)


class _StatusSink:
    """Mappenblick-``RatingSink``, der Bewertungen als Kartograph-Abgabestatus meldet."""

    def __init__(
        self,
        initial: Mapping[str, SubmissionStatus],
        on_rated: Callable[[str, SubmissionStatus], None],
    ) -> None:
        """Merkt sich Vorbelegung und Rückmeldeweg.

        Args:
            initial: Ordner → bereits eingetragener Status.
            on_rated: Wird pro Bewertung mit (Ordner, Status) aufgerufen.
        """
        self._initial = {folder: RATING_BY_STATUS[status] for folder, status in initial.items()}
        self._on_rated = on_rated

    def initial_ratings(self) -> Mapping[str, Rating]:
        """Bereits eingetragene Bewertungen (für die Anzeige im Viewer)."""
        return dict(self._initial)

    def on_rated(self, subfolder_name: str, rating: Rating) -> None:
        """Übersetzt die Bewertung und meldet sie an Kartograph.

        Args:
            subfolder_name: Bewerteter Ordner.
            rating: Mappenblick-Bewertung.
        """
        self._on_rated(subfolder_name, STATUS_BY_RATING[rating])


def open_viewer_window(
    master: ui.Misc,
    archive: SubmissionArchive,
    *,
    title: str,
    folders: Iterable[str],
    labels: Mapping[str, str],
    initial: Mapping[str, SubmissionStatus],
    on_rated: Callable[[str, SubmissionStatus], None],
    register_window: Callable[[ui.Toplevel], None],
) -> ui.Toplevel:
    """Öffnet ein nicht-modales Fenster mit dem Mappenblick-Viewer für *folders*.

    Args:
        master: Kartograph-Hauptfenster.
        archive: Die bereits geöffnete ZIP (gleiche Abhängigkeiten = gleicher Handle).
        title: Fenstertitel.
        folders: Anzuzeigende Ordner (zugeordnete Personen, ggf. nur Unbewertete).
        labels: Ordner → Anzeigename der Person.
        initial: Ordner → bereits eingetragener Status.
        on_rated: Rückmeldung je Bewertung (Ordner, Status).
        register_window: Meldet das Fenster im Overlay-Stack an (nicht blockierend).

    Returns:
        Das Fenster; ein Hinweis erscheint, wenn *folders* leer ist.
    """
    window = ui.Toplevel(master)
    window.title(title)
    window.geometry("1100x800")
    register_window(window)
    content = tui.Frame(window)
    content.pack(fill="both", expand=True)
    panel = ViewerPanel(content, archive._deps, with_rating=True)
    index = archive._index.restricted_to(folders)
    if not panel.show_archive(index, labels=labels, rating_sink=_StatusSink(initial, on_rated)):
        panel.show_message("Keine Abgaben mehr zu bewerten.")
    return window
