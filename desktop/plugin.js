import { host, haptic, useValue } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

/**
 * smb_dlna – Hermes Desktop Plugin
 * Zeigt den Status von Samba (smb + nmb) und MiniDLNA an und bietet
 * Palette-Befehle zum Starten/Stoppen der Dienste.
 * Die eigentlichen systemctl-Aufrufe laufen über den Hermes Gateway (host.rpc)
 * auf dem Python Agent-Plugin (smb_dlna_plugin).
 */

const PLUGIN_ID = 'smb-dlna'

// ---------------------------------------------------------------------------
// UI-Komponente: Status-Karte für einen Dienst
// ---------------------------------------------------------------------------
function ServiceStatus({ unit, label, onStart, onStop }) {
  const active = useValue(host.state.pluginServices?.[PLUGIN_ID]?.[unit]?.active ?? false)
  const enabled = useValue(host.state.pluginServices?.[PLUGIN_ID]?.[unit]?.enabled ?? false)

  const handleStart = async () => {
    await onStart()
    haptic('light')
  }

  const handleStop = async () => {
    await onStop()
    haptic('light')
  }

  return jsxs('div', {
    className: 'smb-dlna-service',
    children: [
      jsx('div', {
        className: 'smb-dlna-service-header',
        children: jsxs('div', { className: 'smb-dlna-service-row', children: [
          jsx('span', { className: 'smb-dlna-label', children: label }),
          jsx('span', {
            className: `smb-dlna-badge ${active ? 'smb-dlna-active' : 'smb-dlna-stopped'}`,
            children: active ? 'laufend' : 'gestoppt',
          }),
        ]}),
      }),
      jsx('div', {
        className: 'smb-dlna-service-actions',
        children: jsxs('div', { className: 'smb-dlna-button-group', children: [
          active
            ? jsx('button', {
                className: 'smb-dlna-btn smb-dlna-btn-stop',
                onClick: handleStop,
                children: 'Stoppen',
              })
            : jsx('button', {
                className: 'smb-dlna-btn smb-dlna-btn-start',
                onClick: handleStart,
                children: 'Starten',
              }),
          jsx('button', {
            className: 'smb-dlna-btn smb-dlna-btn-toggle-autostart',
            title: enabled ? 'Autostart aus' : 'Autostart an',
            onClick: async () => {
              await host.rpc('smb_dlna.toggle_autostart', { unit })
              haptic('light')
            },
            children: enabled ? 'A' : 'a',
          }),
        ]}),
      }),
    ],
  })
}

// ---------------------------------------------------------------------------
// UI-Komponente: Hauptansicht (Pane)
// ---------------------------------------------------------------------------
function StatusPane() {
  const refresh = async () => {
    try {
      await host.rpc('smb_dlna.refresh_status', {})
    } catch (e) {
      // Ignoriert – Status wird eh beim nächsten Poll geladen
    }
  }

  return jsxs('div', {
    className: 'smb-dlna-pane',
    children: [
      jsx('div', {
        className: 'smb-dlna-pane-header',
        children: jsxs('div', { className: 'smb-dlna-pane-title', children: [
          jsx('span', { className: 'smb-dlna-icon', children: '☤' }),
          jsx('span', { className: 'smb-dlna-title-text', children: 'Samba & MiniDLNA' }),
        ]}),
      }),
      jsx('div', {
        className: 'smb-dlna-pane-body',
        children: jsxs('div', { className: 'smb-dlna-services-grid', children: [
          jsx(ServiceStatus, {
            unit: 'smb.service',
            label: 'Samba (smb)',
            onStart: () => host.rpc('smb_dlna.start_smb', {}),
            onStop: () => host.rpc('smb_dlna.stop_smb', {}),
          }),
          jsx(ServiceStatus, {
            unit: 'nmb.service',
            label: 'Samba (nmb)',
            onStart: () => host.rpc('smb_dlna.start_nmb', {}),
            onStop: () => host.rpc('smb_dlna.stop_nmb', {}),
          }),
          jsx(ServiceStatus, {
            unit: 'minidlna.service',
            label: 'MiniDLNA',
            onStart: () => host.rpc('smb_dlna.start_dlna', {}),
            onStop: () => host.rpc('smb_dlna.stop_dlna', {}),
          }),
        ]}),
      }),
      jsx('div', {
        className: 'smb-dlna-pane-footer',
        children: jsx('button', {
          className: 'smb-dlna-btn smb-dlna-btn-refresh',
          onClick: refresh,
          children: 'Aktualisieren',
        }),
      }),
    ],
  })
}

// ---------------------------------------------------------------------------
// HermesPlugin Export
// ---------------------------------------------------------------------------
export default {
  id: PLUGIN_ID,
  name: 'SMB & DLNA Steuerung',
  version: '1.0.0',
  description: 'Status und Steuerung von Samba (SMB1 Share ep) und MiniDLNA über Hermes Desktop',

  // Ein Pane erscheint in der Sidebar und kann per ⌘K Palette geöffnet werden
  panes: [
    {
      id: `${PLUGIN_ID}.status`,
      title: 'Samba & DLNA',
      icon: 'network-wired-symbolic',
      component: StatusPane,
      defaultVisible: false,
    },
  ],

  // Palette-Befehle (⌘K)
  paletteCommands: [
    {
      id: `${PLUGIN_ID}.start_smb`,
      title: 'Samba starten (smb + nmb)',
      icon: 'play',
      run: async () => {
        await host.rpc('smb_dlna.start_all', {})
        haptic('light')
      },
    },
    {
      id: `${PLUGIN_ID}.stop_smb`,
      title: 'Samba stoppen (smb + nmb)',
      icon: 'stop',
      run: async () => {
        await host.rpc('smb_dlna.stop_all', {})
        haptic('light')
      },
    },
    {
      id: `${PLUGIN_ID}.start_dlna`,
      title: 'MiniDLNA starten',
      icon: 'play',
      run: async () => {
        await host.rpc('smb_dlna.start_dlna', {})
        haptic('light')
      },
    },
    {
      id: `${PLUGIN_ID}.stop_dlna`,
      title: 'MiniDLNA stoppen',
      icon: 'stop',
      run: async () => {
        await host.rpc('smb_dlna.stop_dlna', {})
        haptic('light')
      },
    },
    {
      id: `${PLUGIN_ID}.status`,
      title: 'Samba & DLNA Status anzeigen',
      icon: 'info',
      run: async () => {
        await host.pane.open(`${PLUGIN_ID}.status`)
        haptic('light')
      },
    },
  ],

  // Status-Bar Chip (rechts unten)
  statusBar: {
    id: `${PLUGIN_ID}.status-chip`,
    label: 'SMB/DLNA',
    tooltip: 'Samba & MiniDLNA Dienststatus',
    onClick: async () => {
      await host.pane.open(`${PLUGIN_ID}.status`)
      haptic('light')
    },
  },

  // Backend-Namespace für RPC-Aufrufe an den Python Agent-Plugin
  rpcNamespace: 'smb_dlna',

  // Automatisch laden, aber deaktiviert bis der User es einschaltet
  defaultEnabled: false,
}
