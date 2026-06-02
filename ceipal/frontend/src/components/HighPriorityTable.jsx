/**
 * HighPriorityTable.jsx
 * ---------------------
 * Renders the posted requirements table matching the reference design.
 *
 * Columns:
 * Lead | Recruiter | Job Title | Priority | No. of Submissions |
 * Time to Submit | Submission Status
 */

import { useState, useMemo, useEffect } from 'react'

const PAGE_DURATION = 15000

// ── Priority badge ───────────────────────────────────────────────────────────
function PriorityBadge({ priority }) {
  const p = priority?.toLowerCase() ?? ''

  const config = {
    critical: {
      bg: 'rgba(248,113,113,0.22)',
      border: 'rgba(248,113,113,0.62)',
      color: '#fca5a5',
      dot: '#fb7185',
    },
    high: {
      bg: 'rgba(251,146,60,0.22)',
      border: 'rgba(251,146,60,0.62)',
      color: '#fdba74',
      dot: '#fb923c',
    },
    medium: {
      bg: 'rgba(250,204,21,0.2)',
      border: 'rgba(250,204,21,0.58)',
      color: '#fde68a',
      dot: '#facc15',
    },
    low: {
      bg: 'rgba(52,211,153,0.2)',
      border: 'rgba(52,211,153,0.58)',
      color: '#86efac',
      dot: '#34d399',
    },
    'not set': {
      bg: 'rgba(100,116,139,0.1)',
      border: 'rgba(100,116,139,0.25)',
      color: '#64748b',
      dot: '#475569',
    },
  }[p] || {
    bg: 'rgba(100,116,139,0.15)',
    border: 'rgba(100,116,139,0.4)',
    color: '#94a3b8',
    dot: '#94a3b8',
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium tracking-wide"
      style={{
        background: config.bg,
        border: `1px solid ${config.border}`,
        color: config.color,
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: config.dot }}
      />
      {priority}
    </span>
  )
}

// ── Submission status badge ──────────────────────────────────────────────────
function StatusBadge({ status }) {
  const s = status?.toLowerCase() ?? ''

  let config = {
    bg: 'rgba(148,163,184,0.16)',
    border: 'rgba(148,163,184,0.34)',
    color: '#cbd5e1',
  }

  if (s.includes('progress') || s.includes('waiting')) {
    config = {
      bg: 'rgba(96,165,250,0.2)',
      border: 'rgba(96,165,250,0.5)',
      color: '#93c5fd',
    }
  } else if (s.includes('submitted') || s.includes('approved')) {
    config = {
      bg: 'rgba(52,211,153,0.2)',
      border: 'rgba(52,211,153,0.5)',
      color: '#86efac',
    }
  } else if (s.includes('rejected') || s.includes('declined')) {
    config = {
      bg: 'rgba(248,113,113,0.2)',
      border: 'rgba(248,113,113,0.5)',
      color: '#fca5a5',
    }
  }

  return (
    <span
      className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium tracking-wide"
      style={{
        background: config.bg,
        border: `1px solid ${config.border}`,
        color: config.color,
      }}
    >
      {status}
    </span>
  )
}

// ── Skeleton row ─────────────────────────────────────────────────────────────
function SkeletonRow({ i }) {
  return (
    <tr key={i}>
      {[18, 22, 35, 15, 10, 15, 20].map((w, j) => (
        <td key={j} className="px-5 py-4">
          <div
            className="h-3 rounded-full shimmer"
            style={{
              width: `${w}%`,
              animationDelay: `${(i * 6 + j) * 60}ms`,
            }}
          />
        </td>
      ))}
    </tr>
  )
}

function getAssignedRecruiter(recruiter) {
  const raw = String(recruiter || 'Unassigned').trim()
  if (!raw) return 'Unassigned'
  return raw.split(',')[0].trim()
}

function getLead(lead) {
  const raw = String(lead || 'Unassigned').trim()
  if (!raw) return 'Unassigned'
  return raw.split(',')[0].trim()
}

function getTimeToSubmit(row) {
  return row.time_to_submit || row.timeToSubmit || row.timeToSubmitText || '--'
}

