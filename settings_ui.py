"""
Settings window — independent window for hotkey configuration and
other non-core settings. Opened via the gear button on the main mixer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from i18n import on_lang_changed, tr
from theme import DEFAULT_THEME, ThemeColors

# Project metadata
APP_VERSION = "1.0.0"
GITHUB_URL = "https://github.com/Brett-Now/SonarMix"


# ---------------------------------------------------------------------------
# Unified capture line-edit (shared by grid AND toggle row)
# ---------------------------------------------------------------------------

class _CaptureEdit(QLineEdit):
    """Click-to-capture key combo. Class-level mutual exclusion — only
    one instance across the entire tab can be in capture mode at once."""

    _active: _CaptureEdit | None = None
    captured = Signal(str, str)  # config_id, combo_text

    def __init__(self, config_id: str, width: int = 72,
                 placeholder: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_id = config_id
        self._capturing = False
        self._prev_text = ""  # saved on capture start, restored on cancel
        self.setReadOnly(True)
        self.setFixedWidth(width)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setPlaceholderText(placeholder)
        self._reset_style()

    @property
    def config_id(self) -> str:
        return self._config_id

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if _CaptureEdit._active and _CaptureEdit._active is not self:
            _CaptureEdit._active._cancel()
        _CaptureEdit._active = self
        self._prev_text = self.text()
        self._capturing = True
        self.setText("…")
        self.setStyleSheet(
            f"QLineEdit {{ background: {DEFAULT_THEME.accent}; "
            f"color: {DEFAULT_THEME.bg_primary}; font-weight: bold; "
            f"border: 1px solid {DEFAULT_THEME.accent}; border-radius: 3px; "
            f"padding: 2px 4px; }}"
        )

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        if not self._capturing:
            super().keyPressEvent(event)
            return
        modifiers = int(event.modifiers().value)
        key = event.key()

        # Esc → cancel, restore original
        if key == Qt.Key.Key_Escape.value:
            self._cancel()
            return

        # Delete → clear hotkey
        if key == Qt.Key.Key_Delete.value:
            self.captured.emit(self._config_id, "")
            self._commit("")
            return

        is_numpad = bool(modifiers & Qt.KeyboardModifier.KeypadModifier.value)
        key_name = _qt_key_to_name(key, is_numpad)
        if key_name is None or key_name in ("Control", "Alt", "Shift", "Meta"):
            return

        parts: list[str] = []
        if modifiers & Qt.KeyboardModifier.ControlModifier.value:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier.value:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier.value:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier.value:
            parts.append("Win")
        parts.append(key_name)
        combo = "+".join(parts)
        self._commit(combo)
        self.captured.emit(self._config_id, combo)

    def _commit(self, text: str) -> None:
        self.setText(text)
        self._capturing = False
        if _CaptureEdit._active is self:
            _CaptureEdit._active = None
        self._reset_style()

    def _cancel(self) -> None:
        self.setText(self._prev_text)
        self._capturing = False
        if _CaptureEdit._active is self:
            _CaptureEdit._active = None
        self._reset_style()

    def _reset_style(self) -> None:
        self.setStyleSheet(
            f"QLineEdit {{ background: {DEFAULT_THEME.bg_secondary}; "
            f"border: 1px solid {DEFAULT_THEME.border_hover}; "
            f"border-radius: 3px; padding: 2px 4px; "
            f"color: {DEFAULT_THEME.text_primary}; }}"
        )


# ---------------------------------------------------------------------------
# Hotkey grid (QGridLayout of _CaptureEdit rows)
# ---------------------------------------------------------------------------

class HotkeyGrid(QWidget):
    """Hotkey editor: channels as individual rows, no table/grid."""

    _CHANNELS: list[tuple[str, str]] = [
        ("master", "channel.master"),
        ("game", "channel.game"),
        ("chat", "channel.chat"),
        ("media", "channel.media"),
        ("aux", "channel.aux"),
        ("mic", "channel.mic"),
    ]

    CELL_W = 72
    CELL_SPACING = 4   # horizontal gap between adjacent inputs
    LBL_W = 56
    LBL_PAD = 12       # gap between channel name and first input
    GAP = 40           # gap between 个人 and 流 groups
    LEFT = LBL_W + LBL_PAD  # offset for header rows to align with inputs

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._edits: dict[str, _CaptureEdit] = {}

        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(0, 4, 0, 0)

        hdr_color = DEFAULT_THEME.text_primary

        # ── Group headers "个人" / "流" ────────────────────────────
        grp = QHBoxLayout()
        grp.setSpacing(0)
        grp.addSpacing(self.LEFT)

        self._mon_h = QLabel(tr("slider.monitoring"))
        self._mon_h.setFixedWidth(self.CELL_W * 3)
        self._mon_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mon_h.setStyleSheet(f"font-weight: 700; color: {hdr_color};")
        grp.addWidget(self._mon_h)
        grp.addSpacing(self.GAP)

        self._stm_h = QLabel(tr("slider.streaming"))
        self._stm_h.setFixedWidth(self.CELL_W * 3)
        self._stm_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stm_h.setStyleSheet(f"font-weight: 700; color: {hdr_color};")
        grp.addWidget(self._stm_h)

        grp.addStretch()
        root.addLayout(grp)

        # ── Sub-headers "+ / − / 静音" ─────────────────────────────
        sub = QHBoxLayout()
        sub.setSpacing(0)
        sub.addSpacing(self.LEFT)
        self._mute_sub_labels: list[QLabel] = []
        for _g in range(2):
            for t in ("+", "−", "mute"):
                if t != "+":
                    sub.addSpacing(self.CELL_SPACING)
                lbl = QLabel(tr("slider.mute") if t == "mute" else t)
                lbl.setFixedWidth(self.CELL_W)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet(f"color: {DEFAULT_THEME.text_secondary}; font-size: 8pt;")
                if t == "mute":
                    self._mute_sub_labels.append(lbl)
                sub.addWidget(lbl)
            sub.addSpacing(self.GAP)
        sub.addStretch()
        root.addLayout(sub)

        # ── Channel rows ───────────────────────────────────────────
        self._channel_name_labels: list[QLabel] = []
        for short, i18n_key in self._CHANNELS:
            row = QHBoxLayout()
            row.setSpacing(self.CELL_SPACING)

            name = QLabel(tr(i18n_key))
            name.setFixedWidth(self.LBL_W)
            name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._channel_name_labels.append((name, i18n_key))
            row.addWidget(name)
            row.addSpacing(self.LBL_PAD - self.CELL_SPACING)

            for group in ("mon", "stm"):
                for action in ("up", "down", "mute"):
                    config_id = f"{short}_{group}_{action}"
                    edit = _CaptureEdit(config_id, self.CELL_W)
                    self._edits[config_id] = edit
                    row.addWidget(edit)
                row.addSpacing(self.GAP - self.CELL_SPACING)
            row.addStretch()
            root.addLayout(row)

        # ── Explanation note ────────────────────────────────────
        self._note = QLabel(tr("hk.classic_mode_note"))
        self._note.setStyleSheet(
            f"color: {DEFAULT_THEME.text_secondary}; font-size: 8pt; "
            f"font-style: italic; padding-top: 6px;"
        )
        self._note.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self._note)

        root.addStretch()

        # ── Language switch ──────────────────────────────────────
        on_lang_changed(self._refresh_text)

    # ── Data access ──────────────────────────────────────────────────

    def get_hotkeys(self) -> dict[str, str]:
        return {cid: edit.text() for cid, edit in self._edits.items() if edit.text()}

    def cancel_active(self) -> None:
        """Cancel any in-progress capture to avoid stuck highlights."""
        if _CaptureEdit._active:
            _CaptureEdit._active._cancel()
            _CaptureEdit._active = None

    def set_hotkeys(self, hotkeys: dict[str, str]) -> None:
        self.cancel_active()
        for cid, edit in self._edits.items():
            edit.setText(hotkeys.get(cid, ""))

    def _refresh_text(self) -> None:
        """Update all displayed text after a language change."""
        self._mon_h.setText(tr("slider.monitoring"))
        self._stm_h.setText(tr("slider.streaming"))
        for lbl in self._mute_sub_labels:
            lbl.setText(tr("slider.mute"))
        for lbl, key in self._channel_name_labels:
            lbl.setText(tr(key))
        self._note.setText(tr("hk.classic_mode_note"))


# ---------------------------------------------------------------------------
# Key code → name
# ---------------------------------------------------------------------------

def _qt_key_to_name(key: int, is_numpad: bool = False) -> str | None:
    """Map Qt key code to readable name. Excludes Esc."""
    from PySide6.QtCore import Qt as QtCore

    if key == QtCore.Key.Key_Escape.value:
        return None

    if is_numpad:
        numpad_map: dict[int, str] = {
            QtCore.Key.Key_0.value: "Numpad0",
            QtCore.Key.Key_1.value: "Numpad1",
            QtCore.Key.Key_2.value: "Numpad2",
            QtCore.Key.Key_3.value: "Numpad3",
            QtCore.Key.Key_4.value: "Numpad4",
            QtCore.Key.Key_5.value: "Numpad5",
            QtCore.Key.Key_6.value: "Numpad6",
            QtCore.Key.Key_7.value: "Numpad7",
            QtCore.Key.Key_8.value: "Numpad8",
            QtCore.Key.Key_9.value: "Numpad9",
            QtCore.Key.Key_Plus.value: "Numpad+",
            QtCore.Key.Key_Minus.value: "Numpad-",
            QtCore.Key.Key_Asterisk.value: "Numpad*",
            QtCore.Key.Key_Slash.value: "Numpad/",
            QtCore.Key.Key_Period.value: "Numpad.",
        }
        if key in numpad_map:
            return numpad_map[key]

    key_map: dict[int, str] = {
        QtCore.Key.Key_F1.value: "F1",
        QtCore.Key.Key_F2.value: "F2",
        QtCore.Key.Key_F3.value: "F3",
        QtCore.Key.Key_F4.value: "F4",
        QtCore.Key.Key_F5.value: "F5",
        QtCore.Key.Key_F6.value: "F6",
        QtCore.Key.Key_F7.value: "F7",
        QtCore.Key.Key_F8.value: "F8",
        QtCore.Key.Key_F9.value: "F9",
        QtCore.Key.Key_F10.value: "F10",
        QtCore.Key.Key_F11.value: "F11",
        QtCore.Key.Key_F12.value: "F12",
        QtCore.Key.Key_Up.value: "↑",
        QtCore.Key.Key_Down.value: "↓",
        QtCore.Key.Key_Left.value: "←",
        QtCore.Key.Key_Right.value: "→",
        QtCore.Key.Key_Space.value: "Space",
        QtCore.Key.Key_Tab.value: "Tab",
        QtCore.Key.Key_Backspace.value: "Backspace",
        QtCore.Key.Key_Delete.value: "Delete",
        QtCore.Key.Key_Insert.value: "Insert",
        QtCore.Key.Key_Home.value: "Home",
        QtCore.Key.Key_End.value: "End",
        QtCore.Key.Key_PageUp.value: "PgUp",
        QtCore.Key.Key_PageDown.value: "PgDn",
        QtCore.Key.Key_Enter.value: "Enter",
        QtCore.Key.Key_Return.value: "Enter",
        QtCore.Key.Key_Pause.value: "Pause",
        QtCore.Key.Key_Print.value: "PrtSc",
        QtCore.Key.Key_ScrollLock.value: "ScrollLock",
        QtCore.Key.Key_CapsLock.value: "CapsLock",
        QtCore.Key.Key_NumLock.value: "NumLock",
    }

    if key in key_map:
        return key_map[key]

    # Printable ASCII: 0x20–0x7E
    if 0x20 <= key <= 0x7E:
        return chr(key)

    try:
        k = QtCore.Key(key)
        if k.name:
            name = k.name.decode() if isinstance(k.name, bytes) else str(k.name)
            name = name.removeprefix("Key_")
            if not name.startswith("Meta") and name != "Escape":
                return name
    except (ValueError, AttributeError):
        pass

    return None


# ---------------------------------------------------------------------------
# Hotkey settings tab
# ---------------------------------------------------------------------------

class HotkeyTab(QWidget):
    """Tab for configuring all hotkeys."""

    captureStateChanged = Signal(bool)  # True = any capture active

    def __init__(self, config_path: Path,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = config_path

        layout = QVBoxLayout(self)

        # ── Container widget (grid + toggle, scrolls together) ─────
        container = QWidget()
        cv = QVBoxLayout(container)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(8)

        self._grid = HotkeyGrid()
        self._wire_capture_edits(self._grid)
        cv.addWidget(self._grid)

        # Toggle window row — aligned with grid columns
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(self._grid.CELL_SPACING)
        toggle_row.setContentsMargins(0, 0, 0, 0)
        self._toggle_lbl = QLabel(tr("hk.toggle_window"))
        self._toggle_lbl.setFixedWidth(self._grid.LBL_W)
        self._toggle_lbl.setWordWrap(True)
        self._toggle_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        toggle_row.addWidget(self._toggle_lbl)
        toggle_row.addSpacing(self._grid.LBL_PAD - self._grid.CELL_SPACING)

        self._toggle_edit = _CaptureEdit("toggle_window", self._grid.CELL_W)
        self._toggle_edit.captured.connect(self._on_any_captured)
        toggle_row.addWidget(self._toggle_edit)
        toggle_row.addStretch()
        cv.addLayout(toggle_row)
        cv.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; }} "
            f"QScrollArea > QWidget > QWidget {{ background: transparent; }}"
        )
        scroll.setWidget(container)
        layout.addWidget(scroll)

        on_lang_changed(self._refresh_text)

    def _refresh_text(self) -> None:
        """Update labels after language change."""
        self._toggle_lbl.setText(tr("hk.toggle_window"))

    def _wire_capture_edits(self, grid: HotkeyGrid) -> None:
        for edit in grid._edits.values():  # noqa: SLF001
            edit.captured.connect(self._on_any_captured)

    def _on_any_captured(self, config_id: str, combo: str) -> None:
        self.captureStateChanged.emit(True)   # pause hotkeys during capture
        self.captureStateChanged.emit(False)  # resume after

    def load(self, hotkeys: dict[str, str] | None = None) -> None:
        """Load hotkeys from YAML or dict."""
        if hotkeys is not None:
            hk = hotkeys
        elif self._config_path.exists():
            data = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
            hk = data.get("hotkeys", {})
        else:
            hk = {}
        self._grid.set_hotkeys(hk)
        self._toggle_edit.setText(hk.get("toggle_window", ""))

    def save(self) -> None:
        """Save hotkeys to YAML."""
        hotkeys = self._grid.get_hotkeys()
        toggle_val = self._toggle_edit.text().strip()
        if toggle_val:
            hotkeys["toggle_window"] = toggle_val
        existing: dict[str, dict] = {}
        if self._config_path.exists():
            existing = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
        existing["hotkeys"] = hotkeys
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            yaml.dump(existing, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

    def get_hotkeys(self) -> dict[str, str]:
        hotkeys = self._grid.get_hotkeys()
        toggle_val = self._toggle_edit.text().strip()
        if toggle_val:
            hotkeys["toggle_window"] = toggle_val
        return hotkeys


# ---------------------------------------------------------------------------
# General settings tab
# ---------------------------------------------------------------------------

class GeneralTab(QWidget):
    """General settings tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self._group = QGroupBox(tr("general.behaviour"))
        g_layout = QVBoxLayout(self._group)

        self._startup_cb = QCheckBox(tr("general.start_minimized"))
        g_layout.addWidget(self._startup_cb)

        self._on_top_cb = QCheckBox(tr("general.always_on_top"))
        self._on_top_cb.setChecked(True)
        g_layout.addWidget(self._on_top_cb)

        self._toast_cb = QCheckBox(tr("general.show_toast"))
        self._toast_cb.setChecked(True)
        g_layout.addWidget(self._toast_cb)

        layout.addWidget(self._group)
        layout.addStretch()

        on_lang_changed(self._refresh_text)

    def _refresh_text(self) -> None:
        """Update labels after language change."""
        self._group.setTitle(tr("general.behaviour"))
        self._startup_cb.setText(tr("general.start_minimized"))
        self._on_top_cb.setText(tr("general.always_on_top"))
        self._toast_cb.setText(tr("general.show_toast"))

    @property
    def start_minimized(self) -> bool:
        return self._startup_cb.isChecked()

    @property
    def always_on_top(self) -> bool:
        return self._on_top_cb.isChecked()

    @property
    def show_toast(self) -> bool:
        return self._toast_cb.isChecked()

    def set_values(self, data: dict[str, bool]) -> None:
        """Apply settings from a dict."""
        self._startup_cb.setChecked(data.get("start_minimized", False))
        self._on_top_cb.setChecked(data.get("always_on_top", True))
        self._toast_cb.setChecked(data.get("show_toast", True))

    def get_values(self) -> dict[str, bool]:
        return {
            "start_minimized": self.start_minimized,
            "always_on_top": self.always_on_top,
            "show_toast": self.show_toast,
        }


