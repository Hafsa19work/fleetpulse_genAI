// Status semantics from docs/05-ui-ux-design.md §7.
// Colour is never the only channel: every state carries an icon and a label too.

export const STATUS = {
  ok: { icon: '●', label: 'ok', colour: '#1b8a3f' },
  info: { icon: 'ⓘ', label: 'info', colour: '#1565c0' },
  warning: { icon: '⚠', label: 'warn', colour: '#b26a00' },
  critical: { icon: '⛔', label: 'crit', colour: '#c0261a' },
  offline: { icon: '○', label: 'offline', colour: '#5f6368' },
}

export const statusOf = (state) => STATUS[state] ?? STATUS.offline

export const SEVERITY_RANK = { critical: 3, warning: 2, info: 1 }

export function formatAge(seconds) {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 60) return `${Math.round(seconds)} s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)} m ago`
  return `${(seconds / 3600).toFixed(1)} h ago`
}

export function formatNumber(value, unit = '', digits = 0) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(digits)}${unit}`
}

export function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
