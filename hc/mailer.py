"""
hc/mailer.py  —  SMTP email alerts for stream errors and unexpected stops.

Configuration is read from  <BASE_DIR>/mail_config.json  on every send so
the file can be edited without restarting HydraCast.

mail_config.json schema
────────────────────────
{
    "enabled":       true,
    "smtp_host":     "smtp.gmail.com",
    "smtp_port":     587,
    "use_tls":       true,
    "username":      "you@gmail.com",
    "password":      "your-app-password",
    "from_addr":     "you@gmail.com",
    "to_addrs":      ["ops@example.com", "backup@example.com"],
    "on_error":      true,
    "on_stop":       true,
    "cooldown_secs": 300
}

Fields
──────
enabled        Master switch.  Set false to silence all alerts without
               removing the config file.
smtp_host      SMTP server hostname.
smtp_port      Usually 587 (STARTTLS) or 465 (SSL).
use_tls        true  → STARTTLS on port 587 (recommended)
               false → plain SMTP or implicit SSL on port 465
               For port 465 set use_tls: false and the module will use
               smtplib.SMTP_SSL automatically.
username       Login username (often the same as from_addr).
password       App password or SMTP password.  For Gmail create an
               App Password at myaccount.google.com/apppasswords.
from_addr      Envelope / display From address.
to_addrs       List of recipient addresses.
on_error       Send alert when a stream enters ERROR status.
on_stop        Send alert when a stream stops unexpectedly (non-zero exit).
cooldown_secs  Minimum seconds between two alerts for the same stream.
               Prevents alert floods during repeated auto-restart cycles.
               Default 300 s (5 min).  Set 0 to disable cooldown.

Gmail quick-start
─────────────────
1. Enable 2-Step Verification on your Google account.
2. Go to myaccount.google.com/apppasswords → create a password for
   "HydraCast".
3. Set smtp_host: "smtp.gmail.com", smtp_port: 587, use_tls: true,
   username/from_addr to your Gmail address, password to the app password.
"""
from __future__ import annotations

import json
import logging
import smtplib
import socket
import threading
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# Module-level cooldown tracker: stream_name → last_sent_timestamp
_cooldown: Dict[str, float] = {}
_cooldown_lock = threading.Lock()

