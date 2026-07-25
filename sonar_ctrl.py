"""
Sonar API wrapper — thin layer over steelseries-sonar-py.

Provides:
- Read all 12 volume values (6 channels × 2 streamer modes) at once
- Set individual channel volume
- Mute/unmute
- Streamer mode detection

Channels (API name → display name):
    master       → Master
    game         → Game
    chatRender   → Chat
    media        → Media
    aux          → Aux
    chatCapture  → Mic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from steelseries_sonar_py import Sonar

from log_handler import log_debug, log_error, log_info, log_warn


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHANNEL_KEYS: Final[tuple[str, ...]] = (
    "master",
    "game",
    "chatRender",
    "media",
    "aux",
    "chatCapture",
)


STREAMER_SLIDERS: Final[tuple[str, str]] = ("monitoring", "streaming")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ChannelVolume:
    """Volume state for a single channel × streamer slider."""

    channel: str          # API key: "master", "game", ...
    streamer_slider: str  # "monitoring" or "streaming"
    volume: float         # 0.0 – 1.0
    muted: bool


@dataclass
class Snapshot:
    """Full snapshot of all 12 volume sliders (6 channels × 2 streamer modes)."""

    channels: dict[str, dict[str, ChannelVolume]] = field(default_factory=dict)
    # channels["master"]["monitoring"] → ChannelVolume

    @classmethod
    def from_api(cls, data: dict, streamer_mode: bool | None = None) -> "Snapshot":
        """Parse the raw JSON from Sonar.get_volume_data().

        Streamer Mode: reads from ``masters.stream`` and ``devices.<ch>.stream``
        (monitoring + streaming sliders per channel).
        Classic Mode: reads from ``masters.classic`` and ``devices.<ch>.classic``
        (single slider, duplicated into both monitoring and streaming keys so
        downstream code works unchanged).

        If *streamer_mode* is None, auto-detects from data structure.
        """
        snapshot = cls()

        # Auto-detect: streamer-mode data has "masters.stream" with
        # monitoring/streaming sub-objects (each with their own volume).
        # Classic-mode data has them absent — volumes live flat under classic.
        if streamer_mode is None:
            master_stream = data.get("masters", {}).get("stream", {})
            streamer_mode = "monitoring" in master_stream

        if streamer_mode:
            snapshot._parse_streamer(snapshot, data)
        else:
            snapshot._parse_classic(snapshot, data)
        return snapshot

    @staticmethod
    def _parse_streamer(snapshot: "Snapshot", data: dict) -> None:
        """Parse Streamer Mode volume data (monitoring + streaming per channel)."""
        masters = data.get("masters", {}).get("stream", {})
        snapshot.channels["master"] = {}
        for slider in STREAMER_SLIDERS:
            sdata = masters.get(slider, {})
            snapshot.channels["master"][slider] = ChannelVolume(
                channel="master",
                streamer_slider=slider,
                volume=sdata.get("volume", 0.5),
                muted=sdata.get("muted", False),
            )

        devices = data.get("devices", {})
        for key in CHANNEL_KEYS:
            if key == "master":
                continue
            snapshot.channels[key] = {}
            device = devices.get(key, {}).get("stream", {})
            for slider in STREAMER_SLIDERS:
                sdata = device.get(slider, {})
                snapshot.channels[key][slider] = ChannelVolume(
                    channel=key,
                    streamer_slider=slider,
                    volume=sdata.get("volume", 0.0),
                    muted=sdata.get("muted", False),
                )

    @staticmethod
    def _parse_classic(snapshot: "Snapshot", data: dict) -> None:
        """Parse Classic Mode volume data — single volume duplicated to both
        monitoring + streaming keys so the UI and hotkey code works unchanged."""
        masters = data.get("masters", {}).get("classic", {})
        master_vol = masters.get("volume", 0.5)
        master_muted = masters.get("muted", False)
        snapshot.channels["master"] = {}
        for slider in STREAMER_SLIDERS:
            snapshot.channels["master"][slider] = ChannelVolume(
                channel="master",
                streamer_slider=slider,
                volume=master_vol,
                muted=master_muted,
            )

        devices = data.get("devices", {})
        for key in CHANNEL_KEYS:
            if key == "master":
                continue
            snapshot.channels[key] = {}
            device = devices.get(key, {}).get("classic", {})
            vol = device.get("volume", 0.0)
            muted = device.get("muted", False)
            for slider in STREAMER_SLIDERS:
                snapshot.channels[key][slider] = ChannelVolume(
                    channel=key,
                    streamer_slider=slider,
                    volume=vol,
                    muted=muted,
                )

    def get(self, channel: str, slider: str) -> float:
        """Get volume 0.0–1.0 for a channel + slider."""
        return self.channels[channel][slider].volume

    def is_muted(self, channel: str, slider: str) -> bool:
        """Check if a channel + slider is muted."""
        return self.channels[channel][slider].muted


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class SonarCtrl:
    """High-level controller for Sonar audio mixer."""

    def __init__(self) -> None:
        self._sonar = Sonar()
        self._streamer_mode: bool | None = None
        # Detect initial mode
        try:
            self._streamer_mode = self._sonar.is_streamer_mode()
            log_info(f"SonarCtrl initialized — streamer mode: {self._streamer_mode}")
        except Exception as e:
            log_error(f"SonarCtrl init failed — cannot reach Sonar API: {e}")
            self._streamer_mode = False

    # ── Streamer mode ────────────────────────────────────────────────

    @property
    def streamer_mode(self) -> bool:
        """Check if Streamer Mode is active (cached after first read)."""
        if self._streamer_mode is None:
            self._streamer_mode = self._sonar.is_streamer_mode()
        return self._streamer_mode

    def refresh_streamer_mode(self) -> bool:
        """Force re-read streamer mode from GG."""
        old = self._streamer_mode
        try:
            self._streamer_mode = self._sonar.is_streamer_mode()
        except Exception as e:
            log_error(f"refresh_streamer_mode failed: {e}")
            return old or False
        if old != self._streamer_mode:
            log_info(f"Streamer mode re-read: {old} → {self._streamer_mode}")
        return self._streamer_mode

    def set_streamer_mode(self, enabled: bool) -> None:
        """Toggle Streamer Mode on/off — also fixes the library's
        volume_path which is only set once in Sonar.__init__()."""
        old = self._streamer_mode
        log_info(f"set_streamer_mode: {old} → {enabled}")
        try:
            self._sonar.set_streamer_mode(enabled)
        except Exception as e:
            log_error(f"set_streamer_mode API call failed: {e}")
            return
        self._streamer_mode = enabled
        # The library switches self.streamer_mode but NOT volume_path.
        # Without this, GET/PUT keeps hitting /volumeSettings/streamer/ → 404.
        old_path = getattr(self._sonar, "volume_path", "?")
        self._sonar.volume_path = (
            "/volumeSettings/streamer" if enabled
            else "/volumeSettings/classic"
        )
        log_debug(f"volume_path fixed: {old_path} → {self._sonar.volume_path}")

    def _streamer_slider_kwarg(self, streamer_slider: str | None) -> dict[str, str]:
        """Build kwargs for API calls — omit streamer_slider in Classic mode."""
        if streamer_slider is None or not self._streamer_mode:
            return {}
        return {"streamer_slider": streamer_slider}

    # ── Volume read ──────────────────────────────────────────────────

    def snapshot(self) -> Snapshot:
        """Fetch full volume data from Sonar API."""
        try:
            data = self._sonar.get_volume_data()
        except Exception as e:
            log_warn(f"snapshot fetch failed: {e}")
            raise
        # Auto-detect mode from data structure (not is_streamer_mode(),
        # which can return the new mode while volume data is still in
        # the old format during the GG mode-switch transition).
        return Snapshot.from_api(data, streamer_mode=None)

    # ── Volume write ─────────────────────────────────────────────────

    def set_volume(self, channel: str, volume: float,
                   streamer_slider: str | None = None) -> None:
        """Set volume 0.0–1.0 for a channel + streamer slider.
        In Classic mode, *streamer_slider* is ignored.
        """
        clamped = max(0.0, min(1.0, volume))

        # Read old volume for logging
        old_pct: int | None = None
        try:
            snap = self.snapshot()
            sl = streamer_slider if (streamer_slider and self._streamer_mode) else "monitoring"
            old_pct = round(snap.get(channel, sl) * 100)
        except Exception:
            pass  # can't read old value — log without it

        kwargs = self._streamer_slider_kwarg(streamer_slider)
        new_pct = round(clamped * 100)
        sl_label = streamer_slider if (streamer_slider and self._streamer_mode) else "—"

        try:
            self._sonar.set_volume(channel, clamped, **kwargs)
        except Exception as e:
            log_error(f"SET volume failed: {channel}/{sl_label} → {new_pct}% — {e}")
            return

        if old_pct is not None and old_pct != new_pct:
            log_info(f"SET volume: {channel}/{sl_label}  {old_pct}% → {new_pct}%")
        elif old_pct is None:
            log_info(f"SET volume: {channel}/{sl_label}  {new_pct}%")
        # else: unchanged — still log at DEBUG level (may indicate GG no-op)
        elif old_pct == new_pct:
            log_debug(f"SET volume: {channel}/{sl_label}  {new_pct}% (unchanged)")

    def set_volume_int(self, channel: str, value: int,
                       streamer_slider: str | None = None) -> None:
        """Set volume from a 0–100 integer slider value."""
        log_debug(f"set_volume_int: {channel}/{streamer_slider} → {value}")
        self.set_volume(channel, value / 100.0, streamer_slider)

    # ── Mute ─────────────────────────────────────────────────────────

    def mute(self, channel: str, muted: bool,
             streamer_slider: str | None = None) -> None:
        """Mute or unmute a channel + streamer slider.
        In Classic mode, *streamer_slider* is ignored.
        """
        kwargs = self._streamer_slider_kwarg(streamer_slider)
        sl_label = streamer_slider if (streamer_slider and self._streamer_mode) else "—"
        state = "MUTED" if muted else "UNMUTED"

        try:
            self._sonar.mute_channel(channel, muted, **kwargs)
        except Exception as e:
            log_error(f"MUTE failed: {channel}/{sl_label} → {state} — {e}")
            return

        log_info(f"MUTE: {channel}/{sl_label}  {state}")

    def toggle_mute(self, channel: str, streamer_slider: str | None = None) -> None:
        """Toggle mute state for a channel + streamer slider."""
        try:
            snap = self.snapshot()
        except Exception:
            log_warn(f"toggle_mute: cannot read state for {channel} — aborting")
            return
        sl = streamer_slider if (streamer_slider and self._streamer_mode) else "monitoring"
        current = snap.is_muted(channel, sl)
        sl_label = streamer_slider if (streamer_slider and self._streamer_mode) else "—"
        new_state = "MUTED" if not current else "UNMUTED"
        log_info(f"TOGGLE mute: {channel}/{sl_label}  {new_state} (was {'MUTED' if current else 'UNMUTED'})")
        self.mute(channel, not current, streamer_slider)


# ---------------------------------------------------------------------------
# Self-test (run directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from i18n import channel_name

    ctrl = SonarCtrl()
    print(f"Streamer mode: {ctrl.streamer_mode}")
    snap = ctrl.snapshot()
    for key in CHANNEL_KEYS:
        mon = snap.get(key, "monitoring")
        stm = snap.get(key, "streaming")
        m_muted = snap.is_muted(key, "monitoring")
        s_muted = snap.is_muted(key, "streaming")
        print(f"  {channel_name(key):6s}  mon={mon:5.0%} {'🔇' if m_muted else '  '}  "
              f"stm={stm:5.0%} {'🔇' if s_muted else '  '}")
