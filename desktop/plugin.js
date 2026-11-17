// smb-dlna — Desktop half. Pages (route + sidebar + palette command) for
// Samba (smb/nmb) and MiniDLNA: status, start/stop, autostart — plus the
// media folders page (media_dir) with folder explorer, media preview and
// optional Samba shares. Talks to this package's dashboard backend via
// ctx.rest (namespace /api/plugins/smb-dlna).
import { host, PALETTE_AREA, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const PATH = '/dienste'
const ID = 'smb-dlna'
const LABELS = { smb: 'Samba (smb + nmb)', dlna: 'MiniDLNA' }

const MEDIA_PATH = '/medienordner'
const TYPES = [
  { value: 'A', label: 'Audio (A)' },
  { value: 'V', label: 'Video (V)' },
  { value: 'P', label: 'Bilder (P)' }
]
const MOUNTS = ['/home', '/media', '/mnt', '/run/media']

const cardStyle = {
  border: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.25))',
  borderRadius: '8px',
  padding: '12px',
  marginBottom: '10px'
}
const muted = { fontSize: '12px', color: 'var(--ui-text-secondary, #888)' }
const mono = { fontFamily: 'var(--ui-font-mono, ui-monospace, monospace)' }
const buttonStyle = {
  padding: '4px 10px',
  fontSize: '12px',
  borderRadius: '6px',
  border: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.35))',
  background: 'transparent',
  color: 'var(--ui-text-primary, inherit)',
  cursor: 'pointer'
}
const inputStyle = {
  fontSize: '12px',
  padding: '3px 6px',
  borderRadius: '6px',
  border: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.35))',
  background: 'var(--ui-background, transparent)',
  color: 'var(--ui-text-primary, inherit)'
}
const rowStyle = {
  display: 'flex',
  gap: '8px',
  alignItems: 'center',
  flexWrap: 'wrap',
  padding: '8px 0',
  borderBottom: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.12))'
}

function Btn(props) {
  return jsx('button', {
    onClick: props.onClick,
    disabled: !!props.disabled,
    type: 'button',
    style: actionButtonStyle(props),
    children: props.children
  })
}

function actionButtonStyle(props) {
  return Object.assign({}, buttonStyle, props && props.disabled ? { opacity: 0.5, cursor: 'default' } : {})
}

function errText(err) {
  return err && err.message ? err.message : String(err)
}

function fmtCounts(counts) {
  if (!counts) return ''
  const parts = []
  if (counts.video) parts.push(counts.video + ' Videos')
  if (counts.audio) parts.push(counts.audio + ' Audio')
  if (counts.image) parts.push(counts.image + ' Bilder')
  if (!parts.length) parts.push(counts.total + ' Dateien')
  return parts.join(' · ')
}

