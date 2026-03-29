'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useEffect } from 'react'

async function enableMocking() {
  if (process.env.NEXT_PUBLIC_MOCK_API !== 'true') return
  const { worker } = await import('@/lib/mock/browser')
  return worker.start({ onUnhandledRequest: 'bypass' })
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(process.env.NEXT_PUBLIC_MOCK_API !== 'true')

  useEffect(() => {
    enableMocking().then(() => setReady(true))
  }, [])

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

  if (!ready) return null

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
