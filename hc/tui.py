"""
hc/tui.py  —  Terminal UI, keyboard handler, and TUI seek prompt.

v6.2 changes
────────────
• ASCII banner replaced with a slim one-liner wordmark header.
• [P] hotkey: live web-port change prompt (updates constants + restarts WebServer).
• Confirmation prompts before Stop-All (X) and Restart (R).
• Distinct Rich color per StreamStatus for quick visual scanning.
• Web UI URL + port shown prominently in the header bar at all times.
• Stream detail overlay redesigned: cleaner, more information.
• Status column widened slightly; status dot colours now unique per state.
"""
from __future__ import annotations

import queue
import sys
import threading
import time
from datetime import datetime
from typing import Optional

import psutil
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from hc.constants import (
    APP_VER, APP_AUTHOR, APP_GITHUB,
    CC, CD, CG, CM, CR, CW, CY, CB,
    CPU_COUNT, IS_WIN, get_web_port, set_web_port,
    SSL_CERT, SSL_KEY, get_ssl_cert, get_ssl_key,
    get_http_port,
)
from hc.manager import StreamManager
from hc.models import StreamStatus
from hc.utils import _local_ip
from hc.worker import LogBuffer


def _web_schema() -> str:
    """
    Return 'https' when SSL is (or will be) active, 'http' otherwise.
    Mirrors the resolution logic in WebServer._resolve_ssl so the TUI
    always shows the correct schema even before the server has started.
    """
    from pathlib import Path
    port = get_web_port()
    # CLI-explicit cert paths
    cli_cert = get_ssl_cert()
    cli_key  = get_ssl_key()
    if cli_cert and cli_key and Path(cli_cert).is_file() and Path(cli_key).is_file():
        return "https"
    # Default ssl/ directory certs
    try:
        if SSL_CERT().is_file() and SSL_KEY().is_file():
            return "https"
    except RuntimeError:
        pass  # set_base_dir not yet called
    # Port 443 triggers auto-generation → will be HTTPS
    if port == 443:
        return "https"
    return "http"


# ── Status colour map  (one distinct colour per state) ───────────────────────
_STATUS_STYLE: dict[StreamStatus, tuple[str, str]] = {
    # state              →  (dot_style,        label_style)
    StreamStatus.STOPPED:   ("dim white",       "dim white"),
    StreamStatus.STARTING:  ("bold yellow",     "yellow"),
    StreamStatus.LIVE:      ("bold green",      "bright_green"),
    StreamStatus.SCHEDULED: ("bold cyan",       "bright_cyan"),
    StreamStatus.ERROR:     ("bold red",        "bright_red"),
    StreamStatus.DISABLED:  ("dim",             "dim"),
    StreamStatus.ONESHOT:   ("bold magenta",    "bright_magenta"),
}


# =============================================================================
# HEADER  (replaces the old ASCII banner)
# =============================================================================

def _header_panel() -> Panel:
    """Slim, information-dense header: wordmark left, Web UI URL(s) right."""
    ip        = _local_ip()
    https_port = get_web_port()
    http_port  = get_http_port()
    schema     = _web_schema()
    use_ssl    = schema == "https"

    left = Text()
    left.append("◈ ", style="bold bright_cyan")
    left.append("HYDRACAST", style="bold bright_white")
    left.append(f"  v{APP_VER}", style="dim white")
    left.append("  ·  Multi-Stream RTSP Scheduler", style="dim white")

    right = Text(justify="right")
    right.append("Web UI  ", style="dim white")
    right.append(f"{schema}://{ip}:{https_port}", style="bold bright_cyan")
    if use_ssl and http_port != 0:
        right.append("  ", style="dim white")
        right.append(f"http://{ip}:{http_port}", style="dim cyan")
        right.append(" →redirect", style="dim white")
    right.append("  [P] change port", style="dim white")

    row = Table.grid(expand=True)
    row.add_column(ratio=1)
    row.add_column(ratio=1, justify="right")
    row.add_row(left, right)

    return Panel(
        row,
        border_style="bright_cyan",
        box=box.HORIZONTALS,
        padding=(0, 1),
    )


