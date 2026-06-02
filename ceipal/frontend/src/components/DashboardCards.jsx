/**
 * DashboardCards.jsx
 * ------------------
 * Four KPI summary cards:
 *   Active Jobs | Recruiters | Applicants | Submissions
 *
 * Props:
 *   stats   - { active_jobs, total_recruiters, total_applicants, total_submissions }
 *   loading - boolean
 *   error   - string | null
 */

const CARD_CONFIGS = [
  {
    key: 'active_jobs',
    label: 'Active Jobs',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="2" y="7" width="20" height="14" rx="2" />
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
        <line x1="12" y1="12" x2="12" y2="16" />
        <line x1="10" y1="14" x2="14" y2="14" />
      </svg>
    ),
    accent: '#00f5ff',
    glow: 'rgba(0,245,255,0.2)',
    bg: 'rgba(0,245,255,0.06)',
    borderColor: 'rgba(0,245,255,0.2)',
  },
  {
    key: 'total_recruiters',
    label: 'Recruiters',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
    accent: '#818cf8',
    glow: 'rgba(129,140,248,0.2)',
    bg: 'rgba(129,140,248,0.06)',
    borderColor: 'rgba(129,140,248,0.2)',
  },
  {
    key: 'total_applicants',
    label: 'Applicants',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
    accent: '#34d399',
    glow: 'rgba(52,211,153,0.2)',
    bg: 'rgba(52,211,153,0.06)',
    borderColor: 'rgba(52,211,153,0.2)',
  },
  {
    key: 'total_submissions',
    label: 'Submissions',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
    accent: '#fb923c',
    glow: 'rgba(251,146,60,0.2)',
    bg: 'rgba(251,146,60,0.06)',
    borderColor: 'rgba(251,146,60,0.2)',
  },
]

function SkeletonCard({ delay }) {
  return (
    <div
      className="glass-card p-6 rounded-2xl shimmer"
      style={{ animationDelay: `${delay}ms`, minHeight: 140 }}
    />
  )
}

function KpiCard({ config, value, delay }) {
  return (
    <div
      className="glass-card rounded-2xl p-6 fade-up group hover:scale-[1.02] transition-transform duration-300 cursor-default"
      style={{
        animationDelay: `${delay}ms`,
        borderColor: config.borderColor,
        background: `linear-gradient(135deg, ${config.bg} 0%, rgba(6,13,31,0.9) 100%)`,
      }}
    >
      {/* Icon */}
      <div
        className="w-11 h-11 rounded-xl flex items-center justify-center mb-4"
        style={{
          background: config.bg,
          border: `1px solid ${config.borderColor}`,
          color: config.accent,
          boxShadow: `0 0 20px ${config.glow}`,
        }}
      >
        {config.icon}
      </div>

      {/* Value */}
      <p
        className="font-display text-4xl font-bold leading-none mb-1"
        style={{
          color: config.accent,
          fontFamily: 'DM Sans, sans-serif',
          textShadow: `0 0 20px ${config.glow}`,
        }}
      >
        {value?.toLocaleString() ?? '—'}
      </p>

      {/* Label */}
      <p className="text-slate-400 text-sm font-medium tracking-wide mt-2">
        {config.label}
      </p>

      {/* Bottom accent line */}
      <div
        className="mt-4 h-[2px] rounded-full opacity-40 group-hover:opacity-70 transition-opacity"
        style={{ background: `linear-gradient(90deg, ${config.accent}, transparent)` }}
      />
    </div>
  )
}

export default function DashboardCards({ stats, loading, error }) {
  if (error) {
    return (
      <div className="col-span-4 text-center py-8">
        <p className="text-red-400 text-sm font-mono">⚠ Failed to load KPIs: {error}</p>
      </div>
    )
  }

  if (loading) {
    return (
      <>
        {CARD_CONFIGS.map((c, i) => (
          <SkeletonCard key={c.key} delay={i * 80} />
        ))}
      </>
    )
  }

  return (
    <>
      {CARD_CONFIGS.map((config, i) => (
        <KpiCard
          key={config.key}
          config={config}
          value={stats?.[config.key]}
          delay={i * 80}
        />
      ))}
    </>
  )
}
