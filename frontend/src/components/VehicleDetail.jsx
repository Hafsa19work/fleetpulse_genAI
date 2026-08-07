import { useEffect, useState } from 'react'
import { api } from '../api'
import { AlertItem } from './AlertItem'
import { TelemetryChart } from './TelemetryChart'
import { STATUS, formatAge, formatNumber, statusOf } from './status'

export function VehicleDetail({ code, vehicle, thresholds, onBack, onAcknowledge, onResolve }) {
  const [history, setHistory] = useState([])
  const [alerts, setAlerts] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [rows, page] = await Promise.all([
          api.vehicleTelemetry(code, 60),
          api.alerts({ vehicle_code: code, limit: 25 }),
        ])
        if (cancelled) return
        setHistory([...rows].reverse()) // API returns newest-first; charts read left to right
        setAlerts(page.items)
        setError(null)
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    }
    load()
    const timer = setInterval(load, 5000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [code])

  if (!vehicle) {
    return (
      <div className="panel">
        <button className="linkish" onClick={onBack}>← Back to fleet</button>
        <p className="empty">Vehicle {code} is not in the current snapshot.</p>
      </div>
    )
  }

  const status = statusOf(vehicle.state)

  return (
    <div className="detail">
      <div className="panel">
        <header className="panel-header">
          <button className="linkish" onClick={onBack}>← Back to fleet</button>
          <h2>
            <span className="mono">{vehicle.code}</span> · {vehicle.label}
          </h2>
          <span className="pill" style={{ background: status.colour }}>
            {status.icon} {status.label}
          </span>
        </header>

        <dl className="metrics">
          <div><dt>Type</dt><dd>{vehicle.vehicle_type}</dd></div>
          <div><dt>Route</dt><dd>{vehicle.route_code ?? '—'}</dd></div>
          <div><dt>Speed</dt><dd>{formatNumber(vehicle.speed_kph, ' kph')}</dd></div>
          <div><dt>Engine</dt><dd>{formatNumber(vehicle.engine_temp_c, ' °C', 1)}</dd></div>
          <div><dt>Fuel</dt><dd>{formatNumber(vehicle.fuel_pct, ' %')}</dd></div>
          {vehicle.vehicle_type === 'truck' && (
            <div><dt>Cargo</dt><dd>{formatNumber(vehicle.cargo_temp_c, ' °C', 1)}</dd></div>
          )}
          <div><dt>Last seen</dt><dd>{formatAge(vehicle.seconds_since_report)}</dd></div>
          <div><dt>Open alerts</dt><dd>{vehicle.open_alerts}</dd></div>
        </dl>
      </div>

      {error && <div className="panel error">{error}</div>}

      <div className="panel">
        <h2>Telemetry history</h2>
        <div className="chart-grid">
          <TelemetryChart
            title="Engine temperature"
            unit=" °C"
            colour={STATUS.critical.colour}
            points={history.map((row) => row.engine_temp_c)}
            thresholds={
              thresholds
                ? [
                    { label: 'warn', value: thresholds.engine_warn_c, colour: STATUS.warning.colour },
                    { label: 'crit', value: thresholds.engine_critical_c, colour: STATUS.critical.colour },
                  ]
                : []
            }
          />
          <TelemetryChart
            title="Speed"
            unit=" kph"
            colour="#1565c0"
            points={history.map((row) => row.speed_kph)}
          />
          <TelemetryChart
            title="Fuel level"
            unit=" %"
            colour={STATUS.ok.colour}
            points={history.map((row) => row.fuel_pct)}
            thresholds={
              thresholds
                ? [{ label: 'low', value: thresholds.fuel_low_pct, colour: STATUS.warning.colour }]
                : []
            }
          />
          {vehicle.vehicle_type === 'truck' && (
            <TelemetryChart
              title="Cargo temperature"
              unit=" °C"
              colour="#6a1b9a"
              points={history.map((row) => row.cargo_temp_c)}
            />
          )}
        </div>
      </div>

      <div className="panel">
        <h2>Alert history for this vehicle</h2>
        {alerts.length === 0 && <p className="empty">No alerts recorded.</p>}
        {alerts.map((alert) => (
          <AlertItem
            key={alert.id}
            alert={alert}
            onAcknowledge={onAcknowledge}
            onResolve={onResolve}
          />
        ))}
      </div>
    </div>
  )
}
