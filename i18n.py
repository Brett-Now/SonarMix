"""
Simple i18n module — dict-based, no external dependencies.
Default language: Chinese (zh). Switch with set_lang("en").
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Translation tables
# ---------------------------------------------------------------------------

_ZH: dict[str, str] = {
    # App
    "app.title": "SonarMix",

    # Channels (display names)
    "channel.master": "主控",
    "channel.game": "游戏",
    "channel.chat": "聊天",
    "channel.media": "媒体",
    "channel.aux": "辅助输入",
    "channel.mic": "麦克风",

    # Slider labels (short)
    "slider.monitoring": "个人",
    "slider.streaming": "流",
    "slider.mute": "静音",

    # Mixer window
    "mixer.settings_tooltip": "设置",
    "mixer.streamer_mode": "Streamer 模式",
    "mixer.mute_all_mon": "个人全静音",
    "mixer.mute_all_stm": "流全静音",
    "mixer.mute_all": "全部静音",

    # Tray
    "tray.show": "显示",
    "tray.hide": "隐藏",
    "tray.settings": "设置",
    "tray.quit": "退出",

    # Settings window
    "settings.title": "SonarMix — 设置",
    "settings.tab_hotkeys": "快捷键",
    "settings.tab_general": "常规",
    "settings.tab_about": "关于",
    "settings.tab_log": "日志",
    "log.clear": "清空",
    "settings.save": "保存",
    "settings.reload": "加载",
    "settings.save_all": "应用",
    "settings.close": "关闭",
    "settings.hotkey_placeholder": "点击此处，按下组合键…",

    # General settings
    "general.behaviour": "行为",
    "general.start_minimized": "启动时最小化到托盘",
    "general.always_on_top": "窗口置顶",
    "general.show_toast": "快捷键调节时显示提示",

    # About
    "about.app_name": "SonarMix",
    "about.description": "SteelSeries GG Sonar 自定义音量混音器",
    "about.tagline": "Windows 系统托盘音量混音器 · 全局热键 · 中英双语 · Streamer/普通一键切换",
    "about.version": "版本",
    "about.author": "作者",
    "about.author_name": "Brett-Now",
    "about.license": "许可证",
    "about.license_value": "MIT",
    "about.github": "GitHub",
    "about.github_url": "https://github.com/Brett-Now/SonarMix",
    "about.features_title": "功能特性",
    "about.features": "6 频道紧凑面板 · Streamer / 普通模式切换\n系统托盘 · 全局热键（最多 37 组）\nToast 弹窗提示 · 中英双语 · 拖拽保护",
    "about.tech_stack": "PySide6 · steelseries-sonar-py · keyboard · PyYAML · PyInstaller",
    "about.ack_title": "致谢",
    "about.ack_body": "本项目基于 Mark7888 开发的 steelseries-sonar-py 构建\n该库封装了 SteelSeries GG Sonar 本地 HTTP API\n所有音量读写与模式切换均通过此库完成",

    # Hotkey action labels
    "hk.classic_mode_note": "普通模式下，快捷键使用「个人」列的设置",
    "hk.toggle_window": "切换窗口",
    "hk.master_mon_up": "主控 个人 +",
    "hk.master_mon_down": "主控 个人 −",
    "hk.master_stm_up": "主控 流 +",
    "hk.master_stm_down": "主控 流 −",
    "hk.game_mon_up": "游戏 个人 +",
    "hk.game_mon_down": "游戏 个人 −",
    "hk.game_stm_up": "游戏 流 +",
    "hk.game_stm_down": "游戏 流 −",
    "hk.chat_mon_up": "聊天 个人 +",
    "hk.chat_mon_down": "聊天 个人 −",
    "hk.chat_stm_up": "聊天 流 +",
    "hk.chat_stm_down": "聊天 流 −",
    "hk.media_mon_up": "媒体 个人 +",
    "hk.media_mon_down": "媒体 个人 −",
    "hk.media_stm_up": "媒体 流 +",
    "hk.media_stm_down": "媒体 流 −",
    "hk.aux_mon_up": "辅助输入 个人 +",
    "hk.aux_mon_down": "辅助输入 个人 −",
    "hk.aux_stm_up": "辅助输入 流 +",
    "hk.aux_stm_down": "辅助输入 流 −",
    "hk.mic_mon_up": "麦克风 个人 +",
    "hk.mic_mon_down": "麦克风 个人 −",
    "hk.mic_stm_up": "麦克风 流 +",
    "hk.mic_stm_down": "麦克风 流 −",
    "hk.master_mon_mute": "主控 个人 静音",
    "hk.master_stm_mute": "主控 流 静音",
    "hk.game_mon_mute": "游戏 个人 静音",
    "hk.game_stm_mute": "游戏 流 静音",
    "hk.chat_mon_mute": "聊天 个人 静音",
    "hk.chat_stm_mute": "聊天 流 静音",
    "hk.media_mon_mute": "媒体 个人 静音",
    "hk.media_stm_mute": "媒体 流 静音",
    "hk.aux_mon_mute": "辅助输入 个人 静音",
    "hk.aux_stm_mute": "辅助输入 流 静音",
    "hk.mic_mon_mute": "麦克风 个人 静音",
    "hk.mic_stm_mute": "麦克风 流 静音",
}

_EN: dict[str, str] = {
    # App
    "app.title": "SonarMix",

    # Channels
    "channel.master": "Master",
    "channel.game": "Game",
    "channel.chat": "Chat",
    "channel.media": "Media",
    "channel.aux": "Aux",
    "channel.mic": "Mic",

    # Slider labels
    "slider.monitoring": "Mon",
    "slider.streaming": "Stm",
    "slider.mute": "Mute",

    # Mixer window
    "mixer.settings_tooltip": "Settings",
    "mixer.streamer_mode": "Streamer Mode",
    "mixer.mute_all_mon": "Mute All Mon",
    "mixer.mute_all_stm": "Mute All Stm",
    "mixer.mute_all": "Mute All",

    # Tray
    "tray.show": "Show",
    "tray.hide": "Hide",
    "tray.settings": "Settings",
    "tray.quit": "Quit",

    # Settings window
    "settings.title": "SonarMix — Settings",
    "settings.tab_hotkeys": "Hotkeys",
    "settings.tab_general": "General",
    "settings.tab_about": "About",
    "settings.tab_log": "Log",
    "log.clear": "Clear",
    "settings.save": "Save",
    "settings.reload": "Load",
    "settings.save_all": "Apply",
    "settings.close": "Close",
    "settings.hotkey_placeholder": "Click to set, press key combo…",

    # General settings
    "general.behaviour": "Behaviour",
    "general.start_minimized": "Start minimized to tray",
    "general.always_on_top": "Always on top",
    "general.show_toast": "Show toast on hotkey volume change",

    # About
    "about.app_name": "SonarMix",
    "about.description": "SteelSeries GG Sonar custom volume mixer",
    "about.tagline": "Windows tray volume mixer · global hotkeys · bilingual · Streamer/Classic toggle",
    "about.version": "Version",
    "about.author": "Author",
    "about.author_name": "Brett-Now",
    "about.license": "License",
    "about.license_value": "MIT",
    "about.github": "GitHub",
    "about.github_url": "https://github.com/Brett-Now/SonarMix",
    "about.features_title": "Features",
    "about.features": "6-channel compact panel · Streamer / Classic toggle\nSystem tray · global hotkeys (up to 37 bindings)\nToast notifications · bilingual UI · drag-safe",
    "about.tech_stack": "PySide6 · steelseries-sonar-py · keyboard · PyYAML · PyInstaller",
    "about.ack_title": "Acknowledgments",
    "about.ack_body": "Built on steelseries-sonar-py by Mark7888\nPython wrapper for SteelSeries GG Sonar local HTTP API\nAll volume, mute, and mode switching is powered by this library",

    # Hotkey action labels
    "hk.classic_mode_note": "In Classic mode, hotkeys use the 'Mon' column settings",
    "hk.toggle_window": "Toggle Window",
    "hk.master_mon_up": "Master Mon +",
    "hk.master_mon_down": "Master Mon −",
    "hk.master_stm_up": "Master Stm +",
    "hk.master_stm_down": "Master Stm −",
    "hk.game_mon_up": "Game Mon +",
    "hk.game_mon_down": "Game Mon −",
    "hk.game_stm_up": "Game Stm +",
    "hk.game_stm_down": "Game Stm −",
    "hk.chat_mon_up": "Chat Mon +",
    "hk.chat_mon_down": "Chat Mon −",
    "hk.chat_stm_up": "Chat Stm +",
    "hk.chat_stm_down": "Chat Stm −",
    "hk.media_mon_up": "Media Mon +",
    "hk.media_mon_down": "Media Mon −",
    "hk.media_stm_up": "Media Stm +",
    "hk.media_stm_down": "Media Stm −",
    "hk.aux_mon_up": "Aux Mon +",
    "hk.aux_mon_down": "Aux Mon −",
    "hk.aux_stm_up": "Aux Stm +",
    "hk.aux_stm_down": "Aux Stm −",
    "hk.mic_mon_up": "Mic Mon +",
    "hk.mic_mon_down": "Mic Mon −",
    "hk.mic_stm_up": "Mic Stm +",
    "hk.mic_stm_down": "Mic Stm −",
    "hk.master_mon_mute": "Master Mon Mute",
    "hk.master_stm_mute": "Master Stm Mute",
    "hk.game_mon_mute": "Game Mon Mute",
    "hk.game_stm_mute": "Game Stm Mute",
    "hk.chat_mon_mute": "Chat Mon Mute",
    "hk.chat_stm_mute": "Chat Stm Mute",
    "hk.media_mon_mute": "Media Mon Mute",
    "hk.media_stm_mute": "Media Stm Mute",
    "hk.aux_mon_mute": "Aux Mon Mute",
    "hk.aux_stm_mute": "Aux Stm Mute",
    "hk.mic_mon_mute": "Mic Mon Mute",
    "hk.mic_stm_mute": "Mic Stm Mute",
}

_TRANSLATIONS: dict[str, dict[str, str]] = {"zh": _ZH, "en": _EN}
_current_lang: str = "zh"
_on_change_callbacks: list = []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def tr(key: str) -> str:
    """Translate a key into the current language. Falls back to the key itself."""
    table = _TRANSLATIONS.get(_current_lang, _ZH)
    return table.get(key, key)


def set_lang(lang: str) -> None:
    """Switch language. Supported: 'zh', 'en'."""
    global _current_lang
    if lang in _TRANSLATIONS and lang != _current_lang:
        _current_lang = lang
        for cb in _on_change_callbacks:
            cb()


def get_lang() -> str:
    """Return the current language code."""
    return _current_lang


def on_lang_changed(callback) -> None:
    """Register a callback to be called when language changes."""
    _on_change_callbacks.append(callback)


# ---------------------------------------------------------------------------
# Convenience: channel display names
# ---------------------------------------------------------------------------

_CHANNEL_DISPLAY_KEYS: dict[str, str] = {
    "master": "channel.master",
    "game": "channel.game",
    "chatRender": "channel.chat",
    "media": "channel.media",
    "aux": "channel.aux",
    "chatCapture": "channel.mic",
}


def channel_name(api_key: str) -> str:
    """Get translated display name for a Sonar API channel key."""
    i18n_key = _CHANNEL_DISPLAY_KEYS.get(api_key, api_key)
    return tr(i18n_key)
