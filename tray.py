"""
System tray icon with context menu.

Features:
- Left-click toggles main window visibility
- Right-click context menu: Show/Hide, Settings, Quit
- Tooltip shows "SonarMix"
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt as QtCore, Signal
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from i18n import on_lang_changed, tr
from log_handler import log_debug, log_info
from theme import DEFAULT_THEME, ThemeColors


# ---------------------------------------------------------------------------
# Icon generation (programmatic — no external assets needed)
# ---------------------------------------------------------------------------

def generate_icon(theme: ThemeColors, size: int = 32) -> QIcon:
    """Generate a tray/window icon: accent-colored circle with an 'S'.

    Exported so main.py can reuse it for the window icon.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(QtCore.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Filled circle background
    painter.setBrush(theme.accent)
    painter.setPen(QtCore.PenStyle.NoPen)
    margin = 2
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)

    # "S" letter
    painter.setPen(theme.bg_primary)
    font = painter.font()
    font.setPixelSize(size - 10)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), QtCore.AlignmentFlag.AlignCenter, "S")

    painter.end()
    return QIcon(pixmap)


# ---------------------------------------------------------------------------
# Tray controller
# ---------------------------------------------------------------------------

class TrayController(QObject):
    """Manages the system tray icon and its context menu."""

    showRequested = Signal()
    hideRequested = Signal()
    quitRequested = Signal()
    settingsRequested = Signal()

    def __init__(self, main_window: QWidget,
                 theme: ThemeColors | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme or DEFAULT_THEME
        self._main_window = main_window
        self._visible = main_window.isVisible()

        # Tray icon
        self._tray = QSystemTrayIcon(parent)
        self._tray.setIcon(generate_icon(self._theme))
        self._tray.setToolTip(tr("app.title"))
        self._tray.activated.connect(self._on_tray_activated)

        # Context menu
        self._menu = QMenu(tr("app.title"))

        self._show_action = QAction(
            tr("tray.hide") if self._visible else tr("tray.show"),
            self._menu,
        )
        self._show_action.triggered.connect(self.toggle)
        self._menu.addAction(self._show_action)

        self._settings_action = QAction(tr("tray.settings"), self._menu)
        self._settings_action.triggered.connect(self.settingsRequested.emit)
        self._menu.addAction(self._settings_action)

        self._menu.addSeparator()

        self._quit_action = QAction(tr("tray.quit"), self._menu)
        self._quit_action.triggered.connect(self.quitRequested.emit)
        self._menu.addAction(self._quit_action)

        self._tray.setContextMenu(self._menu)
        self._tray.show()
        log_info("System tray created")

        # Refresh menu text when language changes
        on_lang_changed(self._refresh_text)

    # ── Visibility ───────────────────────────────────────────────────

    def sync_visibility(self) -> None:
        """Update internal state and menu text to match actual window visibility."""
        self._visible = self._main_window.isVisible()
        self._show_action.setText(tr("tray.hide") if self._visible else tr("tray.show"))

    def toggle(self) -> None:
        """Toggle main window visibility."""
        if self._visible:
            self._hide_window()
        else:
            self._show_window()

    def _show_window(self) -> None:
        log_debug("Tray: window shown")
        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()
        self._visible = True
        self._show_action.setText(tr("tray.hide"))
        self.showRequested.emit()

    def _hide_window(self) -> None:
        log_debug("Tray: window hidden")
        self._main_window.hide()
        self._visible = False
        self._show_action.setText(tr("tray.show"))
        self.hideRequested.emit()

    # ── Tray activation ──────────────────────────────────────────────

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon click events."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left click
            self.toggle()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    # ── Toasts ───────────────────────────────────────────────────────

    def show_toast(self, title: str, message: str,
                   duration_ms: int = 2000) -> None:
        """Show a system notification toast."""
        self._tray.showMessage(
            title, message,
            QSystemTrayIcon.MessageIcon.Information,
            duration_ms,
        )

    def _refresh_text(self) -> None:
        """Update tray menu text after language change."""
        self._tray.setToolTip(tr("app.title"))
        self._show_action.setText(tr("tray.hide") if self._visible else tr("tray.show"))
        self._settings_action.setText(tr("tray.settings"))
        self._quit_action.setText(tr("tray.quit"))

    @property
    def icon(self) -> QSystemTrayIcon:
        return self._tray
