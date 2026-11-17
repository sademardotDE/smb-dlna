"""Medienordner-Konfiguration für MiniDLNA (``media_dir`` in ``/etc/minidlna.conf``).

Bietet das Lesen, Prüfen und Schreiben der ``media_dir``-Einträge sowie einen
lesenden Verzeichnis-Explorer und eine Vorschau der erkannten Medien.

MiniDLNA-Syntax::

    media_dir=A,/home/fm/Musik     # A = Audio
    media_dir=V,/home/fm/Videos    # V = Video
    media_dir=P,/home/fm/Bilder    # P = Pictures
    media_dir=/home/fm/Medien      # ohne Präfix: Typ-Erkennung automatisch

Alle Funktionen liefern Ergebnis-Dicts statt Ausnahmen zu werfen, damit sie
direkt als Dashboard-/Tool-Antworten dienen können.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

DEFAULT_CONF = Path("/etc/minidlna.conf")
SUDO_TIMEOUT = 20

#: Gültige media_dir-Typen (minidlna-Präfixe)
TYPES: tuple[str, ...] = ("A", "V", "P")
TYPE_LABELS: dict[str, str] = {"A": "Audio", "V": "Video", "P": "Bilder"}

#: Endungen für die Medien-Vorschau
VIDEO_EXT = frozenset({
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".mpg", ".mpeg", ".ts", ".m2ts", ".ogv", ".3gp", ".divx",
})
AUDIO_EXT = frozenset({
    ".mp3", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".wav", ".wma",
    ".opus", ".ape", ".wv", ".alac", ".aiff",
})
IMAGE_EXT = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff",
    ".heic", ".heif", ".svg", ".raw", ".cr2", ".nef", ".arw",
})

#: Obergrenzen, damit die Vorschau auch in großen Bäumen schnell bleibt
BROWSE_LIMIT = 500
PREVIEW_MAX_FILES = 20000
PREVIEW_MAX_SECONDS = 3.0


# --------------------------------------------------------------------- Parsing
def _parse_line(line: str) -> tuple[str, str] | None:
    """Liefert ``(typ, pfad)`` für eine ``media_dir``-Zeile, sonst ``None``."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, _, value = stripped.partition("=")
    if key.strip().lower() != "media_dir":
        return None
    value = value.strip()
    if not value:
        return None
    # Präfix "A," / "V," / "P," — nur wenn es genau ein gültiges Zeichen ist
    if len(value) > 2 and value[1] == "," and value[0].upper() in TYPES:
        return value[0].upper(), value[2:].strip()
    return "", value