# =============================================================================
# TUI
# =============================================================================
class TUI:
    def __init__(self, manager: StreamManager, glog: LogBuffer) -> None:
        self.manager  = manager
        self.glog     = glog
        self.selected = 0

    # ── progress bar ─────────────────────────────────────────────────────────

    @staticmethod
    def _progress_bar(pct: float, width: int = 20) -> Text:
        if pct <= 0:
            t = Text()
            t.append("─" * width, style="dim white")
            t.append("   0.0%", style="dim white")
            return t
        filled = max(1, round(pct / 100 * width))
        empty  = width - filled
        t = Text()
        for i in range(filled):
            frac = i / max(1, width)
            col  = CG if frac < .55 else (CY if frac < .80 else CM)
            t.append("█", style=col)
        t.append("░" * empty, style="dim white")
        lc = CM if pct >= 80 else (CY if pct >= 55 else CG)
        t.append(f"  {pct:5.1f}%", style=f"bold {lc}")
        return t

    @staticmethod
    def _fmt_remaining(state) -> str:
        rem = state.time_remaining()
        if rem <= 0:
            return ""
        r = int(rem)
        return f"−{r//3600:02d}:{(r%3600)//60:02d}:{r%60:02d}"

    # ── status cell ──────────────────────────────────────────────────────────

    @staticmethod
    def _status_cell(st) -> Text:
        s   = st.status
        dot_style, lbl_style = _STATUS_STYLE.get(s, ("white", "white"))
        cell = Text()
        if s == StreamStatus.ERROR and st.error_msg:
            cell.append(" ● ", style="bold bright_red")
            cell.append("ERROR",  style="bold bright_red")
            # Show first word of error beside label (truncated)
            snippet = st.error_msg.split("\n")[0][:22]
            cell.append(f"\n  {snippet}", style="dim red")
        else:
            cell.append(f" {s.dot} ", style=dot_style)
            cell.append(s.label,       style=f"bold {lbl_style}")
        return cell

    # ── streams table ─────────────────────────────────────────────────────────

    def _streams_table(self) -> Table:
        tbl = Table(
            box=box.SIMPLE_HEAD, border_style="bright_black",
            header_style=f"bold {CW}", expand=True, padding=(0, 1),
            show_edge=True,
        )
        tbl.add_column("#",        style=CD,          width=3,      no_wrap=True)
        tbl.add_column("STREAM",   style=CW,          min_width=14, no_wrap=True)
        tbl.add_column("PORT",     style=CC,          width=6,      no_wrap=True)
        tbl.add_column("FILES",    style=CD,          width=5,      no_wrap=True)
        tbl.add_column("SCHEDULE", style=CW,          width=10,     no_wrap=True)
        tbl.add_column("STATUS",                      width=12,     no_wrap=True)
        tbl.add_column("PROGRESS",                    min_width=28, no_wrap=True)
        tbl.add_column("POSITION", style=CD,          width=16,     no_wrap=True)
        tbl.add_column("REMAINS",  style=CD,          width=10,     no_wrap=True)
        tbl.add_column("FPS",      style=CD,          width=5,      no_wrap=True)
        tbl.add_column("LOOP",     style=CD,          width=5,      no_wrap=True)
        tbl.add_column("RTSP URL", style="dim cyan",  min_width=24, no_wrap=True)

        for i, st in enumerate(self.manager.states):
            cfg         = st.config
            row_style   = "on grey11" if i == self.selected else ""
            sel_marker  = "▶ " if i == self.selected else "  "
            name_txt    = f"{sel_marker}{cfg.name}"
            if cfg.shuffle:     name_txt += " ⧖"
            if cfg.hls_enabled: name_txt += " ᴴ"
            n_files     = len(cfg.playlist)
            remaining   = self._fmt_remaining(st)
            rem_text    = Text(remaining, style=f"bold {CY}") if remaining else Text("—", style=CD)

            tbl.add_row(
                str(i + 1),
                name_txt,
                str(cfg.port),
                f"×{n_files}" if n_files > 1 else "1",
                cfg.weekdays_display(),
                self._status_cell(st),
                self._progress_bar(st.progress),
                st.format_pos(),
                rem_text,
                f"{st.fps:.0f}" if st.fps > 0 else "—",
                f"×{st.loop_count}" if st.loop_count > 0 else "—",
                cfg.rtsp_url,
                style=row_style,
            )
        return tbl

    # ── system panel ─────────────────────────────────────────────────────────

    def _system_panel(self) -> Panel:
        cpu  = psutil.cpu_percent(interval=None)
        mem  = psutil.virtual_memory()
        states = self.manager.states
        live_n  = sum(1 for s in states if s.status == StreamStatus.LIVE)
        err_n   = sum(1 for s in states if s.status == StreamStatus.ERROR)
        sched_n = sum(1 for s in states if s.status == StreamStatus.SCHEDULED)
        stop_n  = sum(1 for s in states if s.status == StreamStatus.STOPPED)
        pending = sum(1 for e in self.manager.events if not e.played)

        ip         = _local_ip()
        https_port = get_web_port()
        http_port  = get_http_port()
        schema     = _web_schema()
        use_ssl    = schema == "https"

        t = Text()
        t.append("CPU  ", style=CD); t.append_text(self._progress_bar(cpu, 12));    t.append("\n")
        t.append("MEM  ", style=CD); t.append_text(self._progress_bar(mem.percent, 12)); t.append("\n\n")
        t.append("Cores ",  style=CD); t.append(str(CPU_COUNT), style=CC)
        t.append("  Streams ", style=CD); t.append(str(len(states)), style=CW); t.append("\n")
        # Status breakdown with distinct colours
        t.append("● ", style="bold bright_green");   t.append(f"LIVE {live_n}  ",  style=CG)
        t.append("◷ ", style="bold bright_cyan");    t.append(f"SCHED {sched_n}",  style=CC); t.append("\n")
        t.append("● ", style="dim white");            t.append(f"STOP {stop_n}  ", style=CD)
        t.append("● ", style="bold bright_red");      t.append(f"ERR {err_n}",     style=CR if err_n else CD)
        t.append("\n")
        t.append("◈ ", style=CM); t.append(f"Events {pending} pending\n\n", style=CM)
        t.append(f"  LAN: {ip}\n", style=CD)
        t.append(f"  Web: {schema}://{ip}:{https_port}\n", style="bold bright_cyan")
        if use_ssl and http_port != 0:
            t.append(f"  HTTP→HTTPS: :{http_port}\n", style="dim cyan")
        t.append(datetime.now().strftime("  %a  %Y-%m-%d  %H:%M:%S"), style=CD)

        return Panel(t, title=f"[bold {CW}]SYSTEM[/]",
                     border_style="bright_black", box=box.ROUNDED, padding=(0, 1))

    # ── log panel ────────────────────────────────────────────────────────────

    def _log_panel(self) -> Panel:
        entries = self.glog.last(9)
        t = Text()
        colors = {"INFO": CW, "WARN": CY, "ERROR": CR}
        for msg, lvl in entries:
            prefix = {"INFO": "  ", "WARN": "⚠ ", "ERROR": "✖ "}.get(lvl, "  ")
            t.append(prefix, style=colors.get(lvl, CW))
            t.append(msg + "\n", style=colors.get(lvl, CW))
        return Panel(t, title=f"[bold {CW}]EVENT LOG[/]",
                     border_style="bright_black", box=box.ROUNDED, padding=(0, 1))

    # ── hotkeys bar ───────────────────────────────────────────────────────────

    @staticmethod
    def _hotkeys() -> Text:
        t = Text(justify="center")
        keys = [
            ("↑↓/1-9", "Select"), ("R", "Restart"), ("S", "Stop"), ("T", "Start"),
            ("A", "Start All"), ("X", "Stop All"), ("N", "Skip"),
            ("←→", "±10s"), ("⇧←→", "±60s"), ("G", "Goto"),
            ("D", "Detail"), ("V", "Log"), ("F", "Rescan"),
            ("P", "Port"), ("M", "Media Roots"), ("L", "Reload"), ("U", "Export"), ("H", "Help"), ("Q", "Quit"),
        ]
        for k, v in keys:
            t.append(f" [{k}]", style=f"bold {CC}")
            t.append(f" {v}", style=CD)
            t.append(" ·", style="dim bright_black")
        return t

    # ── render ────────────────────────────────────────────────────────────────

    def render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header",  size=3),
            Layout(name="streams", ratio=1),
            Layout(name="bottom",  size=13),
            Layout(name="keys",    size=3),
        )
        layout["header"].update(_header_panel())
        layout["streams"].update(Panel(
            self._streams_table(),
            title=(
                f"[bold {CW}]STREAMS[/]  "
                f"[dim]({len(self.manager.states)} configured)[/]"
            ),
            border_style=CC, box=box.ROUNDED, padding=(0, 0),
        ))
        layout["bottom"].split_row(
            Layout(self._system_panel(), name="sys", ratio=1),
            Layout(self._log_panel(),    name="log", ratio=3),
        )
        layout["keys"].update(Panel(
            Align.center(self._hotkeys(), vertical="middle"),
            border_style="bright_black", box=box.SIMPLE, padding=(0, 0),
        ))
        return layout


