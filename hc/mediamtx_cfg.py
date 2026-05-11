"""
hc/mediamtx_cfg.py  —  Generate per-stream MediaMTX YAML config files.

FIX (v5.0.3):
  • Added `rtmpDisable: yes` — MediaMTX 1.9.1 YAML uses this key (NOT `rtmp: false`
    or `rtmps: false`). Without it, every MediaMTX instance tries to bind port 1935
    for RTMP, causing "address already in use" crashes on the 2nd+ stream.
  • Added `srtDisable: yes` and `webrtcDisable: yes` — same reason; MediaMTX binds
    default SRT (:8890) and WebRTC (:8889) ports unless explicitly disabled.
    With multiple instances these ports also collide.
  • Kept `hls: false` / `hls: true` as-is — these ARE valid 1.9.1 keys.
  • Removed any use of `rtmp:`, `rtmps:`, `webrtc:`, `srt:` boolean keys — all
    raise "unknown field" in MediaMTX 1.9.1.

RTP port assignment (unchanged from v5.0.1):
  rtp_base = port + 2, bumped to next even number if odd.
  Example: 8554 → rtp=8556, rtcp=8557 | 8564 → rtp=8566, rtcp=8567
"""
from __future__ import annotations

import logging
from pathlib import Path

from hc.constants import APP_VER, CONFIGS_DIR, LISTEN_ADDR, LOGS_DIR
from hc.models import StreamState

log = logging.getLogger(__name__)


class MediaMTXConfig:

    @staticmethod
    def _purge_stale(port: int) -> None:
        stale = CONFIGS_DIR() / f"mediamtx_{port}.yml"
        try:
            stale.unlink(missing_ok=True)
            log.debug("Purged stale config for port %d", port)
        except Exception as exc:
            log.warning("Could not purge stale config for port %d: %s", port, exc)

    @staticmethod
    def write(state: StreamState) -> Path:
        cfg   = state.config
        port  = cfg.port
        spath = cfg.rtsp_path
        addr  = LISTEN_ADDR()
        log_f = (LOGS_DIR() / f"mediamtx_{port}.log").resolve()
        cfg_f = CONFIGS_DIR() / f"mediamtx_{port}.yml"

        log.info("[%s] Writing MediaMTX config → %s", cfg.name, cfg_f)

        MediaMTXConfig._purge_stale(port)

        # ── RTP / RTCP port calculation ──────────────────────────────────────
        # RFC 3550 §11: RTP port MUST be even, RTCP = RTP + 1.
        rtp_base = port + 2
        if rtp_base % 2 != 0:
            rtp_base += 1
        rtp_addr  = f"{addr}:{rtp_base}"
        rtcp_addr = f"{addr}:{rtp_base + 1}"

        log.info(
            "[%s] Port assignment: RTSP=%d  RTP=%d (even✓)  RTCP=%d",
            cfg.name, port, rtp_base, rtp_base + 1,
        )

        # ── Protocol disable section ─────────────────────────────────────────
        # CRITICAL: MediaMTX 1.9.1 binds RTMP (:1935), SRT (:8890), and
        # WebRTC (:8889) by DEFAULT even if not configured. With multiple
        # MediaMTX instances, these ports collide on the 2nd instance.
        #
        # The correct 1.9.1 YAML keys to disable them are:
        #   rtmpDisable: yes
        #   srtDisable: yes
        #   webrtcDisable: yes
        #
        # Do NOT use `rtmp: false`, `rtmps: false`, `srt: false`,
        # `webrtc: false` — these raise "unknown field" and crash MediaMTX.
        proto_disable = (
            "rtmpDisable: yes\n"
            "srtDisable: yes\n"
            "webrtcDisable: yes\n"
        )

        # ── HLS section ──────────────────────────────────────────────────────
        if cfg.hls_enabled:
            log.info("[%s] HLS enabled on port %d", cfg.name, cfg.hls_port)
            # Low-Latency HLS requires at least 7 segments.
            hls_section = (
                f"hls: yes\n"
                f"hlsAddress: {addr}:{cfg.hls_port}\n"
                f"hlsAlwaysRemux: yes\n"
                f"hlsVariant: lowLatency\n"
                f"hlsSegmentCount: 7\n"
                f"hlsSegmentDuration: 1s\n"
                f"hlsPartDuration: 200ms\n"
                f"hlsAllowOrigin: \"*\"\n"
            )
            paths_section = (
                f"\npaths:\n"
                f"  {spath}:\n"
                f"    source: publisher\n"
            )
        else:
            hls_section = "hls: no\n"
            paths_section = (
                f"\npaths:\n"
                f"  {spath}: {{}}\n"
            )

        yaml_text = (
            f"# HydraCast v{APP_VER} — {cfg.name} (:{port})\n"
            f"# RTP port {rtp_base} (even ✓)  RTCP port {rtp_base+1} (odd ✓)\n"
            f"# rtmpDisable/srtDisable/webrtcDisable prevent port-1935/8890/8889 conflicts\n"
            f"logLevel: error\n"
            f"logDestinations: [file]\n"
            f"logFile: {str(log_f).replace(chr(92), '/')}\n"
            f"\n"
            f"rtspAddress: {addr}:{port}\n"
            f"rtpAddress:  {rtp_addr}\n"
            f"rtcpAddress: {rtcp_addr}\n"
            f"readTimeout: 15s\n"
            f"writeTimeout: 15s\n"
            f"writeQueueSize: 1024\n"
            f"udpMaxPayloadSize: 1472\n"
            f"\n"
            f"api: no\n"
            f"metrics: no\n"
            f"pprof: no\n"
            f"\n"
            f"{proto_disable}"
            f"{hls_section}"
            f"{paths_section}"
        )

        try:
            cfg_f.write_text(yaml_text, encoding="utf-8")
            log.info("[%s] Config written successfully: %s", cfg.name, cfg_f)
        except Exception as exc:
            log.error("[%s] FAILED to write config %s: %s", cfg.name, cfg_f, exc)
            raise

        log.debug("[%s] Config content:\n%s", cfg.name, yaml_text)

        return cfg_f
