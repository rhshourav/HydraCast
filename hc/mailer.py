"""
hc/mailer.py  —  Email alerts for HydraCast.

Supports two sending modes, auto-detected from mail_config.json:
  1. OAuth2 / Gmail  — no password; user clicks "Connect Gmail" in the Web UI.
  2. SMTP            — works with Outlook, Office 365, Yahoo, custom servers.

mail_config.json schema
────────────────────────
{
    "enabled":       true,
    "mode":          "gmail_oauth2",   ← "gmail_oauth2"  OR  "smtp"
    "to_addrs":      ["ops@example.com"],
    "on_error":      true,
    "on_stop":       true,
    "cooldown_secs": 300,

    // ── Gmail OAuth2 only ──────────────────────────────────────────────────
    "oauth2_token_file": "gmail_token.json",   ← written by the auth flow

    // ── SMTP only ──────────────────────────────────────────────────────────
    "smtp_host":  "smtp.office365.com",
    "smtp_port":  587,
    "use_tls":    true,
    "username":   "you@outlook.com",
    "password":   "your-app-password",
    "from_addr":  "you@outlook.com"
}

Gmail quick-start (OAuth2)
──────────────────────────
1. Put client_secret_*.json (downloaded from Google Cloud Console) in the
   HydraCast base directory — rename it to  gmail_client_secret.json.
2. Open the Web UI → Settings → Mail Alerts → click  "Connect Gmail".
   A browser tab opens; sign in and approve access.
3. The token is saved automatically; no passwords needed ever again.

SMTP quick-start (Outlook / Yahoo / custom)
────────────────────────────────────────────
Set mode="smtp" and fill in smtp_host, smtp_port, username, password,
from_addr.  For Outlook.com: host=smtp-mail.outlook.com port=587 use_tls=true.
For Office 365:              host=smtp.office365.com    port=587 use_tls=true.
For Yahoo:                   host=smtp.mail.yahoo.com   port=587 use_tls=true.
For Gmail SMTP (fallback):   host=smtp.gmail.com        port=587 use_tls=true
                             password = 16-char App Password (not account pw).
"""
from __future__ import annotations

import base64
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

# ── Cooldown tracker ──────────────────────────────────────────────────────────
_cooldown: Dict[str, float] = {}
_cooldown_lock = threading.Lock()

