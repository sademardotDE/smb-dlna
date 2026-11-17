#!/usr/bin/env python3
"""Tests für die Medienordner-Konfiguration (media_config) und ihre API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import media_config as mc

VIDEO = "clip.mp4"
AUDIO = "song.mp3"
IMAGE = "photo.jpg"


# ------------------------------------------------------------------- Hilfen
def make_conf(tmp_path: Path, body: str = "port=8200\n") -> Path:
    conf = tmp_path / "minidlna.conf"
    conf.write_text(body, encoding="utf-8")
    return conf


def make_tree(tmp_path: Path) -> Path:
    """Legt ein kleines Medien-Verzeichnis an."""
    root = tmp_path / "medien"
    (root / "videos").mkdir(parents=True)
    (root / "musik").mkdir(parents=True)
    (root / ".versteckt").mkdir()
    (root / "videos" / VIDEO).write_bytes(b"x")
    (root / "videos" / "mehr.mp4").write_bytes(b"x")
    (root / "musik" / AUDIO).write_bytes(b"x")
    (root / IMAGE).write_bytes(b"x")
    (root / "notiz.txt").write_text("x", encoding="utf-8")
    return root


# ----------------------------------------------------------------- Parsing
def test_read_parses_types_and_comments(tmp_path):
    conf = (
        "# media_dir=V,/kommentar\n"
        "port=8200\n"
        "media_dir=V,/run/media\n"
        "media_dir=/home/fm/Musik\n"
        "media_dir=A,/home/fm/Music\n"
        "friendly_name=FM-DLNA\n"
    )
    path = make_conf(tmp_path, conf)
    result = mc.read_entries(path)
    assert result["ok"] is True
    assert result["entries"] == [
        {"type": "V", "path": "/run/media"},
        {"type": "", "path": "/home/fm/Musik"},
        {"type": "A", "path": "/home/fm/Music"},
    ]


def test_read_missing_conf_is_not_an_error(tmp_path):
    result = mc.read_entries(tmp_path / "fehlt.conf")
    assert result["ok"] is True
    assert result["exists"] is False
    assert result["entries"] == []
    assert "note" in result


# ------------------------------------------------------------- Validierung
@pytest.mark.parametrize("entry,frag", [
    ({"type": "X", "path": "/tmp"}, "Unbekannter Typ"),
    ({"type": "V", "path": "relativ"}, "muss absolut sein"),
    ({"type": "V", "path": "/gibt/es/nicht"}, "existiert nicht"),
])
def test_validate_rejects_bad_entries(entry, frag):
    with pytest.raises(ValueError) as exc:
        mc._validate(entry)
    assert frag in str(exc.value)


def test_validate_rejects_file_instead_of_dir(tmp_path):
    target = tmp_path / "datei.mp4"
    target.write_bytes(b"x")
    with pytest.raises(ValueError, match="kein Verzeichnis"):
        mc._validate({"type": "V", "path": str(target)})


def test_validate_accepts_real_dir(tmp_path):
    typ, path = mc._validate({"type": "a", "path": str(tmp_path)})
    assert typ == "A"
    assert path == str(tmp_path)


# ---------------------------------------------------------------- Schreiben
def test_write_replaces_media_dirs_and_keeps_rest(tmp_path):
    conf = make_conf(tmp_path, "port=8200\nmedia_dir=V,/alt\nfriendly_name=FM\n")
    before = conf.read_text(encoding="utf-8")

    result = mc.write_entries(
        [{"type": "V", "path": str(tmp_path)}, {"type": "A", "path": str(tmp_path)}],
        conf_path=conf,
    )
    assert result["ok"] is True
    assert result["written"] == 2
    assert result["backup"]  # Backup wurde angelegt

    text = conf.read_text(encoding="utf-8")
    assert "media_dir=V," + str(tmp_path) in text
    assert "media_dir=A," + str(tmp_path) in text
    assert "/alt" not in text
    # Nicht-media_dir-Zeilen bleiben unverändert
    assert "port=8200" in text
    assert "friendly_name=FM" in text
    assert before.splitlines()[0] == "port=8200"


def test_write_deduplicates_entries(tmp_path):
    conf = make_conf(tmp_path)
    p = str(tmp_path)
    result = mc.write_entries(
        [{"type": "V", "path": p}, {"type": "V", "path": p}],
        conf_path=conf,
    )
    assert result["ok"] is True
    assert result["written"] == 1
    assert mc.read_entries(conf)["entries"] == [{"type": "V", "path": p}]


def test_write_rejects_invalid_entry_without_touching_file(tmp_path):
    conf = make_conf(tmp_path, "media_dir=V,/original\n")
    original = conf.read_text(encoding="utf-8")
    result = mc.write_entries([{"type": "V", "path": "/gibt/es/nicht"}], conf_path=conf)
    assert result["ok"] is False
    assert "existiert nicht" in result["error"]
    assert conf.read_text(encoding="utf-8") == original


def test_write_on_missing_conf_creates_it(tmp_path):
    conf = tmp_path / "neu.conf"
    result = mc.write_entries([{"type": "V", "path": str(tmp_path)}], conf_path=conf)
    assert result["ok"] is True
    assert conf.is_file()
    assert mc.read_entries(conf)["entries"] == [{"type": "V", "path": str(tmp_path)}]


# ------------------------------------------------------------------ Explorer
def test_browse_lists_directories_only(tmp_path):
    root = make_tree(tmp_path)
    result = mc.browse(str(root))
    assert result["ok"] is True
    names = [e["name"] for e in result["entries"]]
    assert names == sorted(names, key=str.lower)
    assert set(names) == {"videos", "musik"}  # versteckt + Dateien ausgeblendet
    assert result["parent"] == str(root.parent)
    assert result["truncated"] is False


def test_browse_shows_hidden_on_request(tmp_path):
    root = make_tree(tmp_path)
    names = [e["name"] for e in mc.browse(str(root), show_hidden=True)["entries"]]
    assert ".versteckt" in names


def test_browse_rejects_bad_paths(tmp_path):
    assert mc.browse("relativ")["ok"] is False
    assert mc.browse(str(tmp_path / "fehlt"))["ok"] is False
    file = tmp_path / "datei"
    file.write_text("x", encoding="utf-8")
    assert mc.browse(str(file))["ok"] is False


def test_browse_root_has_no_parent():
    result = mc.browse("/")
    assert result["ok"] is True
    assert result["parent"] is None


# ----------------------------------------------------------------- Vorschau
def test_preview_counts_media_types(tmp_path):
    root = make_tree(tmp_path)
    result = mc.preview(str(root))
    assert result["ok"] is True
    counts = result["counts"]
    assert counts["video"] == 2
    assert counts["audio"] == 1
    assert counts["image"] == 1
    assert counts["total"] == 5  # inkl. notiz.txt
    assert result["complete"] is True


def test_preview_of_empty_dir(tmp_path):
    empty = tmp_path / "leer"
    empty.mkdir()
    counts = mc.preview(str(empty))["counts"]
    assert counts["total"] == 0


def test_preview_rejects_bad_path(tmp_path):
    assert mc.preview("relativ")["ok"] is False
    assert mc.preview(str(tmp_path / "fehlt"))["ok"] is False


# ------------------------------------------------------------------ Status
def test_status_combines_entries_and_preview(tmp_path, monkeypatch):
    root = make_tree(tmp_path)
    conf = make_conf(tmp_path, f"media_dir=V,{root}\n")
    result = mc.status(conf)
    assert result["ok"] is True
    assert result["entries"] == [{"type": "V", "path": str(root)}]
    assert result["preview"][0]["counts"]["video"] == 2


def test_status_honours_default_conf_override(tmp_path, monkeypatch):
    """DEFAULT_CONF-Laufzeit-Auflösung: Patch des Modul-Attributs wirkt."""
    conf = make_conf(tmp_path, "media_dir=A,/tmp\n")
    monkeypatch.setattr(mc, "DEFAULT_CONF", conf)
    assert mc.read_entries()["entries"] == [{"type": "A", "path": "/tmp"}]
    assert mc.status()["conf"] == str(conf)


# ------------------------------------------------------------------ API
@pytest.fixture()
def client(tmp_path, monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import importlib.util

    api_path = Path(__file__).resolve().parent / "dashboard" / "plugin_api.py"
    spec = importlib.util.spec_from_file_location("_smb_dlna_api_test", api_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    conf = make_conf(tmp_path, "media_dir=V,/run/media\n")
    # Laufzeit-Auflösung: Patch greift jetzt
    monkeypatch.setattr(module.media_module, "DEFAULT_CONF", conf)
    # Kein sudo-Backup im Test
    monkeypatch.setattr(module.media_module, "_backup", lambda p: None)

    app = fastapi.FastAPI()
    app.include_router(module.router, prefix="/api/plugins/smb-dlna")
    return TestClient(app), conf


def test_api_lists_media_config(client):
    test_client, _ = client
    r = test_client.get("/api/plugins/smb-dlna/media-config")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["entries"] == [{"type": "V", "path": "/run/media"}]


def test_api_browse_and_rejects_bad_paths(client, tmp_path):
    test_client, _ = client
    r = test_client.get("/api/plugins/smb-dlna/browse",
                        params={"path": str(tmp_path)})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r = test_client.get("/api/plugins/smb-dlna/browse", params={"path": "relativ"})
    assert r.status_code == 400
    assert "absolut" in r.json()["detail"]["error"]


def test_api_saves_entries(client, tmp_path):
    test_client, conf = client
    r = test_client.post("/api/plugins/smb-dlna/media-config",
                         json={"entries": [{"type": "V", "path": str(tmp_path)}],
                               "restart": False})
    assert r.status_code == 200
    assert r.json()["written"] == 1
    assert mc.read_entries(conf)["entries"] == [{"type": "V", "path": str(tmp_path)}]


def test_api_rejects_invalid_payload(client):
    test_client, _ = client
    # fehlendes Feld
    r = test_client.post("/api/plugins/smb-dlna/media-config", json={"restart": False})
    assert r.status_code == 400
    # ungültiger Pfad
    r = test_client.post("/api/plugins/smb-dlna/media-config",
                         json={"entries": [{"type": "V", "path": "/gibt/es/nicht"}],
                               "restart": False})
    assert r.status_code == 400
    # ungültiger Typ
    r = test_client.post("/api/plugins/smb-dlna/media-config",
                         json={"entries": [{"type": "X", "path": "/tmp"}],
                               "restart": False})
    assert r.status_code == 400
    # restart ist kein Wahrheitswert
    r = test_client.post("/api/plugins/smb-dlna/media-config",
                         json={"entries": [], "restart": "ja"})
    assert r.status_code == 400