// ------------------------------------------------------------------ Dienste
function ServicesPage({ rest }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState({})

  function load() {
    rest('/services')
      .then((r) => { setData(r); setError(null) })
      .catch((err) => setError(errText(err)))
  }

  useEffect(() => {
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [])

  function act(service, action) {
    setBusy((prev) => Object.assign({}, prev, { [service + action]: true }))
    setError(null)
    rest('/services/' + service + '/' + action, { method: 'POST', body: {} })
      .then(() => load())
      .catch((err) => setError(errText(err)))
      .then(() => setBusy((prev) => { const next = Object.assign({}, prev); delete next[service + action]; return next }))
  }

  if (error && !data) {
    return jsx('div', { style: { padding: '16px', color: 'var(--ui-danger, #d33)' }, children: 'Fehler: ' + error })
  }
  if (!data) return jsx('div', { style: { padding: '16px' }, children: 'Lade Dienste …' })

  const services = data.services || {}
  return jsxs('div', { style: { padding: '16px', maxWidth: '760px' }, children: [
    jsx('h2', { style: { marginTop: 0 }, children: 'Samba & MiniDLNA' }),
    Object.keys(services).map((name) => {
      const svc = services[name] || {}
      const units = svc.units || {}
      const active = !!svc.active
      const enabled = !!svc.enabled
      return jsxs('div', { style: cardStyle, children: [
        jsxs('div', { style: { display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }, children: [
          jsx('strong', { children: LABELS[name] || name }),
          jsx('span', { style: muted, children: active ? 'läuft' : 'gestoppt' }),
          jsx('span', { style: muted, children: enabled ? 'Autostart an' : 'Autostart aus' })
        ] }),
        jsx('div', { style: Object.assign({}, muted, { marginTop: '4px' }), children:
          Object.keys(units).map((unit) => unit + ': ' + (units[unit].active ? 'aktiv' : 'inaktiv')).join(' · ') }),
        jsxs('div', { style: { marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }, children: [
          jsx(Btn, {
            onClick: () => act(name, active ? 'stop' : 'start'),
            disabled: busy[name + 'start'] || busy[name + 'stop'],
            children: active ? 'Stoppen' : 'Starten'
          }),
          jsx(Btn, {
            onClick: () => act(name, enabled ? 'disable' : 'enable'),
            disabled: busy[name + 'enable'] || busy[name + 'disable'],
            children: enabled ? 'Autostart aus' : 'Autostart an'
          })
        ] })
      ] }, name)
    }),
    error ? jsx('div', { style: { color: 'var(--ui-danger, #d33)', fontSize: '12px' }, children: 'Fehler: ' + error }) : null
  ] })
}

// --------------------------------------------------- Ordner-Explorer (Overlay)
function FolderExplorer({ rest, startPath, onPick, onClose }) {
  const [view, setView] = useState(null)
  const [error, setError] = useState(null)
  const [hidden, setHidden] = useState(false)
  const idRef = useRef(0)

  function load(path, note) {
    if (!path) return
    const id = ++idRef.current
    rest('/browse?path=' + encodeURIComponent(path) + '&show_hidden=' + (hidden ? 'true' : 'false'))
      .then((r) => {
        if (idRef.current !== id) return
        setView(r)
        setError(note || null)
      })
      .catch((err) => {
        if (idRef.current !== id) return
        // auf den übergeordneten Pfad wechseln, falls nicht erreichbar
        const up = path.slice(0, path.lastIndexOf('/')) || '/'
        if (up !== path) {
          load(up, '„' + path + '“ ist nicht erreichbar – gewechselt zu „' + up + '“.')
          return
        }
        setError(errText(err))
      })
  }

  useEffect(() => {
    idRef.current = 0
    setView(null)
    setError(null)
    setHidden(false)
    load(startPath)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startPath])

  const current = (view && view.path) || startPath

  let body
  if (error && !view) {
    body = jsx('p', { style: { color: 'var(--ui-danger, #d33)' }, children: 'Fehler: ' + error })
  } else if (!view) {
    body = jsx('p', { style: muted, children: 'Lade Verzeichnisse …' })
  } else if (!view.entries || !view.entries.length) {
    body = jsx('p', { style: muted, children: 'Keine Unterverzeichnisse – dieses Verzeichnis kann gewählt werden.' })
  } else {
    body = jsxs('div', {
      style: {
        maxHeight: '40vh',
        overflowY: 'auto',
        border: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.2))',
        borderRadius: '6px'
      },
      children: [view.entries.map((entry) => jsx('button', {
        key: entry.path,
        type: 'button',
        onClick: () => load(entry.path),
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          width: '100%',
          padding: '7px 10px',
          background: 'transparent',
          border: '0',
          borderBottom: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.12))',
          color: 'var(--ui-text-primary, inherit)',
          textAlign: 'left',
          cursor: 'pointer',
          fontSize: '13px'
        },
        children: [
          jsx('span', { style: { opacity: 0.6 }, children: '▸' }),
          jsx('span', { style: mono, children: entry.name })
        ]
      }, entry.path))]
    })
  }

  return jsxs('div', {
    style: {
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    },
    onClick: onClose,
    children: [
      jsxs('div', {
        style: {
          background: 'var(--ui-background, #1b1b1b)', borderRadius: '10px',
          padding: '16px', width: 'min(680px, 92vw)', maxHeight: '84vh',
          overflow: 'auto'
        },
        onClick: (e) => e.stopPropagation(),
        children: [
          jsx('h3', { style: { marginTop: 0 }, children: 'Ordner auswählen' }),
          jsx('div', { style: Object.assign({ fontWeight: 600, marginBottom: '8px' }, mono), children: current }),
          jsxs('div', { style: { display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }, children: [
            jsx(Btn, {
              disabled: !view || !view.parent,
              onClick: () => { if (view && view.parent) load(view.parent) },
              children: 'Nach oben'
            }),
            jsxs('label', {
              style: { fontSize: '12px', display: 'flex', gap: '6px', alignItems: 'center', cursor: 'pointer' },
              children: [
                jsx('input', {
                  type: 'checkbox',
                  checked: hidden,
                  onChange: () => {
                    const next = !hidden
                    setHidden(next)
                    if (view && view.path) {
                      const id = ++idRef.current
                      rest('/browse?path=' + encodeURIComponent(view.path) + '&show_hidden=' + (next ? 'true' : 'false'))
                        .then((r) => { if (idRef.current === id) { setView(r); setError(null) } })
                        .catch((err) => { if (idRef.current === id) setError(errText(err)) })
                    }
                  }
                }),
                jsx('span', { children: 'Versteckte zeigen' })
              ]
            }),
            MOUNTS.map((mount) => jsx(Btn, { key: mount, onClick: () => load(mount), children: mount }, mount))
          ] }),
          jsx('div', { style: { marginTop: '8px' }, children: body }),
          error ? jsx('p', { style: { color: 'var(--ui-danger, #d33)', fontSize: '12px' }, children: 'Hinweis: ' + error }) : null,
          jsxs('div', {
            style: { display: 'flex', gap: '8px', justifyContent: 'space-between', marginTop: '12px' },
            children: [
              jsx('span', { style: Object.assign({}, mono, { fontSize: '12px', opacity: .7 }), children: current }),
              jsxs('div', { style: { display: 'flex', gap: '8px' }, children: [
                jsx(Btn, { onClick: onClose, children: 'Abbrechen' }),
                jsx(Btn, { onClick: () => onPick(current), children: 'Diesen Ordner wählen' })
              ] })
            ]
          })
        ]
      })
    ]
  })
}