# ── Config template written on first run ──────────────────────────────────────
_CONFIG_TEMPLATE = {
    "enabled":       False,
    "smtp_host":     "smtp.gmail.com",
    "smtp_port":     587,
    "use_tls":       True,
    "username":      "you@gmail.com",
    "password":      "your-app-password",
    "from_addr":     "you@gmail.com",
    "to_addrs":      ["ops@example.com"],
    "on_error":      True,
    "on_stop":       True,
    "cooldown_secs": 300,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _config_path() -> Path:
    from hc.constants import BASE_DIR
    return BASE_DIR() / "mail_config.json"


def _load_config() -> Optional[dict]:
    """
    Load and return the mail config dict, or None if disabled / missing.
    Creates a template file on first call so the operator knows what to fill in.
    """
    path = _config_path()

    if not path.exists():
        try:
            path.write_text(
                json.dumps(_CONFIG_TEMPLATE, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            log.info(
                "mailer: created mail_config.json template at %s — "
                "edit it and set \"enabled\": true to activate alerts.",
                path,
            )
        except Exception as exc:
            log.warning("mailer: could not write config template: %s", exc)
        return None

    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("mailer: failed to read mail_config.json: %s", exc)
        return None

    if not cfg.get("enabled", False):
        return None

    required = ("smtp_host", "smtp_port", "username", "password",
                "from_addr", "to_addrs")
    for key in required:
        if not cfg.get(key):
            log.warning("mailer: mail_config.json missing required field '%s'", key)
            return None

    if not isinstance(cfg["to_addrs"], list) or not cfg["to_addrs"]:
        log.warning("mailer: to_addrs must be a non-empty list")
        return None

    return cfg


def _in_cooldown(stream_name: str, cooldown_secs: float) -> bool:
    """Return True and log if the stream is still in its cooldown window."""
    if cooldown_secs <= 0:
        return False
    now = time.monotonic()
    with _cooldown_lock:
        last = _cooldown.get(stream_name, 0.0)
        if now - last < cooldown_secs:
            remaining = int(cooldown_secs - (now - last))
            log.info(
                "mailer: alert for '%s' suppressed (cooldown %ds remaining).",
                stream_name, remaining,
            )
            return True
        _cooldown[stream_name] = now
    return False


def _build_message(
    cfg: dict,
    subject: str,
    body_lines: List[str],
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg["from_addr"]
    msg["To"]      = ", ".join(cfg["to_addrs"])

    # Plain-text part
    plain = "\n".join(body_lines)
    # HTML part — simple but readable
    html_rows = "".join(
        f"<tr><td style='padding:4px 8px;color:#888'>{ln}</td></tr>"
        if ln.startswith("  ") else
        f"<tr><td style='padding:6px 8px;font-weight:bold'>{ln}</td></tr>"
        for ln in body_lines
        if ln
    )
    html = f"""
<html><body style="font-family:monospace;background:#1a1a1a;color:#e0e0e0;padding:24px">
  <div style="max-width:600px;margin:auto;background:#242424;border-radius:8px;
              border-left:4px solid #e55;padding:16px">
    <h2 style="margin:0 0 16px;color:#f88">{subject}</h2>
    <table style="width:100%;border-collapse:collapse">{html_rows}</table>
    <p style="margin:16px 0 0;font-size:11px;color:#555">
      Sent by HydraCast &mdash; {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </p>
  </div>
</body></html>"""

    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))
    return msg


def _send_smtp(cfg: dict, msg: MIMEMultipart) -> None:
    """Open an SMTP connection, authenticate, and send *msg*."""
    host      = cfg["smtp_host"]
    port      = int(cfg["smtp_port"])
    use_tls   = cfg.get("use_tls", True)
    username  = cfg["username"]
    password  = cfg["password"]
    to_addrs  = cfg["to_addrs"]
    timeout   = 15  # seconds

    try:
        if not use_tls and port == 465:
            # Implicit SSL (port 465)
            with smtplib.SMTP_SSL(host, port, timeout=timeout) as server:
                server.login(username, password)
                server.sendmail(cfg["from_addr"], to_addrs, msg.as_string())
        else:
            # STARTTLS (port 587) or plain (rare)
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(username, password)
                server.sendmail(cfg["from_addr"], to_addrs, msg.as_string())

        log.info(
            "mailer: alert sent to %s via %s:%d",
            ", ".join(to_addrs), host, port,
        )
    except smtplib.SMTPAuthenticationError as exc:
        log.error("mailer: SMTP authentication failed — check username/password: %s", exc)
    except (smtplib.SMTPException, socket.error, OSError) as exc:
        log.error("mailer: SMTP send failed (%s:%d): %s", host, port, exc)


# ── Public API ────────────────────────────────────────────────────────────────

def send_error_alert(
    stream_name: str,
    port: int,
    error_msg: str,
    exit_code: int,
    stderr_snippet: str = "",
) -> None:
    """
    Send an alert email when a stream enters ERROR state.
    Runs in a background thread so it never blocks the worker.
    """
    threading.Thread(
        target=_send_error_alert,
        args=(stream_name, port, error_msg, exit_code, stderr_snippet),
        daemon=True,
        name=f"mailer-err-{port}",
    ).start()


def send_stop_alert(
    stream_name: str,
    port: int,
    reason: str = "Unexpected stop",
) -> None:
    """
    Send an alert email when a stream stops unexpectedly.
    Runs in a background thread so it never blocks the worker.
    """
    threading.Thread(
        target=_send_stop_alert,
        args=(stream_name, port, reason),
        daemon=True,
        name=f"mailer-stop-{port}",
    ).start()


# ── Internal implementations (run in daemon threads) ─────────────────────────

def _send_error_alert(
    stream_name: str,
    port: int,
    error_msg: str,
    exit_code: int,
    stderr_snippet: str,
) -> None:
    cfg = _load_config()
    if cfg is None:
        return
    if not cfg.get("on_error", True):
        return
    if _in_cooldown(stream_name, cfg.get("cooldown_secs", 300)):
        return

    subject = f"🔴 HydraCast ERROR — {stream_name}"
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    host    = socket.gethostname()

    body_lines = [
        f"Stream '{stream_name}' has entered ERROR state.",
        "",
        f"  Time      : {now}",
        f"  Host      : {host}",
        f"  Stream    : {stream_name}",
        f"  Port      : {port}",
        f"  Exit code : {exit_code}",
        f"  Error     : {error_msg[:300]}",
    ]
    if stderr_snippet:
        body_lines += [
            "",
            "  FFmpeg stderr (last 300 chars):",
            f"  {stderr_snippet[:300]}",
        ]
    body_lines += [
        "",
        "HydraCast will attempt automatic restart with exponential back-off.",
        "Check the TUI event log or hydracast.log for details.",
    ]

    msg = _build_message(cfg, subject, body_lines)
    _send_smtp(cfg, msg)


def _send_stop_alert(
    stream_name: str,
    port: int,
    reason: str,
) -> None:
    cfg = _load_config()
    if cfg is None:
        return
    if not cfg.get("on_stop", True):
        return
    if _in_cooldown(stream_name, cfg.get("cooldown_secs", 300)):
        return

    subject = f"⚠️ HydraCast STOPPED — {stream_name}"
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    host    = socket.gethostname()

    body_lines = [
        f"Stream '{stream_name}' has stopped unexpectedly.",
        "",
        f"  Time    : {now}",
        f"  Host    : {host}",
        f"  Stream  : {stream_name}",
        f"  Port    : {port}",
        f"  Reason  : {reason}",
        "",
        "The scheduler will restart the stream at the next scheduled window.",
        "Use the TUI (key R) or Web UI to restart it immediately.",
    ]

    msg = _build_message(cfg, subject, body_lines)
    _send_smtp(cfg, msg)


def test_alert(to_addr: Optional[str] = None) -> bool:
    """
    Send a test email using the current config.  Returns True on success.
    Useful from the web UI or CLI for verifying SMTP settings.
    """
    cfg = _load_config()
    if cfg is None:
        log.warning("mailer: test_alert — no valid config (enabled=false or missing)")
        return False

    override_to = [to_addr] if to_addr else None
    if override_to:
        cfg = dict(cfg, to_addrs=override_to)

    subject = "✅ HydraCast — mail alert test"
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body_lines = [
        "This is a test alert from HydraCast.",
        "",
        f"  Time : {now}",
        f"  Host : {socket.gethostname()}",
        "",
        "If you received this, your SMTP configuration is working correctly.",
    ]
    msg = _build_message(cfg, subject, body_lines)
    try:
        _send_smtp(cfg, msg)
        return True
    except Exception as exc:
        log.error("mailer: test_alert failed: %s", exc)
        return False
