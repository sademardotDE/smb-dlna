"""Dashboard-Backend für smb-dlna (Samba/MiniDLNA-Steuerung).

Läuft im Hermes-Dashboard/Gateway-Prozess (hinter dessen Auth) und bedient den
Tab „Dienste": Status, Start/Stopp und Autostart für smb/nmb/minidlna sowie die
Medienordner-Konfiguration (``media_dir`` in ``/etc/minidlna.conf``) mit
Verzeichnis-Explorer und Medien-Vorschau.
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
media_module = importlib.import_module(_NAME + ".media_config")

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


# ------------------------------------------------------------- Medienordner
@router.get("/media-config")
def media_config_status():
    """Aktuelle ``media_dir``-Einträge inkl. Medien-Vorschau je Ordner."""
    return media_module.status()


@router.get("/browse")
def browse_dirs(path: str = "/", show_hidden: bool = False):
    """Lesende Verzeichnisnavigation für den Ordner-Explorer."""
    result = media_module.browse(path, show_hidden=show_hidden)
    if not result.get("ok"):
        raise _error(400, result.get("error") or "Verzeichnis nicht lesbar")
    return result


@router.post("/media-config")
def save_media_config(payload: dict[str, Any]):
    """Schreibt die ``media_dir``-Einträge nach ``/etc/minidlna.conf``.

    Erwartet ``{"entries": [{"type": "A|V|P", "path": "/abs/pfad"}, …],
    "restart": true|false}``.
    """
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise _error(400, "Feld 'entries' fehlt oder ist keine Liste")
    if not isinstance(payload.get("restart", False), bool):
        raise _error(400, "Feld 'restart' muss ein Wahrheitswert sein")
    result = media_module.write_entries(raw_entries, restart=bool(payload.get("restart")))
    if not result.get("ok"):
        raise _error(400, result.get("error") or "Schreiben fehlgeschlagen", result=result)
    return result
