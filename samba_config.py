"""Samba-Freigaben für die Medienordner (``smb.conf``).

Spiegelt die ``media_dir``-Einträge von MiniDLNA als eigene Samba-Shares wider:
pro Medienordner ein Share (Ordnername als Share-Name).

Die Shares liegen in einem klar markierten Block in ``/etc/samba/smb.conf``::

    # BEGIN smb-dlna (auto-generiert — beim Synchronisieren überschrieben)
    [Videos]
       comment = smb-dlna Medienordner
       path = /home/fm/Videos
       …
    # END smb-dlna

Nur dieser Block wird verändert; fremde Shares ([copy], [ep], [homes], …)
bleiben unangetastet. Alle Funktionen liefern Ergebnis-Dicts statt Ausnahmen.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

DEFAULT_CONF = Path("/etc/samba/smb.conf")
SUDO_TIMEOUT = 20

BEGIN_MARK = "# BEGIN smb-dlna (auto-generiert — beim Synchronisieren überschrieben)"
END_MARK = "# END smb-dlna"
COMMENT = "smb-dlna Medienordner"

SMB_UNITS = ("smb.service", "nmb.service")

#: Share-Optionen für die auto-generierten Medien-Freigaben
SHARE_TEMPLATE = (
    "[{name}]\n"
    "   comment = {comment}\n"
    "   path = {path}\n"
    "   browseable = yes\n"
    "   read only = no\n"
    "   guest ok = no\n"
    "   valid users = fm\n"
    "   force user = fm\n"
    "   create mask = 0664\n"
    "   directory mask = 0775\n"
)

_NAME_SAFE = re.compile(r"[^A-Za-z0-9_-]+")
_MAX_NAME = 32


def share_name(folder: str) -> str:
    """Leitet aus dem Ordnernamen einen gültigen Share-Namen ab."""
    base = Path(folder.rstrip("/") or folder).name or "Medien"
    name = _NAME_SAFE.sub("_", base).strip("_")[:_MAX_NAME]
    return name or "Medien"


# --------------------------------------------------------------------- Lesen
def _read_conf(conf_path: str | Path | None = None) -> tuple[Path, str]:
    path = Path(conf_path) if conf_path else DEFAULT_CONF
    try:
        # surrogateescape: Byte-faust (smb.conf ist traditionell latin-1)
        return path, path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return path, ""


def _split_block(text: str) -> tuple[str, str, str]:
    """Trennt ``(vorher, block, nachher)`` an den Markierungen."""
    start = text.find(BEGIN_MARK)
    if start < 0:
        return text, "", ""
    end = text.find(END_MARK, start)
    if end < 0:
        return text, "", ""  # Markierung unvollständig → nicht anfassen
    end += len(END_MARK)
    block = text[start:end]
    vorher = text[:start]
    nachher = text[end:]
    return vorher, block, nachher


def _names_in_block(block: str) -> list[str]:
    return re.findall(r"^\[([^\]]+)\]\s*$", block, flags=re.MULTILINE)


def _names_in_text(text: str) -> set[str]:
    """Alle Share-Namen außerhalb unseres Blocks (fremde Shares).

    ``[global]`` ist die Konfig-Sektion selbst und keine Freigabe.
    """
    vorher, _, nachher = _split_block(text)
    names = set(re.findall(r"^\[([^\]]+)\]\s*$", vorher + nachher,
                           flags=re.MULTILINE))
    names.discard("global")
    return names


def read_shares(conf_path: str | Path | None = None) -> dict[str, Any]:
    """Liest unsere auto-generierten Shares und die fremden daneben."""
    path, text = _read_conf(conf_path)
    if not text and not path.is_file():
        return {"ok": True, "conf": str(path), "exists": False,
                "managed": [], "foreign": [], "note": "smb.conf nicht gefunden."}
    _, block, _ = _split_block(text)
    managed = _names_in_block(block)
    foreign = sorted(_names_in_text(text))
    return {"ok": True, "conf": str(path), "exists": True,
            "managed": managed, "foreign": foreign}


# ------------------------------------------------------------------ Schreiben
def _validate(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Prüft die media_dir-Einträge, liefert Share-Name + Pfad."""
    used: set[str] = set()
    result: list[dict[str, str]] = []
    for entry in entries:
        folder = str(entry.get("path") or "").strip()
        if not folder:
            raise ValueError("Ordnerpfad darf nicht leer sein")
        if not os.path.isdir(folder):
            raise ValueError(f"Verzeichnis existiert nicht: {folder}")
        name = share_name(folder)
        # Konflikt mit einem fremden Share? → Suffix
        base, suffix = name, 1
        while name in used:
            suffix += 1
            name = f"{base}_{suffix}"
        used.add(name)
        result.append({"name": name, "path": folder})
    return result


def _render(validated: list[dict[str, str]]) -> str:
    parts = [BEGIN_MARK, ""]
    for item in validated:
        parts.append(SHARE_TEMPLATE.format(
            name=item["name"], comment=COMMENT, path=item["path"]))
        parts.append("")
    parts.append(END_MARK)
    return "\n".join(parts)