// ── Main component ───────────────────────────────────────────────────────────
export default function HighPriorityTable({
  data,
  loading,
  error,
}) {
  const [sortField, setSortField] = useState('submissions')
  const [sortDir, setSortDir] = useState('desc')
  const [page, setPage] = useState(1)

  const PAGE_SIZE = 10

  const filtered = useMemo(() => {
    if (!data) return []
    return data
  }, [data])

  const parseTimeToSubmitHours = (t) => {
    if (!t || typeof t !== 'string') {
      return Number.NEGATIVE_INFINITY
    }

    const m = t.match(/(\d+)d\s+(\d+)h/i)

    if (m) {
      const d = Number(m[1])
      const h = Number(m[2])
      return d * 24 + h
    }

    const n = Number.parseFloat(t)
    return Number.isFinite(n)
      ? n
      : Number.NEGATIVE_INFINITY
  }

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      if (sortField === 'time_to_submit') {
        const av = parseTimeToSubmitHours(getTimeToSubmit(a))
        const bv = parseTimeToSubmitHours(getTimeToSubmit(b))

        return sortDir === 'asc'
          ? av - bv
          : bv - av
      }

      const av = a[sortField]
      const bv = b[sortField]

      if (typeof av === 'number') {
        return sortDir === 'asc'
          ? av - bv
          : bv - av
      }

      return sortDir === 'asc'
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av))
    })
  }, [filtered, sortField, sortDir])

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)

  const paged = sorted.slice(
    (page - 1) * PAGE_SIZE,
    page * PAGE_SIZE
  )

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('asc')
    }

    setPage(1)
  }

  useEffect(() => {
    if (totalPages <= 1) return undefined

    const timer = setTimeout(() => {
      setPage((currentPage) =>
        currentPage >= totalPages ? 1 : currentPage + 1
      )
    }, PAGE_DURATION)

    return () => clearTimeout(timer)
  }, [page, totalPages])

  const SortIcon = ({ field }) => {
    if (sortField !== field) {
      return (
        <span className="text-slate-600 ml-1">
          ↕
        </span>
      )
    }

    return (
      <span className="text-[#00f5ff] ml-1">
        {sortDir === 'asc' ? '↑' : '↓'}
      </span>
    )
  }

  const columns = [
    { key: 'lead', label: 'Lead' },
    { key: 'recruiter', label: 'Recruiter' },
    { key: 'requirement', label: 'Job Title' },
    { key: 'priority', label: 'Priority' },
    { key: 'submissions', label: 'No. of Submissions' },
    { key: 'time_to_submit', label: 'Time to Submit' },
    { key: 'submission_status', label: 'Submission Status' },
  ]

  return (
    <div className="overflow-hidden rounded-2xl border border-cyan-300/25 bg-[#061525]/95 shadow-[0_0_48px_rgba(34,211,238,0.14)] fade-up delay-500">

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">

          <thead>
            <tr className="border-b border-cyan-300/15 bg-[#09233a]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className="px-5 py-4 text-left text-xs font-mono font-bold text-cyan-200 tracking-widest uppercase cursor-pointer hover:text-emerald-200 transition-colors select-none"
                >
                  {col.label}
                  <SortIcon field={col.key} />
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {error ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-5 py-12 text-center text-red-400 text-sm font-mono"
                >
                  ⚠ {error}
                </td>
              </tr>
            ) : loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <SkeletonRow key={i} i={i} />
              ))
            ) : paged.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-5 py-16 text-center text-slate-600 text-sm font-mono"
                >
                  No activity found for today.
                </td>
              </tr>
            ) : (
              paged.map((row, i) => (
                <tr
                  key={`${row.job_code}-${i}`}
                  className="border-b border-cyan-100/[0.06] bg-white/[0.015] transition hover:bg-cyan-300/[0.08]"
                >

                  {/* Recruiter */}
                  <td className="px-5 py-4">
                    <span className="text-cyan-100 font-medium text-sm">
                      {getLead(row.lead)}
                    </span>
                  </td>

                  <td className="px-5 py-4">
                    <span className="text-slate-100 font-medium text-sm">
                      {getAssignedRecruiter(row.recruiter)}
                    </span>
                  </td>

                  {/* Job Title */}
                  <td className="px-5 py-4">
                    <p className="text-white font-semibold leading-tight">
                      {row.requirement}
                    </p>
                  </td>

                  {/* Priority */}
                  <td className="px-5 py-4">
                    <PriorityBadge priority={row.priority} />
                  </td>

                  {/* Submissions */}
                  <td className="px-5 py-4 text-center">
                    <span
                      className="text-2xl font-bold font-mono"
                      style={{
                        color:
                          row.submissions >= 10
                            ? '#22d3ee'
                            : row.submissions >= 5
                            ? '#a78bfa'
                            : '#34d399',
                      }}
                    >
                      {row.submissions}
                    </span>
                  </td>

                  {/* Time */}
                  <td className="px-5 py-4">
                    <span
                      className="font-mono text-sm"
                      style={{ color: '#fbbf24' }}
                    >
                      {getTimeToSubmit(row)}
                    </span>
                  </td>

                  {/* Status */}
                  <td className="px-5 py-4">
                    <StatusBadge
                      status={row.submission_status}
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {!loading && !error && totalPages > 1 && (
        <div className="px-6 py-4 flex items-center justify-between border-t border-[rgba(255,255,255,0.05)]">

          <p className="text-xs text-slate-600 font-mono">
            Page {page} / {totalPages} · {sorted.length} results
          </p>

          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1.5 rounded-lg text-xs font-mono bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-slate-400 hover:border-[rgba(0,245,255,0.3)] hover:text-[#00f5ff] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              ← Prev
            </button>

            <button
              disabled={page === totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1.5 rounded-lg text-xs font-mono bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-slate-400 hover:border-[rgba(0,245,255,0.3)] hover:text-[#00f5ff] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
