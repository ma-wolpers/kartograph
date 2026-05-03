from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppInfo:
    """Canonical identity metadata for the application."""

    name: str
    version: str
    appdata_folder: str
    window_title: str


APP_INFO = AppInfo(
    name="Kartograph",
    version="0.2.0",
    appdata_folder="Kartograph",
    window_title="Kartograph",
)
