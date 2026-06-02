/**
 * Navbar.jsx
 * ----------
 * Futuristic dashboard navbar matching the BDM analytics UI.
 */

import { useState, useEffect } from 'react'

export default function Navbar() {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)

    return () => clearInterval(timer)
  }, [])

  const formatTime = (d) =>
    d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    })

  const formatDate = (d) =>
    d.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })

  return (
    <header className="sticky top-0 z-50 overflow-hidden border-b border-cyan-500/10 bg-[#07101D]/90 backdrop-blur-2xl">
      {/* BG GLOW */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -left-20 top-0 h-52 w-52 rounded-full bg-cyan-500/10 blur-3xl" />

        <div className="absolute right-0 top-0 h-52 w-52 rounded-full bg-blue-500/10 blur-3xl" />
      </div>

      <div className="relative z-10 flex h-[78px] items-center justify-between px-6 lg:px-8">
        {/* LEFT */}
        <div className="flex items-center">
          {/* BRAND */}
          <div className="flex h-[52px] w-[230px] items-center rounded-md bg-white px-3 shadow-[0_0_18px_rgba(0,255,255,0.14)] ring-1 ring-cyan-400/10 sm:w-[310px] lg:w-[380px]">
            <img
              src="/nmk-global-logo.png"
              alt="NMK Global Incorporated"
              className="h-full w-full object-contain"
            />
          </div>
        </div>

        {/* RIGHT */}
        <div className="flex items-center gap-5">
          {/* CLOCK */}
          <div className="hidden sm:block text-right">
            <p
              className="text-2xl font-black text-white"
              style={{
                fontFamily:
                  'DM Sans, sans-serif',
              }}
            >
              {formatTime(time)}
            </p>

            <p className="mt-1 text-[11px] tracking-wide text-slate-400">
              {formatDate(time)}
            </p>
          </div>

          {/* LIVE STATUS */}
          <div className="flex items-center gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2 backdrop-blur-xl">
            <div className="relative flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>

              <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-400"></span>
            </div>

            <span className="text-xs font-bold uppercase tracking-[0.25em] text-emerald-300">
              Live
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
