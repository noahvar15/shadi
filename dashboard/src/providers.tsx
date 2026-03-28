'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, lazy, Suspense } from 'react'

// Dynamically import devtools so the bundle is excluded from production
const ReactQueryDevtools =
  process.env.NODE_ENV === 'development'
    ? lazy(() =>
        import('@tanstack/react-query-devtools').then((m) => ({
          default: m.ReactQueryDevtools,
        }))
      )
    : null

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {ReactQueryDevtools && (
        <Suspense fallback={null}>
          <ReactQueryDevtools initialIsOpen={false} />
        </Suspense>
      )}
    </QueryClientProvider>
  )
}
