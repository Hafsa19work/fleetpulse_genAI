import { STATUS } from './status'

// Top band of the overview: answers "is anything wrong" before the eye reaches
// the map. AI-generated from prompt P-16.
export function KpiTiles({ counts }) {
  const tiles = [
    {
      key: 'total',
      label: 'Vehicles',
      value: counts.total ?? 0,
      note: `${counts.reporting ?? 0} reporting`,
      colour: '#31415a',
    },
    {
      key: 'critical',
      label: 'Critical',
      value: counts.critical ?? 0,
      note: 'needs action now',
      colour: STATUS.critical.colour,
    },
    {
      key: 'warning',
      label: 'Warnings',
      value: counts.warning ?? 0,
      note: 'monitor',
      colour: STATUS.warning.colour,
    },
    {
      key: 'offline',
      label: 'Offline',
      value: counts.offline ?? 0,
      note: 'no signal',
      colour: STATUS.offline.colour,
    },
  ]

  return (
    <div className="kpi-row">
      {tiles.map((tile) => (
        <div className="kpi-tile" key={tile.key} style={{ borderTopColor: tile.colour }}>
          <div className="kpi-label">{tile.label}</div>
          <div className="kpi-value" style={{ color: tile.colour }}>
            {tile.value}
          </div>
          <div className="kpi-note">{tile.note}</div>
        </div>
      ))}
    </div>
  )
}
