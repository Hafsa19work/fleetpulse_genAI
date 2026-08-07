import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { AlertItem } from './AlertItem'

const PAGE_SIZE = 25

// Full alert history with the filters of FR-28. The overview feed shows only what
// is open; this is where an operator goes to audit what happened earlier.
export function AlertCentre({ onSelectVehicle, onChanged }) {
  const [filters, setFilters] = useState({ status: 'open', severity: '', rule_code: '', vehicle_code: '' })
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState({ items: [], total: 0 })
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const result = await api.alerts({ ...filters, limit: PAGE_SIZE, offset })
      setPage(result)
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [filters, offset])

  useEffect(() => { load() }, [load])

  const act = async (fn, id) => {
    await fn(id)
    await load()
    onChanged?.()
  }

  const update = (key) => (event) => {
    setOffset(0)
    setFilters((current) => ({ ...current, [key]: event.target.value }))
  }

  return (
    <div className="panel">
      <header className="panel-header">
        <h2>Alert centre</h2>
        <span className="muted">{page.total} matching</span>
      </header>

      <div className="filters-row">
        <label>
          Status
          <select value={filters.status} onChange={update('status')}>
            <option value="">any</option>
            <option value="open">open</option>
            <option value="acknowledged">acknowledged</option>
            <option value="resolved">resolved</option>
          </select>
        </label>
        <label>
          Severity
          <select value={filters.severity} onChange={update('severity')}>
            <option value="">any</option>
            <option value="critical">critical</option>
            <option value="warning">warning</option>
            <option value="info">info</option>
          </select>
        </label>
        <label>
          Vehicle
          <input value={filters.vehicle_code} onChange={update('vehicle_code')} placeholder="e.g. BUS-03" />
        </label>
        <label>
          Rule
          <input value={filters.rule_code} onChange={update('rule_code')} placeholder="e.g. OVERSPEED" />
        </label>
      </div>

      {error && <p className="error">{error}</p>}
      {page.items.length === 0 && <p className="empty">Nothing matches these filters.</p>}

      {page.items.map((alert) => (
        <AlertItem
          key={alert.id}
          alert={alert}
          onSelectVehicle={onSelectVehicle}
          onAcknowledge={(id) => act(api.acknowledgeAlert, id)}
          onResolve={(id) => act(api.resolveAlert, id)}
        />
      ))}

      <footer className="pager">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
          ← Previous
        </button>
        <span>
          {page.total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}
        </span>
        <button disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)}>
          Next →
        </button>
      </footer>
    </div>
  )
}
