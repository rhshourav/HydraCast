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
                        b"H": "UP", b"P": "DOWN",
                        b"K": "LEFT", b"M": "RIGHT",
                        b"s": "SHIFTLEFT", b"t": "SHIFTRIGHT",
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
                            "[A": "UP", "[B": "DOWN",
                            "[C": "RIGHT", "[D": "LEFT",
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
