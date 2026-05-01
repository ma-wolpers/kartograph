from __future__ import annotations

import atexit
import faulthandler
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.adapters.gui.main_window import KartographMainWindow
from app.infrastructure.repositories.json_plan_repository import JsonSeatingPlanRepository
from app.infrastructure.repositories.settings_repository import JsonSettingsRepository


def _configure_startup_logging(workspace_root: Path) -> Path:
    logs_dir = workspace_root / "Temp" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "kartograph_startup.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_500_000,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    def _log_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
        logging.getLogger("kartograph.startup").exception(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _log_uncaught_exception
    logging.getLogger("kartograph.startup").info("Startup logging initialized at %s", log_path)
    return log_path


def _configure_hang_trace_logging(workspace_root: Path) -> Path | None:
    logger = logging.getLogger("kartograph.startup")
    logs_dir = workspace_root / "Temp" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    trace_path = logs_dir / "kartograph_hang_traces.log"

    try:
        trace_file = trace_path.open("a", encoding="utf-8")
    except Exception:
        logger.exception("Could not open hang trace log file at %s", trace_path)
        return None

    try:
        faulthandler.enable(file=trace_file, all_threads=True)
        faulthandler.dump_traceback_later(15, repeat=True, file=trace_file, exit=False)
    except Exception:
        logger.exception("Could not enable faulthandler periodic trace dumps")
        trace_file.close()
        return None

    def _cleanup_hang_trace_logging() -> None:
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass
        try:
            trace_file.flush()
            trace_file.close()
        except Exception:
            pass

    atexit.register(_cleanup_hang_trace_logging)
    logger.info("Hang trace logging enabled at %s (periodic every 15s)", trace_path)
    return trace_path


def main() -> None:
    workspace_root = Path(__file__).resolve().parents[1]
    _configure_startup_logging(workspace_root)
    logger = logging.getLogger("kartograph.startup")
    logger.info("Application bootstrap started")
    _configure_hang_trace_logging(workspace_root)

    config_path = workspace_root / "config" / "kartograph_settings.json"
    symbols_path = workspace_root / "config" / "symbols.json"
    default_plans_dir = workspace_root / "plans"

    settings_repository = JsonSettingsRepository(config_path=config_path)
    plan_repository = JsonSeatingPlanRepository()

    logger.info("Creating main window")
    app = KartographMainWindow(
        settings_repository=settings_repository,
        plan_repository=plan_repository,
        default_plans_dir=default_plans_dir,
        symbols_path=symbols_path,
    )
    logger.info("Entering Tk mainloop")
    app.mainloop()
    logger.info("Tk mainloop exited")
