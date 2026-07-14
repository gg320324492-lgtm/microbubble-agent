import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1'
const USERNAME = 'xiaoqi_testbot'
const PASSWORD = 'testbot_pass_2026'
const NULL_VALUE_ERROR = "Cannot read properties of null (reading 'value')"

test.use({ serviceWorkers: 'block' })

test('DesktopDriveView selected folder refs stay reactive', async ({ page }) => {
  const runtimeErrors = []

  page.on('pageerror', (error) => runtimeErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })

  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
  await page.locator('input.el-input__inner').nth(0).fill(USERNAME)
  await page.locator('input.el-input__inner').nth(1).fill(PASSWORD)
  await page.locator('button.login-button').click()
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 15_000 })

  await page.goto(`${BASE_URL}/drive`, { waitUntil: 'networkidle' })
  await expect(page.locator('.desktop-drive-view')).toBeVisible()
  expect(runtimeErrors.filter((message) => message.includes(NULL_VALUE_ERROR))).toEqual([])

  const toolbarCreateButton = page.locator('.drive-toolbar .drive-toolbar-btn:has-text("新建文件夹")')
  await toolbarCreateButton.click()
  const rootDialog = page.locator('.el-dialog:has-text("新建文件夹")')
  await expect(rootDialog).toBeVisible()
  await expect(rootDialog.locator('.parent-folder-path')).toHaveCount(0)
  await expect(rootDialog.locator('.team-hint')).toBeVisible()
  await rootDialog.getByRole('button', { name: '取消' }).click()

  const teamTreeResponse = page.waitForResponse((response) =>
    response.url().includes('/api/v1/folders/tree?scope=team') && response.status() === 200
  )
  await page.locator('.drive-folder-tree-special-item.is-team').click()
  const teamTree = await (await teamTreeResponse).json()
  const teamFolderData = teamTree.tree.find((item) => item.name === '组会PPT')
  expect(teamFolderData).toBeTruthy()

  const teamFolder = page.locator('.folder-tree-node:has-text("组会PPT")').first()
  await expect(teamFolder).toBeVisible({ timeout: 15_000 })
  await teamFolder.locator('.folder-tree-node-row').click()

  await toolbarCreateButton.click()
  const dialog = page.locator('.el-dialog:has-text("新建文件夹")')
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('.parent-folder-path')).toContainText('组会PPT')
  await expect(dialog.locator('.team-hint')).toHaveCount(0)

  await dialog.screenshot({
    path: 'tests/visual/desktop/screenshots/drive-selected-folder-ref-2026-07-14.png',
  })

  let submittedPayload = null
  await page.route('**/api/v1/folders', async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    submittedPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ id: 999999, ...submittedPayload }),
    })
  })
  await dialog.locator('input').first().fill('ref-chain-probe')
  await dialog.getByRole('button', { name: '创建' }).click()
  await expect.poll(() => submittedPayload).not.toBeNull()
  expect(submittedPayload.parent_id).toBe(teamFolderData.id)
  expect(submittedPayload.name).toBe('ref-chain-probe')

  expect(runtimeErrors.filter((message) => message.includes(NULL_VALUE_ERROR))).toEqual([])
})
