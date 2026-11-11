# smb-dlna — Samba & MiniDLNA für Hermes

Hermes-Plugin zur Steuerung von **Samba** (`smb`, `nmb`) und **MiniDLNA**
(`minidlna`) auf systemd-Systemen: **Status**, **Start/Stopp** und
**Autostart** (`systemctl enable/disable`).

## Installation

```bash
hermes plugins install sademardotDE/smb-dlna
hermes plugins enable smb-dlna
hermes gateway restart
```

Prüfen:

```bash
hermes plugins doctor smb-dlna
hermes services status
```

## Agent-Tools

| Tool | Zweck |
| --- | --- |
| `services_status` | Status (aktiv/gestoppt, Autostart) von smb/nmb/minidlna |
| `services_start` / `services_stop` | Dienste starten/stoppen (`smb`, `dlna` oder `all`) |
| `services_enable` / `services_disable` | Autostart schalten (`smb`, `dlna` oder `all`) |

## CLI

```bash
hermes services status
hermes services start                 # all
hermes services stop smb
hermes services enable dlna
hermes services disable all
```

## Oberflächen

- **Dashboard-Tab „Dienste"** (`/dienste`): Karten für Samba und MiniDLNA mit
  Status, Start/Stopp, Autostart.
- **Hermes Desktop**: Seite „Dienste" (Route `/dienste`, Sidebar + Palette
  „Dienste öffnen").

## Systemd-Units

| Dienst | Units |
| --- | --- |
| `smb` | `smb.service`, `nmb.service` |
| `dlna` | `minidlna.service` |

Start/Stopp/Autostart laufen per `sudo systemctl …`; Statusabfragen ohne sudo.
Fehlt systemd oder sind Units nicht vorhanden, antworten die Tools mit einem
JSON-Fehler statt einer Exception.

## Fehlerbehebung

**Problem:** MiniDLNA startete nicht wegen nicht existentem Verzeichnis.

**Ursache:** In `/etc/minidlna.conf` stand `media_dir=V,/run/media/fm`, aber dieses Verzeichnis existierte nicht.

**Lösung:** Pfad auf `media_dir=V,/run/media` geändert und Dienst neugestartet:

```bash
sudo sed -i 's|media_dir=V,/run/media/fm|media_dir=V,/run/media|' /etc/minidlna.conf
sudo systemctl restart minidlna.service
```

## Lizenz

MIT (siehe `LICENSE`).