# ── OAuth2 scopes needed ──────────────────────────────────────────────────────
_GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# ── Default config template (SMTP mode) ──────────────────────────────────────
_CONFIG_TEMPLATE = {
    "enabled":       False,
    "mode":          "smtp",
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


# ═════════════════════════════════════════════════════════════════════════════
# PATH HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _base() -> Path:
    from hc.constants import BASE_DIR
    return BASE_DIR()

def _config_path() -> Path:
    return _base() / "mail_config.json"

def _client_secret_path() -> Optional[Path]:
    """Find any gmail_client_secret.json or client_secret_*.json in BASE_DIR."""
    base = _base()
    for name in ["gmail_client_secret.json"]:
        p = base / name
        if p.exists():
            return p
    matches = sorted(base.glob("client_secret_*.json"))
    return matches[0] if matches else None

def _token_path(cfg: dict) -> Path:
    return _base() / cfg.get("oauth2_token_file", "gmail_token.json")


# ═════════════════════════════════════════════════════════════════════════════
# CONFIG LOADING
# ═════════════════════════════════════════════════════════════════════════════

def _load_config() -> Optional[dict]:
    """
    Load and validate mail_config.json.
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

    if not isinstance(cfg.get("to_addrs"), list) or not cfg["to_addrs"]:
        log.warning("mailer: to_addrs must be a non-empty list")
        return None

    mode = cfg.get("mode", "smtp")

    if mode == "gmail_oauth2":
        token_p = _token_path(cfg)
        if not token_p.exists():
            log.warning(
                "mailer: Gmail OAuth2 mode selected but token file not found at %s. "
                "Open the Web UI → Settings → Mail Alerts → Connect Gmail.",
                token_p,
            )
            return None
        return cfg

    # SMTP mode — validate required fields
    required = ("smtp_host", "smtp_port", "username", "password", "from_addr")
    for key in required:
        if not cfg.get(key):
            log.warning("mailer: mail_config.json missing required SMTP field '%s'", key)
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
# MESSAGE BUILDER
# ═════════════════════════════════════════════════════════════════════════════

def _build_message(
    from_addr: str,
    to_addrs: List[str],
    subject: str,
    body_lines: List[str],
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = ", ".join(to_addrs)

    plain = "\n".join(body_lines)
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


# ═════════════════════════════════════════════════════════════════════════════
# GMAIL OAUTH2 SENDER
# ═════════════════════════════════════════════════════════════════════════════

def _send_gmail_oauth2(cfg: dict, msg: MIMEMultipart) -> None:
    """Send via Gmail API using a stored OAuth2 token. Raises on failure."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        raise RuntimeError(
            "Google API libraries not installed. "
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    token_p = _token_path(cfg)
    creds = Credentials.from_authorized_user_file(str(token_p), _GMAIL_SCOPES)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_p.write_text(creds.to_json(), encoding="utf-8")
            log.info("mailer: Gmail OAuth2 token refreshed.")
        except Exception as exc:
            raise RuntimeError(f"Token refresh failed — re-authenticate via Web UI: {exc}") from exc

    if not creds.valid:
        raise RuntimeError(
            "Gmail OAuth2 token is invalid. "
            "Re-authenticate via Web UI → Settings → Mail Alerts → Connect Gmail."
        )

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    try:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        log.info(
            "mailer: Gmail OAuth2 alert sent to %s",
            ", ".join(cfg["to_addrs"]),
        )
    except HttpError as exc:
        raise RuntimeError(f"Gmail API error: {exc}") from exc


# ═════════════════════════════════════════════════════════════════════════════
# SMTP SENDER  (Outlook, Yahoo, Office365, Gmail-SMTP, custom)
# ═════════════════════════════════════════════════════════════════════════════

def _send_smtp(cfg: dict, msg: MIMEMultipart) -> None:
    """Send via SMTP. Raises on any failure so callers know what happened."""
    host     = cfg["smtp_host"]
    port     = int(cfg["smtp_port"])
    use_tls  = cfg.get("use_tls", True)
    username = cfg["username"]
    password = cfg["password"]
    to_addrs = cfg["to_addrs"]
    timeout  = 20  # seconds

    try:
        if not use_tls and port == 465:
            # Implicit SSL
            with smtplib.SMTP_SSL(host, port, timeout=timeout) as server:
                server.login(username, password)
                server.sendmail(cfg["from_addr"], to_addrs, msg.as_string())
        else:
            # STARTTLS (587) or plain fallback
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(username, password)
                server.sendmail(cfg["from_addr"], to_addrs, msg.as_string())

        log.info(
            "mailer: SMTP alert sent to %s via %s:%d",
            ", ".join(to_addrs), host, port,
        )

    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            f"SMTP authentication failed ({host}:{port}). "
            "For Gmail use an App Password, not your account password. "
            f"Detail: {exc}"
        ) from exc
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"SMTP error ({host}:{port}): {exc}") from exc
    except (socket.timeout, OSError) as exc:
        raise RuntimeError(f"Network error reaching {host}:{port}: {exc}") from exc


# ═════════════════════════════════════════════════════════════════════════════
# UNIFIED SEND DISPATCHER
# ═════════════════════════════════════════════════════════════════════════════

def _dispatch(cfg: dict, subject: str, body_lines: List[str]) -> None:
    """Build the message and send via the configured mode. Raises on failure."""
    mode = cfg.get("mode", "smtp")
    from_addr = (
        "HydraCast <me>"
        if mode == "gmail_oauth2"
        else cfg.get("from_addr", cfg.get("username", ""))
    )
    msg = _build_message(from_addr, cfg["to_addrs"], subject, body_lines)

    if mode == "gmail_oauth2":
        _send_gmail_oauth2(cfg, msg)
    else:
        _send_smtp(cfg, msg)


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
# TEST ALERT  (called from Web UI — returns True/False + error string)
# ═════════════════════════════════════════════════════════════════════════════

