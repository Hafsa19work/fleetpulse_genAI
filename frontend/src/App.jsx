import { useEffect, useState } from 'react'
import { api } from './api'
import { AlertCentre } from './components/AlertCentre'
import { AlertFeed } from './components/AlertFeed'
import { FleetMap } from './components/FleetMap'
import { KpiTiles } from './components/KpiTiles'
import { SettingsThresholds } from './components/SettingsThresholds'
import { VehicleDetail } from './components/VehicleDetail'
import { VehicleTable } from './components/VehicleTable'
import { useLiveFleet } from './hooks/useLiveFleet'

const CONNECTION_LABEL = {
  live: { text: 'live (ws)', className: 'ok' },
  polling: { text: 'polling (ws down)', className: 'warn' },
  connecting: { text: 'connecting…', className: 'muted' },
}

// Map the in-app screen onto a URL, so the browser's Back button walks back
// through screens instead of leaving the dashboard altogether. The SPA is still
// state-driven — this is a thin two-way binding to `history`, not a router.
const pathFor = (view, code) =>
  ({ overview: '/', alerts: '/alerts', settings: '/settings' }[view] ??
    `/vehicles/${encodeURIComponent(code ?? '')}`)

function viewFromPath(pathname) {
  if (pathname.startsWith('/vehicles/')) {
    return { view: 'vehicle', selected: decodeURIComponent(pathname.slice('/vehicles/'.length)) }
  }
  if (pathname === '/alerts') return { view: 'alerts', selected: null }
  if (pathname === '/settings') return { view: 'settings', selected: null }
  return { view: 'overview', selected: null }
}

export default function App() {
  const fleet = useLiveFleet()
  const initial = viewFromPath(window.location.pathname)
  const [view, setView] = useState(initial.view)
  const [selected, setSelected] = useState(initial.selected)
  const [thresholds, setThresholds] = useState(null)

  useEffect(() => {
    api.thresholds().then(setThresholds).catch(() => setThresholds(null))
  }, [])

  // Back and Forward: adopt whatever screen the popped history entry describes.
  useEffect(() => {
    const onPop = (event) => {
      const next = event.state ?? viewFromPath(window.location.pathname)
      setView(next.view)
      setSelected(next.selected)
    }
    window.addEventListener('popstate', onPop)
    // Give the first entry a state object, so returning to it restores properly
    // rather than falling through to the path parser.
    window.history.replaceState(initial, '', pathFor(initial.view, initial.selected))
    return () => window.removeEventListener('popstate', onPop)
    // Deliberately once, on mount: `initial` is a snapshot of the entry URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const go = (nextView, code = null) => {
    if (nextView === view && code === selected) return // no duplicate history entries
    setView(nextView)
    setSelected(code)
    window.history.pushState({ view: nextView, selected: code }, '', pathFor(nextView, code))
  }

  const openVehicle = (code) => go('vehicle', code)

  const connection = CONNECTION_LABEL[fleet.connection]

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <strong>FleetPulse</strong>
          <span className="subtitle">Transportation monitoring · Hafsa Aqeel (53317)</span>
        </div>
        <span className={`connection ${connection.className}`} title="Live connection state">
          ● {connection.text}
        </span>
        <nav>
          <button className={view === 'overview' ? 'active' : ''} onClick={() => go('overview')}>
            Fleet overview
          </button>
          <button className={view === 'alerts' ? 'active' : ''} onClick={() => go('alerts')}>
            Alert centre
          </button>
          <button className={view === 'settings' ? 'active' : ''} onClick={() => go('settings')}>
            Settings
          </button>
        </nav>
      </header>

      {fleet.error && <div className="banner error">API error: {fleet.error}</div>}

      <main>
        {view === 'overview' && (
          <>
            <KpiTiles counts={fleet.counts} />
            <div className="split">
              <FleetMap
                routes={fleet.routes}
                vehicles={fleet.vehicles}
                selected={selected}
                onSelect={openVehicle}
              />
              <AlertFeed
                alerts={fleet.alerts}
                onAcknowledge={fleet.acknowledge}
                onResolve={fleet.resolve}
                onSelectVehicle={openVehicle}
              />
            </div>
            <VehicleTable vehicles={fleet.vehicles} selected={selected} onSelect={openVehicle} />
          </>
        )}

        {view === 'vehicle' && selected && (
          <VehicleDetail
            code={selected}
            vehicle={fleet.vehicles.find((v) => v.code === selected)}
            thresholds={thresholds}
            onBack={() => window.history.back()}
            onAcknowledge={fleet.acknowledge}
            onResolve={fleet.resolve}
          />
        )}

        {view === 'alerts' && (
          <AlertCentre onSelectVehicle={openVehicle} onChanged={fleet.refresh} />
        )}

        {view === 'settings' && (
          <SettingsThresholds thresholds={thresholds} onSaved={setThresholds} />
        )}
      </main>

      <footer className="footer">
        FleetPulse v1.0 · Final Term Project · domain Transportation (July) · type Monitoring
        System (roll digit 7) · Python with AI-generated tests
      </footer>
    </div>
  )
}
