import { useCallback, useEffect, useState } from 'react'
import {
  getCachedRecruitingStatus,
  loadRecruitingStatus,
} from '../services/recruitingStatusData'

const metricCards = [
  { label: 'No. of Primary Recruiters', key: 'technicalRecruitersCount', tone: 'cyan' },
  { label: 'No. of Active Requirements as of Today', key: 'activeRequirementsAsOfToday', tone: 'green' },
  { label: 'No. of Active Requirements Carried Forward up to Yesterday', key: 'activeRequirementsCarriedForwardUpToYesterday', tone: 'amber' },
  { label: 'Recruiters Working on Requirements', key: 'recruitersWorkingOnRequirementsCount', tone: 'violet' },
  { label: 'Recruiters Idle / Not Assigned', key: 'idleRecruitersCount', tone: 'orange' },
  { label: 'Total Submissions Today', key: 'totalSubmissionsToday', tone: 'cyan' },
]

const toneClass = {
  cyan: 'text-[#00eaff]',
  green: 'text-[#39ffad]',
  amber: 'text-[#ffb000]',
  violet: 'text-[#8d5cff]',
  orange: 'text-[#ff9f0a]',
}

function isPersonName(value) {
  const name = String(value || '').trim()
  return (
    name.length > 1 &&
    name.length <= 60 &&
    /[a-z]/i.test(name) &&
    !/[0-9,/\\_=|]/.test(name)
  )
}

function StatusMetric({ metric, value }) {
  return (
    <article className="rounded-lg border border-white/10 bg-[#071120]/90 p-6 shadow-[0_18px_42px_rgba(0,0,0,0.24)]">
      <p className="min-h-[52px] text-xl font-black leading-tight text-white">
        {metric.label}
      </p>
      <strong className={`mt-6 block font-mono text-6xl font-black leading-none ${toneClass[metric.tone]}`}>
        {value ?? 0}
      </strong>
    </article>
  )
}

function NameList({ title, names, emptyText, accentClass }) {
  const displayNames = names.filter(isPersonName)

  return (
    <section className="rounded-lg border border-white/10 bg-[#071120]/90 p-6">
      <div className="mb-5 flex items-start justify-between gap-4">
        <h2 className={`text-2xl font-black ${accentClass}`}>{title}</h2>
        <span className="font-mono text-4xl font-black text-white">{displayNames.length}</span>
      </div>
      {displayNames.length ? (
        <div className="grid max-h-[320px] gap-3 overflow-y-auto pr-2 sm:grid-cols-2">
          {displayNames.map((name) => (
            <div
              key={name}
              className="rounded-md border border-white/10 bg-white/[0.04] px-4 py-3 text-lg font-black text-white"
            >
              {name}
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-white/10 bg-white/[0.04] px-4 py-8 text-center font-mono text-sm text-slate-400">
          {emptyText}
        </p>
      )}
    </section>
  )
}

export default function RecruitingStatus() {
  const [hasInitialCache] = useState(() => Boolean(getCachedRecruitingStatus()))
  const [data, setData] = useState(() => getCachedRecruitingStatus())
  const [loading, setLoading] = useState(() => !getCachedRecruitingStatus())
  const [error, setError] = useState(null)

  const loadStatus = useCallback(async ({ force = false, quiet = false } = {}) => {
    if (!quiet) setLoading(true)
    setError(null)

    const cached = getCachedRecruitingStatus()
    if (!force && cached) {
      setData(cached)
      setLoading(false)
      return
    }

    try {
      const status = await loadRecruitingStatus({ force })
      setData(status)
    } catch (err) {
      setError(err.message || 'Failed to load recruiting status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStatus({ force: true, quiet: hasInitialCache })
  }, [hasInitialCache, loadStatus])

  return (
    <main className="relative min-h-[calc(100vh-74px)] overflow-hidden bg-[#030914]">
      <div className="executive-grid absolute inset-0" />
      <div className="relative z-10 mx-auto max-w-[1920px] px-8 py-9 sm:px-11">
        <div className="mb-7">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h1 className="text-5xl font-black text-white sm:text-7xl">
              Recruiting Status
            </h1>
          </div>
        </div>

        {error && (
          <div className="mb-5 rounded-lg border border-red-400/20 bg-red-950/40 px-5 py-4 font-mono text-sm text-red-200">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {metricCards.map((metric) => (
            <StatusMetric
              key={metric.key}
              metric={metric}
              value={loading ? '...' : data?.[metric.key]}
            />
          ))}
        </div>

        <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-2">
          <NameList
            title="Recruiters Working on Requirements"
            names={data?.recruitersWorkingOnRequirements || []}
            emptyText="No recruiters currently assigned to active requirements."
            accentClass="text-[#39ffad]"
          />
          <NameList
            title="Idle / Not Assigned Recruiters"
            names={data?.idleRecruiters || []}
            emptyText="No idle recruiters currently identified."
            accentClass="text-[#ff9f0a]"
          />
        </div>
      </div>
    </main>
  )
}