# =============================================================================
# KEYBOARD HANDLER
# =============================================================================
class KeyboardHandler:
    def __init__(self) -> None:
        self._q:       queue.Queue = queue.Queue()
        self._running: bool        = False

    def start(self) -> None:
        self._running = True
        threading.Thread(
            target=(self._win_loop if IS_WIN else self._unix_loop),
            daemon=True, name="keyboard",
        ).start()

    def stop(self) -> None:
        self._running = False

    def get(self) -> Optional[str]:
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def _win_loop(self) -> None:
        import msvcrt  # type: ignore
        while self._running:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):
                    ch2 = msvcrt.getch()
                    mapping = {
                        b"H": "UP",   b"P": "DOWN",
                        b"K": "LEFT", b"M": "RIGHT",
                        b"s": "SHIFTLEFT", b"t": "SHIFTRIGHT",
                        b"I": "PAGEUP", b"Q": "PAGEDOWN",
                    }
                    self._q.put(mapping.get(ch2, ""))
                else:
                    try:
                        self._q.put(ch.decode("utf-8").upper())
                    except Exception:
                        pass
            time.sleep(0.04)

    def _unix_loop(self) -> None:
        import tty
        import termios
        import select
        fd = sys.stdin.fileno()
        try:
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            while self._running:
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not r:
                    continue
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r2:
                        seq = sys.stdin.read(2)
                        if seq in ("[1", "[2"):
                            r3, _, _ = select.select([sys.stdin], [], [], 0.05)
                            if r3:
                                more = sys.stdin.read(4)
                                if "D" in more:   self._q.put("SHIFTLEFT")
                                elif "C" in more: self._q.put("SHIFTRIGHT")
                                continue
                        mapping = {
                            "[A": "UP",   "[B": "DOWN",
                            "[C": "RIGHT", "[D": "LEFT",
                            "[5": "PAGEUP", "[6": "PAGEDOWN",
                        }
                        self._q.put(mapping.get(seq, "ESC"))
                    else:
                        self._q.put("ESC")
                else:
                    self._q.put(ch.upper())
        except Exception:
            pass
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass


