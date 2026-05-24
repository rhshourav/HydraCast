"""
hc/mailer.py  —  Email alerts for HydraCast.

Sending mode: Microsoft Graph API via OAuth2 Client Credentials.
Requires an Azure App Registration with:
  • A client secret  (not a certificate)
  • API permission: Microsoft Graph → Application → Mail.Send
  • A mailbox address that the app is allowed to send from

mail_config.hcf schema
────────────────────────
{
    "enabled":       true,
    "tenant_id":     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "client_id":     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "client_secret": "your-client-secret-value",
    "from_addr":     "hydracast@yourdomain.com",
    "to_addrs":      ["ops@example.com"],
    "on_error":      true,
    "on_stop":       true,
    "cooldown_secs": 300
}

Azure quick-start
──────────────────
1. portal.azure.com → Azure Active Directory → App registrations → New registration.
2. Certificates & secrets → New client secret → copy the Value immediately.
3. API permissions → Add → Microsoft Graph → Application permissions → Mail.Send → Grant admin consent.
4. Fill in tenant_id (Directory ID), client_id (Application ID), client_secret, and
   from_addr (a mailbox your tenant controls) in Settings → Mail Alerts in the Web UI.
"""
from __future__ import annotations

import json
import logging
import socket
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# ── Cooldown tracker ──────────────────────────────────────────────────────────
_cooldown: Dict[str, float] = {}
_cooldown_lock = threading.Lock()

# ── Default config template ───────────────────────────────────────────────────
_CONFIG_TEMPLATE = {
    "enabled":       False,
    "tenant_id":     "",
    "client_id":     "",
    "client_secret": "",
    "from_addr":     "you@yourdomain.com",
    "to_addrs":      ["ops@example.com"],
    "on_error":      True,
    "on_stop":       True,
    "cooldown_secs": 300,
}


# ═════════════════════════════════════════════════════════════════════════════
# PATH HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _config_dir() -> Path:
    from hc.constants import CONFIG_DIR
    d = CONFIG_DIR()
    d.mkdir(parents=True, exist_ok=True)
    return d

def _config_path() -> Path:
    return _config_dir() / "mail_config.hcf"


# ═════════════════════════════════════════════════════════════════════════════
# CONFIG LOADING
# ═════════════════════════════════════════════════════════════════════════════

