'use client'

import Link from 'next/link'
import { Stethoscope, ClipboardList, ArrowRight } from 'lucide-react'

export default function RolePage() {
  return (
    <div className="min-h-full flex flex-col items-center justify-center px-6 py-16">
      <div className="mb-10 text-center">
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Welcome to Shadi</h1>
        <p className="text-sm text-[var(--foreground-muted)] mt-1">Select your role to continue</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 w-full max-w-2xl">
        <Link
          href="/nurse"
          className="group flex flex-col gap-4 p-8 bg-[var(--surface)] border border-[var(--border)] rounded-card shadow-card hover:shadow-card-hover hover:border-emerald-400 dark:hover:border-emerald-500 transition-all duration-200"
        >
          <div className="flex items-start justify-between">
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/30">
              <Stethoscope size={40} className="text-emerald-600 dark:text-emerald-400" strokeWidth={1.5} />
            </div>
            <ArrowRight
              size={18}
              className="text-[var(--foreground-muted)] opacity-0 group-hover:opacity-100 translate-x-[-4px] group-hover:translate-x-0 transition-all duration-200"
            />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[var(--foreground)]">I&apos;m a Nurse</h2>
            <p className="text-sm text-[var(--foreground-muted)] mt-1">
              Enter triage notes for a new patient
            </p>
          </div>
        </Link>

        <Link
          href="/doctor"
          className="group flex flex-col gap-4 p-8 bg-[var(--surface)] border border-[var(--border)] rounded-card shadow-card hover:shadow-card-hover hover:border-emerald-400 dark:hover:border-emerald-500 transition-all duration-200"
        >
          <div className="flex items-start justify-between">
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/30">
              <ClipboardList size={40} className="text-emerald-600 dark:text-emerald-400" strokeWidth={1.5} />
            </div>
            <ArrowRight
              size={18}
              className="text-[var(--foreground-muted)] opacity-0 group-hover:opacity-100 translate-x-[-4px] group-hover:translate-x-0 transition-all duration-200"
            />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[var(--foreground)]">I&apos;m a Doctor</h2>
            <p className="text-sm text-[var(--foreground-muted)] mt-1">
              Review active cases and AI diagnostic reports
            </p>
          </div>
        </Link>
      </div>
    </div>
  )
}
