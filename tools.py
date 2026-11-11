"""Hermes-Tools und CLI für das smb-dlna-Plugin."""

from __future__ import annotations

import json
from typing import Any, Callable

try:  # Paket-Import (Hermes-Loader)
    from .smb_dlna_plugin import create_plugin
except ImportError:  # flach (Tests im Repo-Verzeichnis)
    from smb_dlna_plugin import create_plugin

TOOLSET = "smb_dlna"


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _error(exc: BaseException, tool: str) -> str:
    return _json({"ok": False, "error": str(exc), "tool": tool})


def _service(args: dict) -> str:
    return str(args.get("service") or "all")


def _h_status(ctx: Any, args: dict, **_: Any) -> str:
    try:
        return _json(create_plugin().status())
    except Exception as exc:  # noqa: BLE001 - Tool-Vertrag: Fehler als JSON
        return _error(exc, "services_status")


def _h_start(ctx: Any, args: dict, **_: Any) -> str:
    try:
        return _json(create_plugin().start(_service(args)))
    except Exception as exc:  # noqa: BLE001
        return _error(exc, "services_start")


def _h_stop(ctx: Any, args: dict, **_: Any) -> str:
    try:
        return _json(create_plugin().stop(_service(args)))
    except Exception as exc:  # noqa: BLE001
        return _error(exc, "services_stop")


def _h_enable(ctx: Any, args: dict, **_: Any) -> str:
    try:
        return _json(create_plugin().enable(_service(args)))
    except Exception as exc:  # noqa: BLE001
        return _error(exc, "services_enable")


def _h_disable(ctx: Any, args: dict, **_: Any) -> str:
    try:
        return _json(create_plugin().disable(_service(args)))
    except Exception as exc:  # noqa: BLE001
        return _error(exc, "services_disable")


_SERVICE_PROP = {
    "type": "string",
    "enum": ["smb", "dlna", "all"],
    "description": "Welcher Dienst: smb (smb+nmb), dlna (minidlna) oder all (Default).",
}

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "services_status": {
        "name": "services_status",
        "description": "Status von Samba (smb/nmb) und MiniDLNA: aktiv/gestoppt und "
                       "Autostart (systemctl enabled) je Unit.",
        "parameters": {"type": "object", "properties": {}},
    },
    "services_start": {
        "name": "services_start",
        "description": "Startet Samba (smb, nmb), MiniDLNA oder beide (sudo systemctl start).",
        "parameters": {"type": "object", "properties": {"service": _SERVICE_PROP}},
    },
    "services_stop": {
        "name": "services_stop",
        "description": "Stoppt Samba (nmb, smb), MiniDLNA oder beide (sudo systemctl stop).",
        "parameters": {"type": "object", "properties": {"service": _SERVICE_PROP}},
    },
    "services_enable": {
        "name": "services_enable",
        "description": "Aktiviert den Autostart (sudo systemctl enable) für Samba, MiniDLNA oder beide.",
        "parameters": {"type": "object", "properties": {"service": _SERVICE_PROP}},
    },
    "services_disable": {
        "name": "services_disable",
        "description": "Deaktiviert den Autostart (sudo systemctl disable) für Samba, MiniDLNA oder beide.",
        "parameters": {"type": "object", "properties": {"service": _SERVICE_PROP}},
    },
}

_HANDLERS: dict[str, Callable[..., str]] = {
    "services_status": _h_status,
    "services_start": _h_start,
    "services_stop": _h_stop,
    "services_enable": _h_enable,
    "services_disable": _h_disable,
}


def make_handlers(ctx: Any) -> dict[str, Callable[..., str]]:
    handlers: dict[str, Callable[..., str]] = {}
    for name, handler in _HANDLERS.items():
        def bound(args: dict | None = None, _handler=handler, **kwargs: Any) -> str:
            return _handler(ctx, dict(args or {}), **kwargs)

        handlers[name] = bound
    return handlers


def _cli_handler(ctx: Any) -> Callable[[Any], int]:
    def handle(args: Any) -> int:
        command = getattr(args, "services_command", "")
        payload = dict(vars(args))
        service = str(payload.get("service") or "all")
        tool = {
            "status": ("services_status", {}),
            "start": ("services_start", {"service": service}),
            "stop": ("services_stop", {"service": service}),
            "enable": ("services_enable", {"service": service}),
            "disable": ("services_disable", {"service": service}),
        }.get(command)
        if tool is None:
            print(_json({"ok": False, "error": f"Unbekannter Befehl: {command!r}"}))
            return 2
        name, tool_args = tool
        result = _HANDLERS[name](ctx, tool_args)
        print(result)
        try:
            return 0 if json.loads(result).get("ok", True) else 1
        except (ValueError, AttributeError):
            return 1

    return handle


def register_cli(ctx: Any) -> None:
    def setup(subparser: Any) -> None:
        subs = subparser.add_subparsers(dest="services_command", required=True)
        subs.add_parser("status", help="Status aller Dienste")
        for action, help_text in (
            ("start", "Dienste starten"),
            ("stop", "Dienste stoppen"),
            ("enable", "Autostart aktivieren"),
            ("disable", "Autostart deaktivieren"),
        ):
            parser = subs.add_parser(action, help=help_text)
            parser.add_argument("service", nargs="?", default="all",
                                choices=["smb", "dlna", "all"])

    ctx.register_cli_command(
        name="services",
        help="Samba (smb/nmb) und MiniDLNA steuern",
        setup_fn=setup,
        handler_fn=_cli_handler(ctx),
        description="Status, Start/Stopp und Autostart von Samba- und MiniDLNA-Diensten.",
    )


def register(ctx: Any) -> None:
    """Registriert Tools + ``hermes services``-CLI."""
    handlers = make_handlers(ctx)
    for name, schema in TOOL_SCHEMAS.items():
        ctx.register_tool(name=name, toolset=TOOLSET, schema=schema,
                          handler=handlers[name], emoji="🖧")
    register_cli(ctx)
