import { useState, useEffect, useCallback, useRef } from 'react'
import HighPriorityTable from '../components/HighPriorityTable'
import {
  getCachedHighPriorityRequirements,
  loadHighPriorityRequirements,
} from '../services/highPriorityData'

const QUICK_FILTERS = [
  { label: 'Today', key: 'today' },
  { label: 'Yesterday', key: 'yesterday' },
]

function getDateRange(key) {
  const today = new Date()
  const fmt = (d) => d.toISOString().split('T')[0]

  switch (key) {
    case 'today':
      return { dateFrom: fmt(today), dateTo: fmt(today) }
    case 'yesterday': {
      const y = new Date(today)
      y.setDate(y.getDate() - 1)
      return { dateFrom: fmt(y), dateTo: fmt(y) }
    }
    default:
      return { dateFrom: null, dateTo: null }
  }
}

export default function Dashboard() {
  const [requirements, setRequirements] = useState([])
  const [reqLoading, setReqLoading] = useState(true)
  const [reqError, setReqError] = useState(null)
  const [activeFilter, setActiveFilter] = useState('today')
  const latestRequestRef = useRef(0)

  const loadRequirements = useCallback(async (dateFrom, dateTo, { force = false } = {}) => {
    const requestId = latestRequestRef.current + 1
    latestRequestRef.current = requestId

    const cached = getCachedHighPriorityRequirements(dateFrom, dateTo)

    if (!force && Array.isArray(cached)) {
      setRequirements(cached)
      setReqLoading(false)
      setReqError(null)
      return
    }

    if (Array.isArray(cached)) {
      setRequirements(cached)
      setReqLoading(false)
    } else {
      setReqLoading(true)
    }

    setReqError(null)
    try {
      const rows = await loadHighPriorityRequirements({ dateFrom, dateTo, force })
      if (latestRequestRef.current !== requestId) return

      setRequirements(rows)
    } catch (err) {
      if (latestRequestRef.current === requestId && !cached) {
        setReqError(err.message || 'Failed to load')
      }
    } finally {
      if (latestRequestRef.current === requestId) {
        setReqLoading(false)
      }
    }
  }, [])

  const refreshAll = useCallback((force = false) => {
    const range = getDateRange(activeFilter)
    loadRequirements(range.dateFrom, range.dateTo, { force })
  }, [loadRequirements, activeFilter])

  useEffect(() => {
    refreshAll(true)
  }, [refreshAll])

  const handleQuickFilter = (key) => {
    setActiveFilter(key)
  }

  return (
    <main className="min-h-screen" style={{ background: '#020817' }}>
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage: 'linear-gradient(rgba(34,211,238,1) 1px, transparent 1px), linear-gradient(90deg, rgba(52,211,153,1) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[840px] h-[420px] rounded-full opacity-[0.18]"
          style={{ background: 'radial-gradient(ellipse, #22d3ee 0%, transparent 70%)', filter: 'blur(60px)' }}
        />
        <div className="absolute bottom-0 right-0 h-[420px] w-[520px] rounded-full opacity-[0.16]"
          style={{ background: 'radial-gradient(ellipse, #34d399 0%, transparent 70%)', filter: 'blur(70px)' }}
        />
        <div className="absolute bottom-10 left-0 h-[360px] w-[460px] rounded-full opacity-[0.12]"
          style={{ background: 'radial-gradient(ellipse, #a78bfa 0%, transparent 70%)', filter: 'blur(72px)' }}
        />
      </div>

      <div className="relative z-10 max-w-[1600px] mx-auto px-4 sm:px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 fade-up">
          <div>
            <h1 className="text-3xl sm:text-4xl font-bold text-white leading-tight"
              style={{ fontFamily: 'DM Sans, sans-serif' }}>
              Recruitment{' '}
              <span style={{
                background: 'linear-gradient(90deg, #22d3ee, #34d399, #a78bfa)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
              }}>Dashboard</span>
            </h1>
          </div>

          <button
            onClick={() => refreshAll(true)}
            disabled={reqLoading}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all
              bg-cyan-400/12 border border-cyan-300/35 text-cyan-200 shadow-[0_0_18px_rgba(34,211,238,0.12)]
              hover:bg-cyan-300/20 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              className={reqLoading ? 'animate-spin' : ''}>
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Refresh
          </button>
        </div>

        {/* Filter Bar */}
        <div className="glass-card rounded-xl px-5 py-4 fade-up delay-200">
          <div className="flex flex-wrap items-center gap-3">
            {/* Quick filter pills */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {QUICK_FILTERS.map((f) => (
                <button
                  key={f.key}
                  onClick={() => handleQuickFilter(f.key)}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-all
                    ${activeFilter === f.key
                      ? 'bg-gradient-to-r from-cyan-400/25 to-emerald-400/20 border border-cyan-300/55 text-cyan-100 shadow-[0_0_16px_rgba(34,211,238,0.18)]'
                      : 'bg-white/[0.06] border border-white/12 text-slate-300 hover:text-white hover:border-cyan-300/35'
                    }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

          </div>
        </div>

        {/* Table */}
        <HighPriorityTable data={requirements} loading={reqLoading} error={reqError} />

      </div>
    </main>
  )
}
