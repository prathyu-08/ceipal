import { fetchRecruitingStatus } from './dashboardApi'

const STATUS_CACHE_KEY = 'recruiting-status-cache'

let memoryCache = null
let inFlightLoad = null

export function getCachedRecruitingStatus() {
  if (memoryCache) {
    return memoryCache
  }

  try {
    const storedStatus = JSON.parse(localStorage.getItem(STATUS_CACHE_KEY)) || null

    if (storedStatus) {
      memoryCache = storedStatus
      return storedStatus
    }
  } catch {
    // Storage can fail in private mode or when data is malformed.
  }

  return null
}

export async function loadRecruitingStatus({ force = false } = {}) {
  if (!force) {
    const cachedStatus = getCachedRecruitingStatus()

    if (cachedStatus) {
      return cachedStatus
    }
  }

  if (inFlightLoad) {
    return inFlightLoad
  }

  inFlightLoad = fetchRecruitingStatus()
    .then((status) => {
      memoryCache = status

      try {
        localStorage.setItem(STATUS_CACHE_KEY, JSON.stringify(status))
      } catch {
        // Keep rendering if storage is unavailable.
      }

      return status
    })
    .finally(() => {
      inFlightLoad = null
    })

  return inFlightLoad
}