// ------------------------------------------------------------- Medienordner
function MediaPage({ rest }) {
  const [data, setData] = useState(null)
  const [edits, setEdits] = useState([])
  const [saved, setSaved] = useState([])
  const [restart, setRestart] = useState(false)
  const [samba, setSamba] = useState(true)
  const [sambaInfo, setSambaInfo] = useState(null)
  const [busy, setBusy] = useState('')
  const [info, setInfo] = useState('')
  const [error, setError] = useState(null)
  const [explorer, setExplorer] = useState(null)

  function loadSamba() {
    rest('/samba-status')
      .then((r) => setSambaInfo(r))
      .catch(() => setSambaInfo(null))
  }

  function apply(r) {
    const entries = (r.entries || []).map((e) => ({ type: e.type || 'V', path: e.path }))
    setData(r)
    setEdits(entries)
    setSaved(entries)
    setError(null)
  }

  function load() {
    rest('/media-config')
      .then((r) => { apply(r); })
      .catch((err) => setError(errText(err)))
    loadSamba()
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const dirty = JSON.stringify(edits) !== JSON.stringify(saved)
  const previewByPath = {}
  ;((data && data.preview) || []).forEach((p) => { previewByPath[p.path] = p })

  function setType(index, type) {
    setEdits((prev) => prev.map((e, i) => (i === index ? { type, path: e.path } : e)))
  }
  function remove(index) {
    setEdits((prev) => prev.filter((_, i) => i !== index))
  }
  function pickFolder(path) {
    setExplorer(null)
    setEdits((prev) => prev.concat([{ type: 'V', path }]))
  }

  function save() {
    setBusy('save')
    setError(null)
    setInfo('')
    rest('/media-config', {
      method: 'POST',
      body: { entries: edits, restart: restart, samba: samba }
    })
      .then((r) => {
        const parts = [(r.written || 0) + ' Eintrag(e) gespeichert']
        if (r.backup) parts.push('Sicherung: ' + r.backup)
        if (r.restart) {
          parts.push(r.restart.ok ? 'MiniDLNA neu gestartet'
            : 'MiniDLNA-Start fehlgeschlagen: ' + r.restart.error)
        }
        if (r.samba) {
          if (r.samba.ok) {
            const names = (r.samba.shares || []).map((s) => s.name)
            parts.push('Samba-Freigabe(n): ' + (names.join(', ') || 'keine'))
            if (r.samba.service && r.samba.service.ok) parts.push('Samba läuft')
          } else {
            parts.push('Samba: ' + (r.samba.error || 'Fehler'))
          }
        }
        if (r.warning) parts.push('Achtung: ' + r.warning)
        setInfo(parts.join(' · '))
        if (r.warning) setError(r.warning)
        load()
      })
      .catch((err) => setError(errText(err)))
      .then(() => setBusy(''))
  }

  if (error && !data) {
    return jsx('div', { style: { padding: '16px', color: 'var(--ui-danger, #d33)' }, children: 'Fehler: ' + error })
  }
  if (!data) return jsx('div', { style: { padding: '16px' }, children: 'Lade Medienordner …' })

  const rows = edits.map((entry, index) => {
    const preview = previewByPath[entry.path]
    let meta = ''
    if (preview) {
      meta = preview.error
        ? preview.error
        : fmtCounts(preview.counts) + (preview.complete === false ? ' (gekürzt)' : '')
    }
    return jsxs('div', { style: rowStyle, children: [
      jsx('select', {
        value: entry.type,
        onChange: (e) => setType(index, e.target.value),
        style: Object.assign({}, inputStyle, { width: '110px' }),
        children: TYPES.map((t) => jsx('option', { value: t.value, children: t.label }, t.value))
      }),
      jsx('span', {
        style: Object.assign({}, mono, { fontSize: '13px', flex: '1 1 auto', wordBreak: 'break-all' }),
        children: entry.path
      }),
      meta ? jsx('span', { style: muted, children: meta }) : null,
      jsx(Btn, { onClick: () => setExplorer(entry.path), children: 'Ändern' }),
      jsx(Btn, { onClick: () => remove(index), children: 'Entfernen' })
    ] }, entry.path + index)
  })

  const sambaBadge = (text) => jsx('span', {
    style: Object.assign({}, muted, {
      padding: '1px 7px',
      border: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.3))',
      borderRadius: '999px'
    }),
    children: text
  })

  return jsxs('div', { style: { padding: '16px', maxWidth: '820px' }, children: [
    jsx('h2', { style: { marginTop: 0 }, children: 'Medienordner' }),
    jsx('p', { style: muted, children:
      'Ordner, die MiniDLNA indexiert (media_dir) — pro Ordner ein Samba-Share, solange die Option unten aktiv ist.' }),

    jsxs('div', { style: cardStyle, children: [
      jsx('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '4px' }, children: [
        jsx(Btn, { onClick: () => setExplorer('/home'), children: '+ Ordner hinzufügen' }),
        MOUNTS.slice(0, 3).map((mount) => jsx(Btn, {
          key: mount,
          onClick: () => setEdits((prev) => prev.concat([{ type: 'V', path: mount }])),
          children: '+ ' + mount
        }, mount))
      ] }),
      rows.length
        ? jsxs('div', { style: { marginTop: '6px' }, children: rows })
        : jsx('p', { style: Object.assign({}, muted, { margin: '10px 0 0' }), children:
            'Noch keine Ordner — über „Ordner hinzufügen“ auswählen.' })
    ] }),

    jsxs('div', { style: { display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }, children: [
      jsxs('label', { style: { fontSize: '12px', display: 'flex', gap: '6px', alignItems: 'center', cursor: 'pointer' }, children: [
        jsx('input', { type: 'checkbox', checked: restart, onChange: (e) => setRestart(e.target.checked) }),
        jsx('span', { children: 'MiniDLNA neu starten' })
      ] }),
      jsxs('label', { style: { fontSize: '12px', display: 'flex', gap: '6px', alignItems: 'center', cursor: 'pointer' }, children: [
        jsx('input', { type: 'checkbox', checked: samba, onChange: (e) => setSamba(e.target.checked) }),
        jsx('span', { children: 'Auch als Samba-Freigabe bereitstellen' })
      ] }),
      jsx('span', { style: { flex: '1 1 auto' } }),
      dirty ? jsx('span', { style: muted, children: 'ungespeichert' }) : null,
      jsx(Btn, { disabled: !dirty || !!busy, onClick: save, children: busy === 'save' ? 'Speichert …' : 'Speichern' })
    ] }),

    info ? jsx('div', {
      style: { fontSize: '12px', padding: '8px 10px', marginTop: '10px', borderRadius: '6px', background: 'var(--ui-surface, rgba(128,128,128,.1))' },
      children: info
    }) : null,
    error ? jsx('div', { style: { color: 'var(--ui-danger, #d33)', fontSize: '12px', marginTop: '8px' }, children: 'Fehler: ' + error }) : null,

    sambaInfo ? jsxs('div', {
      style: Object.assign({}, cardStyle, { marginTop: '14px' }),
      children: [
        jsxs('div', { style: { display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }, children: [
          jsx('strong', { style: { fontSize: '13px' }, children: 'Samba-Freigaben' }),
          sambaBadge(sambaInfo.service && sambaInfo.service.active ? 'läuft' : 'gestoppt'),
          sambaBadge(sambaInfo.service && sambaInfo.service.enabled ? 'Autostart an' : 'Autostart aus'),
          jsx('span', { style: muted, children: 'im Block: ' + ((sambaInfo.managed || []).join(', ') || 'keine') })
        ] }),
        (sambaInfo.shares || []).length
          ? jsxs('div', { style: Object.assign({ marginTop: '6px' }, mono, { fontSize: '12px' }), children: [
              sambaInfo.shares.map((s) => jsx('div', { style: { marginBottom: '2px' }, children: [
                jsx('span', { style: { opacity: .6 }, children: '[' + s.name + '] ' }),
                s.path || '?'
              ] }, s.name))
            ] })
          : jsx('div', { style: Object.assign({ marginTop: '6px' }, muted), children:
              'Noch keine auto-generierten Freigaben — beim Speichern mit „Samba-Freigaben“ aktivieren.' }),
        (sambaInfo.foreign || []).length
          ? jsx('div', { style: Object.assign({ marginTop: '6px' }, muted), children:
              'Weitere Shares (unverändert): ' + sambaInfo.foreign.join(', ') })
          : null
      ]
    }) : null,

    explorer ? jsx(FolderExplorer, {
      rest,
      startPath: explorer,
      onClose: () => setExplorer(null),
      onPick: pickFolder
    }) : null
  ] })
}