# =============================================================================
# TUI SEEK PROMPT
# =============================================================================
def do_seek_prompt(manager: StreamManager, state, console: Console) -> None:
    try:
        ts = Prompt.ask(
            f"\n[{CC}]Seek [{state.config.name}] to (HH:MM:SS or seconds)[/{CC}]",
            console=console, default="00:00:00",
        )
        parts = ts.strip().split(":")
        if len(parts) == 3:
            h, m, s = parts
            secs = int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            secs = int(m) * 60 + float(s)
        else:
            secs = float(parts[0])
        manager.seek_stream(state, max(0.0, secs))
    except Exception:
        pass


# =============================================================================
# PORT CHANGE PROMPT
# =============================================================================
def do_port_prompt(console: Console, glog: LogBuffer) -> None:
    """
    Prompt the operator for a new web port, update constants, and log the
    change.  The caller (main TUI loop) is responsible for restarting the
    WebServer if it needs to bind to the new port immediately.
    """
    try:
        current = get_web_port()
        raw = Prompt.ask(
            f"\n[{CC}]New web-UI port[/{CC}] [{CD}](current: {current})[/{CD}]",
            console=console,
            default=str(current),
        )
        new_port = int(raw.strip())
        if not (1 <= new_port <= 65535):
            console.print(f"[{CR}]  ✖ Port must be 1–65535. Unchanged.[/]")
            return
        if new_port == current:
            console.print(f"[{CD}]  Port unchanged ({current}).[/]")
            return
        set_web_port(new_port)
        glog.add(f"Web port changed {current} → {new_port}  (restart to rebind)")
        console.print(
            f"[{CG}]  ✔ Web port updated to {new_port}.[/]  "
            f"[{CD}]Restart HydraCast to rebind the server socket.[/]"
        )
    except (ValueError, TypeError):
        console.print(f"[{CR}]  ✖ Invalid port number. Unchanged.[/]")
    except Exception as exc:
        console.print(f"[{CR}]  ✖ Error: {exc}[/]")


