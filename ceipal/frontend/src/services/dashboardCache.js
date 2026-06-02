const HIGH_PRIORITY_CACHE_PREFIX = 'high-priority-requirements'
const HIGH_PRIORITY_CACHE_TTL_MS = 15 * 60 * 1000
const BDM_PERFORMANCE_CACHE_PREFIX = 'bdm-performance'
const BDM_PERFORMANCE_CACHE_TTL_MS = 15 * 60 * 1000

function getHighPriorityCacheKey(dateFrom, dateTo) {
  return `${HIGH_PRIORITY_CACHE_PREFIX}:${dateFrom || 'none'}:${dateTo || 'none'}`
}

export function readHighPriorityCache(dateFrom, dateTo) {
  try {
    const raw = localStorage.getItem(getHighPriorityCacheKey(dateFrom, dateTo))
    if (!raw) return null

    const parsed = JSON.parse(raw)

    if (Array.isArray(parsed)) {
      return parsed
    }

    const savedAt = Number(parsed?.savedAt || 0)
    const rows = parsed?.rows

    if (!Array.isArray(rows)) return null
    if (!savedAt || Date.now() - savedAt > HIGH_PRIORITY_CACHE_TTL_MS) return null

    return rows
  } catch {
    return null
  }
}

export function writeHighPriorityCache(dateFrom, dateTo, rows) {
  if (!Array.isArray(rows)) return

  try {
    localStorage.setItem(
      getHighPriorityCacheKey(dateFrom, dateTo),
      JSON.stringify({
        savedAt: Date.now(),
        rows,
      }),
    )
  } catch {
    // Storage can fail in private mode or when quota is full; keep rendering.
  }
}

function getBdmPerformanceCacheKey(period) {
  return `${BDM_PERFORMANCE_CACHE_PREFIX}:${period || 'today'}`
}

export function readBdmPerformanceCache(period) {
  try {
    const raw = localStorage.getItem(getBdmPerformanceCacheKey(period))
    if (!raw) return null

    const parsed = JSON.parse(raw)
    const savedAt = Number(parsed?.savedAt || 0)
    const rows = parsed?.rows

    if (!Array.isArray(rows)) return null
    if (!savedAt || Date.now() - savedAt > BDM_PERFORMANCE_CACHE_TTL_MS) return null

    return rows
  } catch {
    return null
  }
}

export function writeBdmPerformanceCache(period, rows) {
  if (!Array.isArray(rows)) return

  try {
    localStorage.setItem(
      getBdmPerformanceCacheKey(period),
      JSON.stringify({
        savedAt: Date.now(),
        rows,
      }),
    )
  } catch {
    // Storage can fail in private mode or when quota is full; keep rendering.
  }
}
