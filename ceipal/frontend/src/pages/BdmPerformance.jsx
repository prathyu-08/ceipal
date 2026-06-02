import { useCallback, useEffect, useState } from 'react'
import BdmPerformanceTable from '../components/BdmPerformanceTable'
import {
  getCachedBdmPerformance,
  loadBdmPerformance,
} from '../services/bdmPerformanceData'

const REFRESH_MS = 5 * 60 * 1000

export default function BdmPerformance() {
  const [period, setPeriod] = useState('today')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const loadRows = useCallback(async ({ force = false, quiet = false } = {}) => {
    if (!quiet) setLoading(true)
    setError(null)

    const cached = getCachedBdmPerformance(period)
    if (Array.isArray(cached)) {
      setRows(cached)
    }

    if (!force && Array.isArray(cached)) {
      setLoading(false)
      return
    }

    try {
      const nextRows = await loadBdmPerformance({ period, force })
      setRows(nextRows)
    } catch (err) {
      setError(err.message || 'Failed to load BDM performance')
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    const preloadDone = (() => {
      try {
        return localStorage.getItem('dashboard-preload-done') === '1'
      } catch {
        return false
      }
    })()

    // If preload already fetched `/dashboard/bdm-performance`, avoid forcing a 2nd request.
    loadRows({
      force: !preloadDone,
      quiet: preloadDone || Boolean(getCachedBdmPerformance(period)),
    })

    const timer = setInterval(() => loadRows({ quiet: true }), REFRESH_MS)
    return () => clearInterval(timer)
  }, [loadRows, period])


  return (
    <main className="relative min-h-[calc(100vh-78px)] overflow-hidden bg-[#030914]">
      <div className="executive-grid absolute inset-0" />
      <div className="relative z-10 mx-auto max-w-[1920px] px-8 py-9 sm:px-11">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-5xl font-black text-white sm:text-7xl">
              BDM Performance
            </h1>
          </div>

          <div className="flex rounded-2xl border border-cyan-500/20 bg-white/[0.04] p-1">
            {['today', 'yesterday'].map((option) => (
              <button
                key={option}
                onClick={() => setPeriod(option)}
                className={`rounded-xl px-5 py-2 text-sm font-black capitalize transition ${
                  period === option
                    ? 'bg-cyan-500 text-slate-950'
                    : 'text-slate-300 hover:bg-white/[0.06]'
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <BdmPerformanceTable data={rows} loading={loading} error={error} />
      </div>
    </main>
  )
}
