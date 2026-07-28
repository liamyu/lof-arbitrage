const API_BASE = '/api/v1'

async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => fetchJSON('/health'),
  dataStatus: () => fetchJSON('/meta/data-status'),
  opportunities: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return fetchJSON(`/opportunities?${qs}`)
  },
  fundDetail: (code) => fetchJSON(`/funds/${code}`),
  fundHistory: (code, days = 60) => fetchJSON(`/funds/${code}/history?days=${days}`),
  fundScore: (code) => fetchJSON(`/funds/${code}/score`)
}
