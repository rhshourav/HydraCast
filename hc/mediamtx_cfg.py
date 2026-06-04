"""
hc/mediamtx_cfg.py  —  Generate per-stream MediaMTX YAML config files.

PORT SCHEME (v6.2+)
────────────────────
  RTSP port  — must be ODD  (e.g. 8555, 8557, 8559 …)
  HLS  port  — RTSP + 1    (even, adjacent)
  RTP  port  — RTSP + 2    (bumped to next even number if odd; RFC 3550)
  RTCP port  — RTP  + 1    (odd)

  Example:  RTSP=8555  HLS=8556  RTP=8558 (even✓)  RTCP=8559 (odd✓)

  The port checker (web UI + /api/check_port) validates:
    • the chosen port is odd
    • all four derived ports (RTSP, HLS, RTP, RTCP) are free
    • no OS firewall rule blocks them

FIX (v6.6.1 — hlsSegmentMaxSize type):
  • hlsSegmentMaxSize: '20971520'  — quoted as a YAML string.
    MediaMTX (v1.9.x) deserialises this field into a Go string type via its
    alias mechanism.  Writing the bare integer 20971520 causes:
      ERR: json: cannot unmarshal number into Go struct field
           alias.hlsSegmentMaxSize of type string
    Quoting it ('20971520') satisfies the Go JSON unmarshaller.
    MediaMTX then parses the string internally as a byte count.

FIX (v6.5.1 — writeTimeout note):
  • readTimeout / writeTimeout remain at 30 s (set in v6.3).
    These values are NOT the root cause of the broken-pipe restart loop —
    that was -preset slow with -re causing encoder stalls (fixed in worker.py
    v6.5.1 by switching to -preset medium).  30 s is the correct headroom
    for a high-quality encode on a loaded host; reducing it would reintroduce
    the very problem it was raised to avoid.

FIX (v6.3 — quality + HLS/RTSP sync):
  • hlsSegmentDuration: 4s  — aligns with FFmpeg -force_key_frames every 4 s.
    Every HLS segment starts on an IDR frame so HLS and RTSP playback stay in
    lock-step at every segment boundary.  Changing this value requires a
    matching change to the FFmpeg -force_key_frames interval in worker.py.

  • hlsSegmentCount: 10  — raised from 7 to 10.  More segments in the playlist
    gives players a larger buffer window, reducing rebuffering during brief
    network hiccups.  Memory cost is small (10 × 4 s = 40 s of media per
    stream) and does not affect latency.

  • hlsSegmentMaxSize: '20971520'  — caps individual segment file size to
    20 MiB (written as a quoted byte-count string; MediaMTX v1.9.x rejects
    a bare integer for this field with "cannot unmarshal number into string").

  • readTimeout / writeTimeout: 30s  — raised from 15 s to 30 s to give
    the high-quality encoder enough headroom to push frames without triggering
    a session teardown under CPU load.

FIX (v5.0.6 / v6.0):
  • spath = cfg.rtsp_path  (no "~all" fallback).
    The new version used  spath = cfg.rtsp_path if cfg.rtsp_path else "~all"
    because models.py was returning "" for empty stream_path.  models.py is
    now fixed to always return "stream" as the default, so rtsp_path is never
    empty and the ~all wildcard is not needed.

    Using ~all caused two problems:
      1. MediaMTX v1.9.1 does not reliably match the bare root path "/" under
         ~all, so FFmpeg's push to rtsp://127.0.0.1:<port>/ was rejected.
      2. All streams on the same server shared one wildcard path block, which
         broke multi-stream isolation.

  • hlsAllowOrigin: '*'  — singular, plain string (unchanged from v5.0.6).
  • hlsPartDuration: 0s  — disables Low-Latency HLS (LL-HLS).

Previously fixed:
  v5.0.5 — hlsAlwaysRemux: true, removed `source: publisher` from paths
  v5.0.4 — rtmp/srt/webrtc: false (correct v1.9.1 disable keys)
  v5.0.3 — log file opened with "w" so stale errors don't pollute new runs
"""
from __future__ import annotations

