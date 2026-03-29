import axios, { isAxiosError } from 'axios'

// Same-origin by default: browser requests hit Next.js, which rewrites /api/* → FastAPI.
// NEXT_PUBLIC_API_URL is only set in vitest (for MSW interception) — never at runtime.
// The backend URL for the server-side rewrite is API_URL in next.config.ts.
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  // TODO: attach Bearer token when auth is implemented
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    // Preserve the original AxiosError so callers can inspect status, headers,
    // and use isAxiosError() for conditional handling (401 vs 500 vs network).
    if (isAxiosError(error)) {
      return Promise.reject(error)
    }
    return Promise.reject(new Error('Unknown error'))
  }
)
