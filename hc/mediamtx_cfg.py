"""
hc/mediamtx_cfg.py  —  Generate per-stream MediaMTX YAML config files.

FIX (v5.0.4):
  • The correct MediaMTX 1.9.1 keys to disable protocols are the simple
    top-level booleans:  rtmp: no  |  srt: no  |  webrtc: no  |  hls: no
    Previous attempts used wrong keys:
      - `rtmp: false` / `rtmps: false`  → "unknown field" crash
      - `rtmpDisable: yes` / `srtDisable: yes` / `webrtcDisable: yes`
        → also "unknown field" crash (these keys do not exist in 1.9.1)
    The boolean value must be `no` (not `false`) — MediaMTX's YAML parser
    accepts standard YAML booleans (yes/no, true/false) but the official
    sample config uses yes/no style throughout.

  • Without disabling them, MediaMTX binds these ports by default:
      RTMP   → :1935
      SRT    → :8890
      WebRTC → :8889
      HLS    → :8888  (when not explicitly configured)
    Every stream after the first fails to start because these shared ports
    are already taken by the first instance.

  • For HLS-enabled streams we set an explicit per-stream hlsAddress so
    each instance binds a unique HLS port (cfg.port + 10000).

RTP port assignment (unchanged):
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

        # ── Protocol sections ────────────────────────────────────────────────
        # CRITICAL: MediaMTX 1.9.1 binds RTMP (:1935), SRT (:8890), and
        # WebRTC (:8889) by default even when unused.  With multiple instances
        # running simultaneously, every instance after the first crashes trying
        # to bind these already-taken ports.
        #
        # The correct 1.9.1 top-level keys are:
        #   rtmp: no      — disables RTMP (default port :1935)
        #   srt: no       — disables SRT  (default port :8890)
        #   webrtc: no    — disables WebRTC (default port :8889)
        #
        # Do NOT use `rtmps: false`, `rtmpDisable: yes`, `srtDisable: yes`,
        # or `webrtcDisable: yes` — all raise "unknown field" in 1.9.1.

        if cfg.hls_enabled:
            log.info("[%s] HLS enabled on port %d", cfg.name, cfg.hls_port)
            # Each HLS-enabled instance gets its own unique port so instances
            # don't collide.  Low-Latency HLS requires at least 7 segments.
            proto_section = (
                f"rtmp: no\n"
                f"srt: no\n"
                f"webrtc: no\n"
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
            proto_section = (
                f"rtmp: no\n"
                f"srt: no\n"
                f"webrtc: no\n"
                f"hls: no\n"
            )
            paths_section = (
                f"\npaths:\n"
                f"  {spath}: {{}}\n"
            )

        yaml_text = (
            f"# HydraCast v{APP_VER} — {cfg.name} (:{port})\n"
            f"# RTP port {rtp_base} (even ✓)  RTCP port {rtp_base+1} (odd ✓)\n"
            f"# rtmp/srt/webrtc disabled to prevent port collisions across instances\n"
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
            f"{proto_section}"
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