def _write(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", errors="surrogateescape")
        return
    except OSError:
        pass  # root-owned → sudo
    proc = subprocess.run(
        ["sudo", "-n", "tee", str(path)],
        input=content, capture_output=True, text=True, timeout=SUDO_TIMEOUT,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise OSError(f"Schreiben nach {path} fehlgeschlagen: {msg}")


def _backup(path: Path) -> str | None:
    if not path.is_file():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.bak-{stamp}")
    proc = subprocess.run(
        ["sudo", "-n", "cp", "-p", str(path), str(target)],
        capture_output=True, text=True, timeout=SUDO_TIMEOUT,
    )
    return str(target) if proc.returncode == 0 else None


def _run(action: str) -> dict[str, Any]:
    """Führt ``sudo systemctl <action>`` für smb+nmb aus."""
    results = []
    for unit in SMB_UNITS:
        proc = subprocess.run(
            ["sudo", "-n", "systemctl", action, unit],
            capture_output=True, text=True, timeout=SUDO_TIMEOUT,
        )
        results.append({"unit": unit, "ok": proc.returncode == 0,
                        "message": (proc.stderr or proc.stdout or "").strip()
                        or f"systemctl {action} {unit}"})
    return {"ok": all(r["ok"] for r in results), "units": results}


def ensure_running() -> dict[str, Any]:
    """Aktiviert den Autostart und startet smb+nmb, falls nicht aktiv."""
    state = status_units()
    if all(state["units"][u]["active"] for u in SMB_UNITS) and \
            all(state["units"][u]["enabled"] for u in SMB_UNITS):
        return {"ok": True, "changed": False, "state": state}
    enabled = _run("enable")
    started = _run("start")
    time.sleep(0.5)
    return {"ok": enabled["ok"] and started["ok"], "changed": True,
            "enabled": enabled, "started": started, "state": status_units()}


def status_units() -> dict[str, Any]:
    """Aktiver/Autostart-Status der Samba-Units (ohne sudo)."""
    units: dict[str, Any] = {}
    for unit in SMB_UNITS:
        active = subprocess.run(["systemctl", "is-active", unit],
                                capture_output=True, text=True,
                                timeout=SUDO_TIMEOUT).returncode == 0
        enabled = subprocess.run(["systemctl", "is-enabled", unit],
                                 capture_output=True, text=True,
                                 timeout=SUDO_TIMEOUT).returncode == 0
        units[unit] = {"active": active, "enabled": enabled}
    return {"units": units,
            "active": all(u["active"] for u in units.values()),
            "enabled": all(u["enabled"] for u in units.values())}


def sync(entries: list[dict[str, Any]],
         conf_path: str | Path | None = None,
         ensure: bool = True) -> dict[str, Any]:
    """Synchronisiert die Samba-Shares mit den Medienordnern.

    Legt für jeden Ordner ein Share an, entfernt Shares für Ordner, die nicht
    mehr in der Liste stehen, und lässt fremde Shares unangetastet.
    """
    try:
        validated = _validate(entries)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    path, text = _read_conf(conf_path)
    if not text and not path.is_file():
        return {"ok": False, "error": f"smb.conf nicht gefunden: {path}"}

    vorher, _, nachher = _split_block(text)
    block = "\n\n" + _render(validated) + "\n"
    if _split_block(text)[1]:
        # vorhandenen Block ersetzen (Leerraum drumherum bleibt)
        sep_v = vorher.rstrip("\n")
        sep_n = nachher.lstrip("\n")
        neu = (sep_v + "\n" + block if sep_v else block.lstrip("\n"))
        if sep_n:
            neu = neu.rstrip("\n") + "\n\n" + sep_n
    else:
        neu = text.rstrip("\n") + "\n\n" + block

    # Kollisionen mit fremden Share-Namen prüfen
    foreign = _names_in_text(text)
    clash = [v["name"] for v in validated if v["name"] in foreign]
    if clash:
        return {"ok": False,
                "error": "Share-Name bereits vergeben: " + ", ".join(clash)}

    backup = _backup(path)
    try:
        _write(path, neu)
    except OSError as exc:
        return {"ok": False, "error": str(exc), "backup": backup}

    # Konfiguration validieren (testparm), sonst zurückrollen
    check = subprocess.run(["sudo", "-n", "testparm", "-s", str(path)],
                           capture_output=True, text=True, timeout=SUDO_TIMEOUT)
    if check.returncode != 0:
        if backup:
            subprocess.run(["sudo", "-n", "cp", "-p", backup, str(path)],
                           capture_output=True, timeout=SUDO_TIMEOUT)
        return {"ok": False, "backup": backup, "rolled_back": True,
                "error": "testparm abgelehnt — smb.conf zurückgerollt: "
                         + (check.stderr or check.stdout or "").strip()}

    result: dict[str, Any] = {
        "ok": True, "conf": str(path), "backup": backup,
        "shares": validated, "written": len(validated),
    }
    if ensure:
        result["service"] = ensure_running()
        if not result["service"].get("ok"):
            result["ok"] = False
            result["error"] = "Freigaben geschrieben, aber Samba konnte nicht " \
                              "gestartet werden."
    return result


# ------------------------------------------------------------------- Status
def status(conf_path: str | Path | None = None) -> dict[str, Any]:
    """Freigaben + Samba-Dienststatus in einem Dict."""
    info = read_shares(conf_path)
    info["service"] = status_units()
    managed = info.get("managed") or []
    # Pfad je unserem Share aus dem Block lesen
    _, text = _read_conf(conf_path)
    _, block, _ = _split_block(text)
    path_of: dict[str, str] = {}
    current = None
    for line in block.splitlines():
        m = re.match(r"^\[([^\]]+)\]\s*$", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r"^\s*path\s*=\s*(.+)$", line)
        if m and current:
            path_of[current] = m.group(1).strip()
    info["shares"] = [{"name": n, "path": path_of.get(n)} for n in managed]
    return info
