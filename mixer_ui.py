"""
Compact main window: 6 channel groups × 2 sliders (monitoring + streaming)
plus a settings gear button. Designed to be small, always-on-top, and quickly
shown/hidden via system tray.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from i18n import channel_name, tr
from sonar_ctrl import CHANNEL_KEYS, SonarCtrl
from theme import DEFAULT_THEME, ThemeColors


# ---------------------------------------------------------------------------
# Slider group for one channel
# ---------------------------------------------------------------------------

class ChannelGroup(QGroupBox):
    """A group box containing one or two sliders for one channel:
    Streamer Mode → monitoring + streaming (2 sliders)
    Classic Mode → monitoring only (streaming row hidden)
    """

    volumeChanged = Signal(str, str, int)  # channel_key, slider_key, value 0–100
    lockChanged = Signal(bool)  # True when any slider is being dragged

    def __init__(self, channel_key: str, theme: ThemeColors,
                 parent: QWidget | None = None) -> None:
        display = channel_name(channel_key)
        super().__init__(display, parent)

        self._channel_key = channel_key
        self._theme = theme
        self._locked = False
        self._streamer_mode = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 14, 6, 6)
        layout.setSpacing(4)

        # Monitoring slider (always visible)
        self._mon_slider, self._mon_vol, self._mon_row, self._mon_left = \
            self._make_slider_row(layout, tr("slider.monitoring"))
        # Streaming slider (hidden in Classic mode)
        self._stm_slider, self._stm_vol, self._stm_row, self._stm_left = \
            self._make_slider_row(layout, tr("slider.streaming"))

        # Lock on press, HTTP on release
        for sl in (self._mon_slider, self._stm_slider):
            sl.sliderPressed.connect(self._on_pressed)
            sl.sliderReleased.connect(self._on_released)

        self._mon_slider.sliderReleased.connect(
            lambda: self._emit("monitoring", self._mon_slider.value())
        )
        self._stm_slider.sliderReleased.connect(
            lambda: self._emit("streaming", self._stm_slider.value())
        )

    def _on_pressed(self) -> None:
        if not self._locked:
            self._locked = True
            self.lockChanged.emit(True)

    def _on_released(self) -> None:
        # Qt delivers sliderReleased before the value is finally set?
        # Short defer so the final value is stable before we unlock.
        if self._locked:
            self._locked = False
            self.lockChanged.emit(False)

    def _make_slider_row(self, layout: QVBoxLayout,
                         label_text: str) -> tuple[QSlider, QLabel, QHBoxLayout, QLabel]:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        left_label = QLabel(label_text)
        left_label.setObjectName("channelLabel")
        left_label.setFixedWidth(24)
        row.addWidget(left_label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(50)
        slider.setSingleStep(1)
        slider.setPageStep(5)
        slider.setObjectName(f"{self._channel_key}_{label_text.lower()}")
        row.addWidget(slider, 1)

        value_label = QLabel("50")
        value_label.setObjectName("volumeLabel")
        value_label.setFixedWidth(22)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(value_label)

        # Update value label during drag (UI only, no HTTP)
        slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))

        layout.addLayout(row)
        return slider, value_label, row, left_label

    def _emit(self, slider_key: str, value: int) -> None:
        self.volumeChanged.emit(self._channel_key, slider_key, value)

    def set_streamer_mode(self, enabled: bool) -> None:
        """Show/hide the streaming slider row + left labels."""
        self._streamer_mode = enabled
        # Streaming row: visible only in Streamer mode
        for i in range(self._stm_row.count()):
            w = self._stm_row.itemAt(i).widget()
            if w:
                w.setVisible(enabled)
        if not enabled:
            self._stm_row.setContentsMargins(0, 0, 0, 0)
        # Classic mode: hide "个人"/"Mon" / "流"/"Stm" labels — single slider
        self._mon_left.setVisible(enabled)
        self._stm_left.setVisible(enabled)

    # ── External setters (called on refresh) ─────────────────────────

    def set_monitoring(self, volume_0100: int) -> None:
        """Set monitoring slider + label without triggering HTTP."""
        self._mon_slider.blockSignals(True)
        self._mon_slider.setValue(volume_0100)
        self._mon_slider.blockSignals(False)
        self._mon_vol.setText(str(volume_0100))

    def set_streaming(self, volume_0100: int) -> None:
        """Set streaming slider + label without triggering HTTP."""
        self._stm_slider.blockSignals(True)
        self._stm_slider.setValue(volume_0100)
        self._stm_slider.blockSignals(False)
        self._stm_vol.setText(str(volume_0100))

    def set_mon_left(self, text: str) -> None:
        """Update the monitoring left label text (language toggle)."""
        self._mon_left.setText(text)

    def set_stm_left(self, text: str) -> None:
        """Update the streaming left label text (language toggle)."""
        self._stm_left.setText(text)


# ---------------------------------------------------------------------------
# Main mixer widget
# ---------------------------------------------------------------------------

class MixerWidget(QWidget):
    """Compact mixer panel: 6 channel groups + settings button."""

    settingsRequested = Signal()
    quitRequested = Signal()
    streamerModeChanged = Signal(bool)  # True → Streamer, False → Classic

    def __init__(self, sonar: SonarCtrl, theme: ThemeColors | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sonar = sonar
        self._theme = theme or DEFAULT_THEME
        self._channels: dict[str, ChannelGroup] = {}
        self._lock_count = 0  # > 0 if any slider is being dragged
        self._streamer_mode = True

        self._build_ui()
        self.refresh_all()

    def is_locked(self) -> bool:
        """True while user is dragging any slider (pause hotkeys + refresh)."""
        return self._lock_count > 0

    def _on_lock_changed(self, locked: bool) -> None:
        if locked:
            self._lock_count += 1
        else:
            self._lock_count = max(0, self._lock_count - 1)

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 8)
        root.setSpacing(6)

        # ── Header: Streamer Mode toggle (left) + settings gear (right) ──
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        # Streamer Mode label + switch
        self._mode_label = QLabel(tr("mixer.streamer_mode"))
        self._mode_label.setObjectName("channelLabel")
        self._mode_label.setStyleSheet(
            f"QLabel#channelLabel {{ color: {self._theme.accent}; font-size: 8pt; "
            f"font-weight: 700; padding-left: 2px; }}"
        )
        header.addWidget(self._mode_label)

        self._mode_toggle = QSlider(Qt.Orientation.Horizontal)
        self._mode_toggle.setFixedWidth(28)
        self._mode_toggle.setRange(0, 1)
        self._mode_toggle.setValue(1)  # Streamer ON
        self._mode_toggle.setSingleStep(1)
        self._mode_toggle.setPageStep(1)
        self._mode_toggle.setObjectName("streamerToggle")
        self._mode_toggle.setToolTip(tr("mixer.streamer_mode"))
        self._mode_toggle.valueChanged.connect(self._on_mode_toggled)
        # Style the toggle as an accent-colored pill
        self._mode_toggle.setStyleSheet(f"""
            QSlider#streamerToggle::groove:horizontal {{
                background: {self._theme.slider_groove};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider#streamerToggle::handle:horizontal {{
                background: {self._theme.accent};
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
            QSlider#streamerToggle::sub-page:horizontal {{
                background: {self._theme.accent};
                border-radius: 3px;
            }}
        """)
        header.addWidget(self._mode_toggle)
        header.addStretch()

        lang_btn = QToolButton()
        lang_btn.setText("🌐")
        lang_btn.setToolTip("Switch language / 切换语言")
        lang_btn.setStyleSheet(
            f"QToolButton {{ font-size: 11pt; "
            f"color: {self._theme.accent}; background: transparent; border: none; "
            f"padding: 1px 2px; }} "
            f"QToolButton:hover {{ color: {self._theme.accent_hover}; }}"
        )
        lang_btn.clicked.connect(self._toggle_language)
        self._lang_btn = lang_btn
        header.addWidget(lang_btn)

        gear_btn = QToolButton()
        gear_btn.setText("⚙")
        gear_btn.setToolTip(tr("mixer.settings_tooltip"))
        gear_btn.setStyleSheet(
            f"QToolButton {{ font-size: 12pt; color: {self._theme.text_secondary}; "
            f"background: transparent; border: none; }} "
            f"QToolButton:hover {{ color: {self._theme.accent}; }}"
        )
        gear_btn.clicked.connect(self.settingsRequested.emit)
        header.addWidget(gear_btn)

        root.addLayout(header)

        # ── Slider grid: 2 columns × 3 rows of ChannelGroup ──────────
        grid = QGridLayout()
        grid.setSpacing(6)

        positions = [(r, c) for r in range(3) for c in range(2)]
        for (row, col), key in zip(positions, CHANNEL_KEYS):
            group = ChannelGroup(key, self._theme)
            group.volumeChanged.connect(self._on_volume_changed)
            group.lockChanged.connect(self._on_lock_changed)
            grid.addWidget(group, row, col)
            self._channels[key] = group

        root.addLayout(grid)

        # ── Mute-all button row ───────────────────────────────────────
        mute_row = QHBoxLayout()
        mute_row.setContentsMargins(0, 4, 0, 0)

        # Streamer-mode buttons (mon + stm) — equal computed width
        self._mute_mon_btn = QPushButton(tr("mixer.mute_all_mon"))
        self._mute_mon_btn.setCheckable(True)
        self._mute_mon_btn.setFlat(True)
        self._mute_mon_btn.clicked.connect(self._toggle_all_monitoring)

        self._mute_stm_btn = QPushButton(tr("mixer.mute_all_stm"))
        self._mute_stm_btn.setCheckable(True)
        self._mute_stm_btn.setFlat(True)
        self._mute_stm_btn.clicked.connect(self._toggle_all_streaming)

        # Classic-mode button (single)
        self._mute_all_btn = QPushButton(tr("mixer.mute_all"))
        self._mute_all_btn.setCheckable(True)
        self._mute_all_btn.setFlat(True)
        self._mute_all_btn.clicked.connect(self._toggle_all_classic)
        self._mute_all_btn.hide()  # hidden until Classic mode is active

        # Make mute-all buttons equal width (wider text dictates)
        fm = self._mute_mon_btn.fontMetrics()
        _btn_width = max(
            fm.horizontalAdvance(tr("mixer.mute_all_mon")),
            fm.horizontalAdvance(tr("mixer.mute_all_stm")),
            fm.horizontalAdvance(tr("mixer.mute_all")),
        ) + 24  # padding
        self._mute_mon_btn.setFixedWidth(_btn_width)
        self._mute_stm_btn.setFixedWidth(_btn_width)
        self._mute_all_btn.setFixedWidth(_btn_width)

        mute_row.addWidget(self._mute_mon_btn)
        mute_row.addWidget(self._mute_stm_btn)
        mute_row.addWidget(self._mute_all_btn)
        mute_row.addStretch()

        # ── Version + GitHub link (same row, right-aligned) ─────────
        self._version_label = QLabel(
            f'<a href="https://github.com/Brett-Now/SonarMix" '
            f'style="color: {self._theme.text_muted}; text-decoration: none; '
            f'font-size: 9pt;">GitHub  v1.1.0</a>'
        )
        self._version_label.setOpenExternalLinks(True)
        mute_row.addWidget(self._version_label)

        root.addLayout(mute_row)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # Register language-change callback
        from i18n import on_lang_changed
        on_lang_changed(self._refresh_text)

        # Size the window once for Streamer mode (the larger layout).
        # Mode switches never call adjustSize(), so the window stays the same.
        self.adjustSize()

    # ── Volume change handler ────────────────────────────────────────

    def _on_volume_changed(self, channel_key: str, slider_key: str,
                           value: int) -> None:
        """User released a slider — send HTTP, then refresh all.
        In Classic mode, slider_key is always "monitoring" and we omit it.
        """
        sl = slider_key if self._streamer_mode else None
        self._sonar.set_volume_int(channel_key, value, streamer_slider=sl)
        self.refresh_all()

    def _toggle_all_monitoring(self) -> None:
        """Toggle mute for all monitoring sliders."""
        muted = self._mute_mon_btn.isChecked()
        for key in CHANNEL_KEYS:
            self._sonar.mute(key, muted, streamer_slider="monitoring")
        self.refresh_all()

    def _toggle_all_streaming(self) -> None:
        """Toggle mute for all streaming sliders."""
        muted = self._mute_stm_btn.isChecked()
        for key in CHANNEL_KEYS:
            self._sonar.mute(key, muted, streamer_slider="streaming")
        self.refresh_all()

    def _toggle_all_classic(self) -> None:
        """Toggle mute for all channels (Classic mode — single slider per channel)."""
        muted = self._mute_all_btn.isChecked()
        for key in CHANNEL_KEYS:
            self._sonar.mute(key, muted, streamer_slider=None)
        self.refresh_all()

    def _on_mode_toggled(self) -> None:
        """User clicked the streamer mode toggle.
        Like volume adjustment: API call first, then full refresh.
        """
        enabled = self._mode_toggle.value() == 1
        if enabled == self._streamer_mode:
            return
        self._streamer_mode = enabled
        self._apply_mode_visual()
        try:
            self._sonar.set_streamer_mode(enabled)
        except Exception:
            pass
        # Full refresh — re-reads all values from GG, now in the new mode
        self.refresh_all()
        self.streamerModeChanged.emit(enabled)  # notify hotkeys

    def set_streamer_mode(self, enabled: bool) -> None:
        """Programmatic mode init (from startup — API is already set)."""
        if enabled == self._streamer_mode:
            return
        self._streamer_mode = enabled
        self._mode_toggle.blockSignals(True)
        self._mode_toggle.setValue(1 if enabled else 0)
        self._mode_toggle.blockSignals(False)
        self._apply_mode_visual()
        # Safe: API is in the correct mode, data parses correctly
        self.refresh_all()

    def _apply_mode_visual(self) -> None:
        """Show/hide UI elements for current mode. No HTTP calls."""
        for group in self._channels.values():
            group.set_streamer_mode(self._streamer_mode)

        self._mute_mon_btn.setVisible(self._streamer_mode)
        self._mute_stm_btn.setVisible(self._streamer_mode)
        self._mute_all_btn.setVisible(not self._streamer_mode)

        self._refresh_text()

    def _toggle_language(self) -> None:
        """Toggle between Chinese and English."""
        from i18n import get_lang, set_lang
        new_lang = "en" if get_lang() == "zh" else "zh"
        set_lang(new_lang)

    def _refresh_text(self) -> None:
        """Refresh all visible text after a language change."""
        self._mode_label.setText(tr("mixer.streamer_mode"))

        # Channel group titles
        from sonar_ctrl import CHANNEL_KEYS
        for key in CHANNEL_KEYS:
            if key in self._channels:
                self._channels[key].setTitle(channel_name(key))

        # Mute button text
        self._mute_mon_btn.setText(tr("mixer.mute_all_mon"))
        self._mute_stm_btn.setText(tr("mixer.mute_all_stm"))
        self._mute_all_btn.setText(tr("mixer.mute_all"))

        # Recalculate mute button widths for new text
        fm = self._mute_mon_btn.fontMetrics()
        _btn_width = max(
            fm.horizontalAdvance(tr("mixer.mute_all_mon")),
            fm.horizontalAdvance(tr("mixer.mute_all_stm")),
            fm.horizontalAdvance(tr("mixer.mute_all")),
        ) + 24
        self._mute_mon_btn.setFixedWidth(_btn_width)
        self._mute_stm_btn.setFixedWidth(_btn_width)
        self._mute_all_btn.setFixedWidth(_btn_width)

        # Channel slider left labels
        for group in self._channels.values():
            group.set_mon_left(tr("slider.monitoring"))
            group.set_stm_left(tr("slider.streaming"))

    # ── Refresh ──────────────────────────────────────────────────────

    def refresh_all(self) -> None:
        """Fetch full volume data from Sonar and update all sliders."""
        try:
            snap = self._sonar.snapshot()
        except Exception:
            return  # GG not running or API unreachable — silently skip

        for key in CHANNEL_KEYS:
            if key not in self._channels:
                continue
            group = self._channels[key]
            mon = round(snap.get(key, "monitoring") * 100)
            stm = round(snap.get(key, "streaming") * 100)
            group.set_monitoring(mon)
            group.set_streaming(stm)

        # Sync mute-all button check states
        if self._streamer_mode:
            all_mon_muted = all(
                snap.is_muted(key, "monitoring") for key in CHANNEL_KEYS
            )
            all_stm_muted = all(
                snap.is_muted(key, "streaming") for key in CHANNEL_KEYS
            )
            self._mute_mon_btn.setChecked(all_mon_muted)
            self._mute_stm_btn.setChecked(all_stm_muted)
        else:
            all_muted = all(
                snap.is_muted(key, "monitoring") for key in CHANNEL_KEYS
            )
            self._mute_all_btn.setChecked(all_muted)

    # ── Window events ─────────────────────────────────────────────

    def changeEvent(self, event: Any) -> None:  # noqa: N802
        """Minimize → hide to tray."""
        if event.type() == event.Type.WindowStateChange and self.isMinimized():
            self.hide()
        super().changeEvent(event)

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        """X → quit app."""
        self.quitRequested.emit()
        event.accept()


# ---------------------------------------------------------------------------
# Self-test (run directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    from theme import apply_theme
    apply_theme(app, DEFAULT_THEME)

    ctrl = SonarCtrl()
    w = MixerWidget(ctrl)
    w.setWindowTitle("SonarMix — Test")
    w.show()

    sys.exit(app.exec())
