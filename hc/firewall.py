"""
hc/firewall.py  —  Cross-platform firewall port-opening helpers.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import List, Optional

from hc.constants import IS_LINUX, IS_MAC, IS_WIN, NO_FIREWALL, CD, CG, CY


class FirewallManager:
    _linux_tool: Optional[str] = None

    @classmethod
    def open_ports(cls, ports: List[int], console: object) -> None:
        from rich.console import Console as RC
        con: RC = console  # type: ignore[assignment]
        if NO_FIREWALL():
            con.print(f"[{CD}]ℹ  Firewall config skipped (--no-firewall).[/]")
            return
        if IS_WIN:
            cls._windows(ports, con)
        elif IS_LINUX:
            cls._linux(ports, con)
        elif IS_MAC:
            con.print(
                f"[{CY}]⚠  macOS: manually allow TCP "
                f"{', '.join(map(str, ports))} in Firewall settings.[/]"
            )

    # ── Windows ───────────────────────────────────────────────────────────────
    @classmethod
    def _windows(cls, ports: List[int], con: object) -> None:
        from rich.console import Console as RC
        _con: RC = con  # type: ignore[assignment]
        if not cls._is_admin_win():
            _con.print(
                f"[{CY}]⚠  Not Administrator — manually open TCP "
                f"{', '.join(map(str, ports))}[/]"
            )
            return
        opened = []
        for port in ports:
            rule = f"HydraCast RTSP {port}"
            exists = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule}"],
                capture_output=True, text=True,
            )
            if "No rules match" not in exists.stdout and exists.returncode == 0:
                continue
            r = subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name={rule}", "dir=in", "action=allow",
                 "protocol=TCP", f"localport={port}"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                opened.append(port)
        if opened:
            _con.print(
                f"[{CG}]✔  Firewall (netsh): opened TCP "
                f"{', '.join(map(str, opened))}[/]"
            )

    @staticmethod
    def _is_admin_win() -> bool:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:
            return False

    # ── Linux ────────────────────────────────────────────────────────────────
    @classmethod
    def _linux(cls, ports: List[int], con: object) -> None:
        from rich.console import Console as RC
        _con: RC = con  # type: ignore[assignment]
        if os.geteuid() != 0:
            _con.print(f"[{CY}]⚠  Not root — run: sudo ufw allow <port>/tcp[/]")
            return
        tool = cls._detect_linux_tool()
        if tool == "ufw":           cls._ufw(ports, _con)
        elif tool == "firewalld":   cls._firewalld(ports, _con)
        elif tool == "iptables":    cls._iptables(ports, _con)

    @classmethod
    def _detect_linux_tool(cls) -> Optional[str]:
        if cls._linux_tool:
            return cls._linux_tool
        for binary, key in [
            ("ufw", "ufw"), ("firewall-cmd", "firewalld"), ("iptables", "iptables")
        ]:
            if shutil.which(binary):
                cls._linux_tool = key
                return key
        return None

    @classmethod
    def _ufw(cls, ports: List[int], con: object) -> None:
        from rich.console import Console as RC
        _con: RC = con  # type: ignore[assignment]
        opened = []
        for port in ports:
            r = subprocess.run(
                ["ufw", "allow", f"{port}/tcp"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                opened.append(port)
        if opened:
            _con.print(
                f"[{CG}]✔  Firewall (ufw): allowed TCP "
                f"{', '.join(map(str, opened))}[/]"
            )

    @classmethod
    def _firewalld(cls, ports: List[int], con: object) -> None:
        from rich.console import Console as RC
        _con: RC = con  # type: ignore[assignment]
        for port in ports:
            subprocess.run(
                ["firewall-cmd", "--permanent", "--add-port", f"{port}/tcp"],
                capture_output=True,
            )
        subprocess.run(["firewall-cmd", "--reload"], capture_output=True)
        _con.print(
            f"[{CG}]✔  Firewall (firewalld): added TCP "
            f"{', '.join(map(str, ports))}[/]"
        )

    @classmethod
    def _iptables(cls, ports: List[int], con: object) -> None:
        from rich.console import Console as RC
        _con: RC = con  # type: ignore[assignment]
        opened = []
        for port in ports:
            already = subprocess.run(
                ["iptables", "-C", "INPUT", "-p", "tcp",
                 "--dport", str(port), "-j", "ACCEPT"],
                capture_output=True,
            )
            if already.returncode == 0:
                continue
            r = subprocess.run(
                ["iptables", "-I", "INPUT", "-p", "tcp",
                 "--dport", str(port), "-j", "ACCEPT"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                opened.append(port)
        if opened:
            _con.print(
                f"[{CG}]✔  Firewall (iptables): opened TCP "
                f"{', '.join(map(str, opened))}[/]"
            )
