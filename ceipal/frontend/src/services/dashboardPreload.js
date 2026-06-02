import { loadBdmPerformance } from './bdmPerformanceData'
import { loadHighPriorityRequirements } from './highPriorityData'
import { loadRecruitingStatus } from './recruitingStatusData'

function getTodayRange() {
  const today = new Date()
  const date = today.toISOString().split('T')[0]

  return {
    dateFrom: date,
    dateTo: date,
  }
}

export async function preloadDashboardData() {
  const range = getTodayRange()

  const baseLoads = Promise.allSettled([
    loadRecruitingStatus({ force: true }),
    loadBdmPerformance({ period: 'today', force: true }),
  ])

  await Promise.allSettled([
    loadHighPriorityRequirements({ ...range, force: true, route: 'bdm-wise' }),
  ])
  await Promise.allSettled([
    loadHighPriorityRequirements({ ...range, force: true, route: 'high-priority' }),
  ])

  return baseLoads
}
