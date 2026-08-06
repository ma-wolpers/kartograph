from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.domain.models import SeatingPlan


class SeatingPlanRepository(Protocol):
    """Vertrag für die Persistenz von Sitzplänen, unabhängig vom Speicherformat."""

    def list_plans(self, plans_dir: Path) -> list[tuple[Path, SeatingPlan]]:
        """Listet alle in *plans_dir* gefundenen Sitzpläne mit ihrem Dateipfad auf.

        Args:
            plans_dir: Verzeichnis, das nach Plandateien durchsucht wird.
        """
        ...

    def load_plan(self, plan_path: Path) -> SeatingPlan:
        """Lädt den Sitzplan aus *plan_path*.

        Args:
            plan_path: Pfad der zu ladenden Plandatei.
        """
        ...

    def save_plan(self, plan: SeatingPlan, plan_path: Path) -> None:
        """Speichert *plan* unter *plan_path*.

        Args:
            plan: Zu speichernder Sitzplan.
            plan_path: Zieldatei.
        """
        ...

    def create_new_plan(self, plans_dir: Path, plan_name: str, overwrite: bool = False) -> tuple[Path, SeatingPlan]:
        """Legt einen neuen, leeren Plan namens *plan_name* in *plans_dir* an.

        Args:
            plans_dir: Verzeichnis, in dem der Plan abgelegt wird.
            plan_name: Anzeigename des neuen Plans.
            overwrite: Überschreibt eine bestehende Zieldatei, wenn True.

        Returns:
            Tupel aus (neuem Pfad, neuem Plan).
        """
        ...

    def rename_plan(self, source_path: Path, new_name: str, overwrite: bool = False) -> tuple[Path, SeatingPlan]:
        """Benennt den Plan unter *source_path* um und verschiebt ggf. die Datei.

        Args:
            source_path: Aktuelle Plandatei.
            new_name: Neuer Anzeigename.
            overwrite: Überschreibt eine Zieldatei, wenn True.

        Returns:
            Tupel aus (neuem Pfad, umbenanntem Plan).
        """
        ...

    def delete_plan(self, plan_path: Path) -> None:
        """Löscht den Plan unter *plan_path*.

        Args:
            plan_path: Pfad der zu löschenden Plandatei.
        """
        ...

    def duplicate_plan(
        self,
        source_path: Path,
        target_name: str,
        overwrite: bool = False,
    ) -> tuple[Path, SeatingPlan]:
        """Erstellt eine Kopie des Plans unter *source_path* mit dem Namen *target_name*.

        Args:
            source_path: Zu duplizierende Plandatei.
            target_name: Anzeigename der Kopie.
            overwrite: Überschreibt eine Zieldatei, wenn True.

        Returns:
            Tupel aus (Pfad der Kopie, kopiertem Plan).
        """
        ...

    def plan_name_taken(self, source_path: Path, name: str) -> bool:
        """Prüft, ob *name* bereits von einem anderen Plan als *source_path* verwendet wird.

        Args:
            source_path: Plandatei, die von der Prüfung ausgenommen wird.
            name: Zu prüfender Anzeigename.
        """
        ...


class SettingsRepository(Protocol):
    """Vertrag für die Persistenz der Anwendungseinstellungen."""

    def load_settings(self) -> dict:
        """Lädt die gespeicherten Einstellungen, oder ein leeres Dict, falls keine vorhanden sind."""
        ...

    def save_settings(self, payload: dict) -> None:
        """Speichert *payload* als Einstellungen.

        Args:
            payload: Zu speichernde Einstellungen.
        """
        ...
