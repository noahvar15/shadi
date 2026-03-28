'use client'

import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'

export function DarkModeToggle() {
  const [isDark, setIsDark] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const stored = localStorage.getItem('theme')
    const dark = stored ? stored === 'dark' : mql.matches
    setIsDark(dark)
    document.documentElement.classList.toggle('dark', dark)

    // Follow OS theme changes when the user hasn't set an explicit preference
    const onSystemChange = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem('theme')) {
        setIsDark(e.matches)
        document.documentElement.classList.toggle('dark', e.matches)
      }
    }
    mql.addEventListener('change', onSystemChange)
    return () => mql.removeEventListener('change', onSystemChange)
  }, [])

  const toggle = () => {
    const next = !isDark
    setIsDark(next)
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('theme', next ? 'dark' : 'light')
  }

  if (!mounted) {
    return <div className="h-8 w-8" />
  }

  return (
    <button
      onClick={toggle}
      className="h-8 w-8 rounded-lg flex items-center justify-center text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  )
}
