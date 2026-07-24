# SAO Utils 2 挂件支持 — 设计文档

> 状态：已确认，待实现  
> 日期：2026-07-24  
> 上级需求：CLAUDE.md v1.2 里程碑

---

## 一、架构总览

```
SonarMix (Python/Qt)                          SAO Utils 2 桌面
┌──────────────────────────────────┐          ┌─────────────────────────┐
│  main.py                         │          │  widget/                │
│  ├── SonarMixApp                 │          │  ├── package.json       │
│  │   ├── SonarCtrl (threading.Lock)  ◄──HTTP──┤── SonarMixWidget.qml  │
│  │   ├── HttpServer (daemon线程)    │          │  └── Presets/        │
│  │   ├── MixerWidget              │          │      └── sonarmix.png  │
│  │   ├── HotkeyManager            │          └─────────────────────────┘
│  │   ├── SettingsWindow           │
│  │   │   └── GeneralTab (新增开关)  │
│  │   └── TrayController           │
│  └────────────────────────────────┘
```

**数据流**：
```
GG Sonar ← steelseries-sonar-py ← SonarCtrl ←→ HTTP API ←→ QML Widget (XMLHttpRequest 轮询)
```

---

## 二、新增文件

### 2.1 `server.py` — HTTP API Server

**技术选型**：Python stdlib `http.server.HTTPServer` + daemon 线程  
**绑定地址**：`127.0.0.1`（仅本机，安全）  
**默认端口**：`18999`（可配置）

**类结构**：

```python
class SonarHttpServer:
    def __init__(self, sonar: SonarCtrl, port: int = 18999)
    def start() -> bool      # 启动 daemon 线程，失败返回 False（端口占用等）
    def stop()               # 关闭 server，join 线程
    def is_running() -> bool
```

**线程安全**：所有请求处理在主线程之外，通过 `SonarCtrl` 内置的 `threading.Lock` 保护（见 3.1 节）。

**API 端点**：

| 方法 | 路径 | 请求体 | 响应 | 说明 |
|------|------|--------|------|------|
| `GET` | `/api/status` | — | JSON（见下方示例） | 全量音量快照 + 模式 |
| `POST` | `/api/set-volume` | `{"channel":"game","slider":"monitoring","volume":80}` | `{"ok":true}` | 设置单频道音量 |
| `POST` | `/api/toggle-mute` | `{"channel":"master","slider":"monitoring"}` | `{"ok":true}` | 切换静音 |
| `POST` | `/api/set-mode` | `{"streamer_mode":true}` | `{"ok":true}` | 切换模式 |

**`GET /api/status` 响应**：
```json
{
  "mode": "streamer",
  "channels": {
    "master":     {"monitoring": {"volume": 80, "muted": false}, "streaming": {"volume": 100, "muted": false}},
    "game":       {"monitoring": {"volume": 50, "muted": false}, "streaming": {"volume": 50, "muted": false}},
    "chatRender": {"monitoring": {"volume": 30, "muted": true},  "streaming": {"volume": 40, "muted": false}},
    "media":      {"monitoring": {"volume": 60, "muted": false}, "streaming": {"volume": 60, "muted": false}},
    "aux":        {"monitoring": {"volume": 45, "muted": false}, "streaming": {"volume": 45, "muted": false}},
    "chatCapture":{"monitoring": {"volume": 90, "muted": false}, "streaming": {"volume": 90, "muted": false}}
  }
}
```
> `volume` 为 0–100 整数，`muted` 为 boolean。  
> Classic 模式下 `monitoring` 和 `streaming` 值相同。

**CORS**：所有响应加 `Access-Control-Allow-Origin: *` header（SAO Utils 2 内部浏览器可能跨域）。

**异常处理**：
- 端口被占用 → `log_error` + 返回 `start() == False`
- Sonar API 不可用（GG 未运行）→ 返回 `{"error": "sonar_unavailable"}` + HTTP 503
- 请求体 JSON 解析失败 → `{"error": "bad_request"}` + HTTP 400

---

### 2.2 `widget/SonarMixWidget.qml` — SAO Utils 2 桌面挂件

**继承**：`NERvGear.Templates.Widget`（即 Qt Quick `Item`）  
**零依赖**：只用 `QtQuick` 内置类型（Rectangle、MouseArea、Text、Timer），不 import `QtQuick.Controls`

#### DotSlider 自定义组件（内嵌在 QML 中）

```
┌─────────────────────────────────────────┐
│  ●────────────────────────────○───────  │  ← 灰色轨道 + 绿色已填充 + 当前圆点
│  频道名                         65%      │  ← 左侧标签 + 右侧数值
└─────────────────────────────────────────┘
```

**元素**（全 Rectangle + MouseArea + Text）：

