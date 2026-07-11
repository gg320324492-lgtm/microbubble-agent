/**
 * Bug A: 完整流程 addInitScript 必须在 navigation 前
 */

import { test } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

test('完整 XHR hook', async ({ page }) => {
  // Init script 在 navigation 前
  await page.addInitScript(() => {
    const OrigXHR = window.XMLHttpRequest
    window.__xhrLog = []
    function HookedXHR() {
      const xhr = new OrigXHR()
      const origOpen = xhr.open
      xhr.open = function (method, url, ...rest) {
        window.__xhrLog.push({ method, url, time: Date.now() })
        return origOpen.call(this, method, url, ...rest)
      }
      return xhr
    }
    HookedXHR.prototype = OrigXHR.prototype
    Object.defineProperty(HookedXHR, 'UNSENT', { value: 0 })
    window.XMLHttpRequest = HookedXHR
  })

  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('input.el-input__inner', { timeout: 10_000 })
  await page.locator('input.el-input__inner').nth(0).fill('xiaoqi_testbot')
  await page.locator('input.el-input__inner').nth(1).fill('testbot_pass_2026')
  await page.click('button.login-button')
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 15_000 }).catch(() => {})
  await page.waitForTimeout(1500)

  await page.goto(`${BASE_URL}/drive`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.drive-sidebar', { timeout: 15_000 })
  await page.waitForTimeout(3000)

  const initLogs = await page.evaluate(() => window.__xhrLog || [])
  console.log('\n[Init XHR logs]:')
  console.log(`  count=${initLogs.length}`)
  initLogs.forEach((l) => console.log(`    ${l.method} ${l.url}`))

  // 清空 + 测 fetchTree 不同 scope
  await page.evaluate(() => { window.__xhrLog = [] })

  const r1 = await page.evaluate(async () => {
    const app = document.querySelector('#app').__vue_app__
    const pinia = app.config.globalProperties.$pinia
    const store = pinia._s.get('folderTree')
    await store.fetchTree('personal')
    return store.folderTree.length
  })
  const xhr1 = await page.evaluate(() => window.__xhrLog)
  console.log(`\n[A] fetchTree('personal'): count=${r1}, XHR=${JSON.stringify(xhr1.map(x=>x.url))}`)

  await page.evaluate(() => { window.__xhrLog = [] })
  const r2 = await page.evaluate(async () => {
    const app = document.querySelector('#app').__vue_app__
    const pinia = app.config.globalProperties.$pinia
    const store = pinia._s.get('folderTree')
    await store.fetchTree('team')
    return store.folderTree.length
  })
  const xhr2 = await page.evaluate(() => window.__xhrLog)
  console.log(`\n[B] fetchTree('team'): count=${r2}, XHR=${JSON.stringify(xhr2.map(x=>x.url))}`)

  await page.evaluate(() => { window.__xhrLog = [] })
  const r3 = await page.evaluate(async () => {
    const app = document.querySelector('#app').__vue_app__
    const pinia = app.config.globalProperties.$pinia
    const store = pinia._s.get('folderTree')
    await store.fetchTree('all')
    return store.folderTree.length
  })
  const xhr3 = await page.evaluate(() => window.__xhrLog)
  console.log(`\n[C] fetchTree('all'): count=${r3}, XHR=${JSON.stringify(xhr3.map(x=>x.url))}`)
})