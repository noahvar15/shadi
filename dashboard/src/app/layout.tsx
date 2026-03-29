import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from '@/providers'
import { AppSidebar } from '@/components/AppSidebar'
import { AppHeader } from '@/components/AppHeader'

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
      {/* Apply theme class before first paint to prevent flash of wrong theme */}
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');if(t==='dark'){document.documentElement.classList.add('dark')}}catch(e){}})()`,
          }}
        />
      </head>
      <body className={inter.className}>
        <div className="flex h-screen overflow-hidden">

          <AppSidebar />

          {/* Main column */}
          <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
            <AppHeader />

            {/* Page content — Providers wraps only page children so the layout
                shell stays server-rendered and avoids SSR/client hydration mismatch */}
            <main className="flex-1 min-h-0 overflow-y-auto">
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
