// Thin API client. Every network call in the SPA goes through here, so error
// handling and the base path are defined in exactly one place.
// AI-generated from prompt P-16, then edited by hand.

const BASE = ''

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      // Non-JSON error body — keep the status line.
    }
    throw new Error(detail)
  }
  if (response.status === 204) return null
  return response.json()
}

export const api = {
  snapshot: () => request('/api/fleet/snapshot'),
  health: () => request('/api/health'),
  stats: () => request('/api/stats'),
  rules: () => request('/api/config/rules'),

  alerts: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== '' && v !== null),
    )
    return request(`/api/alerts?${query}`)
  },
  acknowledgeAlert: (id) => request(`/api/alerts/${id}/acknowledge`, { method: 'POST' }),
  resolveAlert: (id) => request(`/api/alerts/${id}/resolve`, { method: 'POST' }),

  vehicleTelemetry: (code, limit = 60) =>
    request(`/api/vehicles/${encodeURIComponent(code)}/telemetry?limit=${limit}`),

  thresholds: () => request('/api/config/thresholds'),
  updateThresholds: (patch) =>
    request('/api/config/thresholds', { method: 'PUT', body: JSON.stringify(patch) }),
  resetThresholds: () => request('/api/config/thresholds/reset', { method: 'POST' }),
}
