"""
hc/mediamtx_cfg.py  —  Generate per-stream MediaMTX YAML config files.

FIX (v5.0.2):
  • Removed `rtmps: false` — MediaMTX v1.9.1 does NOT support this field.
    Keeping it caused immediate startup crash with:
      ERR: json: unknown field "rtmps"
  • Removed `rtmp: false` for the same reason (not supported in 1.9.1 YAML).
    Both RTMP and RTMPS are simply not listed, which causes MediaMTX to use
    its built-in defaults (disabled unless explicitly configured elsewhere).
  • Added verbose logging at every step so failures are traceable.

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

        # ── Protocol section ─────────────────────────────────────────────────
        # IMPORTANT: Do NOT include `rtmp: false` or `rtmps: false`.
        # MediaMTX 1.9.1 YAML parser raises "unknown field" for these and
        # the process exits immediately (code 1).  Omitting them is safe —
        # RTMP/RTMPS simply remain at their built-in defaults (disabled).
        if cfg.hls_enabled:
            log.info("[%s] HLS enabled on port %d", cfg.name, cfg.hls_port)
            # Low-Latency HLS requires at least 7 segments.
            proto_section = (
                f"hls: true\n"
                f"hlsAddress: {addr}:{cfg.hls_port}\n"
                f"hlsAlwaysRemux: yes\n"
                f"hlsVariant: lowLatency\n"
                f"hlsSegmentCount: 7\n"
                f"hlsSegmentDuration: 1s\n"
                f"hlsPartDuration: 200ms\n"
                f"hlsAllowOrigin: \"*\"\n"
                f"webrtc: false\n"
                f"srt: false\n"
                f"\npaths:\n"
                f"  {spath}:\n"
                f"    source: publisher\n"
            )
        else:
            proto_section = (
                f"hls: false\n"
                f"webrtc: false\n"
                f"srt: false\n"
                f"\npaths:\n"
                f"  {spath}: {{}}\n"
            )

        yaml_text = (
            f"# HydraCast v{APP_VER} — {cfg.name} (:{port})\n"
            f"# RTP port {rtp_base} (even ✓)  RTCP port {rtp_base+1} (odd ✓)\n"
            f"# NOTE: rtmp/rtmps keys omitted — not supported by MediaMTX 1.9.1 YAML\n"
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
            f"api: false\n"
            f"metrics: false\n"
            f"pprof: false\n"
            f"\n"
            f"{proto_section}"
        )

        try:
            cfg_f.write_text(yaml_text, encoding="utf-8")
            log.info("[%s] Config written successfully: %s", cfg.name, cfg_f)
        except Exception as exc:
            log.error("[%s] FAILED to write config %s: %s", cfg.name, cfg_f, exc)
            raise

        # Log the full config at DEBUG level for deep troubleshooting
        log.debug("[%s] Config content:\n%s", cfg.name, yaml_text)

        return cfg_f
