# smb_dlna
Plugin schaltet meine smb dnla dienst an und aus

## Fehlerbehebung

**Problem:** MiniDLNA startete nicht wegen nicht existentem Verzeichnis.

**Ursache:** In `/etc/minidlna.conf` stand `media_dir=V,/run/media/fm`, aber dieses Verzeichnis existierte nicht.

**Lösung:** Pfad auf `media_dir=V,/run/media` geändert und Dienst neugestartet:
```bash
sudo sed -i 's|media_dir=V,/run/media/fm|media_dir=V,/run/media|' /etc/minidlna.conf
sudo systemctl restart minidlna.service
```

Nach der Änderung zeigt `smb_dlna_plugin.py --status` allen drei Dienste korrekten Status an.
