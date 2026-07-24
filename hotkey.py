"""
Global hotkey manager using the `keyboard` library.

Architecture:
- Unified callback: all hotkeys go through _on_hotkey(id)
- Dispatch dict: maps hotkey config ID → action handler
- Single reusable toast widget (no repeated create/destroy)

Toast widget floats near the mouse cursor or screen center.
"""

from __future__ import annotations

from typing import Any, Callable

import keyboard
from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from i18n import channel_name, tr
from sonar_ctrl import SonarCtrl
from theme import DEFAULT_THEME, ThemeColors


# ---------------------------------------------------------------------------
# Toast widget (reusable, single instance)
# ---------------------------------------------------------------------------

class ToastWidget(QFrame):
    """A floating, auto-hiding toast notification for volume changes."""

    TIMEOUT_MS = 1700

    def __init__(self, theme: ThemeColors | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme or DEFAULT_THEME
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.setObjectName("toastFrame")
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        self._label = QLabel(tr("app.title"))
        self._label.setObjectName("toastLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self.setStyleSheet(f"""
            QFrame#toastFrame {{
                background-color: {self._theme.bg_secondary};
                border-left: 4px solid {self._theme.accent};
                border-top: 1px solid {self._theme.border};
                border-right: 1px solid {self._theme.border};
                border-bottom: 1px solid {self._theme.border};
                border-radius: 4px;
            }}
            QLabel#toastLabel {{
                color: {self._theme.text_primary};
                font-size: 10pt;
                font-weight: 600;
            }}
        """)

        self.adjustSize()

    def show_at(self, pos: QPoint, text: str) -> None:
        """Show toast at the given position with the given text."""
        self._label.setText(text)
        self.adjustSize()
        self.move(pos)
        self.show()
        self._timer.start(self.TIMEOUT_MS)

    def show_top_left(self, text: str) -> None:
        """Show toast at top-left of screen, fixed margin from edge."""
        from PySide6.QtGui import QGuiApplication

        self._label.setText(text)
        self.adjustSize()

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.left() + 16
            y = geo.top() + 16
        else:
            x, y = 16, 16

        self.move(QPoint(x, y))
        self.show()
        self._timer.start(self.TIMEOUT_MS)


# ---------------------------------------------------------------------------
# Hotkey dispatcher
# ---------------------------------------------------------------------------

# Action type sentinel values
_ACTION_VOL = 0   # volume adjust (±1 step)
_ACTION_MUTE = 1  # toggle mute

_STEP = 1.0  # volume change per hotkey press (percentage points)


def _build_action_map() -> dict[str, tuple[int, str, str, int]]:
    """Build dispatch dict: config_id → (action_type, channel_key, slider_key, delta)."""
    ch_map = {
        "master": "master",
        "game": "game",
        "chat": "chatRender",
        "media": "media",
        "aux": "aux",
        "mic": "chatCapture",
    }
    result: dict[str, tuple[int, str, str, int]] = {}
    for short, api_key in ch_map.items():
        for slider, slider_key in [("mon", "monitoring"), ("stm", "streaming")]:
            result[f"{short}_{slider}_up"] = (_ACTION_VOL, api_key, slider_key, +1)
            result[f"{short}_{slider}_down"] = (_ACTION_VOL, api_key, slider_key, -1)
            result[f"{short}_{slider}_mute"] = (_ACTION_MUTE, api_key, slider_key, 0)
    return result


class HotkeyManager(QObject):
    """Register and dispatch global hotkeys. Thread-safe via Qt signals."""

    # Emitted from keyboard thread → delivered to main thread
    _toastRequested = Signal(str)
    _toggleRequested = Signal()

    def __init__(self, sonar: SonarCtrl,
                 theme: ThemeColors | None = None) -> None:
        super().__init__()
        self._sonar = sonar
        self._theme = theme or DEFAULT_THEME
        self._action_map = _build_action_map()
        self._hotkeys_config: dict[str, str] = {}
        self._paused = False
        self._shutting_down = False
        self._toast: ToastWidget | None = None
        self._show_toast = True
        self._streamer_mode = True
        self._toggle_callback: Callable[[], None] | None = None
        self._lock_callback: Callable[[], bool] | None = None

        # Thread-safe: _toastRequested signal → show toast in main thread
        self._toastRequested.connect(self._show_toast_safe)

    # ── Toast (thread-safe) ───────────────────────────────────────────

    def set_show_toast(self, enabled: bool) -> None:
        self._show_toast = enabled

    def _show_toast_safe(self, text: str) -> None:
        """Slot: show toast in the Qt main thread."""
        if self._toast is None:
            self._toast = ToastWidget(self._theme)
        self._toast.show_top_left(text)

    # ── Toggle callback (show/hide main window) ──────────────────────

    def set_toggle_callback(self, callback: Callable[[], None]) -> None:
        """Set the callback for the 'toggle_window' hotkey."""
        self._toggle_callback = callback
        self._toggleRequested.connect(callback)

    def set_lock_callback(self, callback: Callable[[], bool]) -> None:
        """Set a callback that returns True when the mixer is locked (user dragging)."""
        self._lock_callback = callback

    def set_streamer_mode(self, enabled: bool) -> None:
        """Update current mode — affects whether streamer_slider is passed to API."""
        self._streamer_mode = enabled

    # ── Register / unregister ────────────────────────────────────────

    def register_all(self, hotkeys: dict[str, str]) -> None:
        """Register all hotkeys from config. Clears previous registrations first."""
        self.unregister_all()
        self._hotkeys_config = hotkeys

        for config_id, combo in hotkeys.items():
            if not combo:
                continue
            try:
                keyboard.add_hotkey(
                    self._normalize_combo(combo),
                    lambda cid=config_id: self._on_hotkey(cid),
                    suppress=False,
                )
            except Exception as e:
                import sys
                print(f"[SonarMix] Failed to register hotkey {combo}: {e}", file=sys.stderr)

    def shutdown(self) -> None:
        """Permanently disable hotkeys. Call once before app quit."""
        self._shutting_down = True
        self.unregister_all()

    def unregister_all(self) -> None:
        """Remove all registered hotkeys (safe for pause/resume cycle)."""
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    def pause(self) -> None:
        """Temporarily unregister all hotkeys (e.g. during settings key capture)."""
        if self._paused:
            return
        self._paused = True
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    def resume(self) -> None:
        """Re-register all hotkeys after pause."""
        if not self._paused:
            return
        self._paused = False
        self.register_all(self._hotkeys_config)

    @staticmethod
    def _normalize_combo(combo: str) -> str:
        """Normalize combo strings for the keyboard library."""
        # keyboard lib expects lowercase with specific names
        replacements = {
            "Ctrl": "ctrl",
            "Alt": "alt",
            "Shift": "shift",
            "Win": "windows",
            "↑": "up",
            "↓": "down",
            "←": "left",
            "→": "right",
        }
        parts = combo.split("+")
        return "+".join(replacements.get(p, p).lower() for p in parts)

    # ── Dispatch ─────────────────────────────────────────────────────

    def _on_hotkey(self, config_id: str) -> None:
        """Unified hotkey callback — runs in keyboard thread, dispatches safely."""
        if self._shutting_down:
            return

        # Toggle window — always allowed, ignores lock
        if config_id == "toggle_window":
            self._toggleRequested.emit()
            return

        # Check lock (user dragging a slider)
        if self._lock_callback and self._lock_callback():
            return

        action = self._action_map.get(config_id)
        if action is None:
            return

        action_type, channel_key, slider_key, direction = action

        # In Classic mode, ignore streaming hotkeys (no streaming sliders exist)
        if not self._streamer_mode and slider_key == "streaming":
            return

        # In Classic mode, omit streamer_slider from API calls
        api_slider: str | None = slider_key if self._streamer_mode else None

        try:
            if action_type == _ACTION_MUTE:
                self._sonar.toggle_mute(channel_key, api_slider)
                snap = self._sonar.snapshot()
                muted = snap.is_muted(channel_key, slider_key)
                if self._show_toast:
                    display = channel_name(channel_key)
                    if self._streamer_mode:
                        slider_name = (tr("slider.monitoring")
                                       if slider_key == "monitoring"
                                       else tr("slider.streaming"))
                    else:
                        slider_name = ""
                    state = "🔇" if muted else "🔊"
                    text = f"{display} {slider_name}  {state}" if slider_name else f"{display}  {state}"
                    self._toastRequested.emit(text)
            else:
                snap = self._sonar.snapshot()
                current = snap.get(channel_key, slider_key)
                new_vol = max(0.0, min(1.0, current + direction * _STEP / 100.0))
                self._sonar.set_volume(channel_key, new_vol,
                                       streamer_slider=api_slider)
                if self._show_toast:
                    display = channel_name(channel_key)
                    if self._streamer_mode:
                        slider_name = (tr("slider.monitoring")
                                       if slider_key == "monitoring"
                                       else tr("slider.streaming"))
                    else:
                        slider_name = ""
                    vol_pct = round(new_vol * 100)
                    text = f"{display} {slider_name}  {vol_pct}%" if slider_name else f"{display}  {vol_pct}%"
                    self._toastRequested.emit(text)
        except Exception:
            pass  # API unavailable — silently ignore hotkey
