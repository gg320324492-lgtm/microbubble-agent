import { test, expect } from '@playwright/test'

const FILE_ID = 1038
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'
const SANDBOX_FAILURE = /origin ['"]null['"]|lacks the ['"]allow-same-origin['"] flag/i

test.use({ serviceWorkers: 'block' })

test('PPT 在线预览不被 sandbox 破坏并完成渲染', async ({ page }) => {
  test.setTimeout(120_000)

  const sandboxErrors = []
  page.on('console', (message) => {
    if (SANDBOX_FAILURE.test(message.text())) sandboxErrors.push(message.text())
  })
  page.on('pageerror', (error) => {
    if (SANDBOX_FAILURE.test(error.message)) sandboxErrors.push(error.message)
  })

  await page.goto('/login', { waitUntil: 'domcontentloaded' })
  const inputs = page.locator('input.el-input__inner')
  await inputs.nth(0).fill(USERNAME)
  await inputs.nth(1).fill(PASSWORD)
  await page.locator('button.login-button').click()
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 15_000 })

  await page.goto(`/drive/file/${FILE_ID}`, { waitUntil: 'domcontentloaded' })
  const previewButton = page.getByRole('button', { name: '在线预览' })
  await expect(previewButton).toBeVisible({ timeout: 15_000 })
  await previewButton.click()

  const iframe = page.locator('iframe.preview-office-iframe')
  await expect(iframe).toBeVisible({ timeout: 15_000 })
  expect(await iframe.getAttribute('sandbox'), 'Office iframe 不应设置 sandbox').toBeNull()
  await expect(iframe).toHaveAttribute('referrerpolicy', 'no-referrer')

  await expect.poll(
    () => page.frames().some((frame) => /PowerPointFrame\.aspx/i.test(frame.url())),
    { timeout: 60_000, intervals: [500, 1_000, 2_000] },
  ).toBe(true)

  const powerpointFrame = page.frames().find((frame) => /PowerPointFrame\.aspx/i.test(frame.url()))
  expect(powerpointFrame, 'PowerPoint 内层应用 frame 应完成加载').toBeTruthy()

  await expect.poll(
    () => powerpointFrame.evaluate(() => document.body?.innerText?.trim() || ''),
    { timeout: 60_000, intervals: [1_000, 2_000, 5_000] },
  ).toMatch(/SLIDE 1 OF \d+/i)

  const slideState = await powerpointFrame.evaluate(() => {
    const panel = document.querySelector('#SlidePanel')
    const rect = panel?.getBoundingClientRect()
    return {
      text: document.body?.innerText || '',
      panelVisible: Boolean(panel && rect && rect.width > 0 && rect.height > 0),
      canvasCount: document.querySelectorAll('#SlidePanel canvas, #SlidePanel svg').length,
    }
  })

  expect(slideState.text, '应读取到真实幻灯片内容').toContain('鱼菜共生系统中氮转化途径')
  expect(slideState.panelVisible, 'PowerPoint 应创建可见幻灯片面板').toBe(true)
  expect(slideState.canvasCount, '幻灯片面板应创建 canvas/svg 渲染节点').toBeGreaterThan(0)
  expect(sandboxErrors, 'Office frame 不应再退化为 origin=null').toEqual([])

  await page.screenshot({
    path: 'tests/visual/desktop/screenshots/office-preview-no-sandbox.png',
    fullPage: false,
  })
})
