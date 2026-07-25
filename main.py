"""
SonarMix — SteelSeries GG Sonar volume mixer.
Entry point: creates the mixer window, system tray, hotkeys, and settings.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from hotkey import HotkeyManager
from i18n import tr
from log_handler import init_log_file, log_debug, log_error, log_info, log_warn, shutdown_log_file
from mixer_ui import MixerWidget
from settings_ui import APP_VERSION, SettingsWindow
from sonar_ctrl import SonarCtrl
from theme import DEFAULT_THEME, apply_theme
from tray import TrayController, generate_icon

# ---------------------------------------------------------------------------
# Config path
# ---------------------------------------------------------------------------

# When frozen (PyInstaller), __file__ points inside the temp extraction dir.
# Use the exe's directory instead so config.yaml is editable & persists across runs.
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).resolve().parent
else:
    _BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = _BASE_DIR
CONFIG_PATH = CONFIG_DIR / "config.yaml"


# ---------------------------------------------------------------------------
# Global exception hook — capture unhandled crashes into the log file
# ---------------------------------------------------------------------------

_original_excepthook = sys.excepthook

def _global_excepthook(exc_type, exc_value, exc_tb):
    """Log unhandled Python exceptions before letting the default handler run."""
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    log_error("Unhandled exception — " + "".join(tb_lines).rstrip())
    _original_excepthook(exc_type, exc_value, exc_tb)


sys.excepthook = _global_excepthook


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class SonarMixApp:
    """Root application — wires together all modules."""

    def __init__(self) -> None:
        # ── Log file (early, before anything else writes to the emitter) ──
        log_path = init_log_file(_BASE_DIR, APP_VERSION)
        mode_str = "frozen" if getattr(sys, "frozen", False) else "dev"
        log_info(f"SonarMix v{APP_VERSION} starting ({mode_str} mode)")
        log_info(f"Base dir: {_BASE_DIR}")
        log_info(f"Config path: {CONFIG_PATH}")
        if log_path:
            log_debug(f"Log file: {log_path}")

        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        apply_theme(self._app, DEFAULT_THEME)

        # App-wide icon (tray + windows)
        self._icon = generate_icon(DEFAULT_THEME)
        self._app.setWindowIcon(self._icon)

        # ── Core components ──────────────────────────────────────────
        self._sonar = SonarCtrl()
        self._hotkeys = HotkeyManager(self._sonar)

        # Admin check — global keyboard hooks require elevation on Windows
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if is_admin:
            log_info("Running as Administrator — hotkey hook stable")
        else:
            log_warn("Not running as Administrator — hotkeys may be blocked by Windows security policy. Restart as Admin.")

        # ── Main window ──────────────────────────────────────────────
        self._mixer = MixerWidget(self._sonar)
        self._mixer.setWindowTitle(tr("app.title"))
        # Streamer Mode: init from GG, wire toggle ↔ API + hotkeys
        initial_mode = self._sonar.refresh_streamer_mode()
        self._mixer.set_streamer_mode(initial_mode)
        self._hotkeys.set_streamer_mode(initial_mode)
        mode_str = "Streamer" if initial_mode else "Classic"
        log_info(f"Sonar mode: {mode_str}")
        self._mixer.streamerModeChanged.connect(self._on_streamer_mode_changed)
        # Minimize → hide to tray, Close → quit
        self._base_flags = (
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self._mixer.setWindowFlags(self._base_flags)

        # ── System tray ──────────────────────────────────────────────
        self._tray = TrayController(self._mixer)
        self._tray.quitRequested.connect(self._quit)
        self._tray.settingsRequested.connect(self._show_settings)
        self._mixer.quitRequested.connect(self._quit)

        # ── Settings window ──────────────────────────────────────────
        self._settings = SettingsWindow(CONFIG_PATH)
        self._settings.configSaved.connect(self._on_config_saved)
        self._settings.configLoaded.connect(self._on_config_loaded)
        self._mixer.settingsRequested.connect(self._show_settings)

        # Pause hotkeys while user captures a key combo in settings
        self._settings._hotkey_tab.captureStateChanged.connect(
            lambda capturing: self._hotkeys.pause() if capturing else self._hotkeys.resume()
        )

        # ── Hotkey wiring ────────────────────────────────────────────
        self._hotkeys.set_toggle_callback(self._tray.toggle)
        self._hotkeys.set_lock_callback(self._mixer.is_locked)

        # ── Config ───────────────────────────────────────────────────
        self._load_config()
        self._apply_window_flags()

        # Persist language choice to config.yaml
        from i18n import get_lang, on_lang_changed
        self._current_lang = get_lang()
        log_debug(f"UI language: {self._current_lang}")
        on_lang_changed(self._on_language_changed)

        # ── Periodic refresh (catch external changes in GG) ──────────
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._periodic_refresh)
        self._refresh_timer.start(2000)  # every 2 seconds
        log_debug("Periodic refresh timer started (2000 ms)")

        # ── Start visible or minimized ────────────────────────────────
        if self._start_minimized:
            self._mixer.hide()
            log_info("Window hidden to tray (start minimized)")
        else:
            self._mixer.show()
            log_info("Window shown")

        # Install Windows session-lock guard (clears stuck keys on unlock)
        self._hotkeys.install_session_guard(int(self._mixer.winId()))
        self._tray.sync_visibility()

    # ── Lifecycle ────────────────────────────────────────────────────

    def run(self) -> int:
        """Run the Qt event loop."""
        return self._app.exec()

    def _quit(self) -> None:
        """Clean shutdown — unhook keyboard before Qt event loop dies."""
        log_info("Shutting down — stopping refresh, unhooking hotkeys...")
        self._refresh_timer.stop()
        self._hotkeys.shutdown()
        self._app.quit()
        shutdown_log_file()

    # ── Config ───────────────────────────────────────────────────────

    _DEFAULT_CONFIG = {
        "hotkeys": {},
        "settings": {
            "always_on_top": True,
            "language": "zh",
            "show_toast": True,
            "start_minimized": False,
        },
    }

    def _load_config(self) -> None:
        """Load config from YAML and apply hotkeys + settings.
        Creates a default config.yaml on first run if missing.
        """
        import yaml

        self._start_minimized = False

        if not CONFIG_PATH.exists():
            CONFIG_PATH.write_text(
                yaml.dump(self._DEFAULT_CONFIG, allow_unicode=True,
                          default_flow_style=False),
                encoding="utf-8",
            )
            log_info("Config not found — created default config.yaml")
            data = self._DEFAULT_CONFIG
        else:
            try:
                data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
            except Exception as e:
                log_error(f"Config YAML parse error: {e} — using defaults")
                data = self._DEFAULT_CONFIG

        hk = data.get("hotkeys", {})
        hk_count = len([v for v in hk.values() if v])
        s = data.get("settings", {})
        lang = s.get("language", "zh")
        log_info(
            f"Config loaded: {hk_count} hotkey(s), "
            f"language={lang}, "
            f"always_on_top={s.get('always_on_top', True)}, "
            f"show_toast={s.get('show_toast', True)}, "
            f"start_minimized={s.get('start_minimized', False)}"
        )

        self._hotkeys.register_all(hk)
        self._hotkeys.set_show_toast(s.get("show_toast", True))
        self._start_minimized = s.get("start_minimized", False)

        # Language — apply saved preference
        if s.get("language"):
            from i18n import set_lang
            set_lang(s["language"])

    def _save_language(self) -> None:
        """Write current language to config.yaml."""
        import yaml
        from i18n import get_lang

        try:
            data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        data.setdefault("settings", {})["language"] = get_lang()
        CONFIG_PATH.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False),
                               encoding="utf-8")

    def _on_config_saved(self) -> None:
        """Hotkeys + settings applied → reload and refresh."""
        log_info("Config saved — reloading...")
        self._load_config()
        self._apply_window_flags()

    def _on_config_loaded(self) -> None:
        """Settings loaded from file → apply flags."""
        log_debug("Config loaded into settings window")
        self._apply_window_flags()

    def _apply_window_flags(self) -> None:
        """Apply always-on-top from current settings state."""
        flags = self._base_flags
        if self._settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
            log_debug("Window flag: always-on-top ON")
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
            log_debug("Window flag: always-on-top OFF")
        self._mixer.setWindowFlags(flags)
        self._mixer.show()  # setWindowFlags hides, re-show

    def _on_streamer_mode_changed(self, enabled: bool) -> None:
        """Sync hotkey manager to current mode — streaming hotkeys are ignored in Classic."""
        mode_str = "Streamer" if enabled else "Classic"
        log_info(f"Streamer mode changed → {mode_str}")
        self._hotkeys.set_streamer_mode(enabled)

    def _on_language_changed(self) -> None:
        """Log language changes from user toggle."""
        from i18n import get_lang
        new_lang = get_lang()
        if new_lang != self._current_lang:
            log_info(f"Language changed: {self._current_lang} → {new_lang}")
            self._current_lang = new_lang

    # ── Settings ─────────────────────────────────────────────────────

    def _show_settings(self) -> None:
        """Open the settings window."""
        log_debug("Settings window opened")
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    # ── Refresh ──────────────────────────────────────────────────────

    def _periodic_refresh(self) -> None:
        """Refresh sliders if visible and not being dragged."""
        if self._mixer.isVisible() and not self._mixer.is_locked():
            self._mixer.refresh_all()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    app = SonarMixApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
