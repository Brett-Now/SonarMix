"""
Thread-safe log emitter — any module can post log messages via the singleton.
The Log tab listens to the Qt signal, and every message is also written
to a timestamped log file under SonarMix_logs/.

Levels: DEBUG < INFO < WARN < ERROR
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal


# ---------------------------------------------------------------------------
# File-backend state (module-level so init_log_file can write early)
# ---------------------------------------------------------------------------

_MAX_LOG_FILES = 7          # keep the most recent N log files
_log_file: object | None = None           # open text file handle
_log_file_path: Path | None = None



def init_log_file(base_dir: Path, version: str) -> Path | None:
    """Create SonarMix_logs/, open a timestamped log, clean old files, write header.

    Returns the log file path for diagnostic display, or ``None`` on failure.
    """
    global _log_file, _log_file_path

    log_dir = base_dir / "SonarMix_logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        _cleanup_old_logs(log_dir)

        ts = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        _log_file_path = log_dir / f"SonarMix_{ts}.log"
        _log_file = open(str(_log_file_path), "w", encoding="utf-8")
    except OSError:
        _log_file = None
        _log_file_path = None
        return None

    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    sep = "═" * 60
    try:
        _log_file.write(f"{sep}\n")
        _log_file.write(f"  SonarMix v{version} — session start\n")
        _log_file.write(f"  {now}\n")
        _log_file.write(f"{sep}\n\n")
        _log_file.flush()
    except OSError:
        pass

    return _log_file_path


def shutdown_log_file() -> None:
    """Write session-end footer and close the log file."""
    global _log_file
    if _log_file is None:
        return
    sep = "─" * 60
    try:
        _log_file.write(f"\n{sep}\n")
        _log_file.write("  Session end\n")
        _log_file.write(f"{sep}\n")
        _log_file.flush()
    except OSError:
        pass
    try:
        _log_file.close()
    except OSError:
        pass
    _log_file = None


def _cleanup_old_logs(log_dir: Path) -> None:
    """Delete log files beyond _MAX_LOG_FILES, sorted by modification time."""
    try:
        files = sorted(
            log_dir.glob("SonarMix_*.log"),
            key=os.path.getmtime,
            reverse=True,
        )
        for f in files[_MAX_LOG_FILES:]:
            try:
                f.unlink()
            except OSError:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Singleton emitter
# ---------------------------------------------------------------------------

class _LogEmitter(QObject):
    """Singleton — emits (timestamp, category, message) tuples.

    Call ``_LogEmitter.post(category, msg)`` from any thread; the
    internal Qt signal is thread-safe.
    """

    _instance: _LogEmitter | None = None

    message = Signal(str, str, str)  # timestamp, category, message

    @classmethod
    def get(cls) -> "_LogEmitter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def post(cls, category: str, message: str) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime())
        cls.get().message.emit(ts, category, message)

        # ── File write (all levels, unconditionally) ──────────────────
        global _log_file
        if _log_file is not None:
            try:
                _log_file.write(f"{ts} {category.ljust(5)} {message}\n")
                _log_file.flush()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def log_debug(msg: str) -> None:
    _LogEmitter.post("DEBUG", msg)


def log_info(msg: str) -> None:
    _LogEmitter.post("INFO", msg)


def log_warn(msg: str) -> None:
    _LogEmitter.post("WARN", msg)


def log_error(msg: str) -> None:
    _LogEmitter.post("ERROR", msg)
