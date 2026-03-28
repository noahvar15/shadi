import { AlertTriangle } from 'lucide-react'

interface DebateSummaryProps {
  consensusLevel: number
  divergentAgents: string[]
}

function consensusPillClass(level: number): string {
  if (level > 0.8) return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'
  if (level >= 0.5) return 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200'
  return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
}

export function DebateSummary({ consensusLevel, divergentAgents }: DebateSummaryProps) {
  const pct = Math.round(consensusLevel * 100)

  return (
    <section aria-labelledby="debate-summary-heading" className="space-y-3">
      <h2
        id="debate-summary-heading"
        className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400"
      >
        Debate Summary
      </h2>

      <div className="flex items-center gap-3 flex-wrap">
        <span
          className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold ${consensusPillClass(consensusLevel)}`}
          aria-label={`Consensus level: ${pct}%`}
        >
          {pct}% consensus
        </span>

        {divergentAgents.length === 0 ? (
          <span className="text-sm text-slate-500 dark:text-slate-400">
            Full consensus reached
          </span>
        ) : (
          <div className="flex items-center gap-2 flex-wrap">
            {divergentAgents.map((agent) => (
              <span
                key={agent}
                className="inline-flex items-center gap-1 text-sm text-amber-700 dark:text-amber-400"
              >
                <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
                {agent}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
