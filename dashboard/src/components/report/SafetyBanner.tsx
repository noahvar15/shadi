import { ShieldAlert } from 'lucide-react'
import type { VetoedItem } from '@/types/report'

interface SafetyBannerProps {
  vetoedRecommendations: VetoedItem[]
}

export function SafetyBanner({ vetoedRecommendations }: SafetyBannerProps) {
  if (vetoedRecommendations.length === 0) return null

  return (
    <div className="w-full bg-red-600 text-white px-4 py-3" role="alert" aria-live="assertive">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center gap-2 mb-2">
          <ShieldAlert className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
          <span className="font-semibold text-sm">
            Safety Veto — The following recommendations were blocked
          </span>
        </div>
        <ul className="space-y-1 pl-7">
          {vetoedRecommendations.map((item, idx) => (
            <li key={idx} className="text-sm">
              <span className="font-semibold">{item.recommendation}</span>
              {' — '}
              <span>{item.reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
