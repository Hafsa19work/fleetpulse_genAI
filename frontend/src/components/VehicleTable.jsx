import { useMemo, useRef, useState } from 'react'
import { SEVERITY_RANK, formatAge, formatNumber, statusOf } from './status'

const STATE_RANK = { critical: 4, offline: 3, warning: 2, info: 1, ok: 0 }

// Sorted worst-first, but the sort is frozen while the pointer is inside the
// table: re-ordering under a moving cursor makes the operator click the wrong row
// (docs/05-ui-ux-design.md §8).
export function VehicleTable({ vehicles, selected, onSelect }) {
  const [typeFilter, setTypeFilter] = useState('all')
  const [frozen, setFrozen] = useState(false)
  const frozenOrder = useRef([])

  const rows = useMemo(() => {
    const filtered =
      typeFilter === 'all' ? vehicles : vehicles.filter((v) => v.vehicle_type === typeFilter)

    if (frozen && frozenOrder.current.length) {
      const index = new Map(frozenOrder.current.map((code, i) => [code, i]))
      return [...filtered].sort(
        (a, b) => (index.get(a.code) ?? 999) - (index.get(b.code) ?? 999),
      )
    }

    const sorted = [...filtered].sort((a, b) => {
      const byState = (STATE_RANK[b.state] ?? 0) - (STATE_RANK[a.state] ?? 0)
      if (byState !== 0) return byState
      const bySeverity =
        (SEVERITY_RANK[b.worst_severity] ?? 0) - (SEVERITY_RANK[a.worst_severity] ?? 0)
      if (bySeverity !== 0) return bySeverity
      return a.code.localeCompare(b.code)
    })
    frozenOrder.current = sorted.map((v) => v.code)
    return sorted
  }, [vehicles, typeFilter, frozen])

  return (
    <div
      className="panel table-panel"
      onMouseEnter={() => setFrozen(true)}
      onMouseLeave={() => setFrozen(false)}
    >
      <header className="panel-header">
        <h2>Vehicles</h2>
        <div className="filters" role="group" aria-label="Filter by vehicle type">
          {['all', 'bus', 'truck'].map((option) => (
            <button
              key={option}
              className={typeFilter === option ? 'chip active' : 'chip'}
              onClick={() => setTypeFilter(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </header>

      <table>
        <thead>
          <tr>
            <th scope="col">State</th>
            <th scope="col">Code</th>
            <th scope="col">Type</th>
            <th scope="col">Route</th>
            <th scope="col">Speed</th>
            <th scope="col">Engine</th>
            <th scope="col">Fuel</th>
            <th scope="col">Cargo</th>
            <th scope="col">Last seen</th>
            <th scope="col">Alerts</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan="10" className="empty">No vehicles registered. Run <code>python -m app.seed</code>.</td>
            </tr>
          )}
          {rows.map((vehicle) => {
            const status = statusOf(vehicle.state)
            return (
              <tr
                key={vehicle.code}
                className={selected === vehicle.code ? 'selected' : ''}
                tabIndex={0}
                onClick={() => onSelect(vehicle.code)}
                onKeyDown={(event) => event.key === 'Enter' && onSelect(vehicle.code)}
              >
                <td style={{ color: status.colour }}>
                  {status.icon} {status.label}
                </td>
                <td className="mono">{vehicle.code}</td>
                <td>{vehicle.vehicle_type}</td>
                <td>{vehicle.route_code ?? '—'}</td>
                <td>{formatNumber(vehicle.speed_kph, ' kph')}</td>
                <td>{formatNumber(vehicle.engine_temp_c, ' °C', 1)}</td>
                <td>{formatNumber(vehicle.fuel_pct, ' %')}</td>
                <td>{formatNumber(vehicle.cargo_temp_c, ' °C', 1)}</td>
                <td>{formatAge(vehicle.seconds_since_report)}</td>
                <td>{vehicle.open_alerts || '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