def read_entries(conf_path: str | Path | None = None) -> dict[str, Any]:
    """Liest alle ``media_dir``-Einträge aus der Konfiguration.

    ``conf_path=None`` löst ``DEFAULT_CONF`` erst zur Laufzeit auf, damit sich
    ein späterer Wechsel des Modul-Attributs auswirkt (Tests).
    """
    path = Path(conf_path) if conf_path else DEFAULT_CONF
    if not path.is_file():
        return {"ok": True, "conf": str(path), "exists": False, "entries": [],
                "note": "Konfigurationsdatei nicht gefunden – Eintrag wird neu angelegt."}
    entries: list[dict[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "conf": str(path), "error": f"Lesen fehlgeschlagen: {exc}",
                "entries": []}
    for line in text.splitlines():
        parsed = _parse_line(line)
        if parsed:
            typ, entry_path = parsed
            entries.append({"type": typ, "path": entry_path})
    return {"ok": True, "conf": str(path), "exists": True, "entries": entries}


# ------------------------------------------------------------------ Validierung
def _validate(entry: dict[str, Any]) -> tuple[str, str]:
    """Liefert ``(typ, pfad)`` oder wirft ``ValueError`` mit deutscher Meldung."""
    typ = str(entry.get("type") or "").strip().upper()
    raw_path = str(entry.get("path") or "").strip()
    if typ not in TYPES:
        raise ValueError(f"Unbekannter Typ {typ!r}; erwartet: {', '.join(TYPES)}")
    if not raw_path:
        raise ValueError("Pfad darf nicht leer sein")
    if not os.path.isabs(raw_path):
        raise ValueError(f"Pfad muss absolut sein: {raw_path}")
    path = Path(raw_path)
    if not path.exists():
        raise ValueError(f"Verzeichnis existiert nicht: {raw_path}")
    if not path.is_dir():
        raise ValueError(f"Ist kein Verzeichnis: {raw_path}")
    if not os.access(path, os.R_OK | os.X_OK):
        raise ValueError(f"Verzeichnis nicht lesbar: {raw_path}")
    return typ, str(path)


# ---------------------------------------------------------------------- Schreiben
def _render(conf_text: str, entries: list[dict[str, str]]) -> str:
    """Ersetzt alle ``media_dir``-Zeilen durch die neuen, bewahrt den Rest."""
    lines = conf_text.splitlines()
    new_lines = [f"media_dir={e['type']},{e['path']}" for e in entries]

    out: list[str] = []
    inserted = False
    for line in lines:
        if _parse_line(line) is not None:
            if not inserted and new_lines:
                out.extend(new_lines)
                inserted = True
            continue
        out.append(line)
    if not inserted and new_lines:
        if out and out[-1].strip():
            out.append("")
        out.extend(new_lines)
    return "\n".join(out) + "\n"


def _write_raw(path: Path, content: str) -> None:
    """Schreibt ``content`` nach ``path`` — direkt oder per ``sudo tee``."""
    try:
        path.write_text(content, encoding="utf-8")
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
    """Sichert ``path`` vor dem Überschreiben; liefert den Backup-Pfad."""
    if not path.is_file():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.bak-{stamp}")
    try:
        shutil.copy2(path, target)
        return str(target)
    except OSError:
        # root-owned → per sudo sichern
        proc = subprocess.run(
            ["sudo", "-n", "cp", "-p", str(path), str(target)],
            capture_output=True, text=True, timeout=SUDO_TIMEOUT,
        )
        return str(target) if proc.returncode == 0 else None


def write_entries(entries: list[dict[str, Any]],
                  conf_path: str | Path | None = None,
                  restart: bool = False) -> dict[str, Any]:
    """Validiert und schreibt die ``media_dir``-Einträge.

    Danach optional ``minidlna`` neu starten, damit die Änderung wirkt.
    ``conf_path=None`` löst ``DEFAULT_CONF`` zur Laufzeit auf.
    """
    path = Path(conf_path) if conf_path else DEFAULT_CONF
    try:
        validated = [_validate(e) for e in entries]
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    # Doppelte Einträge (gleicher Typ + Pfad) entfernen, Reihenfolge bewahren
    seen: set[tuple[str, str]] = set()
    clean: list[dict[str, str]] = []
    for typ, entry_path in validated:
        key = (typ, entry_path)
        if key not in seen:
            seen.add(key)
            clean.append({"type": typ, "path": entry_path})

    try:
        original = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except OSError as exc:
        return {"ok": False, "error": f"Lesen fehlgeschlagen: {exc}"}

    backup = _backup(path)
    try:
        _write_raw(path, _render(original, clean))
    except OSError as exc:
        return {"ok": False, "error": str(exc), "backup": backup}

    result: dict[str, Any] = {
        "ok": True, "conf": str(path), "entries": clean,
        "backup": backup, "written": len(clean),
    }
    if restart:
        result["restart"] = restart_minidlna()
    return result


def restart_minidlna() -> dict[str, Any]:
    """Startet ``minidlna`` neu (bei laufendem Dienst) bzw. startet ihn."""
    proc = subprocess.run(
        ["sudo", "-n", "systemctl", "restart", "minidlna.service"],
        capture_output=True, text=True, timeout=SUDO_TIMEOUT,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        return {"ok": False, "error": msg}
    time.sleep(0.5)
    check = subprocess.run(
        ["systemctl", "is-active", "minidlna.service"],
        capture_output=True, text=True, timeout=SUDO_TIMEOUT,
    )
    return {"ok": True, "active": check.returncode == 0,
            "state": (check.stdout or "").strip() or "unbekannt"}


# --------------------------------------------------------------------- Explorer
def browse(path: str = "/",
           show_hidden: bool = False) -> dict[str, Any]:
    """Listet Unterverzeichnisse von ``path`` (lesend, ohne Dateien)."""
    raw = (path or "/").strip()
    if not os.path.isabs(raw):
        return {"ok": False, "error": f"Pfad muss absolut sein: {raw}"}
    target = Path(raw)
    if not target.is_dir():
        return {"ok": False, "error": f"Ist kein Verzeichnis: {raw}"}
    if not os.access(target, os.R_OK | os.X_OK):
        return {"ok": False, "error": f"Verzeichnis nicht lesbar: {raw}"}

    dirs: list[dict[str, Any]] = []
    truncated = False
    try:
        with os.scandir(target) as it:
            for entry in it:
                if len(dirs) >= BROWSE_LIMIT:
                    truncated = True
                    break
                name = entry.name
                if not show_hidden and name.startswith("."):
                    continue
                try:
                    if not entry.is_dir(follow_symlinks=True):
                        continue
                except OSError:
                    continue
                dirs.append({"name": name, "path": str(target / name)})
    except PermissionError:
        return {"ok": False, "error": f"Zugriff verweigert: {raw}"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    dirs.sort(key=lambda d: d["name"].lower())
    parent = str(target.parent) if target != target.parent else None
    return {"ok": True, "path": str(target), "parent": parent,
            "entries": dirs, "truncated": truncated,
            "hidden_shown": bool(show_hidden)}


# ----------------------------------------------------------------------- Vorschau
def preview(path: str) -> dict[str, Any]:
    """Zählt Video-, Audio- und Bilddateien unter ``path`` (zeitlich begrenzt)."""
    if not os.path.isabs(path):
        return {"ok": False, "error": f"Pfad muss absolut sein: {path}"}
    target = Path(path)
    if not target.is_dir():
        return {"ok": False, "error": f"Ist kein Verzeichnis: {path}"}

    counts = {"video": 0, "audio": 0, "image": 0, "other": 0, "total": 0}
    started = time.monotonic()
    complete = True
    stack = [target]
    try:
        while stack:
            current = stack.pop()
            with os.scandir(current) as it:
                for entry in it:
                    if counts["total"] >= PREVIEW_MAX_FILES or \
                            time.monotonic() - started >= PREVIEW_MAX_SECONDS:
                        complete = False
                        stack.clear()
                        break
                    try:
                        if entry.is_dir(follow_symlinks=True):
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    ext = os.path.splitext(entry.name)[1].lower()
                    counts["total"] += 1
                    if ext in VIDEO_EXT:
                        counts["video"] += 1
                    elif ext in AUDIO_EXT:
                        counts["audio"] += 1
                    elif ext in IMAGE_EXT:
                        counts["image"] += 1
                    else:
                        counts["other"] += 1
    except PermissionError:
        return {"ok": False, "error": f"Zugriff verweigert: {path}"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "path": str(target), "counts": counts,
            "complete": complete,
            "duration_ms": int((time.monotonic() - started) * 1000)}


# ------------------------------------------------------------------- Übersicht
def status(conf_path: str | Path | None = None) -> dict[str, Any]:
    """Vollständige Übersicht: Einträge + Vorschau + MiniDLNA-Status."""
    info = read_entries(conf_path)
    entries = info.get("entries") or []
    previews: list[dict[str, Any]] = []
    for entry in entries:
        item = {"type": entry["type"], "path": entry["path"]}
        result = preview(entry["path"])
        if result.get("ok"):
            item["counts"] = result["counts"]
            item["complete"] = result["complete"]
        else:
            item["error"] = result.get("error")
        previews.append(item)
    info["preview"] = previews
    return info
