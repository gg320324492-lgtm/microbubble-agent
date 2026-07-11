/**
 * v2.28 (2026-07-12) FolderTree 三态玻璃态视觉验证
 *
 * 验证 3 个三态 (loading / error / empty) 的新 .drive-folder-tree-* 玻璃态样式
 * 截图保存到 tests/visual/desktop/screenshots/dbg-threestates-{state}.png
 *
 * 每个 test 单一动作, 1 个失败不影响其他
 */

import { test } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'

async function loginAsTestBot(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('input.el-input__inner', { timeout: 10_000 }).catch(() => {})
  await page.locator('input.el-input__inner').nth(0).fill('xiaoqi_testbot').catch(() => {})
  await page.locator('input.el-input__inner').nth(1).fill('testbot_pass_2026').catch(() => {})
  await page.click('button.login-button').catch(() => {})
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 15_000 }).catch(() => {})
  await page.goto(`${BASE_URL}/drive`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.drive-sidebar', { timeout: 15_000 })
  await page.waitForTimeout(800)
}

async function forceFolderTreeState(page, { empty = true, loading = false, error = null } = {}) {
  await page.evaluate(({ empty, loading, error }) => {
    const app = document.querySelector('#app').__vue_app__
    const pinia = app.config.globalProperties.$pinia
    const store = pinia._s.get('folderTree')
    store.folderTree = empty ? [] : []
    store.loading = loading
    store.loadError = error
  }, { empty, loading, error })
}

test.describe('FolderTree v2.28 三态玻璃态', () => {
  test.setTimeout(60_000)

  test('empty 状态: hero + title + hint + CTA', async ({ page }) => {
    await loginAsTestBot(page)
    await forceFolderTreeState(page, { empty: true })
    await page.waitForSelector('.drive-folder-tree-empty', { timeout: 5_000 })
    await page.waitForTimeout(500)

    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/dbg-threestates-A-empty.png',
      fullPage: false,
      clip: { x: 0, y: 100, width: 280, height: 480 },
    })

    const heroBg = await page.locator('.drive-folder-tree-empty-hero').evaluate(el => getComputedStyle(el).backgroundImage)
    const ctaBg = await page.locator('.drive-folder-tree-empty-cta').evaluate(el => getComputedStyle(el).backgroundImage)
    console.log(`\n[empty] hero bg: ${heroBg?.slice(0, 60)}`)
    console.log(`[empty] cta  bg: ${ctaBg?.slice(0, 60)}`)
  })

  test('loading 状态: 旋转图标 + 进度文案', async ({ page }) => {
    await loginAsTestBot(page)
    await forceFolderTreeState(page, { loading: true })
    await page.waitForSelector('.drive-folder-tree-loading', { timeout: 5_000 })
    await page.waitForTimeout(300)

    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/dbg-threestates-B-loading.png',
      fullPage: false,
      clip: { x: 0, y: 100, width: 280, height: 200 },
    })

    const iconTransform = await page.locator('.drive-folder-tree-loading .el-icon').evaluate(el => getComputedStyle(el).animation)
    const text = await page.locator('.drive-folder-tree-loading-text').innerText()
    console.log(`\n[loading] icon animation: ${iconTransform?.slice(0, 60)}`)
    console.log(`[loading] text: "${text.trim()}"`)
  })

  test('error 状态: 红字 + 重试按钮', async ({ page }) => {
    await loginAsTestBot(page)
    await forceFolderTreeState(page, { error: '加载失败: 网络超时' })
    await page.waitForSelector('.drive-folder-tree-error', { timeout: 5_000 })
    await page.waitForTimeout(300)

    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/dbg-threestates-C-error.png',
      fullPage: false,
      clip: { x: 0, y: 100, width: 280, height: 240 },
    })

    const errorBg = await page.locator('.drive-folder-tree-error').evaluate(el => getComputedStyle(el).backgroundColor)
    const retryBg = await page.locator('.drive-folder-tree-error .el-button').evaluate(el => getComputedStyle(el).backgroundColor)
    console.log(`\n[error] container bg: ${errorBg}`)
    console.log(`[error] retry btn  bg: ${retryBg}`)
  })
})
