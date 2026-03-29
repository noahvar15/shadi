'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Search, FileText, User } from 'lucide-react'
import { DarkModeToggle } from '@/components/DarkModeToggle'
import { NotificationBell } from '@/components/NotificationBell'
import { api } from '@/lib/api'

interface PatientRecord {
  patient_id: string
  patient_name: string
  dob: string | null
}

function getInitials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

interface PatientResult {
  case_id: string
  patient_id: string
  patient_name?: string
  status: string
  chief_complaint?: string
}

const STATUS_COLOR: Record<string, string> = {
  complete: 'text-emerald-500',
  running: 'text-amber-500',
  queued: 'text-slate-400',
  failed: 'text-red-500',
}

function highlight(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return text
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 rounded-sm">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  )
}

function PatientSearch() {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [allCases, setAllCases] = useState<PatientResult[]>([])
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Load cases once
  useEffect(() => {
    api
      .get<PatientResult[]>('/api/cases')
      .then(({ data }) => setAllCases(data))
      .catch(() => {})
  }, [])

  // Filter
  const q = query.trim().toLowerCase()
  const results = q
    ? allCases.filter(
        (c) =>
          c.patient_name?.toLowerCase().includes(q) ||
          c.patient_id.toLowerCase().includes(q) ||
          c.case_id.toLowerCase().includes(q),
      )
    : []

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setActiveIdx(-1)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Reset active index when results change
  useEffect(() => {
    setActiveIdx(-1)
  }, [query])

  const navigate = useCallback(
    (c: PatientResult) => {
      router.push(`/cases/${c.case_id}/triage`)
      setQuery('')
      setOpen(false)
      setActiveIdx(-1)
      inputRef.current?.blur()
    },
    [router],
  )

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault()
      navigate(results[activeIdx])
    } else if (e.key === 'Escape') {
      setOpen(false)
      setActiveIdx(-1)
      inputRef.current?.blur()
    }
  }

  return (
    <div ref={containerRef} className="relative flex-1 max-w-sm">
      <div className="relative">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--foreground-muted)] pointer-events-none"
        />
        <input
          ref={inputRef}
          type="search"
          value={query}
          placeholder="Search patients…"
          aria-label="Search patients"
          aria-autocomplete="list"
          aria-expanded={open && results.length > 0}
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          className="w-full pl-8 pr-3 py-1.5 text-sm rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
        />
      </div>

      {open && results.length > 0 && (
        <ul
          role="listbox"
          className="absolute top-full left-0 right-0 mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg z-50 overflow-hidden max-h-72 overflow-y-auto"
        >
          {results.map((c, i) => (
            <li
              key={c.case_id}
              role="option"
              aria-selected={i === activeIdx}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => navigate(c)}
              className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${
                i === activeIdx
                  ? 'bg-emerald-50 dark:bg-emerald-900/20'
                  : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
              }`}
            >
              <User
                size={14}
                className="mt-0.5 shrink-0 text-[var(--foreground-muted)]"
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--foreground)] truncate">
                  {highlight(c.patient_name ?? c.patient_id, query)}
                </p>
                <p className="text-xs text-[var(--foreground-muted)] font-mono mt-0.5 truncate">
                  {highlight(c.case_id, query)}
                </p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span
                  className={`text-xs font-medium ${STATUS_COLOR[c.status] ?? 'text-slate-400'}`}
                >
                  {c.status}
                </span>
                <FileText size={12} className="text-[var(--foreground-muted)]" />
              </div>
            </li>
          ))}
        </ul>
      )}

      {open && query.trim().length > 0 && results.length === 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg z-50 px-4 py-3 text-sm text-[var(--foreground-muted)]">
          No patients match &ldquo;{query}&rdquo;
        </div>
      )}
    </div>
  )
}

function NursePatientSearch() {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PatientRecord[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Debounced fetch
  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      setOpen(false)
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setIsSearching(true)
      try {
        const res = await fetch(
          `/api/patients/search?name=${encodeURIComponent(query.trim())}`,
          { signal: controller.signal },
        )
        if (res.ok) {
          const data: PatientRecord[] = await res.json()
          setResults(data)
          setOpen(true)
        }
      } catch {
        // aborted or network error
      } finally {
        setIsSearching(false)
      }
    }, 300)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query])

  useEffect(() => { setActiveIdx(-1) }, [query])

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
        setActiveIdx(-1)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const select = useCallback((pt: PatientRecord) => {
    const params = new URLSearchParams({ patient_id: pt.patient_id, patient_name: pt.patient_name })
    if (pt.dob) params.set('dob', pt.dob)
    router.push(`/nurse?${params.toString()}`)
    setQuery('')
    setOpen(false)
    setActiveIdx(-1)
    inputRef.current?.blur()
  }, [router])

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx((i) => Math.min(i + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && activeIdx >= 0) { e.preventDefault(); select(results[activeIdx]) }
    else if (e.key === 'Escape') { setOpen(false); setActiveIdx(-1); inputRef.current?.blur() }
  }

  return (
    <div ref={containerRef} className="relative flex-1 max-w-sm">
      <div className="relative">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--foreground-muted)] pointer-events-none"
        />
        <input
          ref={inputRef}
          type="search"
          value={query}
          placeholder="Search patients…"
          aria-label="Search patients"
          aria-autocomplete="list"
          aria-expanded={open && results.length > 0}
          autoComplete="off"
          onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => { if (query.trim().length >= 2) setOpen(true) }}
          onKeyDown={handleKeyDown}
          className="w-full pl-8 pr-3 py-1.5 text-sm rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
        />
        {isSearching && (
          <svg className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin h-3.5 w-3.5 text-[var(--foreground-muted)]" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
        )}
      </div>

      {open && (
        <ul
          role="listbox"
          className="absolute top-full left-0 right-0 mt-1 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg z-50 overflow-hidden max-h-72 overflow-y-auto"
        >
          {results.length === 0 ? (
            <li className="px-4 py-3 text-sm text-[var(--foreground-muted)] italic">
              No patients match &ldquo;{query}&rdquo;
            </li>
          ) : results.map((pt, i) => (
            <li
              key={pt.patient_id}
              role="option"
              aria-selected={i === activeIdx}
              onMouseEnter={() => setActiveIdx(i)}
              onMouseDown={(e) => { e.preventDefault(); select(pt) }}
              className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${
                i === activeIdx ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
              }`}
            >
              <User size={14} className="mt-0.5 shrink-0 text-[var(--foreground-muted)]" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--foreground)] truncate">
                  {highlight(pt.patient_name, query)}
                </p>
                {pt.dob && (
                  <p className="text-xs text-[var(--foreground-muted)] mt-0.5">
                    DOB: {new Date(pt.dob + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </p>
                )}
              </div>
              <span className="font-mono text-xs text-[var(--foreground-muted)] shrink-0 mt-0.5">{pt.patient_id}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function AppHeader() {
  const pathname = usePathname()
  const [initials, setInitials] = useState('')

  const isDoctor = pathname.startsWith('/doctor') || pathname.startsWith('/cases')
  const isNurse = pathname.startsWith('/nurse')

  useEffect(() => {
    try {
      const raw = localStorage.getItem('shadi_session')
      if (raw) {
        const { name } = JSON.parse(raw)
        setInitials(name ? getInitials(name) : '')
      } else {
        setInitials('')
      }
    } catch {
      setInitials('')
    }
  }, [pathname])

  if (pathname === '/') return null

  return (
    <header className="h-16 flex-shrink-0 flex items-center gap-4 px-6 bg-[var(--surface)] border-b border-[var(--border)]">
      {isDoctor ? (
        <PatientSearch />
      ) : isNurse ? (
        <NursePatientSearch />
      ) : (
        <div className="flex-1" />
      )}

      <div className="flex items-center gap-2 ml-auto">
        <NotificationBell />
        <DarkModeToggle />
        {initials && (
          <div
            className="h-8 w-8 rounded-full bg-emerald-600 flex items-center justify-center text-white text-xs font-semibold select-none"
            title="Signed in user"
          >
            {initials}
          </div>
        )}
      </div>
    </header>
  )
}
