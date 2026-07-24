"""
Theme definitions for SonarMix.
Hardcoded color tokens extracted from Vue.js documentation themes.
Two variants: Light and Dark, sharing the same accent (#42b983).
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ThemeColors:
    """A single theme's complete color palette."""

    accent: str
    accent_hover: str

    text_primary: str
    text_secondary: str
    text_muted: str

    bg_primary: str
    bg_secondary: str
    bg_hover: str
    bg_code: str

    border: str
    border_hover: str

    # Derived / semantic colors
    slider_track: str        # accent color mapped
    slider_handle: str       # accent color
    slider_handle_hover: str  # accent hover
    slider_groove: str       # subtle track
    danger: str
    danger_dim: str
    success: str
    warning: str

    toast_bg: str
    toast_fg: str
    toast_border: str

    mute_active: str         # when channel is muted
    mute_inactive: str       # when channel is active


# ---------------------------------------------------------------------------
# Light Theme
# ---------------------------------------------------------------------------

LIGHT: Final[ThemeColors] = ThemeColors(
    accent="#42b983",
    accent_hover="#5ec9a3",

    text_primary="#34495e",
    text_secondary="#8b949e",
    text_muted="#6e7681",

    bg_primary="#ffffff",
    bg_secondary="#f8f8f8",
    bg_hover="#f0f0f0",
    bg_code="#f8f8f8",

    border="#eeeeee",
    border_hover="#dddddd",

    slider_track="#42b983",
    slider_handle="#42b983",
    slider_handle_hover="#5ec9a3",
    slider_groove="#d0d7de",

    danger="#cb2431",
    danger_dim="#f8514926",
    success="#42b983",
    warning="#bf8700",

    toast_bg="#2d2d2d",
    toast_fg="#e6edf3",
    toast_border="#30363d",

    mute_active="#cb2431",
    mute_inactive="#42b983",
)


# ---------------------------------------------------------------------------
# Dark Theme (default)
# ---------------------------------------------------------------------------

DARK: Final[ThemeColors] = ThemeColors(
    accent="#42b983",
    accent_hover="#5ec9a3",

    text_primary="#e6edf3",
    text_secondary="#8b949e",
    text_muted="#6e7681",

    bg_primary="#1a1a1a",
    bg_secondary="#2d2d2d",
    bg_hover="#252525",
    bg_code="#282828",

    border="#30363d",
    border_hover="#444444",

    slider_track="#42b983",
    slider_handle="#42b983",
    slider_handle_hover="#5ec9a3",
    slider_groove="#3d444d",

    danger="#f85149",
    danger_dim="#f8514926",
    success="#42b983",
    warning="#d2991d",

    toast_bg="#2d2d2d",
    toast_fg="#e6edf3",
    toast_border="#30363d",

    mute_active="#f85149",
    mute_inactive="#42b983",
)


# ---------------------------------------------------------------------------
# Default theme for the application
# ---------------------------------------------------------------------------

DEFAULT_THEME: Final[ThemeColors] = DARK


def apply_theme(app, theme: ThemeColors) -> str:
    """Generate and apply a Qt stylesheet from a theme, return the stylesheet."""
    ss = f"""
    /* === SonarMix Global Stylesheet === */

    QMainWindow {{
        background-color: {theme.bg_primary};
    }}

    QWidget {{
        color: {theme.text_primary};
        font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        font-size: 9pt;
    }}

    /* ── Sliders ─────────────────────────────────── */

    QSlider::groove:horizontal {{
        background: {theme.slider_groove};
        height: 4px;
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: {theme.slider_handle};
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }}

    QSlider::handle:horizontal:hover {{
        background: {theme.slider_handle_hover};
    }}

    QSlider::sub-page:horizontal {{
        background: {theme.slider_track};
        border-radius: 2px;
    }}

    /* ── Buttons ─────────────────────────────────── */

    QPushButton {{
        background-color: {theme.bg_secondary};
        border: 1px solid {theme.border};
        border-radius: 3px;
        padding: 3px 8px;
        color: {theme.text_primary};
        min-width: 20px;
        min-height: 20px;
    }}

    QPushButton:hover {{
        background-color: {theme.bg_hover};
        border-color: {theme.border_hover};
    }}

    QPushButton:pressed {{
        background-color: {theme.accent};
        color: #ffffff;
    }}

    /* ── Labels ──────────────────────────────────── */

    QLabel {{
        color: {theme.text_primary};
        background: transparent;
    }}

    QLabel#channelLabel {{
        font-weight: 600;
        font-size: 8pt;
        color: {theme.text_secondary};
    }}

    QLabel#volumeLabel {{
        font-size: 7pt;
        color: {theme.text_muted};
        min-width: 24px;
    }}

    /* ── Group Box ───────────────────────────────── */

    QGroupBox {{
        border: 1px solid {theme.border};
        border-radius: 4px;
        margin-top: 6px;
        padding-top: 10px;
        background-color: {theme.bg_secondary};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {theme.accent};
        font-weight: 600;
        font-size: 8pt;
    }}

    /* ── Toast ───────────────────────────────────── */

    QFrame#toastFrame {{
        background-color: {theme.toast_bg};
        border: 1px solid {theme.toast_border};
        border-radius: 6px;
    }}

    QLabel#toastLabel {{
        color: {theme.toast_fg};
        font-size: 10pt;
        font-weight: 600;
    }}

    /* ── Tool Buttons ────────────────────────────── */

    QToolButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 3px;
        padding: 2px;
        color: {theme.text_secondary};
    }}

    QToolButton:hover {{
        background-color: {theme.bg_hover};
        color: {theme.accent};
    }}

    /* ── Scrollbar ───────────────────────────────── */

    QScrollBar:vertical {{
        background: {theme.bg_primary};
        width: 6px;
        border: none;
    }}

    QScrollBar::handle:vertical {{
        background: {theme.slider_groove};
        border-radius: 3px;
        min-height: 20px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {theme.text_muted};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
    app.setStyleSheet(ss)
    return ss
