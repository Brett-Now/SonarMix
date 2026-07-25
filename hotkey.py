"""
Global hotkey manager using the `keyboard` library.

Architecture:
- Unified callback: all hotkeys go through _on_hotkey(id)
- Dispatch dict: maps hotkey config ID → action handler
- Single reusable toast widget (no repeated create/destroy)

Toast widget floats near the mouse cursor or screen center.
"""

from __future__ import annotations

import ctypes
import time
from typing import Any, Callable

import keyboard
from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from i18n import channel_name, tr
from log_handler import log_debug, log_error, log_info, log_warn
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


# ---------------------------------------------------------------------------
# Windows session-lock guard (native event filter)
# ---------------------------------------------------------------------------

# Win32 constants for WTSRegisterSessionNotification
_WM_WTSSESSION_CHANGE = 0x02B1
_WTS_SESSION_LOCK = 0x7
_WTS_SESSION_UNLOCK = 0x8
_NOTIFY_FOR_THIS_SESSION = 0

# MSG struct for PeekMessage-style native event parsing
class _WinMsg(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_ulonglong),
        ("lParam", ctypes.c_longlong),
        ("time", ctypes.c_uint),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class SessionLockGuard(QAbstractNativeEventFilter):
    """Listens for WM_WTSSESSION_CHANGE and clears stuck _pressed_events.

    Registers the given window handle with WTSRegisterSessionNotification.
    On session UNLOCK, immediately clears keyboard._pressed_events — the
    Windows lock screen (Win+L / Ctrl+Alt+Del / screensaver / UAC secure
    desktop) swallows key-up events, leaving stale scan-code entries that
    silently break all registered hotkeys.
    """

    def __init__(self, clear_callback: Callable[[], int],
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._clear = clear_callback
        self._hwnd = 0

    def register(self, hwnd: int) -> bool:
        """Register hwnd for session-change notifications. Returns True on success."""
        self._hwnd = hwnd
        try:
            result = ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
                ctypes.c_void_p(hwnd), _NOTIFY_FOR_THIS_SESSION)
            return bool(result)
        except Exception:
            return False

    def unregister(self) -> None:
        """Unregister session notifications. Safe to call multiple times."""
        if self._hwnd:
            try:
                ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(
                    ctypes.c_void_p(self._hwnd))
            except Exception:
                pass
            self._hwnd = 0

    def nativeEventFilter(self, event_type: bytes,
                          message: int) -> tuple[bool, int]:
        """Qt callback: dispatched for every native Windows message."""
        try:
            msg = ctypes.cast(message, ctypes.POINTER(_WinMsg))
            if msg.contents.message == _WM_WTSSESSION_CHANGE:
                if msg.contents.wParam == _WTS_SESSION_UNLOCK:
                    cleared = self._clear()
                    if cleared > 0:
                        log_info(
                            f"Session-unlock guard: cleared {cleared} "
                            f"stuck key(s) from _pressed_events")
        except Exception:
            pass
        return False, 0


