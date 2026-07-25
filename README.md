<h1 align="center">SonarMix</h1>

<p align="center">
  <em>A compact Windows system-tray volume mixer for <strong>SteelSeries GG Sonar</strong><br/>with global hotkeys, bilingual UI, and one-click Streamer/Classic mode toggle.</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License: MIT"/></a>
  <a href="https://github.com/Brett-Now/SonarMix/stargazers"><img src="https://img.shields.io/github/stars/Brett-Now/SonarMix?style=flat-square" alt="GitHub Stars"/></a>
  <a href="https://github.com/Brett-Now/SonarMix/releases"><img src="https://img.shields.io/github/v/release/Brett-Now/SonarMix?include_prereleases&style=flat-square" alt="Release"/></a>
  <a href="#tech-stack"><img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"/></a>
  <a href="#tech-stack"><img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey?style=flat-square" alt="Windows 10/11"/></a>
</p>

<p align="center">
  <b>English</b> | <a href="README_zh.md">简体中文</a>
</p>

---

## Screenshots

<p align="center">
  <table align="center">
    <tr>
      <td align="center"><b>Classic Mode</b></td>
      <td align="center"><b>Streamer Mode</b></td>
    </tr>
    <tr>
      <td align="center"><img src="screenshots/screenshot-classic.png" alt="Classic Mode"/></td>
      <td align="center"><img src="screenshots/screenshot-streamer.png" alt="Streamer Mode"/></td>
    </tr>
    <tr>
      <td align="center" colspan="2"><b>Settings</b></td>
    </tr>
    <tr>
      <td align="center" colspan="2"><img src="screenshots/screenshot-settings.png" alt="Settings"/></td>
    </tr>
  </table>
</p>

---

## Features

| Category | Details |
|----------|---------|
| **Compact Panel** | 6 channel groups in a 2×3 grid, always-on-top |
| **Streamer / Classic** | One-click toggle — 12 sliders (monitoring + streaming) or 6 sliders |
| **System Tray** | Left-click show/hide, right-click Settings / Quit |
| **Global Hotkeys** | Configurable key combos per channel (vol ± / mute), up to 37 bindings |
| **Toast Notifications** | Dark card-style popup on hotkey volume changes |
| **Bilingual** | 中文 / English — built-in language toggle |
| **YAML Config** | Hotkeys and settings in `config.yaml`, visual editor in-app |
| **Drag-safe** | Slider drag pauses hotkey + refresh to prevent conflicts |

---

## Prerequisites

- **Windows 10 or 11**
- **SteelSeries GG** with Sonar enabled and running
- **Python 3.10+** (or use the packaged `.exe`)

---

## Quick Start

```bash
# Install dependencies
pip install steelseries-sonar-py PySide6 keyboard PyYAML

# Run
python main.py
```

### Build standalone `.exe`

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name SonarMix --icon=app.ico \
    --add-data "config.yaml;." \
    --hidden-import ssl --hidden-import _ssl --hidden-import certifi \
    --collect-data certifi \
    main.py
```

> [!NOTE]
> If hotkeys don't respond on your system, try running as administrator — the `keyboard` library's global hooks may need elevation on some Windows configurations.

---

## Configuration

`config.yaml` in the app directory:

```yaml
# Examples — add your own in the Settings window (gear icon ⚙)
hotkeys:
  master_mon_up: Numpad8
  master_mon_down: Numpad5
  toggle_window: Ctrl+Shift+S

settings:
  always_on_top: true    # keep window on top
  language: zh           # zh (Chinese) or en (English)
  show_toast: true       # show popup on hotkey volume change
  start_minimized: false # start minimized to tray
```

Open the **Settings** window (gear icon ⚙) for a visual hotkey editor — click any cell and press your key combo.

---

## Project Structure

```text
SonarMix/
├── main.py          # Entry point — wiring, periodic refresh
├── mixer_ui.py      # Main window — slider grid, toggle, mute buttons
├── settings_ui.py   # Settings window — hotkey editor, general, about
├── sonar_ctrl.py    # Sonar API wrapper — snapshot, set volume, mute
├── hotkey.py        # Global hotkey manager + toast popup
├── tray.py          # System tray icon + context menu
├── i18n.py          # Chinese / English translation tables
├── theme.py         # Dark theme color tokens (Vue-inspired)
├── config.yaml      # User config — hotkeys, settings
└── pyproject.toml   # Python project metadata
```

---

## Tech Stack

| Layer | Component |
|-------|-----------|
| **API** | [steelseries-sonar-py](https://github.com/Mark7888/steelseries-sonar-py) |
| **GUI** | [PySide6](https://pypi.org/project/PySide6/) (Qt 6) |
| **Hotkeys** | [keyboard](https://pypi.org/project/keyboard/) |
| **Config** | [PyYAML](https://pypi.org/project/PyYAML/) |
| **Packaging** | [PyInstaller](https://pypi.org/project/pyinstaller/) |

---

## Acknowledgments

This project is built on [**steelseries-sonar-py**](https://github.com/Mark7888/steelseries-sonar-py) by [Mark7888](https://github.com/Mark7888), the Python wrapper for SteelSeries GG Sonar's local HTTP API.

---

## Known Limitations

- **Hotkeys may need admin** — `keyboard` library hooks may require elevation on some Windows setups
- **GG must be running** — SonarMix is a controller, not a standalone mixer
- **Mode switch timing** — Streamer ↔ Classic toggle needs a brief moment for GG to rebuild its audio graph

---

## Disclaimer

1. This tool is for **personal use and technical reference** only.
2. SonarMix is an **unofficial third-party controller** — it is not affiliated with, endorsed by, or connected to SteelSeries.
3. The `keyboard` library hooks at the OS level; users should review their system's security policies before use.
4. The author assumes **no liability** for audio hardware issues, system instability, or any other consequences resulting from use of this software.
5. Do not use for any **illegal, improper, or rights-infringing** purpose.

---

## License

MIT — see [LICENSE](LICENSE)

```
Copyright (c) 2026 Brett Now
```
