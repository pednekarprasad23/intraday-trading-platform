import { Page, APIRequestContext, APIResponse } from '@playwright/test'

/**
 * Authentication helper for E2E tests
 * Handles login and session management for the intraday-trading-platform
 */

export interface AuthResult {
  success: boolean
  page: Page
  token?: string
  error?: string
}

export interface LoginCredentials {
  email: string
  password: string
}

/**
 * Default test credentials
 * In CI, these should be replaced with environment variables
 */
export const TEST_CREDENTIALS: LoginCredentials = {
  email: process.env.TEST_USER_EMAIL || 'admin@intraday.com',
  password: process.env.TEST_USER_PASSWORD || 'password',
}

/**
 * Login via API and set session cookie
 */
export async function loginViaAPI(
  request: APIRequestContext,
  credentials: LoginCredentials = TEST_CREDENTIALS,
): Promise<APIResponse> {
  const response = await request.post('/api/v1/auth/login', {
    data: {
      email: credentials.email,
      password: credentials.password,
    },
  })

  return response
}

/**
 * Login via UI form
 */
export async function loginViaUI(page: Page, credentials: LoginCredentials = TEST_CREDENTIALS): Promise<void> {
  await page.goto('/login')

  // Fill in credentials
  await page.fill('input[name="email"]', credentials.email)
  await page.fill('input[name="password"]', credentials.password)

  // Submit form
  await Promise.all([
    page.waitForURL({ url: /.*/, timesOut: 10000 }),
    page.click('button[type="submit"]'),
  ])

  // Wait for session cookie to be set
  await page.waitForFunction(() => {
    const cookies = document.cookie.split(';')
    return cookies.some(c => c.trim().startsWith('session='))
  }, { timeout: 10000 })
}

/**
 * Logout from the application
 */
export async function logout(page: Page): Promise<void> {
  // Find logout button/link and click it
  const logoutButton = page.locator('a[href="/logout"], button:has-text("Logout")')

  if (await logoutButton.count() > 0) {
    await logoutButton.click()
  } else {
    // Alternative: delete cookie directly
    await page.context().clearCookies()
  }

  // Wait for redirect or cookie removal
  await page.waitForTimeout(1000)
}

/**
 * Ensure we're logged in before running tests
 */
export async function ensureLoggedIn(page: Page): Promise<boolean> {
  // Check if session cookie exists
  const cookies = await page.context().cookies()
  const hasSession = cookies.some(c => c.name === 'session' && c.value.length > 0)

  if (hasSession) {
    return true
  }

  // Try to login
  try {
    await loginViaUI(page)
    return true
  } catch (error) {
    console.error('Login failed:', error)
    return false
  }
}

/**
 * Get valid authentication token for API requests
 */
export async function getAuthHeader(
  request: APIRequestContext,
  credentials: LoginCredentials = TEST_CREDENTIALS,
): Promise<{ authorization?: string }> {
  const response = await loginViaAPI(request, credentials)

  if (response.ok()) {
    const cookies = response.headersArray()
      .filter(h => h.name === 'set-cookie')
      .map(h => h.value)

    const sessionCookie = cookies.find(c => c.startsWith('session='))
    if (sessionCookie) {
      return { cookie: sessionCookie.split(';')[0] }
    }
  }

  return {}
}

/**
 * Wait for auth state to be ready
 */
export async function waitForAuthReady(page: Page, timeout = 10000): Promise<boolean> {
  try {
    await page.waitForFunction(() => {
      const event = document.querySelector('[data-testid="auth-state"]')
      return event?.getAttribute('data-ready') === 'true'
    }, { timeout })

    return true
  } catch {
    return false
  }
}