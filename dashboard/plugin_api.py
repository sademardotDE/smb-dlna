"""Dashboard-Backend für smb-dlna (Samba/MiniDLNA-Steuerung).

Läuft im Hermes-Dashboard/Gateway-Prozess (hinter dessen Auth) und bedient den
Tab „Dienste": Status, Start/Stopp und Autostart für smb/nmb/minidlna.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

_ROOT = Path(__file__).resolve().parents[1]
_NAME = "_smb_dlna_dashboard"

if _NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _NAME, _ROOT / "__init__.py", submodule_search_locations=[str(_ROOT)]
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_NAME] = _mod
    _spec.loader.exec_module(_mod)

plugin_module = importlib.import_module(_NAME + ".smb_dlna_plugin")

router = APIRouter()

_ACTIONS = {"start", "stop", "enable", "disable"}
_SERVICES = {"smb", "dlna", "all"}


def _error(status: int, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"ok": False, "error": message, **extra})


@router.get("/services")
def services_status():
    return plugin_module.create_plugin().status()


@router.get("/status")
def status():
    return plugin_module.create_plugin().status()


@router.post("/services/{service}/{action}")
def service_action(service: str, action: str):
    if service not in _SERVICES:
        raise _error(400, f"Unbekannter Dienst {service!r}; erwartet: smb, dlna, all")
    if action not in _ACTIONS:
        raise _error(400, f"Unbekannte Aktion {action!r}; erwartet: start, stop, enable, disable")
    plugin = plugin_module.create_plugin()
    result = getattr(plugin, action)(service)
    if not result.get("ok"):
        raise _error(400, result.get("error") or "systemctl fehlgeschlagen", result=result)
    return {"ok": True, **result}
