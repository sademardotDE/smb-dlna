#!/usr/bin/env python3
"""Tests für die Samba-Freigaben der Medienordner (samba_config)."""

from __future__ import annotations

from pathlib import Path

import pytest

import samba_config as sc

BASE_CONF = """[global]
   workgroup = WORKGROUP

[copy]
   comment = Scanner output share
   path = /home/fm/scans
   read only = no

[ep]
   comment = externe Platten
   path = /run/media/fm
"""


@pytest.fixture()
def conf(tmp_path: Path) -> Path:
    path = tmp_path / "smb.conf"
    path.write_text(BASE_CONF, encoding="utf-8")
    return path


@pytest.fixture()
def ordner(tmp_path: Path) -> dict[str, Path]:
    """Zwei Medien-Ordner wie in der media_dir-Konfiguration."""
    videos = tmp_path / "Videos"
    bilder = tmp_path / "Bilder"
    videos.mkdir()
    bilder.mkdir()
    return {"videos": videos, "bilder": bilder}


# ------------------------------------------------------------ Share-Name
@pytest.mark.parametrize("folder,erwartet", [
    ("/home/fm/Videos", "Videos"),
    ("/home/fm/Schreibtisch/Music", "Music"),
    ("/home/fm/Meine Fotos!", "Meine_Fotos"),
    ("/weird//", "weird"),
    ("/", "Medien"),
])
def test_share_name(folder, erwartet):
    assert sc.share_name(folder) == erwartet


def test_share_name_ist_immer_gültig():
    name = sc.share_name("/home/fm/[globale] Sektion?")
    assert "[" not in name and "]" not in name
    assert name and len(name) <= sc._MAX_NAME


# ---------------------------------------------------------------- Lesen
def test_read_shares_trennt_managed_und_foreign(conf, ordner):
    result = sc.read_shares(conf)
    assert result["ok"] is True
    assert result["managed"] == []
    assert result["foreign"] == ["copy", "ep"]
    assert "global" not in result["foreign"], "[global] ist keine Freigabe"


def test_read_shares_ohne_datei(tmp_path):
    result = sc.read_shares(tmp_path / "fehlt.conf")
    assert result["ok"] is True
    assert result["exists"] is False


def test_read_shares_nach_sync(conf, ordner):
    sc.sync([{"path": str(ordner["videos"])}], conf_path=conf, ensure=False)
    result = sc.read_shares(conf)
    assert result["managed"] == ["Videos"]
    assert result["foreign"] == ["copy", "ep"]


# --------------------------------------------------------------- Schreiben
def test_sync_legt_freigaben_an_und_behält_fremde(conf, ordner):
    result = sc.sync([{"path": str(ordner["videos"])}, {"path": str(ordner["bilder"])}],
                     conf_path=conf, ensure=False)
    assert result["ok"] is True
    assert [s["name"] for s in result["shares"]] == ["Videos", "Bilder"]
    assert result["backup"]

    text = conf.read_text(encoding="utf-8")
    assert "[Videos]" in text and "[Bilder]" in text
    assert f"path = {ordner['videos']}" in text
    assert "[copy]" in text and "[ep]" in text, "fremde Shares bleiben"
    assert "path = /home/fm/scans" in text
    assert sc.BEGIN_MARK in text and sc.END_MARK in text


def test_sync_entfernt_freigaben_für_entfallene_ordner(conf, ordner):
    sc.sync([{"path": str(ordner["videos"])}, {"path": str(ordner["bilder"])}],
            conf_path=conf, ensure=False)
    result = sc.sync([{"path": str(ordner["bilder"])}], conf_path=conf, ensure=False)
    assert result["ok"] is True

    text = conf.read_text(encoding="utf-8")
    assert "[Videos]" not in text, "entfallener Share wird entfernt"
    assert "[Bilder]" in text
    assert "[copy]" in text


def test_sync_ist_idempotent(conf, ordner):
    erster = sc.sync([{"path": str(ordner["videos"])}], conf_path=conf, ensure=False)
    zweiter = sc.sync([{"path": str(ordner["videos"])}], conf_path=conf, ensure=False)
    assert erster["ok"] and zweiter["ok"]
    assert conf.read_text(encoding="utf-8").count(sc.BEGIN_MARK) == 1
    assert conf.read_text(encoding="utf-8").count("[Videos]") == 1


def test_sync_ablehnt_ungültige_pfade(conf, ordner):
    original = conf.read_text(encoding="utf-8")
    result = sc.sync([{"path": "/gibt/es/nicht"}], conf_path=conf, ensure=False)
    assert result["ok"] is False
    assert "existiert nicht" in result["error"]
    assert conf.read_text(encoding="utf-8") == original, "Datei unverändert"


def test_sync_ablehnt_leeren_pfad(conf):
    result = sc.sync([{"path": ""}], conf_path=conf, ensure=False)
    assert result["ok"] is False


def test_sync_ablehnt_kollision_mit_fremdem_share(conf, tmp_path):
    ep_ordner = tmp_path / "ep"
    ep_ordner.mkdir()
    original = conf.read_text(encoding="utf-8")
    result = sc.sync([{"path": str(ep_ordner)}], conf_path=conf, ensure=False)
    assert result["ok"] is False
    assert "bereits vergeben" in result["error"]
    assert conf.read_text(encoding="utf-8") == original


def test_sync_ohne_smb_conf(tmp_path, ordner):
    result = sc.sync([{"path": str(ordner["videos"])}],
                     conf_path=tmp_path / "fehlt.conf", ensure=False)
    assert result["ok"] is False
    assert "nicht gefunden" in result["error"]


