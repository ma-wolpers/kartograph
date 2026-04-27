# Kartograph

Kartograph is a desktop app for creating and managing seating plans.

## Features

- Plan list with keyboard navigation (`Up`, `Down`, `Enter`)
- Grid based editor with square cells
- Infinite-feel scrolling in both directions
- Zoom in/out
- Selection with mouse and keyboard
- `Ctrl+N` for new plan with teacher desk at `(0, 0)`
- Live JSON save in a configurable plans folder
- Light and dark theme

## Start

Vor der ersten Nutzung im Ordner `tools4school` einmal ausfuehren:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r kartograph/requirements.txt
```

Fuer Entwicklung und Tests:

```powershell
pip install -r kartograph/requirements-dev.txt
python -m pytest -q kartograph
```

```bat
start-kartograph.bat
```

or

```powershell
python kartograph.py
```
