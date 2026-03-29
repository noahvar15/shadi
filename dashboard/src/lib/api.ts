import axios, { isAxiosError } from 'axios'

// Empty string = same-origin: requests go to Next.js which rewrites /api/* → FastAPI.
// Set NEXT_PUBLIC_API_URL only for cross-origin deployments (e.g. separate domains).
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
