// The single source of live fleet state (docs/05-ui-ux-design.md §10).
// AI-generated from prompt P-16; the reconnect backoff and the "patch in place"
// merge were rewritten by hand after the generated version re-fetched the whole
// snapshot on every message, which defeated the point of the WebSocket.

import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'

const POLL_INTERVAL_MS = 5000
const MAX_BACKOFF_MS = 30000
const FEED_LIMIT = 50

export function useLiveFleet() {
  const [vehicles, setVehicles] = useState([])
  const [routes, setRoutes] = useState([])
  const [counts, setCounts] = useState({})
  const [alerts, setAlerts] = useState([])
  const [connection, setConnection] = useState('connecting') // live | polling | connecting
  const [error, setError] = useState(null)

  const socketRef = useRef(null)
  const backoffRef = useRef(1000)
  const pollRef = useRef(null)
  const closedRef = useRef(false)

  const loadSnapshot = useCallback(async () => {
    try {
      const data = await api.snapshot()
      setVehicles(data.vehicles)
      setRoutes(data.routes)
      setCounts(data.counts)
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  const loadAlerts = useCallback(async () => {
    try {
      const page = await api.alerts({ status: 'open', limit: FEED_LIMIT })
      setAlerts(page.items)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  // Patch one vehicle in place rather than re-rendering the whole table: the
  // operator's scroll position and pointer target must survive an update.
  const applyVehicleUpdate = useCallback((update) => {
    setVehicles((current) =>
      current.map((vehicle) =>
        vehicle.code === update.code
          ? {
              ...vehicle,
              latitude: update.latitude,
              longitude: update.longitude,
              speed_kph: update.speed_kph,
              heading_deg: update.heading_deg,
              engine_temp_c: update.engine_temp_c,
              fuel_pct: update.fuel_pct,
              cargo_temp_c: update.cargo_temp_c,
              last_seen_at: update.last_seen_at,
              seconds_since_report: 0,
            }
          : vehicle,
      ),
    )
  }, [])

  const applyAlert = useCallback((alert) => {
    setAlerts((current) => {
      const existing = current.findIndex((a) => a.id === alert.id)
      if (existing >= 0) {
        // A deduplicated refire: bump the counter on the card already on screen.
        const next = [...current]
        next[existing] = { ...next[existing], ...alert, isNew: true }
        return next
      }
      return [{ ...alert, isNew: true }, ...current].slice(0, FEED_LIMIT)
    })
    // A new alert changes a vehicle's state, which only the snapshot knows how to
    // compute (worst-severity across all its open alerts).
    loadSnapshot()
  }, [loadSnapshot])

  const startPolling = useCallback(() => {
    if (pollRef.current) return
    setConnection('polling')
    pollRef.current = setInterval(() => {
      loadSnapshot()
      loadAlerts()
    }, POLL_INTERVAL_MS)
  }, [loadSnapshot, loadAlerts])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (closedRef.current) return
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/live`)
    socketRef.current = socket

    socket.onopen = () => {
      backoffRef.current = 1000
      stopPolling()
      setConnection('live')
    }
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data)
      if (message.type === 'vehicle_update') applyVehicleUpdate(message.vehicle)
      else if (message.type === 'alert_raised') applyAlert(message.alert)
    }
    socket.onclose = () => {
      if (closedRef.current) return
      startPolling()
      const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS)
      backoffRef.current = delay * 2
      setTimeout(connect, delay)
    }
    socket.onerror = () => socket.close()
  }, [applyVehicleUpdate, applyAlert, startPolling, stopPolling])

  useEffect(() => {
    closedRef.current = false
    loadSnapshot()
    loadAlerts()
    connect()
    return () => {
      closedRef.current = true
      stopPolling()
      socketRef.current?.close()
    }
  }, [connect, loadSnapshot, loadAlerts, stopPolling])

  const acknowledge = useCallback(async (id) => {
    await api.acknowledgeAlert(id)
    setAlerts((current) => current.filter((alert) => alert.id !== id))
    loadSnapshot()
  }, [loadSnapshot])

  const resolve = useCallback(async (id) => {
    await api.resolveAlert(id)
    setAlerts((current) => current.filter((alert) => alert.id !== id))
    loadSnapshot()
  }, [loadSnapshot])

  return {
    vehicles,
    routes,
    counts,
    alerts,
    connection,
    error,
    acknowledge,
    resolve,
    refresh: () => {
      loadSnapshot()
      loadAlerts()
    },
  }
}
