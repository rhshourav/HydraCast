"""
hc/mediamtx_cfg.py  —  Generate per-stream MediaMTX YAML config files.

FIX (v5.0.6):
  • hlsAllowOrigin: '*'  — singular, plain string.
    v1.9.1 uses the OLD singular key. The plural `hlsAllowOrigins` with a
    list was introduced in a later release; using it in v1.9.1 raises
    ERR: json: unknown field "hlsAllowOrigins".

Previously fixed:
  v5.0.5 — hlsAlwaysRemux: true, removed `source: publisher` from paths
  v5.0.4 — rtmp/srt/webrtc: false (correct v1.9.1 disable keys)
  v5.0.3 — log file opened with "w" so stale errors don't pollute new runs

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
        # Disable keys verified against v1.9.1 YAML:
        #   rtmp: false | srt: false | webrtc: false
        # Without these, every instance after the first fails binding :1935/:8890/:8889.
        #
        # HLS CORS key for v1.9.1:
        #   hlsAllowOrigin: '*'   ← singular, plain string
        #   hlsAllowOrigins: ['*'] was introduced in a later version;
        #   using it in v1.9.1 raises ERR: unknown field "hlsAllowOrigins".
        #
        # hlsAlwaysRemux: true — pre-generates segments so viewers don't get
        #   a 404 before the first reader connects.
        #
        # paths block uses {} (empty) — FFmpeg pushes via RTSP so no source
        #   directive is needed. `source: publisher` is for pull sources only.

        if cfg.hls_enabled:
            log.info("[%s] HLS enabled on port %d", cfg.name, cfg.hls_port)
            proto_section = (
                f"rtmp: false\n"
                f"srt: false\n"
                f"webrtc: false\n"
                f"\n"
                f"hls: true\n"
                f"hlsAddress: {addr}:{cfg.hls_port}\n"
                f"hlsAlwaysRemux: true\n"
                f"hlsVariant: fmp4\n"
                f"hlsSegmentCount: 6\n"
                f"hlsSegmentDuration: 4s\n"
                f""
                f"hlsAllowOrigin: '*'\n"
            )
        else:
            proto_section = (
                f"rtmp: false\n"
                f"srt: false\n"
                f"webrtc: false\n"
                f"hls: false\n"
            )

        paths_section = (
            f"\npaths:\n"
            f"  {spath}: {{}}\n"
        )

        yaml_text = (
            f"# HydraCast v{APP_VER} — {cfg.name} (:{port})\n"
            f"# RTP port {rtp_base} (even ✓)  RTCP port {rtp_base+1} (odd ✓)\n"
            f"# rtmp/srt/webrtc: false prevents port-1935/8890/8889 collisions\n"
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
