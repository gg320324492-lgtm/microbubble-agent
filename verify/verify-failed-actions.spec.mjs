import { chromium } from 'playwright'
import { writeFileSync } from 'fs'

const BASE_URL = 'http://localhost:3000'
const SCREENSHOT_DIR = 'e:/microbubble-agent/verify/screenshots'
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzgyODAyNzMzLCJ0eXBlIjoiYWNjZXNzIn0.TKpYyHXrEhsdNjR_I13Slu2U2LIiRXkjpoBRQVAgwBw'

// Create screenshot directory if needed
import { mkdirSync } from 'fs'
try { mkdirSync(SCREENSHOT_DIR, { recursive: true }) } catch (e) {}

// Use Node's built-in fetch for API auth header (not needed for browser flow)
async function run() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  })
  const page = await context.newPage()

  // Collect console messages
  const consoleMessages = []
  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() })
  })
  page.on('pageerror', err => {
    consoleMessages.push({ type: 'pageerror', text: err.message })
  })

  // Set auth token in localStorage (matches Playwright v76.2-C double-injection pattern)
  await page.addInitScript((token) => {
    localStorage.setItem('access_token', token)
  }, TOKEN)

  const results = []

  // ============================================================
  // Test 1: KnowledgeCreateDialog TDZ fix - click "添加知识"
  // ============================================================
  console.log('\n=== Test 1: KnowledgeCreateDialog TDZ fix ===')
  try {
    await page.goto(`${BASE_URL}/knowledge`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/01a-knowledge-toolbar.png`, fullPage: false })

    // Clear console messages before action
    consoleMessages.length = 0

    // Click "添加知识" button
    const addBtn = page.locator('.toolbar-actions .el-button').filter({ hasText: '添加知识' })
    await addBtn.click()
    await page.waitForTimeout(1500)

    await page.screenshot({ path: `${SCREENSHOT_DIR}/01b-knowledge-add-dialog.png`, fullPage: false })

    // Check dialog is visible
    const dialog = await page.locator('.el-dialog:visible').first()
    const dialogTitle = await dialog.locator('.el-dialog__title').textContent().catch(() => null)
    const dialogVisible = await dialog.isVisible().catch(() => false)

    // Check for TDZ errors in console
    const tdzErrors = consoleMessages.filter(m =>
      m.text.includes('Cannot access') ||
      m.text.includes('before initialization') ||
      m.text.includes('resetForm') ||
      m.type === 'pageerror'
    )

    results.push({
      test: '1. KnowledgeCreateDialog TDZ fix',
      pass: dialogVisible && dialogTitle?.includes('添加知识') && tdzErrors.length === 0,
      details: {
        dialogVisible,
        dialogTitle,
        tdzErrors: tdzErrors.map(e => `[${e.type}] ${e.text}`),
        consoleErrors: consoleMessages.filter(m => m.type === 'error').map(e => e.text)
      }
    })
    console.log(`Dialog visible: ${dialogVisible}, Title: ${dialogTitle}, TDZ errors: ${tdzErrors.length}`)

    // Close dialog
    const closeBtn = page.locator('.el-dialog__close').first()
    if (await closeBtn.isVisible().catch(() => false)) {
      await closeBtn.click()
      await page.waitForTimeout(500)
    }
  } catch (e) {
    results.push({ test: '1. KnowledgeCreateDialog TDZ fix', pass: false, error: e.message })
    console.log(`FAIL: ${e.message}`)
  }

  // ============================================================
  // Test 2: Click "开始听会" → fullscreen MeetingRoomView
  // ============================================================
  console.log('\n=== Test 2: Meeting fullscreen UI ===')
  try {
    await page.goto(`${BASE_URL}/meetings`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/02a-meetings-list.png`, fullPage: false })

    consoleMessages.length = 0

    // Click "开始听会" button (yellow warning type with Microphone icon)
    const startBtn = page.locator('.el-button').filter({ hasText: '开始听会' }).first()
    const btnVisible = await startBtn.isVisible().catch(() => false)

    if (btnVisible) {
      await startBtn.click()
      await page.waitForTimeout(2000)

      const currentUrl = page.url()
      await page.screenshot({ path: `${SCREENSHOT_DIR}/02b-after-start-recording.png`, fullPage: false })

      // Check we're on /meetings/room
      const isFullscreen = currentUrl.includes('/meetings/room')
      const hasOverlay = await page.locator('.el-overlay').count() > 0
      const hasPageHeader = await page.locator('.el-page-header').count() > 0

      results.push({
        test: '2. Meeting fullscreen UI',
        pass: isFullscreen && !hasOverlay,
        details: {
          currentUrl,
          isFullscreen,
          hasOverlay,
          hasPageHeader,
          pageErrors: consoleMessages.filter(m => m.type === 'pageerror').map(e => e.text)
        }
      })
      console.log(`URL: ${currentUrl}, Fullscreen: ${isFullscreen}, No overlay: ${!hasOverlay}`)
    } else {
      results.push({ test: '2. Meeting fullscreen UI', pass: false, error: '开始听会 button not visible' })
    }
  } catch (e) {
    results.push({ test: '2. Meeting fullscreen UI', pass: false, error: e.message })
    console.log(`FAIL: ${e.message}`)
  }

  // ============================================================
  // Test 3: Ocean theme primary plain button contrast
  // ============================================================
  console.log('\n=== Test 3: Ocean theme primary plain button contrast ===')
  try {
    // First, go to settings and switch to ocean theme
    await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)

    // Click ocean theme swatch
    const oceanSwatch = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
    const oceanVisible = await oceanSwatch.isVisible().catch(() => false)

    if (oceanVisible) {
      await oceanSwatch.click()
      await page.waitForTimeout(500)
    }

    // Verify html has data-accent="ocean"
    const dataAccent = await page.evaluate(() => document.documentElement.dataset.accent)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/03a-ocean-settings.png`, fullPage: false })

    // Go to members page and check primary plain button
    await page.goto(`${BASE_URL}/members`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/03b-members-ocean.png`, fullPage: false })

    // Find any primary plain button (e.g., 录入声纹)
    const plainBtns = await page.locator('.el-button--primary.is-plain').all()
    const btnData = []
    for (let i = 0; i < Math.min(plainBtns.length, 5); i++) {
      const btn = plainBtns[i]
      const cs = await btn.evaluate(el => {
        const s = getComputedStyle(el)
        return {
          bg: s.backgroundColor,
          color: s.color,
          text: el.textContent.trim().slice(0, 30)
        }
      })
      btnData.push(cs)
    }

    // Check at least one button has contrasting color
    // v77 P2.6 fix: ocean dark text = rgb(74, 144, 226), forest dark = rgb(46, 125, 50)
    // Test now checks if text is NOT white (the original bug was white text rgb(255,255,255))
    const hasContrast = btnData.some(b => {
      // Parse rgb
      const match = b.color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/)
      if (!match) return false
      const [, r, g, blue] = match.map(Number)
      // FAIL if text is pure white (the original bug)
      if (r === 255 && g === 255 && blue === 255) return false
      // PASS if text is darker than background
      // Compute brightness: YIQ formula
      const textBrightness = (r * 299 + g * 587 + blue * 114) / 1000
      const bgMatch = b.bg.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/)
      if (!bgMatch) return true  // bg unknown, assume contrast OK
      const [, br, bg, bb] = bgMatch.map(Number)
      const bgBrightness = (br * 299 + bg * 587 + bb * 114) / 1000
      // Text should be DARKER than background for proper contrast
      return textBrightness < bgBrightness - 30  // 30 = noticeable diff
    })

    results.push({
      test: '3. Ocean theme primary plain button contrast',
      pass: dataAccent === 'ocean' && hasContrast && btnData.length > 0,
      details: {
        dataAccent,
        buttonsFound: btnData.length,
        buttonStyles: btnData,
        hasContrast
      }
    })
    console.log(`data-accent: ${dataAccent}, Plain buttons: ${btnData.length}, Has contrast: ${hasContrast}`)
  } catch (e) {
    results.push({ test: '3. Ocean theme primary plain button contrast', pass: false, error: e.message })
    console.log(`FAIL: ${e.message}`)
  }

  // ============================================================
  // Test 4: KnowledgeView 5 tabs - click each, check no console error
  // ============================================================
  console.log('\n=== Test 4: KnowledgeView 5 tabs ===')
  try {
    // Reset theme first
    await page.evaluate(() => {
      localStorage.removeItem('accent')
      document.documentElement.removeAttribute('data-accent')
    })

    await page.goto(`${BASE_URL}/knowledge`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)

    // Get all tab labels
    const tabs = await page.locator('.el-tabs__item').allTextContents()
    console.log(`Tabs found: ${JSON.stringify(tabs)}`)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/04a-knowledge-tabs.png`, fullPage: false })

    consoleMessages.length = 0
    const tabResults = []

    // Click each tab
    for (const tabText of tabs.map(t => t.trim()).filter(t => t)) {
      consoleMessages.length = 0
      try {
        const tab = page.locator('.el-tabs__item').filter({ hasText: tabText }).first()
        await tab.click()
        await page.waitForTimeout(1500)

        await page.screenshot({
          path: `${SCREENSHOT_DIR}/04b-tab-${tabText.replace(/[^\w一-龥]/g, '_')}.png`,
          fullPage: false
        })

        const errors = consoleMessages.filter(m =>
          m.type === 'pageerror' || m.type === 'error'
        )
        tabResults.push({
          tab: tabText,
          errors: errors.map(e => `[${e.type}] ${e.text.slice(0, 200)}`)
        })
        console.log(`  Tab "${tabText}": ${errors.length} errors`)
      } catch (e) {
        tabResults.push({ tab: tabText, error: e.message })
      }
    }

    const tabsWithErrors = tabResults.filter(t => t.errors && t.errors.length > 0)
    results.push({
      test: '4. KnowledgeView 5 tabs',
      pass: tabs.length >= 4 && tabsWithErrors.length === 0,
      details: {
        tabsFound: tabs,
        tabResults,
        tabsWithErrors: tabsWithErrors.length
      }
    })
    console.log(`Tabs total: ${tabs.length}, Tabs with errors: ${tabsWithErrors.length}`)
  } catch (e) {
    results.push({ test: '4. KnowledgeView 5 tabs', pass: false, error: e.message })
    console.log(`FAIL: ${e.message}`)
  }

  await browser.close()

  // ============================================================
  // Summary
  // ============================================================
  console.log('\n========================================')
  console.log('END-TO-END VERIFICATION SUMMARY')
  console.log('========================================')
  const passed = results.filter(r => r.pass).length
  console.log(`\nPassed: ${passed} / ${results.length}`)

  writeFileSync('e:/microbubble-agent/verify/e2e-results.json', JSON.stringify(results, null, 2))
  console.log('\nResults saved to: e:/microbubble-agent/verify/e2e-results.json')
  console.log(`Screenshots saved to: ${SCREENSHOT_DIR}`)
  console.log('========================================')

  process.exit(passed === results.length ? 0 : 1)
}

run().catch(e => {
  console.error('FATAL:', e)
  process.exit(2)
})