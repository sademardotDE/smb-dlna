# smb-dlna — Samba & MiniDLNA für Hermes

Hermes-Plugin zur Steuerung von **Samba** (`smb`, `nmb`) und **MiniDLNA**
(`minidlna`) auf systemd-Systemen: **Status**, **Start/Stopp** und
**Autostart** (`systemctl enable/disable`).

Die host-spezifische Einstellungen dieser Maschine (Systemd-Drop-In,
smb.conf-Anpassungen für alte TV-Clients, bekannte Grenzen) stehen in
[SYSTEM.md](SYSTEM.md).

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
  Auswählen der `media_dir`-Ordner und der optionalen Samba-Freigaben.
- **Hermes Desktop**: Seiten **„Dienste"** (`/dienste`) und **„Medienordner"**
  (`/medienordner`) — jeweils mit Sidebar-Eintrag und Kommando-Palette
  („Dienste öffnen", „Medienordner öffnen"). Die Medienordner-Seite bietet
  Ordnerliste mit Medien-Vorschau, Ordner-Explorer, die Samba-Optionen und
  die Freigaben-Anzeige — derselbe Funktionsumfang wie die Dashboard-Karte.

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
GET  /api/plugins/smb-dlna/samba-status      Samba-Freigaben + Dienststatus
```

## Samba-Freigaben

Mit der Checkbox **„Auch als Samba-Freigabe bereitstellen"** in der Karte
„Medienordner" werden die `media_dir`-Ordner zusätzlich über SMB bereitgestellt —
**ein Share pro Ordner**, der Name leitet sich vom Ordnernamen ab
(`/home/fm/Videos` → `[Videos]`, `/home/fm/Bilder` → `[Bilder]`).

Die Shares stehen in einem klar markierten Block in `/etc/samba/smb.conf`:

```
# BEGIN smb-dlna (auto-generiert — beim Synchronisieren überschrieben)
[Videos]
   comment = smb-dlna Medienordner
   path = /home/fm/Videos
   browseable = yes
   read only = no
   guest ok = no
   valid users = fm
   force user = fm
   create mask = 0664
   directory mask = 0775
# END smb-dlna
```

Verhalten:

- Nur dieser Block wird verändert — fremde Shares (`[copy]`, `[ep]`, `[homes]`,
  …) bleiben unangetastet.
- Entfällt ein Ordner aus der Liste, wird sein Share beim nächsten Speichern
  wieder entfernt; die Freigaben bleiben so immer synchron mit `media_dir`.
- Vor dem Schreiben wird eine Sicherung als
  `/etc/samba/smb.conf.bak-<Zeitstempel>` angelegt, danach prüft `testparm`
  die Datei — scheitert die Prüfung, wird automatisch zurückgerollt.
- Kollidiert ein Ordnername mit einem bereits vergebenen Share-Namen, bricht
  der Speichervorgang mit einer Fehlermeldung ab, statt den fremden Share zu
  überschreiben.
- Nach dem Schreiben werden `smb.service` und `nmb.service` aktiviert
  (Autostart) und gestartet.

Der Freigabe-Zugriff erfolgt als Benutzer `fm` mit Passwort (`guest ok = no`).
Schlägt die Samba-Synchronisierung fehl, bleibt `media_dir` trotzdem
gespeichert — der Fehler erscheint als Warnung in der Karte.

Status der Freigaben zeigt die Karte „Medienordner" unter
`GET /api/plugins/smb-dlna/samba-status` (verwaltete Shares, fremde Shares,
Units aktiv/Autostart).

## Systemd-Units

| Dienst | Units |
| --- | --- |
| `smb` | `smb.service`, `nmb.service` |
| `dlna` | `minidlna.service` |

Start/Stopp/Autostart laufen per `sudo systemctl …`; Statusabfragen ohne sudo.
Fehlt systemd oder sind Units nicht vorhanden, antworten die Tools mit einem
JSON-Fehler statt einer Exception.

## Konfiguration — nur eine, und die ist zentral

Es gibt **genau eine** smb-dlna-Konfiguration, und sie liegt nicht in den
Hermes-Profilen:

| Was | Wo | Gilt für |
| --- | --- | --- |
| Medienordner (`media_dir`, Präfixe A/V/P) | `/etc/minidlna.conf` | alle Profile |
| Samba-Freigaben (auto-generierter Block) | `/etc/samba/smb.conf` | alle Profile |

- Das Plugin liest und schreibt **ausschließlich** diese beiden Dateien unter
  `/etc`. Es gibt keine `plugins.entries.smb-dlna`-Einstellung in irgendeiner
  `config.yaml` und keine weiteren Konfigurationsdateien im Plugin-Verzeichnis.
- Ein Ändern der Medienordner wirkt deshalb sofort für jeden Zugriff — egal
  über welches Profil (Dashboard, Desktop oder Agent-Tools), alle sehen
  denselben Stand.
- Das Einzige, was sich je Profil wiederholt, ist der Aktivierungseintrag
  `- smb-dlna` unter `plugins.enabled` in der `config.yaml`. Das ist keine
  Konfiguration, sondern Hermes' Profil-Mechanik: jedes Profil besitzt eine
  eigene, in sich geschlossene `config.yaml` (verschiedene Modelle, Kanäle,
  Aliase) und erbt **nicht** aus `~/.hermes/config.yaml`. Der Eintrag ist in
  allen Profilen identisch.

**Prüfen, dass überall derselbe Stand läuft:**

```bash
hermes -p <profil> plugins show smb-dlna   # erwartet: v1.4.0
hermes -p <profil> plugins doctor smb-dlna # erwartet: OK
```

## Fehlerbehebung

**Problem:** MiniDLNA startete nicht wegen nicht existentem Verzeichnis.

**Ursache:** In `/etc/minidlna.conf` stand `media_dir=V,/run/media/fm`, aber dieses Verzeichnis existierte nicht.

**Lösung:** Pfad auf `media_dir=V,/run/media` geändert und Dienst neugestartet:

```bash
sudo sed -i 's|media_dir=V,/run/media/fm|media_dir=V,/run/media|' /etc/minidlna.conf
sudo systemctl restart minidlna.service
```

**Problem:** MiniDLNA startet, meldet aber `Permission denied` für die
`media_dir`-Ordner, obwohl Rechte und Benutzer stimmen.

**Ursache:** Die Unit setzt `ProtectHome=on` und hängt `/home` unsichtbar ein.

**Lösung:** Drop-In mit `ProtectHome=read-only` — Details und weitere
Diagnosefälle (leerer Bilder-Index, PNG-Grenze, NTLM-Anmeldung alter
TV-Clients) in [SYSTEM.md](SYSTEM.md).

## Lizenz

MIT (siehe `LICENSE`).
