import { fetchBdmPerformance } from './dashboardApi'
import {
  readBdmPerformanceCache,
  writeBdmPerformanceCache,
} from './dashboardCache'

const memoryCache = new Map()
const inFlightLoads = new Map()

function getCacheKey(period) {
  return period || 'today'
}

export function getCachedBdmPerformance(period = 'today') {
  const cacheKey = getCacheKey(period)
  const memoryRows = memoryCache.get(cacheKey)

  if (Array.isArray(memoryRows)) {
    return memoryRows
  }

  const storedRows = readBdmPerformanceCache(period)

  if (Array.isArray(storedRows)) {
    memoryCache.set(cacheKey, storedRows)
    return storedRows
  }

  return null
}

export async function loadBdmPerformance({
  period = 'today',
  force = false,
} = {}) {
  const cacheKey = getCacheKey(period)

  if (!force) {
    const cachedRows = getCachedBdmPerformance(period)

    if (Array.isArray(cachedRows)) {
      return cachedRows
    }
  }

  const inFlightLoad = inFlightLoads.get(cacheKey)

  if (inFlightLoad) {
    return inFlightLoad
  }

  const load = fetchBdmPerformance(period)
    .then((data) => {
      const rows = Array.isArray(data) ? data : []

      memoryCache.set(cacheKey, rows)
      writeBdmPerformanceCache(period, rows)

      return rows
    })
    .finally(() => {
      inFlightLoads.delete(cacheKey)
    })

  inFlightLoads.set(cacheKey, load)

  return load
}
