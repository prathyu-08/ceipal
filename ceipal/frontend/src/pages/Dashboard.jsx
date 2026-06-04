import {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from 'react'

import {
  getCachedHighPriorityRequirements,
  loadHighPriorityRequirements,
} from '../services/highPriorityData'
import PriorityScreen3 from './priorityscreen3'

const QUICK_FILTERS = [
  { label: 'Today', key: 'today' },
  { label: 'Yesterday', key: 'yesterday' },
]

const REQUIREMENTS_PER_PAGE = 5
const PAGE_DURATION = 15000

function getDateRange(key) {
  const today = new Date()

  const fmt = (d) =>
    d.toISOString().split('T')[0]

  switch (key) {
    case 'today':
      return {
        dateFrom: fmt(today),
        dateTo: fmt(today),
      }

    case 'yesterday': {
      const y = new Date(today)

      y.setDate(y.getDate() - 1)

      return {
        dateFrom: fmt(y),
        dateTo: fmt(y),
      }
    }

    default:
      return {
        dateFrom: null,
        dateTo: null,
      }
  }
}

function PriorityPill({ priority }) {
  const key = String(
    priority || 'Not Set',
  ).toLowerCase()

  const config =
    {
      critical:
        'bg-red-500/15 text-red-300 border-red-400/20',

      high:
        'bg-orange-500/15 text-orange-300 border-orange-400/20',

      medium:
        'bg-yellow-500/15 text-yellow-300 border-yellow-400/20',

      low:
        'bg-green-500/15 text-green-300 border-green-400/20',

      'not set':
        'bg-slate-500/15 text-slate-300 border-slate-400/20',
    }[key] ||
    'bg-cyan-500/15 text-cyan-300 border-cyan-400/20'

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold ${config}`}
    >
      <span className="h-2 w-2 rounded-full bg-current animate-pulse" />

      {priority || 'Not Set'}
    </span>
  )
}

function StatusBadge({ status }) {
  const key = String(
    status || 'Pending',
  ).toLowerCase()

  const config = key.includes('placed')
    ? 'bg-green-500/15 text-green-300 border-green-400/20'
    : key.includes('interview')
      ? 'bg-blue-500/15 text-blue-300 border-blue-400/20'
      : key.includes('reject')
        ? 'bg-red-500/15 text-red-300 border-red-400/20'
        : key.includes('submit')
          ? 'bg-indigo-500/15 text-indigo-300 border-indigo-400/20'
          : 'bg-slate-500/15 text-slate-300 border-slate-400/20'

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold ${config}`}
    >
      <span className="h-2 w-2 rounded-full bg-current animate-pulse" />

      {status || 'Pending'}
    </span>
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

function MetricCard({ label, value }) {
  return (
    <div className="relative overflow-hidden rounded-[24px] border border-cyan-500/10 bg-[#0d1726] p-5 backdrop-blur-xl shadow-[0_0_35px_rgba(0,255,255,0.05)]">
      <div className="absolute inset-0 rounded-[24px] bg-gradient-to-br from-white/[0.03] to-transparent" />

      <div className="relative z-10">
        <p className="text-[10px] uppercase tracking-[0.25em] text-cyan-300">
          {label}
        </p>

        <div
          className="mt-4 text-4xl font-black text-white"
          style={{
            fontFamily:
              'DM Sans, sans-serif',
          }}
        >
          {value}
        </div>
      </div>
    </div>
  )
}

export default function Dashboard({ onComplete }) {
  // Fetch once and reuse the same requirements dataset for the entire UI.
  // This prevents BDM-wise and High-priority from re-fetching the same range.
  const [requirements, setRequirements] =
    useState([])

  const [reqLoading, setReqLoading] =
    useState(true)


  const [reqError, setReqError] =
    useState(null)

  const [activeSlide, setActiveSlide] =
    useState(0)

  const [showPriorityScreen, setShowPriorityScreen] =
    useState(false)

  const [requirementPage, setRequirementPage] =
    useState(1)

  const [activeFilter, setActiveFilter] =
    useState('today')

  const latestRequestRef = useRef(0)

  const loadRequirements = useCallback(
    async (dateFrom, dateTo, { force = false } = {}) => {
      const requestId =
        latestRequestRef.current + 1

      latestRequestRef.current = requestId

      const cached = getCachedHighPriorityRequirements(
        dateFrom,
        dateTo,
      )

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
        const rows =
          await loadHighPriorityRequirements({
            dateFrom,
            dateTo,
            force,
            route: 'bdm-wise',
          })

        if (latestRequestRef.current !== requestId) {
          return
        }

        setRequirements(rows)

      } catch (err) {
        if (latestRequestRef.current === requestId && !cached) {
          setReqError(
            err.message || 'Failed to load',
          )
        }
      } finally {
        if (latestRequestRef.current === requestId) {
          setReqLoading(false)
        }
      }
    },
    [],
  )

  useEffect(() => {
    const range =
      getDateRange(activeFilter)

    loadRequirements(
      range.dateFrom,
      range.dateTo,
      { force: true },
    )
  }, [activeFilter, loadRequirements])

  const groupedBdms = useMemo(() => {
    const groups = new Map()

    requirements.forEach((item) => {
      const bdm =
        item.bdm || 'Unassigned BDM'

      if (!groups.has(bdm)) {
        groups.set(bdm, {
          bdm,
          requirements: [],
          recruiters: new Set(),
          leads: new Set(),
          totalSubmissions: 0,
        })
      }

      const group = groups.get(bdm)

      group.requirements.push(item)

      group.totalSubmissions += Number(
        item.submissions || 0,
      )

      String(
        item.recruiter || 'Unassigned',
      )
        .split(',')
        .map((name) => name.trim())
        .filter(Boolean)
        .forEach((name) =>
          group.recruiters.add(name),
        )

      String(
        item.lead || 'Unassigned',
      )
        .split(',')
        .map((name) => name.trim())
        .filter(Boolean)
        .forEach((name) =>
          group.leads.add(name),
        )
    })

    return Array.from(groups.values())
      .map((group) => ({
        ...group,

        recruiters: Array.from(
          group.recruiters,
        ).sort((a, b) =>
          a.localeCompare(b),
        ),
        leads: Array.from(
          group.leads,
        ).sort((a, b) =>
          a.localeCompare(b),
        ),
      }))
      .sort(
        (a, b) =>
          b.totalSubmissions -
            a.totalSubmissions ||
          a.bdm.localeCompare(b.bdm),
      )
  }, [requirements])

  const activeBdm =
    groupedBdms[activeSlide]

  const requirementTotalPages =
    activeBdm
      ? Math.max(
          1,
          Math.ceil(
            activeBdm.requirements.length /
              REQUIREMENTS_PER_PAGE,
          ),
        )
      : 1

  const pagedRequirements = activeBdm
    ? activeBdm.requirements.slice(
        (requirementPage - 1) *
          REQUIREMENTS_PER_PAGE,
        requirementPage *
          REQUIREMENTS_PER_PAGE,
      )
    : []

  useEffect(() => {
    if (!reqLoading && !reqError && !activeBdm && onComplete) {
      const emptyTimer = setTimeout(onComplete, PAGE_DURATION)
      return () => clearTimeout(emptyTimer)
    }

    if (showPriorityScreen) {
      const priorityTimer =
        setTimeout(() => {
          if (onComplete) {
            onComplete()
            return
          }

          setShowPriorityScreen(false)

          setActiveSlide(0)

          setRequirementPage(1)
        }, PAGE_DURATION)

      return () =>
        clearTimeout(priorityTimer)
    }

    if (!activeBdm) return

    const timer = setTimeout(() => {
      if (
        requirementPage <
        requirementTotalPages
      ) {
        setRequirementPage(
          (prev) => prev + 1,
        )
      } else {
        const isLastBdm =
          activeSlide ===
          groupedBdms.length - 1

        if (isLastBdm) {
          if (onComplete) {
            onComplete()
          } else {
            setShowPriorityScreen(true)
          }
        } else {
          setActiveSlide(
            (prev) => prev + 1,
          )
        }

        setRequirementPage(1)
      }
    }, PAGE_DURATION)

    return () => clearTimeout(timer)
  }, [
    reqLoading,
    reqError,
    activeBdm,
    requirementPage,
    requirementTotalPages,
    groupedBdms.length,
    activeSlide,
    showPriorityScreen,
    onComplete,
  ])

  return (
    <main className="min-h-screen" style={{ background: '#03060f' }}>
      {/* BACKGROUND */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: 'linear-gradient(rgba(0,245,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,245,255,1) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[800px] h-[400px] rounded-full opacity-[0.08]"
          style={{ background: 'radial-gradient(ellipse, #00f5ff 0%, transparent 70%)', filter: 'blur(60px)' }}
        />
      </div>

      <div className="relative z-10 max-w-[1600px] mx-auto px-4 sm:px-6 py-8 space-y-6">
        <div>
          <h1 className="text-4xl font-black text-white sm:text-6xl">
            BDM Wise
          </h1>
        </div>

        {/* FILTERS */}
        <section className="rounded-[28px] border border-cyan-500/10 bg-[#06101f]/95 p-5 backdrop-blur-xl shadow-[0_0_40px_rgba(0,255,255,0.04)]">
          <div className="flex flex-wrap items-center gap-3">
            {QUICK_FILTERS.map(
              (filter) => (
                <button
                  key={filter.key}
                  onClick={() =>
                    setActiveFilter(
                      filter.key,
                    )
                  }
                  className={`h-11 rounded-2xl px-5 text-sm font-semibold transition-all ${
                    activeFilter ===
                    filter.key
                      ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-[0_0_20px_rgba(0,255,255,0.25)]'
                      : 'border border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]'
                  }`}
                >
                  {filter.label}
                </button>
              ),
            )}

          </div>
        </section>

        {/* MAIN */}
        <section className="mt-5">
          <div className="col-span-12">
            {reqLoading ? (
              <div className="rounded-[30px] border border-cyan-500/10 bg-[#06101f]/95 p-20 text-center backdrop-blur-xl">
                <div className="mx-auto h-14 w-14 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent" />

                <p className="mt-5 text-slate-300">
                  Loading analytics...
                </p>
              </div>
            ) : reqError ? (
              <div className="rounded-[30px] border border-red-500/20 bg-red-500/10 p-10 text-center text-red-300">
                {reqError}
              </div>
            ) : !activeBdm ? (
              <div className="rounded-[30px] border border-cyan-500/10 bg-[#06101f]/95 p-20 text-center backdrop-blur-xl">
                No data found
              </div>
            ) : showPriorityScreen ? (
              <PriorityScreen3 />
            ) : (
              <div
                key={`${activeSlide}-${requirementPage}`}
                className="animate-[fadeSlide_0.8s_ease] overflow-hidden rounded-[30px] border border-cyan-500/10 bg-[#06101f]/95 backdrop-blur-xl shadow-[0_0_60px_rgba(0,255,255,0.05)]"
              >
                {/* HEADER */}
                <div className="px-6 pt-6 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[rgba(0,245,255,0.08)]">
                  <div>
                    <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">
                      Recruitment Manager
                    </p>

                    <h2
                      className="mt-3 text-6xl font-black text-white tracking-tight"
                      style={{
                        fontFamily:
                          'DM Sans, sans-serif',
                      }}
                    >
                      {activeBdm.bdm}
                    </h2>
                  </div>

                  <div className="grid grid-cols-3 gap-5">
                    <MetricCard
                      label="Requirements"
                      value={
                        activeBdm.requirements
                          .length
                      }
                    />

                    <MetricCard
                      label="Submissions"
                      value={
                        activeBdm.totalSubmissions
                      }
                    />

                    <MetricCard
                      label="Leads"
                      value={
                        activeBdm.leads
                          .length
                      }
                    />
                  </div>
                </div>

                {/* TABLE */}
                <div className="overflow-hidden">
                  <table className="w-full">
                    <thead className="sticky top-0 bg-[#0b1628]">
                      <tr className="border-b border-white/[0.05]">
                        {[
                          'Requirement',
                          'Lead',
                          'Recruiter',
                          'Priority',
                          'Submissions',
                          'Status',
                        ].map((column) => (
                          <th
                            key={column}
                            className="px-8 py-5 text-left text-[11px] uppercase tracking-[0.3em] text-cyan-300"
                          >
                            {column}
                          </th>
                        ))}
                      </tr>
                    </thead>

                    <tbody>
                      {pagedRequirements.map(
                        (
                          row,
                          index,
                        ) => (
                          <tr
                            key={index}
                            className="border-b border-white/[0.03] transition hover:bg-cyan-500/5"
                          >
                            <td className="px-8 py-5 font-semibold text-white text-lg">
                              {
                                row.requirement
                              }
                            </td>

                            <td className="px-8 py-5 text-slate-300">
                              {
                                getLead(row.lead)
                              }
                            </td>

                            <td className="px-8 py-5 text-slate-300">
                              {
                                getAssignedRecruiter(row.recruiter)
                              }
                            </td>

                            <td className="px-8 py-5">
                              <PriorityPill
                                priority={
                                  row.priority
                                }
                              />
                            </td>

                            <td
                              className="px-8 py-5 text-4xl font-black text-white"
                              style={{
                                fontFamily:
                                  'DM Sans, sans-serif',
                              }}
                            >
                              {
                                row.submissions
                              }
                            </td>

                            <td className="px-8 py-5">
                              <StatusBadge
                                status={
                                  row.submission_status
                                }
                              />
                            </td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>

                {/* NAVIGATION */}
                <div className="flex items-center justify-between border-t border-white/5 px-8 py-5">
                  <button
                    onClick={() => {
                      setRequirementPage(1)

                      setActiveSlide(
                        (prev) =>
                          prev === 0
                            ? groupedBdms.length -
                              1
                            : prev - 1,
                      )
                    }}
                    className="flex items-center gap-2 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-6 py-3 text-sm font-semibold text-cyan-300 transition hover:bg-cyan-500/20"
                  >
                    ← Previous
                  </button>

                  <div className="flex items-center gap-3">
                    {groupedBdms.map(
                      (_, index) => (
                        <button
                          key={index}
                          onClick={() => {
                            setActiveSlide(
                              index,
                            )

                            setRequirementPage(1)
                          }}
                          className={`h-3 w-3 rounded-full transition ${
                            activeSlide ===
                            index
                              ? 'bg-cyan-400 scale-125'
                              : 'bg-white/20 hover:bg-white/40'
                          }`}
                        />
                      ),
                    )}
                  </div>

                  <button
                    onClick={() => {
                      setRequirementPage(1)

                      setActiveSlide(
                        (prev) =>
                          groupedBdms.length
                            ? (prev + 1) %
                              groupedBdms.length
                            : 0,
                      )
                    }}
                    className="flex items-center gap-2 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-6 py-3 text-sm font-semibold text-cyan-300 transition hover:bg-cyan-500/20"
                  >
                    Next →
                  </button>
                </div>

                {/* FOOTER */}
                <div className="flex items-center justify-between border-t border-white/5 px-8 py-4 text-sm text-slate-400">
                  <div>
                    BDM{' '}
                    {activeSlide + 1} of{' '}
                    {groupedBdms.length}
                  </div>

                  <div>
                    Page{' '}
                    {requirementPage} of{' '}
                    {requirementTotalPages}
                  </div>

                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  )
}