import logging
from pathlib import Path

from hc.constants import APP_VER, CONFIG_DIR, LISTEN_ADDR, LOGS_DIR
from hc.models import StreamState

log = logging.getLogger(__name__)


class MediaMTXConfig:

    @staticmethod
    def _purge_stale(port: int) -> None:
        stale = CONFIG_DIR() / f"mediamtx_{port}.yml"
        try:
            stale.unlink(missing_ok=True)
            log.debug("Purged stale config for port %d", port)
        except Exception as exc:
            log.warning("Could not purge stale config for port %d: %s", port, exc)

    @staticmethod
    def write(state: StreamState) -> Path:
        cfg   = state.config
        port  = cfg.port
        # rtsp_path is always non-empty ("stream" is the fallback when
        # stream_path is not configured) — no "~all" needed.
        spath = cfg.rtsp_path
        addr  = LISTEN_ADDR()
        log_f = (LOGS_DIR() / f"mediamtx_{port}.log").resolve()
        cfg_f = CONFIG_DIR() / f"mediamtx_{port}.yml"

        log.info("[%s] Writing MediaMTX config → %s", cfg.name, cfg_f)

        MediaMTXConfig._purge_stale(port)

        # ── RTP / RTCP port calculation ──────────────────────────────────────
        # Port scheme: RTSP = odd (e.g. 8555), HLS = RTSP+1 (even),
        #              RTP  = RTSP+2 bumped to next even (RFC 3550 §11),
        #              RTCP = RTP+1 (odd).
        # Example: RTSP=8555 → HLS=8556, RTP=8558 (even✓), RTCP=8559 (odd✓)
        rtp_base = port + 2
        if rtp_base % 2 != 0:
            rtp_base += 1
        rtp_addr  = f"{addr}:{rtp_base}"
        rtcp_addr = f"{addr}:{rtp_base + 1}"

        log.info(
            "[%s] Port assignment: RTSP=%d (odd✓)  HLS=%d  RTP=%d (even✓)  RTCP=%d",
            cfg.name, port, cfg.hls_port, rtp_base, rtp_base + 1,
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
                f"hlsVariant: mpegts\n"
                # ── HLS/RTSP sync (v6.3) ──────────────────────────────────────
                # 4 s segments align exactly with FFmpeg -force_key_frames every
                # 4 s (worker.py).  Each segment therefore starts on an IDR frame
                # so HLS and RTSP playback stay in lock-step.  Changing this
                # value requires a matching change to worker.py.
                f"hlsSegmentCount: 10\n"
                f"hlsSegmentDuration: 4s\n"
                f"hlsPartDuration: 0s\n"
                # 20 MiB cap — quoted string required by MediaMTX v1.9.x Go unmarshaller.
                f"hlsSegmentMaxSize: '20971520'\n"
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
            f"# Stream path: /{spath}   RTSP push → rtsp://127.0.0.1:{port}/{spath}\n"
            f"# RTSP={port} (odd✓)  HLS={cfg.hls_port}  RTP={rtp_base} (even✓)  RTCP={rtp_base+1}\n"
            f"# rtmp/srt/webrtc: false prevents port-1935/8890/8889 collisions\n"
            f"logLevel: error\n"
            f"logDestinations: [file]\n"
            f"logFile: {str(log_f).replace(chr(92), '/')}\n"
            f"\n"
            f"rtspAddress: {addr}:{port}\n"
            f"rtpAddress:  {rtp_addr}\n"
            f"rtcpAddress: {rtcp_addr}\n"
            # readTimeout/writeTimeout raised to 30 s (v6.3): the high-quality
            # slow preset encoder can briefly stall on CPU-heavy frames; 15 s
            # was tight enough to trigger spurious RTSP session teardowns.
            f"readTimeout: 30s\n"
            f"writeTimeout: 30s\n"
            f"writeQueueSize: 2048\n"
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