| 元素 | QML 实现 | 尺寸/样式 |
|------|---------|----------|
| 轨道线 | `Rectangle` | h=4px, radius=2, 灰色 `#3d444d` |
| 已填充 | `Rectangle` | h=4px, radius=2, 绿色 `#42b983`, width 动态 |
| 当前圆点 | `Rectangle` | 10×10→16×16（拖拽时放大）, radius=半宽, 绿色 `#42b983` + glow 阴影 |
| 交互 | `MouseArea` | 覆盖整行, `onPressed`+`onPositionChanged`（支持拖拽） |
| 标签 | `Text` | 左侧频道名, font 9pt |
| 数值 | `Text` | 右侧百分比, font 8pt, 颜色 `#8b949e` |

**计算**：`volume = Math.round(mouseX / trackWidth * 100)`, clamp 0–100

**交互细节**：
- 点击轨道：直接跳到对应位置
- 拖拽圆点：跟随鼠标，松手后圆点缩回 10px
- 拖拽中：圆点放大 1.6x + 外发光（`radius: 10` 的半透明 `Rectangle`）
- 松手：发送 `POST /api/set-volume`

#### 紧凑/展开模式

**紧凑模式**（默认，~240×80px）：
```
┌──────────────────────────────────┐
│  Master  Game  Chat  Media  Aux  Mic  │  ← 6 个频道名 + 音量数字，单行
│   80%   50%    30%   60%   45%   90%  │
│                          [展开] [⚙]  │
└──────────────────────────────────┘
```
- 每个频道显示名称 + 百分比，字体小
- 点击频道名 → 展开为滑块面板
- `[展开]` 按钮 → 切换到展开模式
- `[⚙]` → 打开 SonarMix 主窗口（通过 API）

**展开模式**（~280×360px）：
```
┌──────────────────────────────────┐
│  Master    ●══════════════○  80% │  ← 6 行 DotSlider
│  Game      ●═══════○───────── 50% │     Streamer: 每个频道 2 行
│  Chat      ●════○──────────── 30% │     Classic: 每个频道 1 行
│  Media     ●══════════○─────── 60% │
│  Aux       ●══════○─────────── 45% │
│  Mic       ●══════════════○─── 90% │
│                          [紧凑] [⚙] │
└──────────────────────────────────┘
```
- Streamer 模式：每个频道 2 个 DotSlider（Mon + Stm），用标签区分
- Classic 模式：每个频道 1 个 DotSlider
- `[紧凑]` → 切回紧凑模式

**模式感知**：从 `/api/status` 的 `mode` 字段判断，动态显示/隐藏 streaming slider。

#### 轮询与容错

```
Timer(500ms) → XMLHttpRequest GET /api/status
  ├── 成功 → 更新所有 Slider + 标签 → 重置失败计数 → 显示"已连接"
  ├── 失败 → 失败计数 +1
  │   ├── < 30 次 → 继续轮询，显示"连接中…"
  │   └── ≥ 30 次 → 停止 Timer → 显示"未连接 - 点击重试"
  └── 用户点击"点击重试"区域 → 重置计数 → 重启 Timer
```

**视觉状态**：
- 已连接：频道名正常颜色，Slider 绿色可交互
- 连接中（<30 次失败）：频道名灰色，Slider 不可交互
- 未连接（≥30 次失败）：所有文字灰色，显示"SonarMix 未连接"居中大字 + "点击重试"小字

#### 配色

全部硬编码，和 SonarMix 主窗口一致：
- 主色：`#42b983`（Vue 绿）
- 背景：`#1a1a1a`（Dark 主题，透明也可 — SAO 挂件通常透明）
- 文字：`#e6edf3`（主）/ `#8b949e`（次）/ `#6e7681`（弱）
- 滑块轨道：`#3d444d`

---

### 2.3 `widget/package.json` — 扩展清单

```json
{
    "name": "com.brettnow.sonarmix",
    "version": "1.2.0",
    "title": { "en": "SonarMix", "zh": "SonarMix 音量" },
    "description": {
        "en": "Desktop volume mixer widget for SteelSeries GG Sonar",
        "zh": "SteelSeries GG Sonar 桌面音量混音器挂件"
    },
    "author": "Brett-Now",
    "resources": [
        {
            "location": "/widget/sonarmix",
            "catalog": "widget",
            "title": { "en": "SonarMix Volume", "zh": "SonarMix 音量混音器" },
            "entry": "SonarMixWidget.qml"
        }
    ]
}
```

### 2.4 `widget/Presets/sonarmix.png`

预览图：在 SonarMix 现有图标（绿底 S）基础上加一个音量滑块示意。用程序化生成（PIL/PySide6 QPainter）或手动截图。尺寸 256×256。

---

## 三、修改现有文件

### 3.1 `sonar_ctrl.py` — 线程安全

给 `SonarCtrl` 加 `threading.Lock`，所有公开方法（`snapshot()`、`set_volume()`、`set_volume_int()`、`mute()`、`toggle_mute()`、`set_streamer_mode()`、`refresh_streamer_mode()`）加 `with self._lock:`。

```python
import threading

class SonarCtrl:
    def __init__(self) -> None:
        self._sonar = Sonar()
        self._streamer_mode: bool | None = None
        self._lock = threading.Lock()  # ← 新增
```

### 3.2 `settings_ui.py` — 常规设置新增

在 `GeneralTab` 中新增（紧跟 `show_toast` checkbox 之后）：

