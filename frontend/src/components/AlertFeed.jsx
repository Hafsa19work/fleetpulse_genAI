import { useMemo, useState } from 'react'
import { AlertItem } from './AlertItem'
import { SEVERITY_RANK } from './status'

// Sorted worst-first so the most severe item is topmost regardless of colour —
// severity is encoded by position as well as by hue (accessibility, NFR-07).
export function AlertFeed({ alerts, onAcknowledge, onResolve, onSelectVehicle }) {
  const [filter, setFilter] = useState('all')

  const visible = useMemo(() => {
    const filtered = filter === 'all' ? alerts : alerts.filter((a) => a.severity === filter)
    return [...filtered].sort((a, b) => {
      const bySeverity = (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0)
      if (bySeverity !== 0) return bySeverity
      return new Date(b.raised_at) - new Date(a.raised_at)
    })
  }, [alerts, filter])

  return (
    <div className="panel feed-panel">
      <header className="panel-header">
        <h2>Alert feed</h2>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by severity">
          <option value="all">All severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>
      </header>

      <div className="feed" aria-live="polite" aria-relevant="additions">
        {visible.length === 0 && <p className="empty">No open alerts. The fleet is healthy.</p>}
        {visible.map((alert) => (
          <AlertItem
            key={alert.id}
            alert={alert}
            onAcknowledge={onAcknowledge}
            onResolve={onResolve}
            onSelectVehicle={onSelectVehicle}
          />
        ))}
      </div>
    </div>
  )
}
