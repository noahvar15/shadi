import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from '@/providers'
import { DarkModeToggle } from '@/components/DarkModeToggle'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Shadi — Clinical Diagnostic Reasoning',
  description: 'Multi-agent diagnostic reasoning for emergency medicine',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          <nav className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
            <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
              {/* Wordmark */}
              <div className="flex-shrink-0 flex items-baseline gap-2">
                <span className="text-xl font-bold text-emerald-500">Shadi</span>
                <span className="hidden sm:inline text-xs text-slate-400 dark:text-slate-500 font-medium tracking-wide">
                  Clinical Diagnostic Reasoning
                </span>
              </div>

              {/* Patient search */}
              <div className="flex-1 max-w-md mx-auto">
                <input
                  type="search"
                  placeholder="Search patients..."
                  disabled
                  className="w-full px-3 py-1.5 text-sm rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 opacity-50 cursor-not-allowed"
                />
              </div>

              {/* Right controls */}
              <div className="flex-shrink-0 flex items-center gap-2">
                <DarkModeToggle />
                <div
                  className="h-8 w-8 rounded-full bg-emerald-500 flex items-center justify-center text-white text-xs font-semibold select-none"
                  title="User account"
                >
                  ES
                </div>
              </div>
            </div>
          </nav>

          <main>{children}</main>
        </Providers>
      </body>
    </html>
  )
}
