#!/usr/bin/env python3
"""Hermes plugin: Start/Stop Samba (SMB1, Share ep) und MiniDLNA Dienste.

Hermes-kompatibel: exposes create_plugin() und status().
CLI-Befehle für Hermes-Integration:
  --status        JSON-Status aller Dienste
  --start-smb     smb + nmb starten
  --stop-smb      smb + nmb stoppen
  --start-dlna    minidlna starten
  --stop-dlna     minidlna stoppen
  --start-all     alle starten
  --stop-all      alle stoppen
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


class SMB_DLNA_Plugin:
    """Steuert smb, nmb und minidlna systemd Dienste."""

    name = "smb_dlna"
    version = "1.0.0"
    description = "Samba (read-only ep) und MiniDLNA Steuerung für Hermes"

    # systemd Units
    SMB_UNIT = "smb.service"
    NMBD_UNIT = "nmb.service"
    DLNA_UNIT = "minidlna.service"

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path) if config_path else None

    def _run(self, *args: str) -> tuple[int, str, str]:
        """Führt einen Befehl aus (mit sudo falls nötig)."""
        try:
            res = subprocess.run(
                list(args),
                capture_output=True,
                text=True,
                timeout=15,
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except FileNotFoundError:
            return 127, "", f"Befehl nicht gefunden: {args[0]}"
        except subprocess.TimeoutExpired:
            return 124, "", "Timeout"

    def _systemctl(self, action: str, unit: str) -> tuple[bool, str]:
        code, out, err = self._run("sudo", "systemctl", action, unit)
        ok = code == 0
        msg = out or err or f"{action} {unit}"
        return ok, msg

    def _is_active(self, unit: str) -> bool:
        code, _, _ = self._run("systemctl", "is-active", unit)
        return code == 0

    def _is_enabled(self, unit: str) -> bool:
        code, _, _ = self._run("systemctl", "is-enabled", unit)
        return code == 0

    def status(self) -> dict[str, Any]:
        """Gibt den Status aller drei Dienste zurück."""
        result: dict[str, Any] = {
            "plugin": self.name,
            "version": self.version,
            "services": {},
        }
        for unit in (self.SMB_UNIT, self.NMBD_UNIT, self.DLNA_UNIT):
            active = self._is_active(unit)
            enabled = self._is_enabled(unit)
            result["services"][unit] = {
                "active": active,
                "enabled": enabled,
            }
        return result

    def start_smb(self) -> tuple[bool, str]:
        ok, msg = self._systemctl("start", self.SMB_UNIT)
        if ok:
            self._systemctl("start", self.NMBD_UNIT)
        return ok, msg

    def stop_smb(self) -> tuple[bool, str]:
        ok, msg = self._systemctl("stop", self.SMB_UNIT)
        if ok:
            self._systemctl("stop", self.NMBD_UNIT)
        return ok, msg

    def start_dlna(self) -> tuple[bool, str]:
        return self._systemctl("start", self.DLNA_UNIT)

    def stop_dlna(self) -> tuple[bool, str]:
        return self._systemctl("stop", self.DLNA_UNIT)

    def start_all(self) -> tuple[bool, str]:
        ok1, _ = self.start_smb()
        ok2, _ = self.start_dlna()
        return ok1 and ok2, "alle Dienste gestartet" if (ok1 and ok2) else "teilweise fehlgeschlagen"

    def stop_all(self) -> tuple[bool, str]:
        ok1, _ = self.stop_smb()
        ok2, _ = self.stop_dlna()
        return ok1 and ok2, "alle Dienste gestoppt" if (ok1 and ok2) else "teilweise fehlgeschlagen"


# ---------------------------------------------------------------------------
# Hermes Plugin Registrierung (Agent- + Desktop-RPC-Schnittstelle)
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Registriert RPC-Handler für die Hermes Desktop-App.

    Wird vom Hermes Gateway aufgerufen, damit desktop/plugin.js über
    host.rpc('smb_dlna.<methode>', {...}) auf diesen Plugin zugreifen kann.
    """
    plugin = create_plugin()

    async def rpc_status(_params: dict) -> dict:
        return plugin.status()

    async def rpc_start_smb(_params: dict) -> dict:
        ok, msg = plugin.start_smb()
        return {"ok": ok, "msg": msg}

    async def rpc_stop_smb(_params: dict) -> dict:
        ok, msg = plugin.stop_smb()
        return {"ok": ok, "msg": msg}

    async def rpc_start_nmb(_params: dict) -> dict:
        ok, msg = plugin._systemctl("start", plugin.NMBD_UNIT)
        return {"ok": ok, "msg": msg}

    async def rpc_stop_nmb(_params: dict) -> dict:
        ok, msg = plugin._systemctl("stop", plugin.NMBD_UNIT)
        return {"ok": ok, "msg": msg}

    async def rpc_start_dlna(_params: dict) -> dict:
        ok, msg = plugin.start_dlna()
        return {"ok": ok, "msg": msg}

    async def rpc_stop_dlna(_params: dict) -> dict:
        ok, msg = plugin.stop_dlna()
        return {"ok": ok, "msg": msg}

    async def rpc_start_all(_params: dict) -> dict:
        ok, msg = plugin.start_all()
        return {"ok": ok, "msg": msg}

    async def rpc_stop_all(_params: dict) -> dict:
        ok, msg = plugin.stop_all()
        return {"ok": ok, "msg": msg}

    async def rpc_toggle_autostart(params: dict) -> dict:
        unit = params.get("unit", plugin.SMB_UNIT)
        enabled = plugin._is_enabled(unit)
        action = "disable" if enabled else "enable"
        ok, msg = plugin._systemctl(action, unit)
        return {"ok": ok, "msg": msg, "unit": unit, "enabled": not enabled}

    async def rpc_refresh_status(_params: dict) -> dict:
        return plugin.status()

    handlers = {
        "status": rpc_status,
        "start_smb": rpc_start_smb,
        "stop_smb": rpc_stop_smb,
        "start_nmb": rpc_start_nmb,
        "stop_nmb": rpc_stop_nmb,
        "start_dlna": rpc_start_dlna,
        "stop_dlna": rpc_stop_dlna,
        "start_all": rpc_start_all,
        "stop_all": rpc_stop_all,
        "toggle_autostart": rpc_toggle_autostart,
        "refresh_status": rpc_refresh_status,
    }

    # Versuche, Hermes' RPC-Registrierung zu nutzen (falls vom ctx unterstützt)
    register_rpc = getattr(ctx, "register_rpc", None)
    if callable(register_rpc):
        try:
            register_rpc("smb_dlna", handlers)
        except Exception:
            pass  # Fallback: Handler bleiben lokal verfügbar


