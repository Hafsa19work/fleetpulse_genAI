// Inline SVG line chart with threshold guides. No charting library: the whole SPA
// stays dependency-free apart from React, which keeps the offline demo honest.
// AI-generated from prompt P-16.

const W = 520
const H = 150
const PAD = { top: 12, right: 12, bottom: 20, left: 44 }

export function TelemetryChart({ title, unit, points, thresholds = [], colour = '#31415a' }) {
  const values = points.filter((p) => p !== null && p !== undefined)

  if (values.length < 2) {
    return (
      <div className="chart">
        <h3>{title}</h3>
        <p className="empty">Not enough readings yet.</p>
      </div>
    )
  }

  const guideValues = thresholds.map((t) => t.value)
  const min = Math.min(...values, ...guideValues)
  const max = Math.max(...values, ...guideValues)
  const span = max - min || 1
  const pad = span * 0.12

  const scaleX = (i) => PAD.left + (i / (values.length - 1)) * (W - PAD.left - PAD.right)
  const scaleY = (v) =>
    H - PAD.bottom - ((v - (min - pad)) / (span + 2 * pad)) * (H - PAD.top - PAD.bottom)

  const path = values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${scaleX(i)} ${scaleY(v)}`).join(' ')
  const latest = values[values.length - 1]

  return (
    <div className="chart">
      <h3>
        {title} <span className="chart-latest" style={{ color: colour }}>{latest.toFixed(1)}{unit}</span>
      </h3>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: latest ${latest.toFixed(1)}${unit}`}>
        <line x1={PAD.left} y1={H - PAD.bottom} x2={W - PAD.right} y2={H - PAD.bottom} className="axis" />
        <line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={H - PAD.bottom} className="axis" />

        {thresholds.map((t) => (
          <g key={t.label}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={scaleY(t.value)}
              y2={scaleY(t.value)}
              stroke={t.colour}
              strokeDasharray="5 4"
              strokeWidth="1"
            />
            <text x={W - PAD.right} y={scaleY(t.value) - 4} textAnchor="end" className="guide-label" fill={t.colour}>
              {t.label} {t.value}{unit}
            </text>
          </g>
        ))}

        <path d={path} fill="none" stroke={colour} strokeWidth="2" />
        <circle cx={scaleX(values.length - 1)} cy={scaleY(latest)} r="3.5" fill={colour} />

        <text x={PAD.left - 6} y={scaleY(max)} textAnchor="end" className="tick">{max.toFixed(0)}</text>
        <text x={PAD.left - 6} y={scaleY(min)} textAnchor="end" className="tick">{min.toFixed(0)}</text>
        <text x={PAD.left} y={H - 6} className="tick">oldest</text>
        <text x={W - PAD.right} y={H - 6} textAnchor="end" className="tick">now</text>
      </svg>
    </div>
  )
}
