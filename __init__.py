"""Hermes-Plugin: Samba (smb/nmb) und MiniDLNA steuern (Status, Start/Stopp, Autostart)."""

from __future__ import annotations

from typing import Any

try:  # Paket-Import (Hermes-Loader)
    from .smb_dlna_plugin import Smb_dlna_Plugin, create_plugin
except ImportError:  # flach (Tests im Repo-Verzeichnis)
    from smb_dlna_plugin import Smb_dlna_Plugin, create_plugin

__version__ = "1.1.0"

__all__ = ["Smb_dlna_Plugin", "create_plugin", "register", "__version__"]


def register(ctx: Any) -> None:
    """Hermes-Einstiegspunkt: Tools + CLI registrieren."""
    try:
        from .tools import register as _register
    except ImportError:  # flach
        from tools import register as _register

    _register(ctx)
