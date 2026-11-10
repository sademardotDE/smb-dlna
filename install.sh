#!/bin/bash
# =============================================================================
# install.sh – Automatische Installation des smb_dlna Hermes Plugins
# Richtet Python-Plugin, Hermes-Desktop-Plugin und GUI ein.
# =============================================================================
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DESKTOP_PLUGIN_DIR="$HERMES_HOME/desktop-plugins/smb_dlna"

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
info()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[OK]  \033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m[ERR] \033[0m %s\n' "$*" >&2; }

# -----------------------------------------------------------------------------
# Voraussetzungen prüfen
# -----------------------------------------------------------------------------
check_prerequisites() {
    info "Prüfe Voraussetzungen …"

    local missing=0

    command -v python3 >/dev/null 2>&1 || { err "python3 nicht gefunden."; missing=1; }
    command -v systemctl >/dev/null 2>&1 || { err "systemctl nicht gefunden (systemd erforderlich)."; missing=1; }
    command -v sudo >/dev/null 2>&1 || { err "sudo nicht gefunden."; missing=1; }

    if ! command -v zenity >/dev/null 2>&1; then
        warn "zenity nicht gefunden – GUI (smb_dlna_gui) wird nicht funktionieren."
    fi
    if ! command -v pkexec >/dev/null 2>&1; then
        warn "pkexec nicht gefunden – GUI benötigt Root-Rechte über pkexec."
    fi

    if [ "$missing" -ne 0 ]; then
        err "Erforderliche Voraussetzungen fehlen. Installation abgebrochen."
        exit 1
    fi

    ok "Voraussetzungen erfüllt."
}

# -----------------------------------------------------------------------------
# Python-Plugin bereitstellen
# -----------------------------------------------------------------------------
install_python_plugin() {
    info "Richte Python-Plugin ein …"

    chmod +x "$PLUGIN_DIR/smb_dlna_plugin.py"
    chmod +x "$PLUGIN_DIR/smb_dlna_gui"

    ok "Python-Plugin bereit unter $PLUGIN_DIR"
}

# -----------------------------------------------------------------------------
# Hermes Desktop Plugin installieren
# -----------------------------------------------------------------------------
install_desktop_plugin() {
    info "Installiere Hermes-Desktop-Plugin …"

    mkdir -p "$DESKTOP_PLUGIN_DIR"
    cp "$PLUGIN_DIR/desktop/plugin.js" "$DESKTOP_PLUGIN_DIR/plugin.js"

    ok "Desktop-Plugin installiert unter $DESKTOP_PLUGIN_DIR/plugin.js"
    info "In Hermes Desktop: ⌘K → 'Reload desktop plugins', dann unter 'Capabilities → Plugins' aktivieren."
}

# -----------------------------------------------------------------------------
# systemd Units prüfen
# -----------------------------------------------------------------------------
check_systemd_units() {
    info "Prüfe systemd Units …"

    for unit in smb.service nmb.service minidlna.service; do
        if systemctl list-unit-files "$unit" >/dev/null 2>&1; then
            ok "Unit vorhanden: $unit"
        else
            warn "Unit nicht gefunden: $unit (bitte Samba/MiniDLNA installieren und aktivieren)."
        fi
    done
}

# -----------------------------------------------------------------------------
# Hauptablauf
# -----------------------------------------------------------------------------
main() {
    echo "============================================================================="
    echo "  smb_dlna Hermes Plugin – Installation"
    echo "============================================================================="
    echo

    check_prerequisites
    install_python_plugin
    install_desktop_plugin
    check_systemd_units

    echo
    echo "============================================================================="
    ok "Installation abgeschlossen."
    echo
    echo "Nächste Schritte:"
    echo "  1. Hermes Desktop starten und ⌘K → 'Reload desktop plugins' ausführen."
    echo "  2. Unter 'Capabilities → Plugins' das Plugin 'smb_dlna' aktivieren."
    echo "  3. GUI starten: $PLUGIN_DIR/smb_dlna_gui"
    echo "  4. CLI testen:  python3 $PLUGIN_DIR/smb_dlna_plugin.py --status"
    echo
    echo "Hinweis: systemctl-Aufrufe benötigen sudo/pkexec-Rechte."
    echo "============================================================================="
}

main "$@"
