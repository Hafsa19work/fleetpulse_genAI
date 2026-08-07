import { useEffect, useState } from 'react'
import { api } from '../api'

const FIELDS = [
  ['overspeed_tolerance_kph', 'Overspeed tolerance', 'kph over the route limit'],
  ['engine_warn_c', 'Engine warning', '°C'],
  ['engine_critical_c', 'Engine critical', '°C'],
  ['fuel_low_pct', 'Fuel low', '%'],
  ['fuel_critical_pct', 'Fuel critical', '%'],
  ['harsh_braking_delta_kph', 'Harsh braking Δ', 'kph between readings'],
  ['harsh_braking_window_s', 'Harsh braking window', 'seconds'],
  ['heartbeat_timeout_s', 'Heartbeat timeout', 'seconds'],
  ['schedule_grace_s', 'Schedule grace (buses)', 'seconds'],
  ['alert_cooldown_s', 'Alert cooldown', 'seconds'],
]

export function SettingsThresholds({ thresholds, onSaved }) {
  const [draft, setDraft] = useState(thresholds ?? {})
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { if (thresholds) setDraft(thresholds) }, [thresholds])

  const save = async (event) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    try {
      const patch = Object.fromEntries(FIELDS.map(([key]) => [key, Number(draft[key])]))
      const saved = await api.updateThresholds(patch)
      onSaved(saved)
      setMessage('Saved. The next telemetry reading is evaluated against these values.')
    } catch (err) {
      setError(err.message)
    }
  }

  const reset = async () => {
    const saved = await api.resetThresholds()
    setDraft(saved)
    onSaved(saved)
    setMessage('Defaults restored.')
  }

  return (
    <form className="panel settings" onSubmit={save}>
      <header className="panel-header">
        <h2>Rule thresholds</h2>
        <button type="button" onClick={reset}>Reset defaults</button>
      </header>
      <p className="muted">
        Changes take effect immediately — no restart, no code change (FR-22).
      </p>

      <div className="settings-grid">
        {FIELDS.map(([key, label, unit]) => (
          <label key={key}>
            <span>{label}</span>
            <input
              type="number"
              step="any"
              value={draft[key] ?? ''}
              onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
            />
            <small>{unit}</small>
          </label>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {message && <p className="success">{message}</p>}

      <button type="submit" className="primary">Save changes</button>
    </form>
  )
}
