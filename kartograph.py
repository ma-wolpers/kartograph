from __future__ import annotations

from datetime import datetime
from pathlib import Path
import traceback


def _bootstrap_failure_log_path() -> Path:
    repo_root = Path(__file__).resolve().parent
    logs_dir = repo_root / "Temp" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "kartograph_bootstrap_failures.log"


def _log_bootstrap_exception(exc: BaseException) -> None:
    log_path = _bootstrap_failure_log_path()
    timestamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} | Bootstrap failure\n")
        handle.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        handle.write("\n")


if __name__ == "__main__":
    try:
        from app.app import main

        main()
    except BaseException as exc:
        _log_bootstrap_exception(exc)
        raise
