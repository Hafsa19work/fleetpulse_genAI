import { useMemo } from 'react'
import { statusOf } from './status'

// Self-contained SVG map.
//
// Design decision, recorded in docs/03-architecture.md: the UI/UX design first
// specified Leaflet, but Leaflet needs raster tiles from a remote host. The demo
// has to run on an examiner's machine with no internet, so the map is drawn as an
// equirectangular projection of the route polylines and vehicle positions into an
// SVG viewBox instead. No tiles, no external requests, no npm map dependency.
// AI-generated from prompt P-16, projection maths written by hand.

const WIDTH = 800
const HEIGHT = 520
const PAD = 36

function useProjection(routes, vehicles) {
  return useMemo(() => {
    const points = []
    routes.forEach((route) => route.waypoints.forEach((w) => points.push([w.latitude, w.longitude])))
    vehicles.forEach((v) => {
      if (v.latitude !== null && v.longitude !== null) points.push([v.latitude, v.longitude])
    })
    if (points.length === 0) return null

    const lats = points.map((p) => p[0])
    const lons = points.map((p) => p[1])
    // A degree of longitude is shorter than a degree of latitude away from the
    // equator; without this factor the routes would look stretched east-west.
    const midLat = (Math.min(...lats) + Math.max(...lats)) / 2
    const lonScale = Math.cos((midLat * Math.PI) / 180)

    let minX = Math.min(...lons) * lonScale
    let maxX = Math.max(...lons) * lonScale
    let minY = -Math.max(...lats)
    let maxY = -Math.min(...lats)

    // Guard against a zero-size box when the whole fleet sits on one point.
    if (maxX - minX < 1e-6) { minX -= 0.005; maxX += 0.005 }
    if (maxY - minY < 1e-6) { minY -= 0.005; maxY += 0.005 }

    const spanX = maxX - minX
    const spanY = maxY - minY
    const scale = Math.min((WIDTH - 2 * PAD) / spanX, (HEIGHT - 2 * PAD) / spanY)
    const offsetX = (WIDTH - spanX * scale) / 2
    const offsetY = (HEIGHT - spanY * scale) / 2

    return (lat, lon) => [
      (lon * lonScale - minX) * scale + offsetX,
      (-lat - minY) * scale + offsetY,
    ]
  }, [routes, vehicles])
}

export function FleetMap({ routes, vehicles, selected, onSelect }) {
  const project = useProjection(routes, vehicles)

  if (!project) {
    return (
      <div className="panel map-panel">
        <h2>Live fleet map</h2>
        <p className="empty">No routes or positions to draw yet. Start the simulator.</p>
      </div>
    )
  }

  const placed = vehicles.filter((v) => v.latitude !== null && v.longitude !== null)

  return (
    <div className="panel map-panel">
      <h2>Live fleet map</h2>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="map" role="img"
           aria-label={`Map showing ${placed.length} vehicles on ${routes.length} routes`}>
        <rect x="0" y="0" width={WIDTH} height={HEIGHT} className="map-bg" />

        {routes.map((route, index) => {
          const path = route.waypoints
            .map((w) => project(w.latitude, w.longitude).join(','))
            .join(' ')
          return (
            <g key={route.code}>
              <polyline
                points={path}
                className="route-line"
                strokeDasharray={route.vehicle_type === 'truck' ? '8 6' : undefined}
              />
              {route.waypoints.length > 0 && (
                <text
                  x={project(route.waypoints[0].latitude, route.waypoints[0].longitude)[0] + 8}
                  y={project(route.waypoints[0].latitude, route.waypoints[0].longitude)[1] - 8 - index * 4}
                  className="route-label"
                >
                  {route.code}
                </text>
              )}
              {route.stops.map((stop) => {
                const [x, y] = project(stop.latitude, stop.longitude)
                return <circle key={stop.sequence} cx={x} cy={y} r="3" className="stop-dot" />
              })}
            </g>
          )
        })}

        {placed.map((vehicle) => {
          const [x, y] = project(vehicle.latitude, vehicle.longitude)
          const status = statusOf(vehicle.state)
          const isSelected = selected === vehicle.code
          return (
            <g
              key={vehicle.code}
              transform={`translate(${x} ${y})`}
              className={`marker ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelect(vehicle.code)}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => event.key === 'Enter' && onSelect(vehicle.code)}
              aria-label={`${vehicle.code}, ${status.label}`}
            >
              {isSelected && <circle r="14" className="marker-halo" />}
              {vehicle.vehicle_type === 'truck' ? (
                <rect x="-6" y="-6" width="12" height="12" fill={status.colour} stroke="#fff" strokeWidth="1.5" />
              ) : (
                <circle r="7" fill={status.colour} stroke="#fff" strokeWidth="1.5" />
              )}
              <text y="-13" className="marker-label">{vehicle.code}</text>
            </g>
          )
        })}
      </svg>
      <div className="map-legend">
        <span>● bus</span>
        <span>■ truck</span>
        <span>— bus route</span>
        <span className="dashed">— truck route</span>
        <span>· timetabled stop</span>
      </div>
    </div>
  )
}
