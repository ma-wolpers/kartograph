# Architektur (kartograph)

Dieses Dokument beschreibt den aktuellen Ist-Zustand.

## Architekturueberblick
- Einstiegspunkt ist `kartograph.py`.
- Die Anwendung ist in Schichten unter `app/` organisiert:
  - `app/core`: Domainmodell und Use-Cases.
  - `app/infrastructure`: Dateisystem-/Persistenzzugriffe.
  - `app/adapters/gui`: GUI-Adapter und Fensterlogik.
- Sitzplaene werden als JSON-Dateien in `plans/` abgelegt.

## Datenfluss
- GUI-Interaktionen werden in Use-Cases ueberfuehrt.
- Use-Cases lesen/schreiben ueber Repository-Schnittstellen.
- Persistenz erfolgt ueber JSON-Repository-Implementierungen.

## Build- und Laufzeitkontext
- Start lokal ueber `start-kartograph.bat` oder `python kartograph.py`.
- Abhaengigkeiten sind in `requirements.txt` definiert.