```python
# HTTP Server 开关
self._http_cb = QCheckBox(tr("general.http_server"))
self._http_cb.setChecked(False)  # 默认关闭
g_layout.addWidget(self._http_cb)

# 端口号（仅 server 启用时显示）
port_row = QHBoxLayout()
self._port_label = QLabel(tr("general.http_port"))
self._port_edit = QLineEdit("18999")
self._port_edit.setFixedWidth(60)
self._port_edit.setValidator(QIntValidator(1024, 65535))
port_row.addWidget(self._port_label)
port_row.addWidget(self._port_edit)
port_row.addStretch()
g_layout.addLayout(port_row)
```

`get_values()` 和 `set_values()` 加 `http_server_enabled` + `http_port` 字段。

### 3.3 `main.py` — 集成 HTTP Server

```python
from server import SonarHttpServer

class SonarMixApp:
    def __init__(self) -> None:
        ...
        self._http_server = SonarHttpServer(self._sonar)
        # 根据配置启动（在 _load_config 之后）
        ...

    def _on_config_saved(self) -> None:
        self._load_config()
        self._apply_window_flags()
        self._apply_http_server()  # ← 新增

    def _apply_http_server(self) -> None:
        """根据配置启动/停止 HTTP Server"""
        if self._http_enabled:
            if not self._http_server.is_running():
                ok = self._http_server.start(self._http_port)
                if not ok:
                    log_error(f"HTTP server failed to start on port {self._http_port}")
        else:
            self._http_server.stop()

    def _quit(self) -> None:
        self._http_server.stop()  # ← 新增
        self._refresh_timer.stop()
        self._hotkeys.shutdown()
        self._app.quit()
```

`_load_config()` 中读取 `http_server_enabled` 和 `http_port`：
```python
self._http_enabled = s.get("http_server_enabled", False)
self._http_port = s.get("http_port", 18999)
```

### 3.4 `config.yaml` — 新增字段

```yaml
settings:
  always_on_top: true
  language: "zh"
  show_toast: true
  start_minimized: false
  http_server_enabled: false    # ← 新增
  http_port: 18999              # ← 新增
```

### 3.5 `i18n.py` — 新增翻译键

```python
# 中/英 各加：
"general.http_server": "启用 HTTP API 服务" / "Enable HTTP API server"
"general.http_port": "端口" / "Port"
```

---

## 四、实现顺序

| 步骤 | 文件 | 内容 | 预估行数 |
|------|------|------|---------|
| 1 | `sonar_ctrl.py` | 加 `threading.Lock` | +5 |
| 2 | `server.py` | HTTP API Server 完整实现 | ~120 |
| 3 | `i18n.py` | 新增翻译键 | +4 |
| 4 | `settings_ui.py` | GeneralTab 加开关+端口 | ~30 |
| 5 | `main.py` | 集成 HTTP Server 启停 | ~25 |
| 6 | `widget/package.json` | 扩展清单 | 创建 |
| 7 | `widget/SonarMixWidget.qml` | 挂件 QML（DotSlider + 轮询 + 紧凑/展开） | ~350 |
| 8 | `widget/Presets/sonarmix.png` | 生成预览图 | 创建 |
| 9 | `CLAUDE.md` | 更新当前进度 | 编辑 |

---

## 五、打包与分发

```
widget/
├── package.json
├── SonarMixWidget.qml
└── Presets/
    └── sonarmix.png
```

→ 选中 widget 目录内**所有文件**（不包含 widget 父文件夹）→ ZIP 压缩 → 改后缀 `.nvg` → 用户双击安装 → 在「挂件库 → 预置挂件」拖到桌面。

---

## 六、注意事项（交接要点）

1. **DotSlider 无依赖**：只用 Rectangle + MouseArea + Text，不 import QtQuick.Controls。这是为了最大兼容性，因为 SAO Utils 2 的 Qt 版本未知
2. **`SonarCtrl._lock`**：`threading.Lock` 是关键修改——否则 HTTP 线程和 Qt 主线程可能同时调 API 导致竞态
3. **Server 绑定 127.0.0.1**：只监听本机，生产环境不要用 0.0.0.0
4. **CORS header**：QML `XMLHttpRequest` 从 `nvg://` 协议发请求可能跨域，Server 必须返回 `Access-Control-Allow-Origin: *`
5. **端口冲突**：`start()` 失败时 log_error，UI 不做额外弹窗
6. **挂件模式偏好**：紧凑/展开状态写入 `settings` 对象（`NERvGear.Templates.Widget` 自动持久化），无需手工处理
7. **QML URL 硬编码**：挂件中 `http://127.0.0.1:18999` 写死。如果用户改了端口，需要在挂件设置里同步修改（v1.3 迭代）
8. **PyInstaller**：打包时 server.py 自动包含，无需特殊配置

---

## 七、未纳入范围（v1.3+）

- 挂件端口号自动发现（当前需手动和 SonarMix 设一致）
- 挂件内嵌 Streamer/Classic 模式切换开关
- 挂件静音按钮
- 多挂件实例同时运行
- Release 自动更新检查
