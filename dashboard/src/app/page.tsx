'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Stethoscope, ClipboardList, ArrowRight, ArrowLeft } from 'lucide-react'

type Role = 'nurse' | 'doctor'
type Step = 'select' | 'login'

export default function RolePage() {
  const router = useRouter()
  const [step, setStep] = useState<Step>('select')
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  function selectRole(role: Role) {
    setSelectedRole(role)
    setStep('login')
    setError(null)
    setUsername('')
    setPassword('')
  }

  function handleBack() {
    setStep('select')
    setSelectedRole(null)
    setUsername('')
    setPassword('')
    setError(null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!username.trim() || !password) {
      setError('Username and password are required.')
      return
    }

    localStorage.setItem(
      'shadi_session',
      JSON.stringify({ role: selectedRole, name: username.trim() })
    )
    router.push(selectedRole === 'nurse' ? '/nurse' : '/doctor')
  }

  return (
    <div className="min-h-full flex flex-col items-center justify-center px-6 py-16">
      {step === 'select' && (
        <div className="w-full animate-fade-in">
          <div className="mb-10 text-center">
            <div className="inline-flex items-center gap-2 mb-3">
              <Stethoscope size={28} className="text-emerald-500 dark:text-emerald-400" strokeWidth={1.5} />
              <span className="text-3xl font-bold text-[var(--foreground)] tracking-tight">Shadi</span>
            </div>
            <p className="text-sm text-[var(--foreground-muted)]">Clinical diagnostic assistant — select your role to continue</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 w-full max-w-2xl mx-auto">
            <button
              onClick={() => selectRole('nurse')}
              className="group flex flex-col gap-4 p-8 bg-[var(--surface)] border border-[var(--border)] rounded-card shadow-card hover:shadow-card-hover hover:border-emerald-400 dark:hover:border-emerald-500 transition-all duration-200 text-left"
            >
              <div className="flex items-start justify-between">
                <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/30">
                  <Stethoscope size={40} className="text-emerald-600 dark:text-emerald-400" strokeWidth={1.5} />
                </div>
                <ArrowRight
                  size={18}
                  className="text-[var(--foreground-muted)] opacity-0 group-hover:opacity-100 translate-x-[-4px] group-hover:translate-x-0 transition-all duration-200 mt-1"
                />
              </div>
              <div>
                <h2 className="text-lg font-bold text-[var(--foreground)]">I&apos;m a Nurse</h2>
                <p className="text-sm text-[var(--foreground-muted)] mt-1">
                  Enter triage notes for a new patient
                </p>
              </div>
            </button>

            <button
              onClick={() => selectRole('doctor')}
              className="group flex flex-col gap-4 p-8 bg-[var(--surface)] border border-[var(--border)] rounded-card shadow-card hover:shadow-card-hover hover:border-emerald-400 dark:hover:border-emerald-500 transition-all duration-200 text-left"
            >
              <div className="flex items-start justify-between">
                <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/30">
                  <ClipboardList size={40} className="text-emerald-600 dark:text-emerald-400" strokeWidth={1.5} />
                </div>
                <ArrowRight
                  size={18}
                  className="text-[var(--foreground-muted)] opacity-0 group-hover:opacity-100 translate-x-[-4px] group-hover:translate-x-0 transition-all duration-200 mt-1"
                />
              </div>
              <div>
                <h2 className="text-lg font-bold text-[var(--foreground)]">I&apos;m a Doctor</h2>
                <p className="text-sm text-[var(--foreground-muted)] mt-1">
                  Review active cases and AI diagnostic reports
                </p>
              </div>
            </button>
          </div>
        </div>
      )}

      {step === 'login' && selectedRole && (
        <div className="w-full max-w-sm mx-auto animate-fade-in">
          <button
            onClick={handleBack}
            className="inline-flex items-center gap-1 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors mb-6"
          >
            <ArrowLeft size={14} />
            Back
          </button>

          <div className="bg-[var(--surface)] border border-[var(--border)] rounded-card shadow-card p-8">
            <div className="mb-6 text-center">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-800/50 mb-4">
                {selectedRole === 'nurse' ? (
                  <Stethoscope size={13} className="text-emerald-600 dark:text-emerald-400" />
                ) : (
                  <ClipboardList size={13} className="text-emerald-600 dark:text-emerald-400" />
                )}
                <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300 capitalize">
                  Logging in as {selectedRole}
                </span>
              </div>
              <h1 className="text-xl font-bold text-[var(--foreground)]">Sign In</h1>
            </div>

            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="username" className="block text-sm font-medium text-[var(--foreground)]">
                  Username <span className="text-red-500" aria-hidden="true">*</span>
                </label>
                <input
                  id="username"
                  type="text"
                  required
                  autoFocus
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                  placeholder="Enter your username"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="password" className="block text-sm font-medium text-[var(--foreground)]">
                  Password <span className="text-red-500" aria-hidden="true">*</span>
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                  placeholder="Enter your password"
                />
              </div>

              {error && (
                <div
                  role="alert"
                  className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm"
                >
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-semibold rounded-lg transition-colors mt-2"
              >
                Sign In as {selectedRole === 'nurse' ? 'Nurse' : 'Doctor'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