# ---------------------------------------------------------------------------
# About tab
# ---------------------------------------------------------------------------

class AboutTab(QWidget):
    """About tab — app info, features, credits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        # ── App name ──────────────────────────────────────────────
        self._name = QLabel(tr("about.app_name"))
        self._name.setStyleSheet("font-size: 18pt; font-weight: 700; color: #42b983;")
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._name)

        # ── Version ───────────────────────────────────────────────
        self._ver = QLabel(f"v{APP_VERSION}")
        self._ver.setStyleSheet("font-size: 9pt; color: #8b949e;")
        self._ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._ver)

        # ── Tagline ───────────────────────────────────────────────
        self._tagline = QLabel(tr("about.tagline"))
        self._tagline.setStyleSheet("font-size: 8pt; color: #6e7681;")
        self._tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tagline.setWordWrap(True)
        layout.addWidget(self._tagline)

        layout.addSpacing(6)

        # ── Info table ────────────────────────────────────────────
        info = QFormLayout()
        info.setSpacing(6)
        info.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        info.setContentsMargins(0, 0, 0, 0)

        self._info_pairs: list[tuple[QLabel, QLabel, str, str]] = []
        info_data: list[tuple[str, str]] = [
            ("about.author", "about.author_name"),
            ("about.license", "about.license_value"),
            ("about.github", "about.github_url"),
        ]
        for label_key, value in info_data:
            lbl = QLabel(tr(label_key) + ":")
            lbl.setStyleSheet("font-size: 9pt; color: #8b949e; font-weight: 600;")
            val_str = tr(value) if value.startswith("about.") else value
            if label_key == "about.github":
                val = QLabel(
                    f'<a href="{GITHUB_URL}" style="color: #42b983; '
                    f'text-decoration: none; font-size: 9pt;">{val_str}</a>'
                )
                val.setOpenExternalLinks(True)
            else:
                val = QLabel(val_str)
                val.setStyleSheet("font-size: 9pt;")
            info.addRow(lbl, val)
            self._info_pairs.append((lbl, val, label_key, value))

        info_widget = QWidget()
        info_widget.setLayout(info)
        layout.addWidget(info_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        # ── Separator ─────────────────────────────────────────────
        sep = QLabel("─" * 40)
        sep.setStyleSheet("color: #30363d; font-size: 6pt;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sep)

        layout.addSpacing(4)

        # ── Features ──────────────────────────────────────────────
        self._feat_title = QLabel(tr("about.features_title"))
        self._feat_title.setStyleSheet("font-size: 9pt; font-weight: 700; color: #e6edf3;")
        self._feat_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._feat_title)

        self._feat_body = QLabel(tr("about.features"))
        self._feat_body.setStyleSheet(
            "font-size: 8pt; color: #8b949e; line-height: 1.6;"
        )
        self._feat_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._feat_body.setWordWrap(True)
        layout.addWidget(self._feat_body)

        layout.addSpacing(8)

        # ── Tech stack ────────────────────────────────────────────
        self._tech = QLabel(tr("about.tech_stack"))
        self._tech.setStyleSheet("font-size: 7pt; color: #6e7681;")
        self._tech.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._tech)

        layout.addStretch()

        on_lang_changed(self._refresh_text)

    def _refresh_text(self) -> None:
        """Update labels after language change."""
        self._name.setText(tr("about.app_name"))
        self._tagline.setText(tr("about.tagline"))
        for lbl, val, label_key, value in self._info_pairs:
            lbl.setText(tr(label_key) + ":")
            if label_key == "about.github":
                val_str = tr(value) if value.startswith("about.") else value
                val.setText(
                    f'<a href="{GITHUB_URL}" style="color: #42b983; '
                    f'text-decoration: none; font-size: 9pt;">{val_str}</a>'
                )
            elif value.startswith("about."):
                val.setText(tr(value))
        self._feat_title.setText(tr("about.features_title"))
        self._feat_body.setText(tr("about.features"))
        self._tech.setText(tr("about.tech_stack"))


# ---------------------------------------------------------------------------
# Settings window
# ---------------------------------------------------------------------------

class SettingsWindow(QWidget):
    """Independent settings window."""

    configSaved = Signal()
    configLoaded = Signal()

    def __init__(self, config_path: Path, theme: ThemeColors | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme or DEFAULT_THEME
        self._config_path = config_path

        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(620, 400)
        self.resize(650, 480)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()

        self._hotkey_tab = HotkeyTab(config_path)
        self._general_tab = GeneralTab()
        self._about_tab = AboutTab()

        self._tabs.addTab(self._hotkey_tab, tr("settings.tab_hotkeys"))
        self._tabs.addTab(self._general_tab, tr("settings.tab_general"))
        self._tabs.addTab(self._about_tab, tr("settings.tab_about"))

        layout.addWidget(self._tabs)

        # Bottom buttons: 加载 | 应用 | 关闭
        btn_row = QHBoxLayout()
        self._load_btn = QPushButton(tr("settings.reload"))
        self._load_btn.clicked.connect(self._load_all)
        self._apply_btn = QPushButton(tr("settings.save_all"))
        self._apply_btn.clicked.connect(self._apply_all)
        self._close_btn = QPushButton(tr("settings.close"))
        self._close_btn.clicked.connect(self.close)

        btn_row.addWidget(self._load_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self._load_all()
        on_lang_changed(self._refresh_text)

    def _refresh_text(self) -> None:
        """Update window title, tabs, and buttons after language change."""
        self.setWindowTitle(tr("settings.title"))
        self._tabs.setTabText(0, tr("settings.tab_hotkeys"))
        self._tabs.setTabText(1, tr("settings.tab_general"))
        self._tabs.setTabText(2, tr("settings.tab_about"))
        self._load_btn.setText(tr("settings.reload"))
        self._apply_btn.setText(tr("settings.save_all"))
        self._close_btn.setText(tr("settings.close"))

    # ── Persistence ──────────────────────────────────────────────────

    def _load_all(self) -> None:
        """Load all settings from config.yaml."""
        if not self._config_path.exists():
            return
        data = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        if not data:
            return
        self._hotkey_tab.load(data.get("hotkeys", {}))
        self._general_tab.set_values(data.get("settings", {}))
        self.configLoaded.emit()

    def _apply_all(self) -> None:
        """Save all settings to config.yaml and apply."""
        hotkeys = self._hotkey_tab.get_hotkeys()
        settings = self._general_tab.get_values()

        data: dict[str, dict] = {"hotkeys": hotkeys, "settings": settings}
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        self.configSaved.emit()

    # ── Public accessors ─────────────────────────────────────────────

    def get_hotkeys(self) -> dict[str, str]:
        return self._hotkey_tab.get_hotkeys()

    @property
    def show_toast(self) -> bool:
        return self._general_tab.show_toast

    @property
    def always_on_top(self) -> bool:
        return self._general_tab.always_on_top

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        self.hide()
        event.ignore()
