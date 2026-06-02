const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
const inFlightRequests = new Map()

async function apiFetch(path) {
  if (inFlightRequests.has(path)) {
    return inFlightRequests.get(path)
  }

  const request = (async () => {
    const response = await fetch(`${BASE_URL}${path}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    })

    if (!response.ok) {
      const errorBody = await response.text()
      throw new Error(`API error ${response.status}: ${errorBody}`)
    }

    return await response.json()
  })()

  inFlightRequests.set(path, request)

  try {
    return await request
  } finally {
    inFlightRequests.delete(path)
  }
}

export async function fetchHighPriorityRequirements({ dateFrom, dateTo } = {}) {
  const params = new URLSearchParams()
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  const qs = params.toString()
  return apiFetch(`/dashboard/high-priority${qs ? '?' + qs : ''}`)
}

export async function fetchBdmWiseRequirements({ dateFrom, dateTo } = {}) {
  const params = new URLSearchParams()
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  const qs = params.toString()
  return apiFetch(`/dashboard/bdm-wise${qs ? '?' + qs : ''}`)
}

export async function fetchDashboardStats() {
  return apiFetch('/dashboard/stats')
}

export async function fetchRecruitingStatus() {
  return apiFetch('/dashboard/status')
}

export async function fetchBdmPerformance(period = 'today') {
  const params = new URLSearchParams({ period })
  return apiFetch(`/dashboard/bdm-performance?${params.toString()}`)
}