class HotkeyManager(QObject):
    """Register and dispatch global hotkeys. Thread-safe via Qt signals.

    All Sonar API calls are deferred to the Qt main thread via signals.
    The keyboard hook callback ONLY emits signals and returns immediately —
    blocking HTTP calls in the hook thread would cause Windows to unregister
    the low-level keyboard hook after ~200 ms.
    """

    # Emitted from keyboard thread → delivered to main thread
    _toastRequested = Signal(str)
    _toggleRequested = Signal()
    _muteRequested = Signal(str, str)        # channel_key, slider_key
    _volumeRequested = Signal(str, str, int)  # channel_key, slider_key, direction

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
        self._session_guard = SessionLockGuard(self._clear_pressed_events)
        self._fallback_timer = QTimer(self)
        self._fallback_timer.setSingleShot(False)
        self._fallback_timer.setInterval(30_000)   # sweep every 30 s
        self._fallback_timer.timeout.connect(self._fallback_check)
        # Track when each scan code first appeared in _pressed_events,
        # so the fallback timer only evicts genuinely stale keys.
        self._fallback_stuck_since: dict[int, float] = {}
        self._fallback_timer.start()

        # Thread-safe: signals → Qt main thread slots
        self._toastRequested.connect(self._show_toast_safe)
        self._muteRequested.connect(self._on_mute_action)
        self._volumeRequested.connect(self._on_volume_action)

        # Windows lock-screen resilience: three-layer guard
        self._register_lock_screen_guard()

    # ── Toast (thread-safe) ───────────────────────────────────────────

    def set_show_toast(self, enabled: bool) -> None:
        self._show_toast = enabled
        log_debug(f"Toast display: {'ON' if enabled else 'OFF'}")

    def _show_toast_safe(self, text: str) -> None:
        """Slot: show toast in the Qt main thread."""
        if self._toast is None:
            self._toast = ToastWidget(self._theme)
        self._toast.show_top_left(text)
        log_debug(f"Toast: {text}")

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
        if enabled != self._streamer_mode:
            # Count streaming hotkeys that are now active/inactive
            stm_keys = [cid for cid in self._hotkeys_config
                        if cid.endswith("_stm_up") or cid.endswith("_stm_down") or cid.endswith("_stm_mute")]
            active_stm = sum(1 for cid in stm_keys if self._hotkeys_config.get(cid))
            if active_stm > 0:
                action = "enabled" if enabled else "disabled"
                log_info(f"Streamer mode → {enabled} — {active_stm} streaming hotkey(s) {action}")
        self._streamer_mode = enabled

    # ── Register / unregister ────────────────────────────────────────

    def register_all(self, hotkeys: dict[str, str]) -> None:
        """Register all hotkeys from config. Clears previous registrations first."""
        self.unregister_all()
        self._hotkeys_config = hotkeys

        count = 0
        for config_id, combo in hotkeys.items():
            if not combo:
                continue
            try:
                keyboard.add_hotkey(
                    self._normalize_combo(combo),
                    lambda cid=config_id: self._on_hotkey(cid),
                    suppress=False,
                )
                log_info(f"Registered hotkey: \"{combo}\" → {config_id}")
                count += 1
            except Exception as e:
                import sys
                print(f"[SonarMix] Failed to register hotkey {combo}: {e}", file=sys.stderr)
                log_error(f"Failed to register \"{combo}\" ({config_id}): {e}")

        # Re-register internal Win+L guard (unhook_all wipes it)
        self._register_lock_screen_guard()

        if count > 0:
            log_info(f"Hotkey registration complete: {count} hotkey(s) active")
        else:
            log_warn("No hotkeys configured — hotkeys inactive")

    def shutdown(self) -> None:
        """Permanently disable hotkeys. Call once before app quit."""
        log_info("HotkeyManager shutting down — unhooking all hotkeys...")
        self._shutting_down = True
        self._fallback_timer.stop()
        self.unregister_all()
        self._session_guard.unregister()

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
        log_debug("Hotkeys paused (key capture active)")
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    def resume(self) -> None:
        """Re-register all hotkeys after pause."""
        if not self._paused:
            return
        self._paused = False
        log_debug(f"Hotkeys resumed — re-registering {len(self._hotkeys_config)} binding(s)")
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

    # ── Stuck-key guard (Windows lock-screen resilience) ────────────────
    #
    # Problem: the keyboard library tracks pressed keys in a module-level
    # _pressed_events dict.  When Windows locks (Win+L, Ctrl+Alt+Del,
    # screensaver, UAC secure desktop), key-UP events are swallowed by the
    # lock screen, leaving stale scan codes in _pressed_events permanently.
    # After unlock, any hotkey whose modifier scan codes overlap with the
    # stale entries silently fails — the library builds a wrong hotkey
    # tuple.
    #
    # Three-layer defense (all event-driven, zero polling threads):
    #   1. Win+L hook     — clears _pressed_events BEFORE the lock screen
    #                        can eat the key-up for the most-common case.
    #   2. SessionLockGuard — native WM_WTSSESSION_CHANGE listener; clears
    #                        _pressed_events on session UNLOCK.  Covers
    #                        ALL lock methods (<100 ms reaction).
    #   3. Fallback QTimer — 30 s sweep; evicts ONLY scan codes held
    #                        >60 s.  Never clears keys the user is
    #                        currently pressing.  Last-resort safety net.
    #
    # Layer 2 is registered externally via install_session_guard(hwnd)
    # once the main window is shown.

    _FALLBACK_INTERVAL_MS = 30_000   # sweep interval
    _FALLBACK_TTL = 60.0             # evict only keys stuck longer than this

    @classmethod
    def _clear_pressed_events(cls) -> int:
        """Safely clear the internal _pressed_events dict.

        Returns the number of scan codes that were cleared.
        Uses dict.clear() rather than individual del — the keyboard lib's
        internal key-up handler uses pop(code, None), so clearing is safe.
        """
        try:
            with keyboard._pressed_events_lock:
                count = len(keyboard._pressed_events)
                keyboard._pressed_events.clear()
            return count
        except Exception:
            return 0

    def _on_win_l(self) -> None:
        """Callback for internal Win+L hotkey — runs in keyboard hook thread.

        Win+L triggers the Windows lock screen, which swallows the
        subsequent Win-key-up and L-key-up events.  We clear
        _pressed_events immediately while the hook thread can still
        process events.
        """
        try:
            cleared = self._clear_pressed_events()
            if cleared > 0:
                log_info(f"Lock-screen guard: cleared {cleared} key(s) "
                         f"from _pressed_events before lock")
        except Exception:
            pass

    def _register_lock_screen_guard(self) -> None:
        """Register an internal Win+L hotkey to guard against stuck keys."""
        try:
            keyboard.add_hotkey(
                "windows+l",
                self._on_win_l,
                suppress=False,
            )
        except Exception as e:
            log_warn(f"Lock-screen guard registration failed: {e}")

    def install_session_guard(self, hwnd: int) -> None:
        """Register the native session-lock listener on the given window handle.

        Call after the main window is shown (winId() is valid).
        Must be called from the Qt main thread.
        """
        # Install on QApplication so all native messages are filtered
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._session_guard)
        if self._session_guard.register(hwnd):
            log_info("Session-lock guard registered")
        else:
            log_warn("Session-lock guard registration failed — "
                     "fallback timer will still protect")

    def _fallback_check(self) -> None:
        """Fallback sweep: evict scan codes stuck > _FALLBACK_TTL seconds.

        Runs in Qt main thread via QTimer.  Uses per-key timestamps to
        avoid clearing keys the user is currently pressing.
        """
        try:
            with keyboard._pressed_events_lock:
                current = set(keyboard._pressed_events.keys())
                now = time.time()

                # Register first-seen timestamps
                for code in current:
                    if code not in self._fallback_stuck_since:
                        self._fallback_stuck_since[code] = now

                # Drop tracking for keys released normally
                for code in list(self._fallback_stuck_since):
                    if code not in current:
                        del self._fallback_stuck_since[code]

                # Evict only genuinely stale keys
                evicted = [
                    code for code, since in self._fallback_stuck_since.items()
                    if now - since >= self._FALLBACK_TTL
                ]
                for code in evicted:
                    del keyboard._pressed_events[code]
                    del self._fallback_stuck_since[code]

                if evicted:
                    log_warn(
                        f"Fallback sweep: evicted {len(evicted)} "
                        f"stuck scan code(s) {evicted}")
        except Exception:
            pass  # internal API may change — never disrupt the app

    # ── Dispatch (keyboard hook thread — MUST return quickly) ─────────

    def _on_hotkey(self, config_id: str) -> None:
        """Hotkey callback — runs in keyboard processing thread.

        CRITICAL: Any exception here silently kills the keyboard library's
        processing thread, permanently disabling ALL hotkeys. Everything is
        wrapped in try/except for defense in depth.
        """
        try:
            if self._shutting_down:
                return

            # Toggle window — always allowed, ignores lock
            if config_id == "toggle_window":
                log_debug("Hotkey triggered: toggle_window")
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

            log_debug(f"Hotkey triggered: {config_id}")

            # Defer ALL API work to main thread — no HTTP here
            if action_type == _ACTION_MUTE:
                self._muteRequested.emit(channel_key, slider_key)
            else:
                self._volumeRequested.emit(channel_key, slider_key, direction)
        except Exception:
            log_error(f"Hotkey callback crashed for {config_id}")
            import traceback
            traceback.print_exc()

    # ── Action slots (Qt main thread — safe for HTTP) ──────────────────

    def _on_mute_action(self, channel_key: str, slider_key: str) -> None:
        """Slot: toggle mute (runs in Qt main thread)."""
        api_slider: str | None = slider_key if self._streamer_mode else None
        try:
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
        except Exception:
            pass  # API unavailable — silently ignore

    def _on_volume_action(self, channel_key: str, slider_key: str,
                          direction: int) -> None:
        """Slot: adjust volume by ±1 step (runs in Qt main thread)."""
        api_slider: str | None = slider_key if self._streamer_mode else None
        try:
            snap = self._sonar.snapshot()
            current = snap.get(channel_key, slider_key)
            new_vol = max(0.0, min(1.0, current + direction * _STEP / 100.0))
            current_pct = round(current * 100)
            new_pct = round(new_vol * 100)
            log_info(f"Hotkey: {channel_key}/{slider_key}  {'+' if direction > 0 else '−'}1  {current_pct}% → {new_pct}%")
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
                text = f"{display} {slider_name}  {new_pct}%" if slider_name else f"{display}  {new_pct}%"
                self._toastRequested.emit(text)
        except Exception:
            pass  # API unavailable — silently ignore
