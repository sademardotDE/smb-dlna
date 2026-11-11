#!/usr/bin/env python3
"""Hermes-Plugin: Samba (smb + nmb) und MiniDLNA steuern.

Bietet Status, Start/Stopp und Autostart (``systemctl enable/disable``) für die
systemd-Units ``smb.service``, ``nmb.service`` und ``minidlna.service`` — als
Agent-Tools (``services_*``), CLI (``hermes services …``), Dashboard-Tab und
Desktop-Seite.

Für start/stop/enable/disable wird ``sudo`` verwendet; Statusabfragen laufen
ohne sudo. Fehlen Units oder ist kein systemd vorhanden, liefern die Methoden
einen Fehler statt einer Exception.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

TIMEOUT_SECONDS = 15


class Smb_dlna_Plugin:
    """Steuert smb, nmb und minidlna systemd Dienste."""

    name = "smb-dlna"
    version = "1.1.0"
    description = "Samba (smb/nmb) und MiniDLNA: Status, Start/Stopp, Autostart"

    SMB_UNIT = "smb.service"
    NMBD_UNIT = "nmb.service"
    DLNA_UNIT = "minidlna.service"

    #: logische Dienste -> systemd-Units (smb inkl. nmb)
    SERVICES: dict[str, tuple[str, ...]] = {
        "smb": ("smb.service", "nmb.service"),
        "dlna": ("minidlna.service",),
    }
    ALL_UNITS: tuple[str, ...] = ("smb.service", "nmb.service", "minidlna.service")

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path) if config_path else None

    # ------------------------------------------------------------- Grundlagen
    def _run(self, *args: str) -> tuple[int, str, str]:
        """Führt einen Befehl aus: ``(returncode, stdout, stderr)``."""
        try:
            res = subprocess.run(list(args), capture_output=True, text=True,
                                 timeout=TIMEOUT_SECONDS)
            return res.returncode, (res.stdout or "").strip(), (res.stderr or "").strip()
        except FileNotFoundError:
            return 127, "", f"Befehl nicht gefunden: {args[0]}"
        except subprocess.TimeoutExpired:
            return 124, "", f"Timeout nach {TIMEOUT_SECONDS}s: {' '.join(args)}"

    def _systemctl(self, action: str, unit: str, *, sudo: bool = False) -> tuple[bool, str]:
        cmd = (["sudo", "systemctl", action, unit] if sudo
               else ["systemctl", action, unit])
        code, out, err = self._run(*cmd)
        return code == 0, out or err or f"systemctl {action} {unit}"

    def _is_active(self, unit: str) -> bool:
        code, _, _ = self._run("systemctl", "is-active", unit)
        return code == 0

    def _is_enabled(self, unit: str) -> bool:
        code, _, _ = self._run("systemctl", "is-enabled", unit)
        return code == 0

    def _select(self, service: str) -> list[str]:
        name = (service or "all").strip().lower()
        if name in ("all", "*", ""):
            return list(self.SERVICES)
        if name not in self.SERVICES:
            raise ValueError(f"Unbekannter Dienst {service!r}; erwartet: all, "
                             f"{', '.join(self.SERVICES)}")
        return [name]

    def _unit_status(self, unit: str) -> dict[str, Any]:
        return {"unit": unit, "active": self._is_active(unit),
                "enabled": self._is_enabled(unit)}

    # ---------------------------------------------------------------- Status
    def status(self) -> dict[str, Any]:
        """Status aller Units und logischen Dienste."""
        units = {unit: self._unit_status(unit) for unit in self.ALL_UNITS}
        services: dict[str, Any] = {}
        for name, unit_names in self.SERVICES.items():
            services[name] = {
                "units": {unit: units[unit] for unit in unit_names},
                "active": all(units[unit]["active"] for unit in unit_names),
                "enabled": all(units[unit]["enabled"] for unit in unit_names),
            }
        return {"plugin": self.name, "version": self.version,
                "units": units, "services": services}

    # ------------------------------------------------------ Start / Stopp
    def start(self, service: str = "all") -> dict[str, Any]:
        try:
            names = self._select(service)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        results: dict[str, Any] = {}
        for name in names:
            unit_results = []
            for unit in self.SERVICES[name]:
                ok, message = self._systemctl("start", unit, sudo=True)
                unit_results.append({"unit": unit, "ok": ok, "message": message})
            results[name] = {"ok": all(item["ok"] for item in unit_results),
                             "units": unit_results}
        return {"ok": all(item["ok"] for item in results.values()), "started": results}

    def stop(self, service: str = "all") -> dict[str, Any]:
        try:
            names = self._select(service)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        results: dict[str, Any] = {}
        for name in names:
            unit_results = []
            # nmb vor smb stoppen (übliche Reihenfolge)
            for unit in reversed(self.SERVICES[name]):
                ok, message = self._systemctl("stop", unit, sudo=True)
                unit_results.append({"unit": unit, "ok": ok, "message": message})
            results[name] = {"ok": all(item["ok"] for item in unit_results),
                             "units": unit_results}
        return {"ok": all(item["ok"] for item in results.values()), "stopped": results}

    # ---------------------------------------------------------- Autostart
    def enable(self, service: str = "all") -> dict[str, Any]:
        try:
            names = self._select(service)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        results: dict[str, Any] = {}
        for name in names:
            unit_results = []
            for unit in self.SERVICES[name]:
                ok, message = self._systemctl("enable", unit, sudo=True)
                unit_results.append({"unit": unit, "ok": ok, "message": message})
            results[name] = {"ok": all(item["ok"] for item in unit_results),
                             "units": unit_results}
        return {"ok": all(item["ok"] for item in results.values()), "enabled": results}

    def disable(self, service: str = "all") -> dict[str, Any]:
        try:
            names = self._select(service)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        results: dict[str, Any] = {}
        for name in names:
            unit_results = []
            for unit in self.SERVICES[name]:
                ok, message = self._systemctl("disable", unit, sudo=True)
                unit_results.append({"unit": unit, "ok": ok, "message": message})
            results[name] = {"ok": all(item["ok"] for item in unit_results),
                             "units": unit_results}
        return {"ok": all(item["ok"] for item in results.values()), "disabled": results}

    # ---------------------------------------------- Kompatibilität (alt)
    def start_smb(self) -> tuple[bool, str]:
        result = self.start("smb")
        return result["ok"], json.dumps(result.get("started"), ensure_ascii=False)

    def stop_smb(self) -> tuple[bool, str]:
        result = self.stop("smb")
        return result["ok"], json.dumps(result.get("stopped"), ensure_ascii=False)

    def start_dlna(self) -> tuple[bool, str]:
        result = self.start("dlna")
        return result["ok"], json.dumps(result.get("started"), ensure_ascii=False)

    def stop_dlna(self) -> tuple[bool, str]:
        result = self.stop("dlna")
        return result["ok"], json.dumps(result.get("stopped"), ensure_ascii=False)

    def start_all(self) -> tuple[bool, str]:
        result = self.start("all")
        return result["ok"], "alle Dienste gestartet" if result["ok"] else "teilweise fehlgeschlagen"

    def stop_all(self) -> tuple[bool, str]:
        result = self.stop("all")
        return result["ok"], "alle Dienste gestoppt" if result["ok"] else "teilweise fehlgeschlagen"


def register(ctx: Any) -> None:
    """Hermes-Plugin-Einstiegspunkt: delegiert an :mod:`smb_dlna.tools`."""
    try:
        from .tools import register as _register
    except ImportError:  # flach
        from tools import register as _register

    _register(ctx)


def create_plugin(config_path: str | Path | None = None) -> Smb_dlna_Plugin:
    return Smb_dlna_Plugin(config_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smb_dlna_plugin")
    parser.add_argument("--status", action="store_true", help="Status als JSON ausgeben")
    parser.add_argument("--start", choices=["smb", "dlna", "all"], default=None)
    parser.add_argument("--stop", choices=["smb", "dlna", "all"], default=None)
    parser.add_argument("--enable", choices=["smb", "dlna", "all"], default=None)
    parser.add_argument("--disable", choices=["smb", "dlna", "all"], default=None)
    args = parser.parse_args(argv)

    plugin = create_plugin()
    if args.status:
        print(json.dumps(plugin.status(), indent=2, ensure_ascii=False))
        return 0
    for action in ("start", "stop", "enable", "disable"):
        value = getattr(args, action)
        if value is not None:
            result = getattr(plugin, action)(value)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("ok") else 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