def _load_config() -> Optional[dict]:
    """
    Load and validate mail_config.hcf.
    Returns None if disabled or invalid (already logged).
    Creates a template on first run.
    """
    path = _config_path()

    if not path.exists():
        try:
            path.write_text(
                json.dumps(_CONFIG_TEMPLATE, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            log.info(
                "mailer: created mail_config.hcf template at %s — "
                "edit it and set \"enabled\": true to activate alerts.",
                path,
            )
        except Exception as exc:
            log.warning("mailer: could not write config template: %s", exc)
        return None

    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("mailer: failed to read mail_config.hcf: %s", exc)
        return None

    if not cfg.get("enabled", False):
        return None

    if not isinstance(cfg.get("to_addrs"), list) or not cfg["to_addrs"]:
        log.warning("mailer: to_addrs must be a non-empty list")
        return None

    for key in ("tenant_id", "client_id", "client_secret", "from_addr"):
        if not cfg.get(key, "").strip():
            log.warning("mailer: mail_config.hcf missing required field '%s'", key)
            return None

    return cfg


# ═════════════════════════════════════════════════════════════════════════════
# COOLDOWN
# ═════════════════════════════════════════════════════════════════════════════

def _in_cooldown(stream_name: str, cooldown_secs: float) -> bool:
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


# ═════════════════════════════════════════════════════════════════════════════
# MICROSOFT GRAPH OAUTH2  (Client Credentials — no user sign-in required)
# ═════════════════════════════════════════════════════════════════════════════

def _acquire_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """
    Obtain an access token via the OAuth2 client-credentials flow.
    Raises RuntimeError on failure.
    """
    url  = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    body = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://graph.microsoft.com/.default",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "access_token" not in data:
            raise RuntimeError(f"Token response missing access_token: {data}")
        return data["access_token"]
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Token request failed {exc.code}: {detail}") from exc


def _send_via_graph(cfg: dict, subject: str, body_html: str, body_plain: str) -> None:
    """Send an email through Microsoft Graph API. Raises on failure."""
    token = _acquire_token(
        cfg["tenant_id"].strip(),
        cfg["client_id"].strip(),
        cfg["client_secret"].strip(),
    )
    from_addr = cfg["from_addr"].strip()
    to_addrs  = cfg["to_addrs"]

    message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_html,
            },
            "from": {
                "emailAddress": {"address": from_addr}
            },
            "toRecipients": [
                {"emailAddress": {"address": addr}} for addr in to_addrs
            ],
        },
        "saveToSentItems": "false",
    }

    url = f"https://graph.microsoft.com/v1.0/users/{from_addr}/sendMail"
    body_bytes = json.dumps(message, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body_bytes, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
        if status not in (200, 202):
            raise RuntimeError(f"Graph sendMail returned HTTP {status}")
        log.info("mailer: Graph alert sent to %s", ", ".join(to_addrs))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Graph sendMail failed {exc.code}: {detail}") from exc


# ═════════════════════════════════════════════════════════════════════════════
# MESSAGE BUILDER
# ═════════════════════════════════════════════════════════════════════════════

def _build_html(subject: str, body_lines: List[str]) -> str:
    html_rows = "".join(
        f"<tr><td style='padding:4px 8px;color:#888'>{ln}</td></tr>"
        if ln.startswith("  ") else
        f"<tr><td style='padding:6px 8px;font-weight:bold'>{ln}</td></tr>"
        for ln in body_lines
        if ln
    )
    return f"""
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


def _build_plain(body_lines: List[str]) -> str:
    return "\n".join(body_lines)


# ═════════════════════════════════════════════════════════════════════════════
# UNIFIED SEND DISPATCHER
# ═════════════════════════════════════════════════════════════════════════════

def _dispatch(cfg: dict, subject: str, body_lines: List[str]) -> None:
    """Build the message and send via Microsoft Graph. Raises on failure."""
    html  = _build_html(subject, body_lines)
    plain = _build_plain(body_lines)
    _send_via_graph(cfg, subject, html, plain)


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API  (fire-and-forget threads)
# ═════════════════════════════════════════════════════════════════════════════

def send_error_alert(
    stream_name: str,
    port: int,
    error_msg: str,
    exit_code: int,
    stderr_snippet: str = "",
) -> None:
    """Send an alert when a stream enters ERROR state (background thread)."""
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
    """Send an alert when a stream stops unexpectedly (background thread)."""
    threading.Thread(
        target=_send_stop_alert,
        args=(stream_name, port, reason),
        daemon=True,
        name=f"mailer-stop-{port}",
    ).start()


# ═════════════════════════════════════════════════════════════════════════════
# INTERNAL IMPLEMENTATIONS  (run in daemon threads)
# ═════════════════════════════════════════════════════════════════════════════

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

    try:
        _dispatch(cfg, subject, body_lines)
    except Exception as exc:
        log.error("mailer: failed to send error alert for '%s': %s", stream_name, exc)


def _send_stop_alert(stream_name: str, port: int, reason: str) -> None:
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

    try:
        _dispatch(cfg, subject, body_lines)
    except Exception as exc:
        log.error("mailer: failed to send stop alert for '%s': %s", stream_name, exc)


# ═════════════════════════════════════════════════════════════════════════════
# OAUTH2 STATUS STUBS
# ═════════════════════════════════════════════════════════════════════════════
# This build uses the Microsoft Graph client-credentials flow (no interactive
# OAuth2 consent required).  The functions below are stubs so that any module
# that conditionally imports them (e.g. web_handlers_get.py) does not crash
# with ImportError.  If a future build adds interactive OAuth2 flows these
# stubs should be replaced with real implementations.

def get_oauth2_flow_status() -> dict:
    """
    Return the status of a Gmail / generic OAuth2 device-code flow.
    Not implemented in this (Graph client-credentials) build.
    """
    return {
        "status":       "unsupported",
        "token_exists": False,
        "message":      "This build uses Microsoft Graph client credentials; "
                        "interactive OAuth2 flows are not supported.",
    }


def get_microsoft_oauth2_status(cfg: dict) -> dict:
    """
    Return the status of the Microsoft Graph token for *cfg*.
    Performs a lightweight token-acquisition probe to verify credentials.
    """
    required = ("tenant_id", "client_id", "client_secret")
    if not all(cfg.get(k, "").strip() for k in required):
        return {
            "status":       "not_configured",
            "token_exists": False,
            "message":      "Microsoft Graph credentials are incomplete.",
        }
    try:
        _acquire_token(
            cfg["tenant_id"].strip(),
            cfg["client_id"].strip(),
            cfg["client_secret"].strip(),
        )
        return {"status": "ok", "token_exists": True, "message": "Credentials valid."}
    except Exception as exc:
        return {
            "status":       "error",
            "token_exists": False,
            "message":      str(exc),
        }


# ═════════════════════════════════════════════════════════════════════════════
# TEST ALERT  (called from Web UI — returns True/False + error string)
# ═════════════════════════════════════════════════════════════════════════════

def test_alert(to_addr: Optional[str] = None) -> tuple[bool, str]:
    """
    Send a test email. Returns (True, "") on success or (False, error_message).
    Called synchronously from the Web UI handler.
    """
    cfg = _load_config()
    if cfg is None:
        msg = "Mail alerts are disabled or mail_config.hcf is missing/invalid."
        log.warning("mailer: test_alert — %s", msg)
        return False, msg

    if to_addr:
        cfg = dict(cfg, to_addrs=[to_addr])

    subject = "✅ HydraCast — mail alert test"
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body_lines = [
        "This is a test alert from HydraCast.",
        "",
        f"  Time    : {now}",
        f"  Host    : {socket.gethostname()}",
        f"  From    : {cfg.get('from_addr', '')}",
        f"  Tenant  : {cfg.get('tenant_id', '')[:8]}…",
        "",
        "If you received this, your Outlook/Microsoft mail configuration is working correctly.",
    ]

    try:
        _dispatch(cfg, subject, body_lines)
        return True, ""
    except Exception as exc:
        log.error("mailer: test_alert failed: %s", exc)
        return False, str(exc)
