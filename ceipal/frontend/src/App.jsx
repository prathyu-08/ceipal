import { useCallback, useEffect, useState } from 'react'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import PriorityScreen3 from './pages/priorityscreen3'
import RecruitingStatus from './pages/RecruitingStatus'
import BdmPerformance from './pages/BdmPerformance'

const SLIDES = [
  { key: 'status' },
  { key: 'dashboard' },
  { key: 'priority' },
  { key: 'bdm' },
]

const SLIDE_MS = 15000

export default function App() {
  const [activeSlide, setActiveSlide] = useState(0)

  const showNextSlide = useCallback(() => {
    setActiveSlide((slide) => (slide + 1) % SLIDES.length)
  }, [])

  useEffect(() => {
    if (SLIDES[activeSlide].key === 'dashboard') return undefined

    const timer = setTimeout(showNextSlide, SLIDE_MS)

    return () => clearTimeout(timer)
  }, [activeSlide, showNextSlide])

  const renderSlide = () => {
    switch (SLIDES[activeSlide].key) {
      case 'status':
        return <RecruitingStatus />
      case 'bdm':
        return <BdmPerformance />
      case 'dashboard':
        return <Dashboard onComplete={showNextSlide} />
      case 'priority':
        return <PriorityScreen3 />
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-[#03060f]">
      <Navbar />
      <div className="fixed bottom-5 left-1/2 z-50 flex -translate-x-1/2 gap-2 rounded-full border border-cyan-500/20 bg-[#06101f]/90 px-4 py-2 backdrop-blur-xl">
        {SLIDES.map((slide, index) => (
          <button
            key={slide.key}
            onClick={() => setActiveSlide(index)}
            className={`h-2.5 w-8 rounded-full transition ${
              index === activeSlide ? 'bg-cyan-300' : 'bg-white/20 hover:bg-white/40'
            }`}
            aria-label={`Show ${slide.key} slide`}
          />
        ))}
      </div>
      {renderSlide()}
    </div>
  )
}
