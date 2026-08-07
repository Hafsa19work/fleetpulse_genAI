import { statusOf, formatTime } from './status'

// Reused by the alert feed and the alert centre — one of the two deliberately
// generic components in the design (docs/05-ui-ux-design.md §10).
export function AlertItem({ alert, onAcknowledge, onResolve, onSelectVehicle, compact = false }) {
  const status = statusOf(alert.severity)

  return (
    <article className={`alert-item ${alert.isNew ? 'flash' : ''}`} style={{ borderLeftColor: status.colour }}>
      <header>
        <span className="alert-severity" style={{ color: status.colour }}>
          {status.icon} {alert.severity.toUpperCase()}
        </span>
        <button className="linkish" onClick={() => onSelectVehicle?.(alert.vehicle_code)}>
          {alert.vehicle_code}
        </button>
        <span className="alert-time">{formatTime(alert.raised_at)}</span>
        {alert.occurrences > 1 && <span className="badge" title="repeat occurrences">×{alert.occurrences}</span>}
      </header>
      <p className="alert-message">{alert.message}</p>
      {!compact && (
        <footer>
          <span className="alert-rule">{alert.rule_code}</span>
          <span className="alert-status">{alert.status}</span>
          <span className="spacer" />
          {alert.status === 'open' && (
            <button onClick={() => onAcknowledge(alert.id)}>Acknowledge</button>
          )}
          {alert.status !== 'resolved' && (
            <button onClick={() => onResolve(alert.id)}>Resolve</button>
          )}
        </footer>
      )}
    </article>
  )
}