# =============================================================================
# MEDIA ROOTS MANAGER PROMPT
# =============================================================================
def do_media_roots_prompt(console: Console, glog: LogBuffer) -> None:
    """
    Interactive TUI prompt to manage extra media root directories.
    Commands:
      list              — show current roots
      add <path>        — add an extra root
      remove <path>     — remove an extra root (default root cannot be removed)
      clear             — remove all extra roots (keeps default)
      done / q / enter  — exit prompt
    """
    from pathlib import Path
    from hc.constants import (
        MEDIA_DIR, get_media_roots, add_media_root,
        remove_media_root, set_media_roots,
    )

    def _print_roots() -> None:
        roots = get_media_roots()
        console.print(f"\n[bold {CW}]  Media root directories ({len(roots)} total):[/]")
        for i, r in enumerate(roots):
            tag  = f"[{CD}](default)[/]" if i == 0 else ""
            exists_style = CG if r.is_dir() else CR
            console.print(f"    [{CC}]{i + 1}.[/{CC}] [{exists_style}]{r}[/] {tag}")
        console.print()

    console.print(f"\n[bold {CC}]◈ Media Root Folder Manager[/]")
    console.print(f"[{CD}]  Commands: list · add <path> · remove <path> · clear · done[/]\n")
    _print_roots()

    while True:
        try:
            raw = Prompt.ask(
                f"[{CC}]media-roots[/{CC}]",
                console=console,
                default="done",
            ).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not raw or raw.lower() in ("done", "q", "quit", "exit"):
            console.print(f"[{CD}]  Exiting media roots manager.[/]\n")
            break

        parts = raw.split(None, 1)
        cmd   = parts[0].lower()
        arg   = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "list":
            _print_roots()

        elif cmd == "add":
            if not arg:
                console.print(f"[{CR}]  ✖ Usage: add <absolute-path>[/]")
                continue
            p = Path(arg)
            if not p.is_absolute():
                console.print(f"[{CR}]  ✖ Path must be absolute: {p}[/]")
                continue
            if not p.exists():
                console.print(f"[{CR}]  ✖ Path does not exist: {p}[/]")
                continue
            if not p.is_dir():
                console.print(f"[{CR}]  ✖ Path is not a directory: {p}[/]")
                continue
            added = add_media_root(p)
            if added:
                glog.add(f"[MediaRoots] Added extra root: {p}", "INFO")
                console.print(f"[{CG}]  ✔ Added: {p}[/]")
                _print_roots()
            else:
                console.print(
                    f"[{CY}]  ⚠ Already present (or is the default root): {p}[/]"
                )

        elif cmd == "remove":
            if not arg:
                console.print(f"[{CR}]  ✖ Usage: remove <absolute-path>[/]")
                continue
            p = Path(arg)
            try:
                default = MEDIA_DIR()
                if p.resolve() == default.resolve():
                    console.print(
                        f"[{CR}]  ✖ The default media root cannot be removed: {default}[/]"
                    )
                    continue
            except RuntimeError:
                pass
            removed = remove_media_root(p)
            if removed:
                glog.add(f"[MediaRoots] Removed extra root: {p}", "INFO")
                console.print(f"[{CG}]  ✔ Removed: {p}[/]")
                _print_roots()
            else:
                console.print(f"[{CY}]  ⚠ Not found in extra roots list: {p}[/]")

        elif cmd == "clear":
            confirmed = Confirm.ask(
                f"  [{CY}]Remove ALL extra roots (default root is kept)?[/{CY}]",
                console=console,
                default=False,
            )
            if confirmed:
                set_media_roots([])
                glog.add("[MediaRoots] All extra roots cleared.", "INFO")
                console.print(f"[{CG}]  ✔ Extra roots cleared.[/]")
                _print_roots()
            else:
                console.print(f"[{CD}]  Cancelled.[/]")

        else:
            console.print(
                f"[{CR}]  ✖ Unknown command '{cmd}'.[/] "
                f"[{CD}]Use: list · add <path> · remove <path> · clear · done[/]"
            )



