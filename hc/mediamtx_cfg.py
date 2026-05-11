"""
hc/mediamtx_cfg.py  —  Generate per-stream MediaMTX YAML config files.

RTP port assignment (v5 fix):
  Each MediaMTX instance receives:
    rtspAddress : base_port           (TCP, must be ≥1024)
    rtpAddress  : rtp_port            (UDP, **must be even** per RTP RFC 3550)
    rtcpAddress : rtp_port + 1        (UDP, odd — one above RTP)

  We compute:
    rtp_base = base_port + 2
    if rtp_base is odd: rtp_base += 1   ← bump to next even number
    rtp_port  = rtp_base
    rtcp_port = rtp_base + 1

  With the recommended ≥10-port gap between streams this never collides.
  Example: 8554 → rtp=8556, rtcp=8557 | 8564 → rtp=8566, rtcp=8567

Fixes (v5.0.1):
  • rtmp: false  — prevents MediaMTX from trying to bind :1935 (RTMP)
  • rtmps: false — prevents :1936 bind attempts
  • srt: false, webrtc: false — belt-and-suspenders protocol lockdown
  • hlsSegmentCount: 7 — Low-Latency HLS requires ≥7 segments (was 3)
  • hlsSegmentDuration: 1s — tighter latency for LL-HLS
"""
from __future__ import annotations

from pathlib import Path

from hc.constants import APP_VER, CONFIGS_DIR, LISTEN_ADDR, LOGS_DIR
from hc.models import StreamState


class MediaMTXConfig:

    @staticmethod
    def _purge_stale(port: int) -> None:
        stale = CONFIGS_DIR() / f"mediamtx_{port}.yml"
        try:
            stale.unlink(missing_ok=True)
        except Exception:
            pass

    @staticmethod
    def write(state: StreamState) -> Path:
        cfg   = state.config
        port  = cfg.port
        spath = cfg.rtsp_path
        addr  = LISTEN_ADDR()
        log_f = (LOGS_DIR() / f"mediamtx_{port}.log").resolve()
        cfg_f = CONFIGS_DIR() / f"mediamtx_{port}.yml"

        MediaMTXConfig._purge_stale(port)

        # ── Compute RTP / RTCP ports ─────────────────────────────────────────
        # RTP must be even (RFC 3550 §11). RTCP = RTP + 1.
        rtp_base = port + 2
        if rtp_base % 2 != 0:   # ensure even
            rtp_base += 1
        rtp_addr  = f"{addr}:{rtp_base}"
        rtcp_addr = f"{addr}:{rtp_base + 1}"

        # ── Protocol section (HLS optional) ──────────────────────────────────
        # NOTE: Low-Latency HLS requires at minimum 7 segments.
        # hlsSegmentCount < 7 causes repeated "[HLS] Low-Latency HLS requires
        # at least 7 segments" errors in the MediaMTX log.
        if cfg.hls_enabled:
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
                f"rtmp: false\n"
                f"rtmps: false\n"
                f"\npaths:\n"
                f"  {spath}:\n"
                f"    source: publisher\n"
            )
        else:
            proto_section = (
                f"hls: false\n"
                f"webrtc: false\n"
                f"srt: false\n"
                # Explicitly disable RTMP/RTMPS so MediaMTX never attempts
                # to bind :1935 / :1936 — the most common startup error.
                f"rtmp: false\n"
                f"rtmps: false\n"
                f"\npaths:\n"
                f"  {spath}: {{}}\n"
            )

        yaml_text = (
            f"# HydraCast v{APP_VER} — {cfg.name} (:{port})\n"
            f"# RTP port {rtp_base} (even ✓)  RTCP port {rtp_base+1} (odd ✓)\n"
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

        cfg_f.write_text(yaml_text, encoding="utf-8")
        return cfg_f
