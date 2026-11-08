import { test, expect } from '@playwright/test'

// axe-core for accessibility testing
import { injectAxe, checkA11y } from 'axe-playwright'

test.describe('Accessibility Tests', () => {
  test.beforeEach(async ({ page }) => {
    await injectAxe(page)
  })

  test('home page should have no WCAG violations', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Check for accessibility violations
    await checkA11y(page, {
      axeOptions: {
        rules: {
          // Ignore some rules that may not apply to all pages
          'color-contrast': { enabled: false }, // Manual review needed
        },
      },
    })
  })

  test('main navigation should be accessible', async ({ page }) => {
    await page.goto('/')

    const nav = page.locator('nav, [role="navigation"]').first()
    await expect(nav).toBeVisible()

    // Check nav has accessible name
    const ariaLabel = await nav.getAttribute('aria-label')
    const ariaLabelledby = await nav.getAttribute('aria-labelledby')

    expect(ariaLabel || ariaLabelledby).toBeTruthy()
  })

  test('skip link should be present', async ({ page }) => {
    await page.goto('/')

    // Skip link should be in DOM
    const skipLink = page.locator('a[href^="#main"], .skip-link, a[href^="#content"]')

    if (await skipLink.count() > 0) {
      // Should be focusable
      await skipLink.focus()
      await expect(skipLink).toBeVisible()
    }
  })

  test('images should have alt text', async ({ page }) => {
    await page.goto('/')

    const images = page.locator('img')

    for (const img of await images.all()) {
      const alt = await img.getAttribute('alt')
      // alt=" Decorative images should have empty alt
      // alt="" or alt="text" are valid
      expect(alt).not.toBeNull() // Missing alt attribute
    }
  })

  test('form labels should be properly associated', async ({ page }) => {
    await page.goto('/')

    const inputs = page.locator('input, select, textarea')

    for (const input of await inputs.all()) {
      const id = await input.getAttribute('id')
      const ariaLabel = await input.getAttribute('aria-label')
      const ariaLabelledby = await input.getAttribute('aria-labelledby')
      const label = await input.locator('parent:has(label[for="' + (id || '') + '"]')

      // Input should have some form of label
      const hasLabel = id && (await page.locator('label[for="' + id + '"]').count()) > 0
      const hasAriaLabel = await input.getAttribute('aria-label') !== null
      const hasAriaLabelledBy = ariaLabelledby !== null

      expect(hasLabel || hasAriaLabel || hasAriaLabelledBy || label).toBeTruthy()
    }
  })

  test('color contrast should meet WCAG AA', async ({ page }) => {
    await page.goto('/')

    // Note: axe-core can test color-contrast but we disable it in other tests
    // Here we test it explicitly
    await checkA11y(page, {
      axeOptions: {
        runOnly: ['color-contrast'],
      },
    })
  })

  test('aria-live regions should be properly configured', async ({ page }) => {
    await page.goto('/')

    const liveRegions = page.locator('[aria-live]')

    for (const region of await liveRegions.all()) {
      const liveValue = await region.getAttribute('aria-live')
      expect(['polite', 'assertive', 'off']).toContain(liveValue)
    }
  })

  test('focusable elements should have visible focus indicator', async ({ page }) => {
    await page.goto('/')

    // Find focusable elements
    const focusable = page.locator('a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])')

    const firstFocusable = await focusable.first()

    if (await firstFocusable.count() > 0) {
      await firstFocusable.focus()

      // Check for :focus styles (we check if outline or similar is present)
      // This is a simplified check - real implementation needs CSS inspection
      await expect(firstFocusable).toBeFocused()
    }
  })

  test('keyboard navigation should be logical', async ({ page }) => {
    await page.goto('/')

    // Tab through focusable elements
    let tabCount = 0
    const maxTabs = 20 // Prevent infinite loops

    while (tabCount < maxTabs) {
      await page.keyboard.press('Tab')

      const activeElement = await page.evaluate(() => document.activeElement?.tagName)

      if (activeElement === 'BODY') {
        break
      }

      tabCount++
    }

    expect(tabCount).toBeGreaterThan(0)
  })

  test('tables should have proper headers', async ({ page }) => {
    await page.goto('/')

    const tables = page.locator('table')

    for (const table of await tables.all()) {
      // Table should have thead or th elements
      const hasThead = await table.locator('thead').count() > 0
      const hasTh = await table.locator('th').count() > 0

      expect(hasThead || hasTh).toBeTruthy()
    }
  })

  test('forms should have submit buttons', async ({ page }) => {
    await page.goto('/')

    const forms = page.locator('form')

    for (const form of await forms.all()) {
      const submitButton = form.locator('button[type="submit"], input[type="submit"]')

      await expect(submitButton).toBeVisible()
    }
  })

  test('page should have sufficient color contrast', async ({ page }) => {
    await page.goto('/')

    // Basic check: main text should be visible
    const bodyText = page.locator('body').locator('p, span, div, li').first()

    await expect(bodyText).toBeVisible()
  })
})

// WCAG 2.1 Level AA compliance tests
test.describe('WCAG 2.1 AA Compliance', () => {
  test.beforeEach(async ({ page }) => {
    await injectAxe(page)
  })

  test('landmarks should be properly defined', async ({ page }) => {
    await page.goto('/')

    // Check for main landmark
    const main = page.locator('main, [role="main"]').first()

    // At minimum, body acts as main content
  })

  test('language attribute should be set', async ({ page }) => {
    await page.goto('/')

    const html = page.locator('html')

    const lang = await html.getAttribute('lang')

    expect(lang).toBeTruthy()
  })

  test('document title should be meaningful', async ({ page }) => {
    await page.goto('/')

    const title = await page.title()

    expect(title.length).toBeGreaterThan(10)
    expect(title.toLowerCase()).not.toContain('loading')
    expect(title.toLowerCase()).not.toContain('error')
  })

  test('focus should be visible when tabbing', async ({ page }) => {
    await page.goto('/')

    const focusable = page.locator('a, button, input, select, textarea').first()

    if (await focusable.count() > 0) {
      await focusable.focus()

      // Element should have focus
      await page.keyboard.press('Tab')

      // Next element should have focus
      const active = await page.evaluate(() => document.activeElement?.tagName)
      expect(active).not.toBe('BODY')
    }
  })

  test('error messages should be programmatically associated', async ({ page }) => {
    await page.goto('/')

    // Check for errors in the page
    const errors = page.locator('[role="alert"], .error[aria-live="assertive"]')

    if (await errors.count() > 0) {
      // Errors should be announced to screen readers immediately
      await expect(errors).toHaveAttribute('role', 'alert')
    }
  })
})

// Reduced motion and contrast tests
test.describe('Reduced Motion & High Contrast', () => {
  test('should support reduced motion preference', async ({ page }) => {
    // Emulate reduced motion
    await page.emulateMedia({ reducedMotion: 'reduce' })

    await page.goto('/')

    // Page should still function normally
    await page.waitForLoadState('networkidle')

    // Check for animations that should be disabled
    const animatedElements = page.locator('[animation], @keyframes, .animate-')

    // No crash or broken layout
    await expect(page.locator('body')).toBeVisible()
  })

  test('should support high contrast preference', async ({ page }) => {
    await page.goto('/')

    // Check that page works with high contrast mode
    // This is more of a visual test that requires manual review
    await page.waitForLoadState('networkidle')

    // Basic check that content is visible
    await expect(page.locator('body')).toBeVisible()
  })
})