def _show_detail(live: Live, state, console: Console) -> None:
    if state is None:
        return
    live.stop()
    console.clear()
    cfg = state.config
    st  = state

    # ── left column: config ──────────────────────────────────────────────────
    left = Text()
    left.append("CONFIGURATION\n", style=f"bold {CW}")
    left.append("─" * 32 + "\n", style="dim bright_black")

    def _kv(k: str, v: str, vc: str = CW) -> None:
        left.append(f"  {k:<18}", style=CD)
        left.append(f"{v}\n",     style=vc)

    _kv("Name",        cfg.name,               CW)
    _kv("RTSP Port",   str(cfg.port),           CC)
    _kv("Stream Path", f"/{cfg.rtsp_path}",     CC)
    _kv("RTSP URL",    cfg.rtsp_url,            "dim cyan")
    _kv("External URL",cfg.rtsp_url_external,   "dim cyan")
    if cfg.hls_enabled:
        _kv("HLS URL", cfg.hls_url,             "dim cyan")
    left.append("\n")
    _kv("Schedule",    cfg.weekdays_display(),   CW)
    _kv("Shuffle",     "yes" if cfg.shuffle else "no")
    _kv("HLS",         "enabled" if cfg.hls_enabled else "off",
        CG if cfg.hls_enabled else CD)
    left.append("\n")
    _kv("Bitrate",     f"V:{cfg.video_bitrate}  A:{cfg.audio_bitrate}")
    if cfg.compliance_enabled:
        _kv("Compliance",  f"ON  start {cfg.compliance_start}", CY)
        _kv("Comp. Loop",  "yes" if cfg.compliance_loop else "no")
    if cfg.folder_source:
        _kv("Folder",  str(cfg.folder_source), CD)

    # ── right column: live state ──────────────────────────────────────────────
    right = Text()
    right.append("LIVE STATE\n", style=f"bold {CW}")
    right.append("─" * 32 + "\n", style="dim bright_black")

    dot_style, lbl_style = _STATUS_STYLE.get(st.status, ("white", "white"))
    right.append(f"  {st.status.dot} ", style=dot_style)
    right.append(f"{st.status.label}\n\n", style=f"bold {lbl_style}")

    def _rv(k: str, v: str, vc: str = CW) -> None:
        right.append(f"  {k:<18}", style=CD)
        right.append(f"{v}\n",     style=vc)

    _rv("Position",    st.format_pos())
    _rv("Progress",    f"{st.progress:.1f}%")
    rem = st.time_remaining()
    if rem > 0:
        r = int(rem)
        _rv("Remaining", f"−{r//3600:02d}:{(r%3600)//60:02d}:{r%60:02d}", CY)
    _rv("FPS",         f"{st.fps:.1f}" if st.fps > 0 else "—")
    _rv("Bitrate",     st.bitrate)
    _rv("Speed",       st.speed)
    _rv("Loop count",  str(st.loop_count))
    _rv("Restarts",    str(st.restart_count),
        CR if st.restart_count > 3 else CW)
    if st.started_at:
        _rv("Running since", st.started_at.strftime("%H:%M:%S"))
    current = st.current_file()
    if current:
        right.append("\n")
        right.append(f"  Now playing:\n", style=CD)
        right.append(f"  {current.name}\n", style=CW)
        right.append(f"  {current.parent}\n", style=CD)
    if st.error_msg:
        right.append("\n")
        right.append("  ERROR:\n", style=f"bold {CR}")
        right.append(f"  {st.error_msg[:200]}\n", style=CR)
    if st.compliance_alert:
        right.append("\n")
        right.append("  ⚠ COMPLIANCE ALERT:\n", style=f"bold {CY}")
        right.append(f"  {st.compliance_alert}\n", style=CY)

    # ── playlist section ──────────────────────────────────────────────────────
    playlist_text = Text()
    playlist_text.append(f"\nPLAYLIST  ({len(cfg.playlist)} files)\n",
                          style=f"bold {CW}")
    playlist_text.append("─" * 64 + "\n", style="dim bright_black")
    for idx, item in enumerate(cfg.sorted_playlist()[:20]):
        marker = "▶ " if idx == st.playlist_index else "  "
        pri    = f"[p{item.priority}]" if item.priority != 999 else ""
        playlist_text.append(
            f"  {marker}{idx+1:>3}.  {item.file_path.name}  "
            f"{pri}  @{item.start_position}\n",
            style=CW if idx == st.playlist_index else CD,
        )
    if len(cfg.playlist) > 20:
        playlist_text.append(f"  … and {len(cfg.playlist)-20} more\n", style=CD)

    # ── layout ────────────────────────────────────────────────────────────────
    cols = Table.grid(expand=True)
    cols.add_column(ratio=1)
    cols.add_column(ratio=1)
    cols.add_row(left, right)

    body = Text()
    body.append_text(Text.assemble(cols))    # grid renders inline
    # Fall back: just print the two panels side-by-side
    console.print(Panel(
        left,
        title=f"[bold {CW}]◈ {cfg.name}  —  Configuration[/]",
        border_style=CC, box=box.ROUNDED, padding=(1, 2),
    ))
    console.print(Panel(
        right,
        title=f"[bold {CW}]◈ {cfg.name}  —  Live State[/]",
        border_style=CG if st.status == StreamStatus.LIVE else "bright_black",
        box=box.ROUNDED, padding=(1, 2),
    ))
    console.print(Panel(
        playlist_text,
        title=f"[bold {CW}]◈ {cfg.name}  —  Playlist[/]",
        border_style="bright_black", box=box.ROUNDED, padding=(0, 1),
    ))
    console.print(f"\n[{CD}]  Press any key to return …[/]")


# =============================================================================
# LOG VIEWER OVERLAY
# =============================================================================
def _show_log_viewer(
    live: Live, state, console: Console,
    kb: KeyboardHandler, shutdown_event: threading.Event,
) -> None:
    if state is None:
        return
    live.stop()
    console.clear()
    scroll = 0
    page   = 30

    while not shutdown_event.is_set():
        console.clear()
        entries = list(state.log_buffer.last(200)) if hasattr(state, "log_buffer") else list(state.log)
        visible = entries[scroll: scroll + page]
        colors  = {"INFO": CW, "WARN": CY, "ERROR": CR}
        t = Text()
        for entry in visible:
            if isinstance(entry, tuple):
                msg, lvl = entry
            else:
                msg, lvl = str(entry), "INFO"
            t.append(msg + "\n", style=colors.get(lvl, CW))
        console.print(Panel(
            t,
            title=(
                f"[bold {CW}]LOG — {state.config.name}[/]  "
                f"[{CD}](lines {scroll+1}–"
                f"{min(scroll+page, len(entries))} of {len(entries)})[/]"
            ),
            border_style=CC, box=box.ROUNDED, padding=(0, 1),
        ))
        console.print(f"[{CD}]  ↑↓ scroll  ·  any other key returns[/]")

        key = None
        for _ in range(20):
            key = kb.get()
            if key:
                break
            time.sleep(0.05)

        if key == "UP":
            scroll = max(0, scroll - 1)
        elif key == "DOWN":
            scroll = min(max(0, len(entries) - page), scroll + 1)
        elif key is not None:
            break

    console.clear()
    live.start()


