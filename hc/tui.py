"""
hc/tui.py  —  Terminal UI, keyboard handler, and TUI seek prompt.
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
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from hc.constants import (
    APP_VER, APP_AUTHOR, CC, CD, CG, CM, CR, CW, CY,
    CPU_COUNT, IS_WIN, get_web_port,
)
from hc.manager import StreamManager
from hc.models import StreamStatus
from hc.utils import _local_ip
from hc.worker import LogBuffer

BANNER_TEXT = """\
[bright_cyan]  ██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗  ██████╗ █████╗ ███████╗████████╗[/]
[bright_cyan]  ██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔════╝╚══██╔══╝[/]
[bright_cyan]  ███████║ ╚████╔╝ ██║  ██║██████╔╝███████║██║     ███████║███████╗   ██║   [/]
[cyan]  ██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║██║     ██╔══██║╚════██║   ██║   [/]
[cyan]  ██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║╚██████╗██║  ██║███████║   ██║   [/]
[dim cyan]  ╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   [/]"""


# =============================================================================
# TUI
# =============================================================================
class TUI:
    def __init__(self, manager: StreamManager, glog: LogBuffer) -> None:
        self.manager  = manager
        self.glog     = glog
        self.selected = 0

    @staticmethod
    def _progress_bar(pct: float, width: int = 22) -> Text:
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
            t.append("█", style=CG if frac < .55 else (CY if frac < .80 else CM))
        t.append("░" * empty, style="dim white")
        lc = CM if pct >= 80 else (CY if pct >= 55 else CG)
        t.append(f"  {pct:5.1f}%", style=f"bold {lc}")
        return t

    @staticmethod
    def _fmt_remaining(state) -> str:
        """Return '−HH:MM:SS' remaining label or empty string."""
        rem = state.time_remaining()
        if rem <= 0:
            return ""
        r = int(rem)
        return f"−{r//3600:02d}:{(r%3600)//60:02d}:{r%60:02d}"

    def _streams_table(self) -> Table:
        tbl = Table(
            box=box.SIMPLE_HEAD, border_style="bright_black",
            header_style=f"bold {CW}", expand=True, padding=(0, 1),
            show_edge=True,
        )
        tbl.add_column("#",        style=CD,  width=3,      no_wrap=True)
        tbl.add_column("STREAM",   style=CW,  min_width=14, no_wrap=True)
        tbl.add_column("PORT",     style=CC,  width=6,      no_wrap=True)
        tbl.add_column("FILES",    style=CD,  width=7,      no_wrap=True)
        tbl.add_column("SCHEDULE", style=CW,  width=11,     no_wrap=True)
        tbl.add_column("STATUS",              width=11,     no_wrap=True)
        tbl.add_column("PROGRESS",            min_width=30, no_wrap=True)
        tbl.add_column("POSITION", style=CD,  width=16,     no_wrap=True)
        tbl.add_column("REMAINS",  style=CD,  width=11,     no_wrap=True)
        tbl.add_column("FPS",      style=CD,  width=5,      no_wrap=True)
        tbl.add_column("LOOP",     style=CD,  width=6,      no_wrap=True)
        tbl.add_column("RTSP URL", style="dim cyan", min_width=22, no_wrap=True)

        for i, st in enumerate(self.manager.states):
            cfg = st.config
            s   = st.status
            stat_t = Text()
            if s == StreamStatus.ERROR and st.error_msg:
                stat_t.append(" ● ", style=CR)
                stat_t.append("ERROR", style=f"bold {CR}")
            else:
                stat_t.append(f" {s.dot} ", style=s.color)
                stat_t.append(s.label, style=f"bold {s.color}")

            row_style    = "on grey11" if i == self.selected else ""
            name_display = f"▶ {cfg.name}" if i == self.selected else f"  {cfg.name}"
            if cfg.shuffle:     name_display += " ⧖"
            if cfg.hls_enabled: name_display += " [H]"
            n_files = len(cfg.playlist)

            remaining = self._fmt_remaining(st)
            rem_text  = Text(remaining, style=f"bold {CY}") if remaining else Text("—", style=CD)

            tbl.add_row(
                str(i + 1), name_display, str(cfg.port),
                f"×{n_files}" if n_files > 1 else "1",
                cfg.weekdays_display(), stat_t,
                self._progress_bar(st.progress),
                st.format_pos(),
                rem_text,
                f"{st.fps:.0f}" if st.fps > 0 else "—",
                f"×{st.loop_count}" if st.loop_count > 0 else "—",
                cfg.rtsp_url,
                style=row_style,
            )
        return tbl

    def _system_panel(self) -> Panel:
        cpu    = psutil.cpu_percent(interval=None)
        mem    = psutil.virtual_memory()
        live_n  = sum(1 for s in self.manager.states if s.status == StreamStatus.LIVE)
        err_n   = sum(1 for s in self.manager.states if s.status == StreamStatus.ERROR)
        sched_n = sum(1 for s in self.manager.states if s.status == StreamStatus.SCHEDULED)
        pending = sum(1 for e in self.manager.events if not e.played)
        t = Text()
        t.append("CPU  ", style=CD); t.append_text(self._progress_bar(cpu,    14)); t.append("\n")
        t.append("MEM  ", style=CD); t.append_text(self._progress_bar(mem.percent, 14)); t.append("\n\n")
        t.append("Cores  ",  style=CD); t.append(str(CPU_COUNT), style=CC)
        t.append("  |  Streams  ", style=CD); t.append(str(len(self.manager.states)), style=CW); t.append("\n")
        t.append("LIVE   ", style=CD); t.append(str(live_n), style=CG)
        t.append("   SCHED  ", style=CD); t.append(str(sched_n), style=CC)
        t.append("   ERR  ", style=CD); t.append(str(err_n), style=(CR if err_n else CD)); t.append("\n")
        t.append("Events ", style=CD); t.append(str(pending), style=CM); t.append(" pending\n\n")
        t.append(f"  LAN: {_local_ip()}", style=CD); t.append("\n")
        t.append(f"  Web: http://{_local_ip()}:{get_web_port()}", style="dim cyan"); t.append("\n")
        t.append(datetime.now().strftime("  %a  %Y-%m-%d  %H:%M:%S"), style=CD)
        return Panel(t, title=f"[bold {CW}]SYSTEM[/]",
                     border_style="bright_black", box=box.ROUNDED, padding=(0, 1))

    def _log_panel(self) -> Panel:
        entries = self.glog.last(9)
        t = Text()
        colors = {"INFO": CW, "WARN": CY, "ERROR": CR}
        for msg, lvl in entries:
            t.append(msg + "\n", style=colors.get(lvl, CW))
        return Panel(t, title=f"[bold {CW}]EVENT LOG[/]",
                     border_style="bright_black", box=box.ROUNDED, padding=(0, 1))

    @staticmethod
    def _hotkeys() -> Text:
        t = Text(justify="center")
        for k, v in [
            ("↑↓/1-9", "Select"), ("R", "Restart"), ("S", "Stop"), ("T", "Start"),
            ("A", "All Start"), ("X", "All Stop"), ("N", "Skip Next"),
            ("←→", "±10s"), ("Shift←→", "±60s"),
            ("G", "Goto time"), ("L", "Reload CSV"), ("U", "Export URLs"), ("Q", "Quit"),
        ]:
            t.append(f" [{k}]", style=f"bold {CC}")
            t.append(f" {v} ",  style=CD)
        return t

    def render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="banner",  size=8),
            Layout(name="streams", ratio=1),
            Layout(name="bottom",  size=14),
            Layout(name="keys",    size=3),
        )
        banner_txt = Text.from_markup(BANNER_TEXT)
        sub = Text(
            f"  Multi-Stream RTSP Scheduler  ·  v{APP_VER}  ·  {APP_AUTHOR}  ·  "
            f"Web UI → http://{_local_ip()}:{get_web_port()}",
            style="dim white", justify="center",
        )
        bf = Text()
        bf.append_text(banner_txt)
        bf.append("\n")
        bf.append_text(sub)
        layout["banner"].update(Align.center(bf, vertical="middle"))
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
def do_seek_prompt(
    manager: StreamManager, state, console: Console
) -> None:
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

    # ── overlay: help ─────────────────────────────────────────────────────────
    def _show_help(live: Live) -> None:
        live.stop()
        console.clear()
        rows = [
            ("↑ / ↓",       "Move selection up / down"),
            ("1 – 9",        "Jump directly to stream #N"),
            ("PgUp / PgDn",  "Scroll 5 streams at a time"),
            ("R",            "Restart selected stream"),
            ("S",            "Stop selected stream"),
            ("T",            "Start selected stream"),
            ("A",            "Start ALL streams"),
            ("X",            "Stop ALL streams"),
            ("N",            "Skip to next scheduled event"),
            ("← / →",       "Seek ±10 seconds"),
            ("Shift ← / →", "Seek ±60 seconds"),
            ("G",            "Go-to-time prompt (seek)"),
            ("F",            "Force folder rescan"),
            ("C",            "Clear error state / reset restart count"),
            ("D",            "Stream detail overlay"),
            ("V",            "Per-stream log viewer"),
            ("L",            "Reload streams.csv"),
            ("U",            "Export stream URLs to file"),
            ("H / ?",        "This help screen"),
            ("Q / Ctrl-C",   "Quit HydraCast"),
        ]
        t = Table(box=box.ROUNDED, border_style="bright_black",
                  header_style=f"bold {CW}", show_header=True)
        t.add_column("Key",    style=f"bold {CC}", width=18)
        t.add_column("Action", style=CW)
        for k, v in rows:
            t.add_row(k, v)
        console.print(Panel(
            Align.center(t, vertical="middle"),
            title=f"[bold {CW}]KEYBOARD HELP[/]",
            border_style=CC, box=box.ROUNDED,
        ))
        console.print(f"\n[{CD}]  Press any key to return …[/]")
        _wait_key()
        console.clear()
        live.start()

    # ── overlay: stream detail ────────────────────────────────────────────────
    def _show_detail(live: Live, state) -> None:
        if state is None:
            return
        live.stop()
        console.clear()
        cfg = state.config
        t = Text()
        t.append(f"Name      : {cfg.name}\n",    style=CW)
        t.append(f"Port      : {cfg.port}\n",    style=CC)
        t.append(f"RTSP URL  : {cfg.rtsp_url}\n", style="dim cyan")
        if cfg.hls_enabled:
            t.append(f"HLS port  : {cfg.hls_port}\n", style=CC)
        t.append(f"Schedule  : {cfg.weekdays_display()}\n", style=CW)
        t.append(f"Shuffle   : {'yes' if cfg.shuffle else 'no'}\n", style=CW)
        t.append(f"Loop      : {'yes' if cfg.loop else 'no'}\n",    style=CW)
        t.append(f"Files ({len(cfg.playlist)}):\n", style=CD)
        for p in cfg.playlist:
            t.append(f"  {p}\n", style="dim white")
        console.print(Panel(
            t,
            title=f"[bold {CW}]DETAIL — {cfg.name}[/]",
            border_style=CC, box=box.ROUNDED, padding=(1, 2),
        ))
        console.print(f"\n[{CD}]  Press any key to return …[/]")
        _wait_key()
        console.clear()
        live.start()

    # ── overlay: per-stream log viewer ────────────────────────────────────────
    def _show_log_viewer(live: Live, state) -> None:
        if state is None:
            return
        live.stop()
        console.clear()
        scroll = 0
        page   = 30

        while not shutdown_event.is_set():
            console.clear()
            # StreamState exposes its own LogBuffer as .log_buffer
            entries = list(state.log_buffer.last(200))
            visible = entries[scroll: scroll + page]
            colors  = {"INFO": CW, "WARN": CY, "ERROR": CR}
            t = Text()
            for msg, lvl in visible:
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
            for _ in range(20):          # poll ~1 s
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

    # ── seek helper ───────────────────────────────────────────────────────────
    def _seek(state, delta: float) -> None:
        # seek_start_pos tracks current playback position (set by worker)
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

            # navigation
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

            # stream control
            elif key == "R" and state:
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
                manager.stop_all()
                glog.add("Stop ALL streams")
            elif key == "N" and state:
                manager.skip_next(state)
                glog.add(f"Skip next → {state.config.name}")

            # seeking
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

            # folder / error management
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

            # overlays
            elif key in ("H", "?"):
                _show_help(live)
            elif key == "D":
                _show_detail(live, state)
            elif key == "V":
                _show_log_viewer(live, state)

            # misc
            elif key == "L":
                try:
                    manager.reload_csv()
                    glog.add("streams.csv reloaded")
                except AttributeError:
                    glog.add("reload_csv not available on this manager", "WARN")
            elif key == "U":
                try:
                    url_file = export_urls_fn()
                    glog.add(f"URLs exported → {url_file.name}")
                except Exception as exc:
                    glog.add(f"URL export error: {exc}", "ERROR")

            # quit
            elif key in ("Q", "\x03", "\x1c"):   # Q, Ctrl-C, Ctrl-backslash
                shutdown_event.set()

    kb.stop()
