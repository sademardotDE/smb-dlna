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
  Status, Start/Stopp, Autostart — plus Karte **„Medienordner"** zum
  Auswählen der `media_dir`-Ordner.
- **Hermes Desktop**: Seite „Dienste" (Route `/dienste`, Sidebar + Palette
  „Dienste öffnen").

## Medienordner (media_dir)

Im Dashboard-Tab unter der Karte **„Medienordner"** legen Sie fest, welche
Ordner MiniDLNA indexiert — mehrere Einträge, jeweils mit Typ:

| Präfix | Bedeutung |
| --- | --- |
| `A` | Audio (z. B. `/home/fm/Musik`) |
| `V` | Video (z. B. `/home/fm/Videos`) |
| `P` | Bilder |

Pro Ordner werden die erkannten Medien gezählt (Videos · Audio · Bilder), sodass
vor dem Speichern sichtbar ist, ob der gewählte Ordner tatsächlich Dateien
enthält.

- **Ordner hinzufügen / Ändern** öffnet einen Explorer mit Verzeichnisnavigation,
  „Nach oben", Schnellwahl (`/home`, `/media`, `/mnt`) und optional eingeblendeten
  versteckten Ordnern.
- **Speichern** schreibt die Einträge nach `/etc/minidlna.conf`. Vorher wird
  automatisch eine Sicherung als `/etc/minidlna.conf.bak-<Zeitstempel>` angelegt.
- **MiniDLNA nach dem Speichern neu starten** (Checkbox) lässt die Änderung
  sofort wirken — ohne Neustart greift sie erst beim nächsten Start des Dienstes.

API-Endpunkte (hinter der Dashboard-Auth):

```
GET  /api/plugins/smb-dlna/media-config      Einträge + Medien-Vorschau
GET  /api/plugins/smb-dlna/browse?path=…     Verzeichnisnavigation (nur lesend)
POST /api/plugins/smb-dlna/media-config      {"entries":[{"type":"V","path":"…"}],"restart":false}
```

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
