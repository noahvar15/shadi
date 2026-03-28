import axios, { isAxiosError } from 'axios'

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
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