# =============================================================================
# HELP OVERLAY
# =============================================================================
def _show_help(live: Live, console: Console, kb: KeyboardHandler, shutdown_event: threading.Event) -> None:
    live.stop()
    console.clear()
    rows = [
        ("↑ / ↓",          "Move selection up / down"),
        ("1 – 9",           "Jump directly to stream #N"),
        ("PgUp / PgDn",     "Scroll 5 streams at a time"),
        ("R",               "Restart selected stream  [confirmation]"),
        ("S",               "Stop selected stream"),
        ("T",               "Start selected stream"),
        ("A",               "Start ALL streams"),
        ("X",               "Stop ALL streams  [confirmation]"),
        ("N",               "Skip to next file in playlist"),
        ("← / →",          "Seek ±10 seconds"),
        ("Shift ← / →",    "Seek ±60 seconds"),
        ("G",               "Go-to-time prompt (seek)"),
        ("F",               "Force folder rescan"),
        ("C",               "Clear error state / reset restart count"),
        ("D",               "Stream detail overlay (config + live state)"),
        ("V",               "Per-stream log viewer"),
        ("P",               "Change web-UI port (live, no restart needed for TUI)"),
        ("M",               "Manage media root folders (add / remove / list)"),
        ("L",               "Reload streams.hcf from disk"),
        ("U",               "Export stream URLs to file"),
        ("H / ?",           "This help screen"),
        ("Q / Ctrl-C",      "Quit HydraCast"),
    ]
    t = Table(box=box.ROUNDED, border_style="bright_black",
              header_style=f"bold {CW}", show_header=True)
    t.add_column("Key",    style=f"bold {CC}", width=20)
    t.add_column("Action", style=CW)
    for k, v in rows:
        t.add_row(k, v)
    console.print(Panel(
        Align.center(t, vertical="middle"),
        title=f"[bold {CW}]◈ KEYBOARD HELP[/]",
        border_style=CC, box=box.ROUNDED,
    ))
    console.print(f"\n[{CD}]  Press any key to return …[/]")

    def _wait_key() -> None:
        while kb.get():
            pass
        while not shutdown_event.is_set():
            if kb.get() is not None:
                return
            time.sleep(0.05)

    _wait_key()
    console.clear()
    live.start()


