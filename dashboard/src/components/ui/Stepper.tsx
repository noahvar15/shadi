'use client'

import { Check } from 'lucide-react'

interface StepperProps {
  steps: string[]
  currentStep: number
}

export function Stepper({ steps, currentStep }: StepperProps) {
  const safeCurrentStep = Math.min(Math.max(currentStep, 0), Math.max(steps.length - 1, 0))

  return (
    <nav aria-label="Form steps" className="flex items-start justify-between w-full">
      {steps.map((label, index) => {
        const isCompleted = index < safeCurrentStep
        const isCurrent = index === safeCurrentStep
        const isFuture = index > safeCurrentStep

        return (
          <div key={`${label}-${index}`} className="flex flex-col items-center flex-1 relative">
            {/* Connecting line — drawn to the right of each step except the last */}
            {index < steps.length - 1 && (
              <div
                className={`absolute top-4 left-1/2 w-full h-0.5 ${
                  isCompleted ? 'bg-emerald-500' : 'bg-slate-200 dark:bg-slate-700'
                }`}
                aria-hidden="true"
              />
            )}

            {/* Circle */}
            <div
              className={`relative z-10 h-8 w-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                isCompleted
                  ? 'bg-emerald-500 text-white'
                  : isCurrent
                    ? 'bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 ring-2 ring-emerald-500'
                    : isFuture
                      ? 'bg-white dark:bg-slate-900 text-slate-400 dark:text-slate-500 ring-2 ring-slate-300 dark:ring-slate-600'
                      : ''
              }`}
              aria-current={isCurrent ? 'step' : undefined}
            >
              {isCompleted ? (
                <Check size={14} strokeWidth={3} aria-hidden="true" />
              ) : (
                <span aria-hidden="true">{index + 1}</span>
              )}
              <span className="sr-only">
                {isCompleted ? 'Completed: ' : isCurrent ? 'Current step: ' : 'Upcoming: '}
                {label}
              </span>
            </div>

            {/* Label */}
            <span
              className={`mt-2 text-xs font-medium text-center leading-tight ${
                isCompleted || isCurrent
                  ? 'text-slate-700 dark:text-slate-200'
                  : 'text-slate-400 dark:text-slate-500'
              }`}
            >
              {label}
            </span>
          </div>
        )
      })}
    </nav>
  )
}