def create_plugin(config_path: str | Path | None = None) -> SMB_DLNA_Plugin:
    return SMB_DLNA_Plugin(config_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smb_dlna_plugin")
    parser.add_argument("--status", action="store_true", help="Status als JSON ausgeben")
    parser.add_argument("--start-smb", action="store_true", help="Samba starten")
    parser.add_argument("--stop-smb", action="store_true", help="Samba stoppen")
    parser.add_argument("--start-dlna", action="store_true", help="MiniDLNA starten")
    parser.add_argument("--stop-dlna", action="store_true", help="MiniDLNA stoppen")
    parser.add_argument("--start-all", action="store_true", help="Alle Dienste starten")
    parser.add_argument("--stop-all", action="store_true", help="Alle Dienste stoppen")
    args = parser.parse_args(argv)

    plugin = create_plugin()

    if args.status:
        print(json.dumps(plugin.status(), indent=2, ensure_ascii=False))
        return 0

    if args.start_smb:
        ok, msg = plugin.start_smb()
        print(msg)
        return 0 if ok else 1

    if args.stop_smb:
        ok, msg = plugin.stop_smb()
        print(msg)
        return 0 if ok else 1

    if args.start_dlna:
        ok, msg = plugin.start_dlna()
        print(msg)
        return 0 if ok else 1

    if args.stop_dlna:
        ok, msg = plugin.stop_dlna()
        print(msg)
        return 0 if ok else 1

    if args.start_all:
        ok, msg = plugin.start_all()
        print(msg)
        return 0 if ok else 1

    if args.stop_all:
        ok, msg = plugin.stop_all()
        print(msg)
        return 0 if ok else 1

    # Default: Status ausgeben
    print(json.dumps(plugin.status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