# =============================================================================
# MAIN TUI LOOP
# =============================================================================
def run_tui_loop(
    *,
    manager: StreamManager,
    glog: LogBuffer,
    console: Console,
    shutdown_event: threading.Event,
    export_urls_fn,
) -> None:
    """
    Blocking TUI main loop.

    Renders the Rich dashboard at ~4 fps and dispatches every keystroke to
    the appropriate StreamManager action.  Returns when shutdown_event is set
    (Q key, Ctrl-C, or external SIGTERM).

    Parameters
    ----------
    manager         : StreamManager instance controlling all streams.
    glog            : Global LogBuffer for status messages.
    console         : Rich Console (force_terminal=True).
    shutdown_event  : threading.Event — loop exits when this is set.
    export_urls_fn  : Callable that writes stream_urls.txt and returns the path.
    """
    tui = TUI(manager, glog)
    kb  = KeyboardHandler()
    kb.start()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _selected_state():
        states = manager.states
        if not states:
            return None
        return states[min(tui.selected, len(states) - 1)]

    def _clamp():
        n = len(manager.states)
        if n:
            tui.selected = max(0, min(tui.selected, n - 1))

    def _wait_key() -> None:
        """Drain queue then block until the next keypress."""
        while kb.get():
            pass
        while not shutdown_event.is_set():
            if kb.get() is not None:
                return
            time.sleep(0.05)

    def _confirm(live: Live, question: str) -> bool:
        """Pause live, ask yes/no, resume. Returns True if confirmed."""
        live.stop()
        console.clear()
        console.print(f"\n[bold {CY}]  ⚠  {question}[/]")
        console.print(f"[{CD}]  [Y] Yes   [N] No / any other key — cancel\n[/]")
        while not shutdown_event.is_set():
            k = kb.get()
            if k == "Y":
                console.clear()
                live.start()
                return True
            if k is not None:
                console.clear()
                live.start()
                return False
            time.sleep(0.05)
        live.start()
        return False

    def _seek(state, delta: float) -> None:
        current = getattr(state, "seek_start_pos", 0.0) or 0.0
        manager.seek_stream(state, max(0.0, current + delta))

    # ── main render loop ──────────────────────────────────────────────────────
    with Live(
        console=console,
        refresh_per_second=4,
        screen=True,
        transient=False,
    ) as live:
        while not shutdown_event.is_set():
            _clamp()
            live.update(tui.render())

            key = kb.get()
            if key is None:
                time.sleep(0.05)
                continue

            state = _selected_state()
            n     = len(manager.states)

            # ── navigation ───────────────────────────────────────────────────
            if key == "UP":
                tui.selected = (tui.selected - 1) % max(1, n)
            elif key == "DOWN":
                tui.selected = (tui.selected + 1) % max(1, n)
            elif key == "PAGEUP":
                tui.selected = max(0, tui.selected - 5)
            elif key == "PAGEDOWN":
                tui.selected = min(max(0, n - 1), tui.selected + 5)
            elif key.isdigit() and key != "0":
                idx = int(key) - 1
                if 0 <= idx < n:
                    tui.selected = idx

            # ── stream control  (destructive actions get confirmation) ────────
            elif key == "R" and state:
                if _confirm(live, f"Restart stream  [{state.config.name}]?"):
                    manager.restart_stream(state)
                    glog.add(f"Restart → {state.config.name}")
            elif key == "S" and state:
                manager.stop_stream(state)
                glog.add(f"Stop → {state.config.name}")
            elif key == "T" and state:
                manager.start_stream(state)
                glog.add(f"Start → {state.config.name}")
            elif key == "A":
                manager.start_all()
                glog.add("Start ALL streams")
            elif key == "X":
                if _confirm(live, "Stop ALL streams?"):
                    manager.stop_all()
                    glog.add("Stop ALL streams")
            elif key == "N" and state:
                manager.skip_next(state)
                glog.add(f"Skip next → {state.config.name}")

            # ── seeking ───────────────────────────────────────────────────────
            elif key == "LEFT"  and state:
                _seek(state, -10.0)
            elif key == "RIGHT" and state:
                _seek(state, +10.0)
            elif key == "SHIFTLEFT"  and state:
                _seek(state, -60.0)
            elif key == "SHIFTRIGHT" and state:
                _seek(state, +60.0)
            elif key == "G" and state:
                live.stop()
                do_seek_prompt(manager, state, console)
                live.start()

            # ── folder / error management ─────────────────────────────────────
            elif key == "F" and state:
                try:
                    manager.rescan_folder(state)
                    glog.add(f"Folder rescan → {state.config.name}")
                except AttributeError:
                    glog.add("rescan_folder not available on this manager", "WARN")
            elif key == "C" and state:
                try:
                    manager.clear_error(state)
                    glog.add(f"Error cleared → {state.config.name}")
                except AttributeError:
                    glog.add("clear_error not available on this manager", "WARN")

            # ── port change ───────────────────────────────────────────────────
            elif key == "P":
                live.stop()
                console.clear()
                do_port_prompt(console, glog)
                _wait_key()
                console.clear()
                live.start()

            elif key == "M":
                live.stop()
                console.clear()
                do_media_roots_prompt(console, glog)
                # Invalidate library cache so next Web UI poll reflects new roots
                try:
                    from hc.web_handler import _invalidate_lib_cache
                    _invalidate_lib_cache()
                except Exception:
                    pass
                _wait_key()
                console.clear()
                live.start()

            # ── overlays ──────────────────────────────────────────────────────
            elif key in ("H", "?"):
                _show_help(live, console, kb, shutdown_event)
            elif key == "D":
                if state:
                    _show_detail(live, state, console)
                    _wait_key()
                    console.clear()
                    live.start()
            elif key == "V":
                _show_log_viewer(live, state, console, kb, shutdown_event)

            # ── misc ──────────────────────────────────────────────────────────
            elif key == "L":
                try:
                    manager.reload_csv()
                    glog.add("streams.hcf reloaded")
                except AttributeError:
                    glog.add("reload_csv not available on this manager", "WARN")
            elif key == "U":
                try:
                    url_file = export_urls_fn()
                    glog.add(f"URLs exported → {url_file.name}")
                except Exception as exc:
                    glog.add(f"URL export error: {exc}", "ERROR")

            # ── quit ─────────────────────────────────────────────────────────
            elif key in ("Q", "\x03", "\x1c"):   # Q, Ctrl-C, Ctrl-backslash
                shutdown_event.set()

    kb.stop()
