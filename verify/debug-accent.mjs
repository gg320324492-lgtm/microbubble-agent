import { chromium } from 'playwright'
const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext()
const page = await ctx.newPage()

await page.goto('http://localhost:3000/settings', { waitUntil: 'networkidle' })
await page.waitForTimeout(500)
console.log('Before click - accent:', await page.evaluate(() => document.documentElement.dataset.accent))

const sw = page.locator('.theme-swatch').filter({ hasText: '海蓝' }).first()
console.log('Swatch count:', await sw.count())
console.log('Visible:', await sw.isVisible().catch(() => false))

await sw.click()
await page.waitForTimeout(2000)  // longer wait

console.log('After click - accent:', await page.evaluate(() => document.documentElement.dataset.accent))
console.log('After click - localStorage accent:', await page.evaluate(() => localStorage.getItem('accent')))

await browser.close()
