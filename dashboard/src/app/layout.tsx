import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from '@/providers'
import { DarkModeToggle } from '@/components/DarkModeToggle'
import { LayoutGrid, FolderPlus, FileText, Settings, HelpCircle } from 'lucide-react'
import Link from 'next/link'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Shadi — Clinical Diagnostic Reasoning',
  description: 'Multi-agent diagnostic reasoning for emergency medicine',
}

const NAV_ITEMS = [
  { href: '/', label: 'Cases', icon: LayoutGrid },
  { href: '/cases/new', label: 'New Case', icon: FolderPlus },
  { href: '/reports', label: 'Reports', icon: FileText },
]

const NAV_SECONDARY = [
  { href: '/settings', label: 'Settings', icon: Settings },
  { href: '/help', label: 'Help', icon: HelpCircle },
]

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/* Apply theme class before first paint to prevent flash of wrong theme */}
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');var d=window.matchMedia('(prefers-color-scheme: dark)').matches;if(t==='dark'||(t===null&&d)){document.documentElement.classList.add('dark')}}catch(e){}})()`,
          }}
        />
      </head>
      <body className={inter.className}>
        <div className="flex h-screen overflow-hidden">

          {/* Sidebar */}
          <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
            {/* Wordmark */}
            <div className="h-16 flex items-center px-5 border-b border-[var(--border)]">
              <span className="text-lg font-bold text-violet-600 dark:text-violet-400">Shadi</span>
              <span className="ml-2 text-[10px] font-medium text-[var(--foreground-muted)] tracking-wide uppercase leading-tight hidden lg:block">
                Diagnostic
              </span>
            </div>

            {/* Primary nav */}
            <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
              {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-900/20 dark:hover:text-violet-300 transition-colors"
                >
                  <Icon size={16} strokeWidth={1.75} />
                  {label}
                </Link>
              ))}
            </nav>

            {/* Secondary nav */}
            <div className="px-3 pb-4 space-y-0.5 border-t border-[var(--border)] pt-3">
              {NAV_SECONDARY.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-900/20 dark:hover:text-violet-300 transition-colors"
                >
                  <Icon size={16} strokeWidth={1.75} />
                  {label}
                </Link>
              ))}
            </div>
          </aside>

          {/* Main column */}
          <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
            {/* Top bar */}
            <header className="h-16 flex-shrink-0 flex items-center gap-4 px-6 bg-[var(--surface)] border-b border-[var(--border)]">
              {/* Patient search */}
              <div className="flex-1 max-w-sm">
                <input
                  type="search"
                  placeholder="Search patients..."
                  aria-label="Search patients"
                  disabled
                  className="w-full px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] opacity-60 cursor-not-allowed focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-2 ml-auto">
                <DarkModeToggle />
                <div
                  className="h-8 w-8 rounded-full bg-violet-600 flex items-center justify-center text-white text-xs font-semibold select-none"
                  title="User account"
                >
                  ES
                </div>
              </div>
            </header>

            {/* Page content — Providers wraps only page children so the layout
                shell stays server-rendered and avoids SSR/client hydration mismatch */}
            <main className="flex-1 overflow-y-auto">
              <Providers>
                {children}
              </Providers>
            </main>
          </div>

        </div>
      </body>
    </html>
  )
}