export default {
  id: ID,
  name: 'Samba & MiniDLNA',
  register(ctx) {
    const rest = (path, opts) => ctx.rest(path, opts)
    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        title: 'Dienste',
        data: { path: PATH },
        render: () => jsx(ServicesPage, { rest })
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        data: { path: PATH, label: 'Dienste', codicon: 'server' }
      },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: 'smb-dlna.open',
          label: 'Dienste öffnen (Samba & MiniDLNA)',
          keywords: ['samba', 'smb', 'dlna', 'minidlna', 'dienst', 'service', 'server'],
          run: () => host.navigate(PATH)
        }
      },
      {
        id: 'media-page',
        area: ROUTES_AREA,
        title: 'Medienordner',
        data: { path: MEDIA_PATH },
        render: () => jsx(MediaPage, { rest })
      },
      {
        id: 'media-nav',
        area: SIDEBAR_NAV_AREA,
        data: { path: MEDIA_PATH, label: 'Medienordner', codicon: 'library' }
      },
      {
        id: 'media-open',
        area: PALETTE_AREA,
        data: {
          id: 'smb-dlna.media',
          label: 'Medienordner öffnen (media_dir & Samba-Freigaben)',
          keywords: ['medien', 'ordner', 'media', 'media_dir', 'dlna', 'freigabe', 'share', 'samba', 'videos', 'bilder'],
          run: () => host.navigate(MEDIA_PATH)
        }
      }
    ])
  }
}
