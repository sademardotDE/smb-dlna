# System-Setup dieser Maschine

Host-spezifische Einstellungen, die für Samba und MiniDLNA nötig waren.
Das Plugin selbst braucht davon nichts — hier steht, warum die Konfiguration
so aussieht, und wie man Fehler wiedererkennt.

## MiniDLNA

### Schutz der Unit: `ProtectHome`

Die mitgelieferte Unit setzt `ProtectHome=on`. Das hängt `/home` für den
Prozess unsichtbar ein — selbst wenn Ordner und Benutzer korrekt sind,
scheitert jeder Zugriff mit `Permission denied`:

```
error: Media directory "V,/home/fm/Videos" not accessible [Permission denied]
```

Abhilfe ist ein Drop-In (nicht die Original-Unit anfassen):

`/etc/systemd/system/minidlna.service.d/override.conf`

```ini
[Service]
DynamicUser=no
User=fm
Group=fm
# /home darf gelesen werden (media_dir), geschrieben wird nur in den Cache
ProtectHome=read-only
```

Danach `sudo systemctl daemon-reload && sudo systemctl restart minidlna.service`.

### Index-Datenbank

Die Unit startet standardmäßig mit `DynamicUser=yes` und legt
`/var/cache/minidlna/` als `nobody` an. Steht in der Unit `User=fm`, gehört
die Datenbank aber noch `nobody` — der Dienst kann sie nicht schreiben:

```bash
sudo chown -R fm:fm /var/cache/minidlna
```

Erkennbar an `files.db` mit fremdem Eigentümer oder an einem Index, der nach
Neustart leer bleibt, obwohl `media_dir` stimmt.

### Grenze: keine PNG-Indizierung

Dieser MiniDLNA-Build (1.3.3) indexiert JPG, aber **keine PNG-Dateien** —
die Extension-Liste im Binary enthält `.jpg`/`.jpeg`, kein `.png`. Prüfung:

```bash
# Testdateien direkt in den media_dir-Ordner (nicht in einen versteckten
# Ordner — Verzeichnisse mit führendem Punkt überspringt MiniDLNA):
convert -size 1x1 xc:red /home/fm/Bilder/ztest.jpg
# … Neustart, dann in der Datenbank nachsehen:
sqlite3 /var/cache/minidlna/files.db "select PATH from DETAILS where PATH like '%ztest%';"
```

Erscheint das JPG, das PNG aber nicht, ist das ein Grenze des Builds und kein
Rechteproblem. Auf diesem Host bleiben die Bilder PNG — am TV erscheinen
deshalb nur die Videos. Wer die Bilder mitsehen will, braucht einen anderen
Server (z. B. Gerbera) oder JPG-Kopien in einem zweiten `media_dir`.

## Samba

### Freigaben-Block

Die Medien-Shares stehen zwischen den Markierungen
`# BEGIN smb-dlna … # END smb-dlna` in `/etc/samba/smb.conf`. Nur dieser
Block wird vom Plugin überschrieben; alles außerhalb ist fremd und bleibt
unangetastet.

Entfernte Fremd-Freigabe: `[ep]` (zeigte auf den nicht existierenden Pfad
`/run/media/fm`). Der Share war tot und ist rausgenommen worden — ergänzt
sich aber nicht selbst, er wird nur nicht mehr angelegt.

### Alte TV-Clients: SMB1 und NTLMv1

Im `[global]`-Block:

```
server min protocol = NT1      # ab SMB1 erlaubt
ntlm auth = yes                # NTLMv1 angenommen (sonst ntlmv2-only)
lanman auth = yes              # reines LM, veraltet, aber für sehr alte Geräte
client ntlmv2 auth = no        # ausgehend ebenfalls NTLMv1
```

Ohne die NTLM-Zeilen schlägt selbst mit SMB1 die **Anmeldung** fehl — ein
alter Client scheitert mit `NT_STATUS_ACCESS_DENIED`, obwohl das Protokoll
passt. Die `lanman`-Optionen sind bei Samba als *deprecated* markiert und
melden beim Start eine Warnung; für alte Clients zählt vor allem
`ntlm auth = yes`.

Prüfen lässt sich das Protokoll erzwungen:

```bash
smbclient -L localhost -N --max-protocol=NT1
```

### Sicherungen

Vor jeder manuellen Änderung an `/etc/samba/smb.conf`:

```bash
sudo cp -p /etc/samba/smb.conf /etc/samba/smb.conf.bak-$(date +%Y%m%d-%H%M%S)
sudo testparm -s   # danach immer prüfen
```

## Diagnosekette

Wenn am TV nichts erscheint, derweil in dieser Reihenfolge prüfen:

1. `systemctl status minidlna.service` — läuft der Dienst?
2. `journalctl -u minidlna.service -n 50` — `Permission denied`? → Drop-In.
3. `curl -s http://127.0.0.1:8200/rootDesc.xml | head -3` — antwortet HTTP?
4. Index-Stand: `sqlite3 /var/cache/minidlna/files.db "select count(*) from DETAILS;"`
5. Samba: `smbclient -L localhost -N` — erscheinen die Shares?
6. Protokoll/Auth: `--max-protocol=NT1`, Log unter `/var/log/samba/`.

## Übernahme ins installierte Plugin

Das Plugin liegt in `/home/fm/smbdlna` (Entwicklung) und wird von dort ins
Profil kopiert — `hermes plugins install` akzeptiert nur Git-Quellen:

```bash
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='.pytest_cache' \
      /home/fm/smbdlna/ /home/fm/.hermes/profiles/scout/plugins/smb-dlna/
hermes plugins doctor smb-dlna
systemctl --user restart hermes-dashboard.service
```

Tests (venv mit pytest **und** fastapi, `-p no:syrupy` sonst Argumentkonflikt):

```bash
/home/fm/.venv/bin/python -m pytest test_plugin.py test_media_config.py \
    test_samba_config.py -q -p no:syrupy
```
