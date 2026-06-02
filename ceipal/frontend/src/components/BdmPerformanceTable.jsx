/**
 * BdmPerformanceTable.jsx
 * -----------------------
 * Executive card layout for BDM KPI performance.
 */

const metricRows = [
  { label: 'Requirements', key: 'requirements_received', tone: 'cyan' },
  { label: 'Submitted', key: 'profiles_submitted', tone: 'cyan' },
  { label: 'Fbk Pending', key: 'feedback_pending', tone: 'amber' },
  { label: 'Interviews', key: 'interviews', tone: 'violet' },
  { label: 'Closures', key: 'closures', tone: 'green' },
]

const toneColor = {
  cyan: '#00eaff',
  amber: '#ff9f0a',
  violet: '#8d5cff',
  green: '#39ffad',
}

function MetricLine({ label, value, tone }) {
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-6 border-b border-white/7 py-1.5 last:border-b-0">
      <span className="text-lg font-black tracking-[-0.01em] text-white">
        {label}
      </span>
      <span
        className="font-mono text-3xl font-black leading-none"
        style={{ color: toneColor[tone] }}
      >
        {value ?? 0}
      </span>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="bdm-card h-[420px] p-7">
      <div className="shimmer h-10 w-44 rounded-full" />
      <div className="mt-8 space-y-5">
        {[1, 2, 3, 4].map((item) => (
          <div key={item} className="flex items-center justify-between">
            <div className="shimmer h-5 w-36 rounded-full" />
            <div className="shimmer h-8 w-14 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  )
}

function BdmCard({ row, featured }) {
  return (
    <article className={`bdm-card ${featured ? 'bdm-card-featured' : ''}`}>
      <div className="relative mb-5 flex h-[116px] items-start">
        <h2 className="pr-14 font-sans text-4xl font-black leading-[1.08] tracking-normal text-white sm:text-5xl">
          {row.bdm_name}
        </h2>
        {featured && (
          <span className="absolute right-0 top-0 text-4xl leading-none text-[#ffb000]">
            &#9733;
          </span>
        )}
      </div>
      <div className="space-y-1">
        {metricRows.map((metric) => (
          <MetricLine
            key={metric.key}
            label={metric.label}
            value={row[metric.key]}
            tone={metric.tone}
          />
        ))}
      </div>
    </article>
  )
}

export default function BdmPerformanceTable({ data, loading, error }) {
  const rows = Array.isArray(data) ? data : []
  const featuredIndex = rows.reduce((bestIndex, row, index) => {
    const best = rows[bestIndex]
    if (!best) return index
    return row.requirements_received > best.requirements_received ? index : bestIndex
  }, 0)

  if (error) {
    return (
      <div className="bdm-panel flex min-h-[280px] items-center justify-center px-6 text-center">
        <p className="max-w-3xl font-mono text-sm text-red-300">{error}</p>
      </div>
    )
  }

  return (
    <section className="bdm-panel">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {loading
          ? Array.from({ length: 5 }).map((_, index) => <SkeletonCard key={index} />)
          : rows.map((row, index) => (
              <BdmCard
                key={`${row.bdm_name}-${index}`}
                row={row}
                featured={index === featuredIndex && rows.length > 1}
              />
            ))}
      </div>

      {!loading && rows.length === 0 && (
        <div className="flex min-h-[280px] items-center justify-center text-center font-mono text-sm text-slate-500">
          No KPI data found.
        </div>
      )}
    </section>
  )
}