def test_alert(to_addr: Optional[str] = None) -> tuple[bool, str]:
    """
    Send a test email. Returns (True, "") on success or (False, error_message).
    Called synchronously from the Web UI handler.
    """
    cfg = _load_config()
    if cfg is None:
        msg = "Mail alerts are disabled or mail_config.json is missing/invalid."
        log.warning("mailer: test_alert — %s", msg)
        return False, msg

    if to_addr:
        cfg = dict(cfg, to_addrs=[to_addr])

    subject = "✅ HydraCast — mail alert test"
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body_lines = [
        "This is a test alert from HydraCast.",
        "",
        f"  Time : {now}",
        f"  Host : {socket.gethostname()}",
        f"  Mode : {cfg.get('mode', 'smtp').upper()}",
        "",
        "If you received this, your mail configuration is working correctly.",
    ]

    try:
        _dispatch(cfg, subject, body_lines)
        return True, ""
    except Exception as exc:
        log.error("mailer: test_alert failed: %s", exc)
        return False, str(exc)


# ═════════════════════════════════════════════════════════════════════════════
# GMAIL OAUTH2 FLOW  (called from Web UI to kick off browser auth)
# ═════════════════════════════════════════════════════════════════════════════

def start_gmail_oauth2_flow() -> tuple[bool, str]:
    """
    Starts the OAuth2 authorization flow.

    - Looks for gmail_client_secret.json (or any client_secret_*.json) in BASE_DIR.
    - Opens a local server on a random port to catch the redirect.
    - Saves the token to gmail_token.json.
    - Returns (True, auth_url) so the Web UI can open the browser, OR
      (False, error_message) if something went wrong before we get a URL.

    The flow runs in a background thread; poll get_oauth2_flow_status() for result.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        return False, (
            "google-auth-oauthlib not installed. "
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    secret = _client_secret_path()
    if secret is None:
        return False, (
            "Client secret file not found in the HydraCast base directory. "
            "Download it from Google Cloud Console and save it as gmail_client_secret.json."
        )

    # Determine token output path from config (or default)
    try:
        cfg = json.loads(_config_path().read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    token_p = _base() / cfg.get("oauth2_token_file", "gmail_token.json")

    def _run_flow() -> None:
        global _oauth2_flow_status, _oauth2_flow_error
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(secret), _GMAIL_SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
            token_p.write_text(creds.to_json(), encoding="utf-8")
            log.info("mailer: Gmail OAuth2 token saved to %s", token_p)
            _oauth2_flow_status = "done"
            _oauth2_flow_error  = ""
        except Exception as exc:
            log.error("mailer: OAuth2 flow failed: %s", exc)
            _oauth2_flow_status = "error"
            _oauth2_flow_error  = str(exc)

    _oauth2_flow_status = "running"
    _oauth2_flow_error  = ""
    threading.Thread(target=_run_flow, daemon=True, name="gmail-oauth2-flow").start()
    return True, (
        "Browser window opened for Google sign-in. "
        "Complete the sign-in then return here and click 'Check Status'."
    )


# Shared state for the OAuth2 flow thread
_oauth2_flow_status: str = "idle"   # "idle" | "running" | "done" | "error"
_oauth2_flow_error:  str = ""


def get_oauth2_flow_status() -> dict:
    """Return current OAuth2 flow status for the Web UI to poll."""
    token_exists = False
    try:
        cfg = json.loads(_config_path().read_text(encoding="utf-8"))
        token_exists = _token_path(cfg).exists()
    except Exception:
        pass
    return {
        "status":       _oauth2_flow_status,
        "error":        _oauth2_flow_error,
        "token_exists": token_exists,
    }


def revoke_gmail_token() -> tuple[bool, str]:
    """Delete the stored Gmail OAuth2 token."""
    try:
        cfg = json.loads(_config_path().read_text(encoding="utf-8"))
        p   = _token_path(cfg)
    except Exception:
        p = _base() / "gmail_token.json"

    if p.exists():
        p.unlink()
        log.info("mailer: Gmail token revoked (%s deleted).", p)
        return True, "Gmail account disconnected."
    return False, "No token file found."