def test_sync_rollt_zurück_wenn_testparm_scheitert(conf, ordner, monkeypatch):
    """Schlägt die Konfigurationsprüfung fehl, bleibt die alte Datei bestehen."""
    original = conf.read_text(encoding="utf-8")

    class Pessimal:
        returncode = 1
        stderr = "invalid"
        stdout = ""

    real_run = sc.subprocess.run

    def fake_run(cmd, **kwargs):
        if "testparm" in cmd:
            return Pessimal()
        return real_run(cmd, **kwargs)  # cp/backup laufen normal mit

    monkeypatch.setattr(sc.subprocess, "run", fake_run)
    result = sc.sync([{"path": str(ordner["videos"])}], conf_path=conf, ensure=False)

    assert result["ok"] is False
    assert result.get("rolled_back") is True
    assert conf.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------- Status
def test_status_listet_freigaben_mit_pfaden(conf, ordner):
    sc.sync([{"path": str(ordner["videos"])}, {"path": str(ordner["bilder"])}],
            conf_path=conf, ensure=False)
    result = sc.status(conf)
    assert result["ok"] is True
    assert {s["name"]: s["path"] for s in result["shares"]} == {
        "Videos": str(ordner["videos"]),
        "Bilder": str(ordner["bilder"]),
    }
    assert "units" in result["service"]
    assert set(result["service"]["units"]) == {"smb.service", "nmb.service"}


def test_status_ohne_datei(tmp_path):
    result = sc.status(tmp_path / "fehlt.conf")
    assert result["ok"] is True
    assert result["shares"] == []


# ------------------------------------------------------------------- API
@pytest.fixture()
def client(tmp_path, monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import importlib.util

    api_path = Path(__file__).resolve().parent / "dashboard" / "plugin_api.py"
    spec = importlib.util.spec_from_file_location("_smb_dlna_api_samba", api_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Beide Konfigpfade auf temporäre Dateien lenken — die realen
    # /etc/minidlna.conf und /etc/samba/smb.conf bleiben unberührt.
    minidlna = tmp_path / "minidlna.conf"
    minidlna.write_text("port=8200\n", encoding="utf-8")
    smbconf = tmp_path / "smb.conf"
    smbconf.write_text(BASE_CONF, encoding="utf-8")
    medien = tmp_path / "Videos"
    medien.mkdir()

    monkeypatch.setattr(module.media_module, "DEFAULT_CONF", minidlna)
    monkeypatch.setattr(module.media_module, "_backup", lambda p: None)
    monkeypatch.setattr(module.samba_module, "DEFAULT_CONF", smbconf)
    monkeypatch.setattr(module.samba_module, "_backup", lambda p: None)
    # Kein systemctl-Aufruf im Test
    monkeypatch.setattr(module.samba_module, "ensure_running",
                        lambda: {"ok": True, "changed": False})
    monkeypatch.setattr(module.media_module, "restart_minidlna",
                        lambda: {"ok": True, "active": True})

    app = fastapi.FastAPI()
    app.include_router(module.router, prefix="/api/plugins/smb-dlna")
    return TestClient(app), smbconf, medien, module


def test_api_samba_status(client):
    test_client, _, _, _ = client
    r = test_client.get("/api/plugins/smb-dlna/samba-status")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["managed"] == []
    assert "ep" in body["foreign"]


def test_api_speichert_mit_samba_freigabe(client):
    test_client, smbconf, medien, _ = client
    r = test_client.post("/api/plugins/smb-dlna/media-config",
                         json={"entries": [{"type": "V", "path": str(medien)}],
                               "restart": False, "samba": True})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["samba"]["ok"] is True
    assert [s["name"] for s in body["samba"]["shares"]] == ["Videos"]
    assert "[Videos]" in smbconf.read_text(encoding="utf-8")
    assert "[ep]" in smbconf.read_text(encoding="utf-8")


def test_api_samba_deaktiviert_berührt_smb_conf_nicht(client):
    test_client, smbconf, medien, _ = client
    vorher = smbconf.read_text(encoding="utf-8")
    r = test_client.post("/api/plugins/smb-dlna/media-config",
                         json={"entries": [{"type": "V", "path": str(medien)}],
                               "restart": False, "samba": False})
    assert r.status_code == 200
    assert "samba" not in r.json()
    assert smbconf.read_text(encoding="utf-8") == vorher


def test_api_samba_fehler_als_warnung(client, monkeypatch):
    test_client, _, medien, module = client
    # Das Paket-Modul `_smb_dlna_dashboard.samba_config` ist ein anderes
    # Objekt als das flache `samba_config` — der API-Handler greift über
    # `module.samba_module.sync` zu, also dort patchen.
    monkeypatch.setattr(module.samba_module, "sync",
                        lambda *a, **k: {"ok": False, "error": "testparm abgelehnt"})
    r = test_client.post("/api/plugins/smb-dlna/media-config",
                         json={"entries": [{"type": "V", "path": str(medien)}],
                               "restart": False, "samba": True})
    assert r.status_code == 200, "media_dir gilt trotz samba-Fehler"
    body = r.json()
    assert body["ok"] is True
    assert body["samba"]["ok"] is False
    assert "Samba-Freigabe schlug fehl" in body["warning"]


def test_api_samba_status_ungültiges_feld(client):
    test_client, _, _, _ = client
    r = test_client.post("/api/plugins/smb-dlna/media-config",
                         json={"entries": [], "samba": "ja"})
    assert r.status_code == 400
    assert "samba" in r.json()["detail"]["error"]
