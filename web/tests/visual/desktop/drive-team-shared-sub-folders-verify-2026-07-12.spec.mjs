/**
 * tests/visual/desktop/drive-team-shared-sub-folders-verify-2026-07-12.spec.mjs
 *
 * v2.26 验证: 团队共享盘 > 组会PPT > 23 个成员子文件夹
 *
 * 用户问题: "你用Playwright看一下有没有子文件夹，团队共享盘中"
 *
 * 修复链:
 * - Bug A (axios params 丢失) → fetchTree 改用 fetch + URLSearchParams
 * - Bug B (FolderTree 展开仅 7/23) → 待修
 *
 * 运行:
 *   BASE_URL=https://agent.mnb-lab.cn \
 *   TEST_TOKEN=$(curl -s -X POST $BASE_URL/api/v1/auth/login \
 *     -H 'Content-Type: application/json' \
 *     -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
 *     | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])") \
 *   npx playwright test tests/visual/desktop/drive-team-shared-sub-folders-verify-2026-07-12.spec.mjs \
 *     --project=desktop-chrome
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

test.describe('团队共享盘 > 组会PPT > 23 个成员子文件夹 (2026-07-12 验证)', () => {
  test.beforeAll(async () => {
    if (!TEST_TOKEN) throw new Error('TEST_TOKEN 未设置')
  })

  test('UI 层验证: 团队共享盘下 组会PPT 含 23 个成员命名子文件夹', async ({ page }) => {
    // === Login ===
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('input.el-input__inner', { timeout: 10_000 })
    await page.locator('input.el-input__inner').nth(0).fill('xiaoqi_testbot')
    await page.locator('input.el-input__inner').nth(1).fill('testbot_pass_2026')
    await page.click('button.login-button')
    await page.waitForURL((url) => url.pathname !== '/login', { timeout: 15_000 }).catch(() => {})
    await page.waitForTimeout(1500)

    // === 跳到 /drive ===
    await page.goto(`${BASE_URL}/drive`, { waitUntil: 'networkidle' })
    await page.waitForSelector('.drive-sidebar', { timeout: 15_000 })
    await page.waitForTimeout(2000)

    // === Step A: 点击 🌐 团队共享盘 ===
    await page.evaluate(() => {
      document.querySelector('.drive-folder-tree-special-item.is-team')?.click()
    })
    await page.waitForTimeout(3500)  // 等 watch + fetchTree('team') + 重渲染

    // === Step B: 验证 is-active + 面包屑 ===
    await expect(page.locator('.drive-folder-tree-special-item.is-team.is-active')).toHaveCount(1, { timeout: 10_000 })
    await expect(page.locator('.drive-breadcrumb')).toContainText('🌐 团队共享盘', { timeout: 10_000 })

    // === Step C: 验证侧栏出现 组会PPT 节点 (Bug A 修复标志) ===
    const groupPPTNode = page.locator('.folder-tree-node:has-text("组会PPT")').first()
    await expect(groupPPTNode).toBeVisible({ timeout: 10_000 })

    // === Step D: 展开 组会PPT 节点 ===
    const expandIcon = groupPPTNode.locator('.folder-tree-node-toggle').first()
    await expect(expandIcon).toBeVisible({ timeout: 3000 })
    await expandIcon.click({ force: true })
    await page.waitForTimeout(2000)

    // === Step E: 截图最终状态 ===
    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/team-shared-E-fully-expanded.png',
      fullPage: true,
    })

    // === Step F: 验证 23 个成员 sub-folder 全部可见 ===
    const memberNames = [
      '余歆睿', '关小未', '冯懿鑫', '刘子毅', '吴孟铨',
      '宋洋', '张宏魁', '张懿', '李胜景', '李锐远',
      '杜同贺', '杨慈', '王书馨', '耿嘉栋', '胡小琪',
      '艾琳朔', '蒋芦笛', '贾琦', '赵航佳', '陈天祥',
      '陈金薪', '雒培媛', '韩重阳',
    ]

    const visible = []
    const missing = []
    for (const name of memberNames) {
      const count = await page.locator(`.folder-tree-node-name:has-text("${name}")`).count()
      if (count > 0) visible.push(name)
      else missing.push(name)
    }

    console.log(`\n[F] Visible members: ${visible.length}/23`)
    visible.forEach((m) => console.log(`     ✓ ${m}`))
    if (missing.length) {
      console.log(`\n[F] Missing: ${missing.length}`)
      missing.forEach((m) => console.log(`     ✗ ${m}`))
    }

    // === Step G: 期望 23/23 ===
    expect(visible.length, '团队共享盘应包含 23 个成员命名子文件夹').toBe(23)
  })
})