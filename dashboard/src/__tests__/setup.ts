/**
 * Global test setup — starts the MSW node server before all tests and tears it
 * down after.  Each test resets handlers and mock data to defaults so tests
 * stay fully isolated from one another.
 */
import { beforeAll, afterEach, afterAll } from 'vitest'
import { server, resetMockCases } from './msw-server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetMockCases()
})
afterAll(() => server.close())
