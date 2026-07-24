"""
Thread-safe log emitter — any module can post log messages via the singleton.
The About tab's log panel listens to the signal and displays messages.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal


class _LogEmitter(QObject):
    """Singleton — emits (timestamp, category, message) tuples."""

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


# Convenience functions
def log_info(msg: str) -> None:
    _LogEmitter.post("INFO", msg)

def log_warn(msg: str) -> None:
    _LogEmitter.post("WARN", msg)

def log_error(msg: str) -> None:
    _LogEmitter.post("ERROR", msg)
