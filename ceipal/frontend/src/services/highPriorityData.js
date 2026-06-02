import {
  fetchBdmWiseRequirements,
  fetchHighPriorityRequirements,
} from './dashboardApi'
import {
  readHighPriorityCache,
  writeHighPriorityCache,
} from './dashboardCache'

const memoryCache = new Map()
const inFlightLoads = new Map()

function getCacheKey(dateFrom, dateTo) {
  return `${dateFrom || 'none'}:${dateTo || 'none'}`
}

function getLoadKey(route, dateFrom, dateTo) {
  return `${route || 'high-priority'}:${getCacheKey(dateFrom, dateTo)}`
}

function fetchRequirements(route, dateFrom, dateTo) {
  if (route === 'bdm-wise') {
    return fetchBdmWiseRequirements({ dateFrom, dateTo })
  }

  return fetchHighPriorityRequirements({ dateFrom, dateTo })
}

export function getCachedHighPriorityRequirements(dateFrom, dateTo) {
  const cacheKey = getCacheKey(dateFrom, dateTo)
  const memoryRows = memoryCache.get(cacheKey)

  if (Array.isArray(memoryRows)) {
    return memoryRows
  }

  const storedRows = readHighPriorityCache(dateFrom, dateTo)

  if (Array.isArray(storedRows)) {
    memoryCache.set(cacheKey, storedRows)
    return storedRows
  }

  return null
}

export async function loadHighPriorityRequirements({
  dateFrom,
  dateTo,
  force = false,
  route = 'high-priority',
} = {}) {
  const cacheKey = getCacheKey(dateFrom, dateTo)
  const loadKey = getLoadKey(route, dateFrom, dateTo)

  if (!force) {
    const cachedRows = getCachedHighPriorityRequirements(dateFrom, dateTo)

    if (Array.isArray(cachedRows)) {
      return cachedRows
    }
  }

  const inFlightLoad = inFlightLoads.get(loadKey)

  if (inFlightLoad) {
    return inFlightLoad
  }

  const load = fetchRequirements(route, dateFrom, dateTo)
    .then((data) => {
      const rows = Array.isArray(data) ? data : []

      memoryCache.set(cacheKey, rows)
      writeHighPriorityCache(dateFrom, dateTo, rows)

      return rows
    })
    .finally(() => {
      inFlightLoads.delete(loadKey)
    })

  inFlightLoads.set(loadKey, load)

  return load
}
