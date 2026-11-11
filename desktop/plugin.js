// smb-dlna — Desktop half. Page (route + sidebar + palette command) for Samba
// (smb/nmb) and MiniDLNA: status, start/stop, autostart. Talks to this package's
// dashboard backend via ctx.rest (namespace /api/plugins/smb-dlna).
import { host, PALETTE_AREA, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const PATH = '/dienste'
const ID = 'smb-dlna'
const LABELS = { smb: 'Samba (smb + nmb)', dlna: 'MiniDLNA' }

const cardStyle = {
  border: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.25))',
  borderRadius: '8px',
  padding: '12px',
  marginBottom: '10px'
}
const muted = { fontSize: '12px', color: 'var(--ui-text-secondary, #888)' }
const buttonStyle = {
  padding: '4px 10px',
  fontSize: '12px',
  borderRadius: '6px',
  border: '1px solid var(--ui-stroke-secondary, rgba(128,128,128,.35))',
  background: 'transparent',
  color: 'var(--ui-text-primary, inherit)',
  cursor: 'pointer'
}

function Btn(props) {
  return jsx('button', {
    onClick: props.onClick,
    disabled: !!props.disabled,
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
      }
    ])
  }
}
