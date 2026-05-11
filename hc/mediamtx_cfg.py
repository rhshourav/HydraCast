"""
hc/mediamtx_cfg.py  —  Generate per-stream MediaMTX YAML config files.

FIX (v5.0.5):  HLS not working — three bugs corrected using the official
               mediamtx.yml as ground truth.

  BUG 1 — Wrong key: `hlsAllowOrigin` (singular)
    The real key is `hlsAllowOrigins` (plural), and it takes a YAML list.
    Using the singular form is silently ignored — CORS is never set.
    Fix: hlsAllowOrigins: ['*']

  BUG 2 — Wrong key: `source: publisher` in the HLS paths block
    FFmpeg pushes to MediaMTX via RTSP; `source: publisher` is only needed
    when MediaMTX itself is meant to pull from an external source URL.
    For a push workflow the path entry must be empty (same as non-HLS).
    Using `source: publisher` can prevent the path from accepting the
    FFmpeg RTSP push correctly.
    Fix: use `{spath}: {{}}` for HLS paths too.

  BUG 3 — `hlsAlwaysRemux: yes` accepted, but behaviour note
    `hlsAlwaysRemux` must be true so MediaMTX pre-generates HLS segments
    immediately when the stream starts, rather than waiting for the first
    viewer to connect (which would cause a long initial delay or 404).
    Using `yes` is fine YAML — keeping it `true` to match the official style.

Previously fixed (v5.0.4):
  • `rtmp: no` / `srt: no` / `webrtc: no` — correct 1.9.1 disable keys.
  • Removed `rtmps:`, `rtmpDisable:`, `srtDisable:`, `webrtcDisable:` —
    all raise "unknown field" in 1.9.1.

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
        # MediaMTX 1.9.1 binds RTMP (:1935), SRT (:8890), WebRTC (:8889) by
        # default. Multiple instances collide on these ports.
        # Correct disable keys (verified against official mediamtx.yml):
        #   rtmp: false  |  srt: false  |  webrtc: false
        #
        # HLS key corrections (verified against official mediamtx.yml):
        #   hlsAllowOrigins (plural, list)  — NOT hlsAllowOrigin (singular)
        #   hlsAlwaysRemux: true            — ensures segments are pre-built
        #                                     before first viewer connects
        #   paths entry uses {}             — NOT `source: publisher`
        #                                     (publisher is for pull sources)

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
                f"hlsVariant: lowLatency\n"
                f"hlsSegmentCount: 7\n"
                f"hlsSegmentDuration: 1s\n"
                f"hlsPartDuration: 200ms\n"
                f"hlsAllowOrigins: ['*']\n"  # plural + list — critical
            )
        else:
            proto_section = (
                f"rtmp: false\n"
                f"srt: false\n"
                f"webrtc: false\n"
                f"hls: false\n"
            )

        # Paths section: empty braces `{{}}` = accept publisher push.
        # Do NOT use `source: publisher` — that is for pull (MediaMTX fetches
        # from an external URL). FFmpeg pushes via RTSP, so the path just needs
        # to exist with no special source directive.
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
