/**
 * tests/visual/desktop/drive-team-shared-sub-folders-verify-2026-07-12.spec.mjs
 *
 * 验证任务: 团队共享盘 > 组会PPT 是否有 23 个成员命名子文件夹
 * 用户问题: "你用Playwright看一下有没有子文件夹，团队共享盘中"
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
    if (!TEST_TOKEN) {
      throw new Error('TEST_TOKEN 未设置')
    }
  })

  test('UI 层验证: 团队共享盘下 组会PPT 含 23 个成员命名子文件夹', async ({ page }) => {
    // === Step 1: 登录 ===
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('input.el-input__inner', { timeout: 10_000 })
    const inputs = page.locator('input.el-input__inner')
    await inputs.nth(0).fill('xiaoqi_testbot')
    await inputs.nth(1).fill('testbot_pass_2026')
    await page.click('button.login-button')
    await page.waitForURL((url) => url.pathname !== '/login', { timeout: 15_000 }).catch(() => {})
    await page.waitForTimeout(1500)
    console.log(`[1] 登录后 URL: ${page.url()}`)

    // === Step 2: 跳到 /drive ===
    await page.goto(`${BASE_URL}/drive`, { waitUntil: 'networkidle' })
    await page.waitForSelector('.drive-sidebar', { timeout: 15_000 })
    await page.waitForTimeout(2000)  // 等 Vue + tree fetch 完成
    console.log(`[2] /drive 加载完成`)

    // === Step 3: 截图初始状态 (个人网盘视图) ===
    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/team-shared-A-initial.png',
      fullPage: true,
    })

    // === Step 4: 点击 🌐 团队共享盘 — 用 span 文字定位 + 默认中心点击 ===
    const teamSpan = page.locator('span:has-text("🌐 团队共享盘")').first()
    await expect(teamSpan).toBeVisible({ timeout: 5000 })
    console.log('[4] FolderTree 找到 "🌐 团队共享盘" 节点')

    // 4.1 用 JS 直接触发 click 事件, 绕过位置/遮挡问题
    await page.evaluate(() => {
      const el = document.querySelector('.drive-folder-tree-special-item.is-team')
      if (el) el.click()
    })
    // 4.2 等 Vue watch + fetchFolderTree + fetchDriveFiles
    await page.waitForTimeout(3500)
    console.log('[4] 已触发 团队共享盘 click')

    // === Step 5: 验证 specialView 切换成功 ===
    // 5.1 验证 .is-active class 已加上
    const teamActive = page.locator('.drive-folder-tree-special-item.is-team.is-active')
    await expect(teamActive).toHaveCount(1, { timeout: 10_000 })
    console.log('[5.1] 团队共享盘 .is-active 已加上 (specialView=team 切换成功)')

    // 5.2 验证面包屑
    const breadcrumb = page.locator('.drive-breadcrumb')
    await expect(breadcrumb).toContainText('🌐 团队共享盘', { timeout: 10_000 })
    console.log('[5.2] 面包屑含 🌐 团队共享盘')

    // === Step 6: 截图 team view (root level) ===
    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/team-shared-B-team-view-root.png',
      fullPage: true,
    })

    // === Step 7: 找 组会PPT 节点 — 团队共享盘 scope tree 应该加载组会PPT ===
    const groupPPTNode = page.locator('.folder-tree-node:has-text("组会PPT")').first()
    await expect(groupPPTNode).toBeVisible({ timeout: 10_000 })
    console.log('[7] FolderTree 找到 "组会PPT" 节点')

    // === Step 8: 展开 组会PPT 节点 ===
    const expandIcon = groupPPTNode.locator('.el-tree-node__expand-icon').first()
    if (await expandIcon.isVisible({ timeout: 3000 }).catch(() => false)) {
      // 先 click expand icon 让 el-tree 标记 expanded
      await expandIcon.click({ force: true })
      await page.waitForTimeout(500)
      console.log('[8a] 点击组会PPT 展开图标')
    }
    // 备用: 直接点击节点本身
    await groupPPTNode.click({ force: true })
    await page.waitForTimeout(2000)
    console.log('[8b] 点击组会PPT 节点')

    // === Step 9: 截图 组会PPT 展开后 ===
    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/team-shared-C-expanded.png',
      fullPage: true,
    })

    // === Step 10: 验证 23 个成员 sub-folder 可见 ===
    const memberNames = [
      '余歆睿', '关小未', '冯懿鑫', '刘子毅', '吴孟铨',
      '宋洋', '张宏魁', '张懿', '李胜景', '李锐远',
      '杜同贺', '杨慈', '王书馨', '耿嘉栋', '胡小琪',
      '艾琳朔', '蒋芦笛', '贾琦', '赵航佳', '陈天祥',
      '陈金薪', '雒培媛', '韩重阳',
    ]

    console.log('\n[10] 检查 23 个成员名是否在 FolderTree/FileGrid 中可见:')
    const visible = []
    const missing = []
    for (const name of memberNames) {
      const count = await page.locator(`.folder-tree-node:has-text("${name}"), .file-grid-item:has-text("${name}")`).count()
      if (count > 0) {
        visible.push(name)
        console.log(`     ✓ ${name}  (locator count=${count})`)
      } else {
        missing.push(name)
        console.log(`     ✗ ${name}  NOT FOUND`)
      }
    }
    console.log(`\n[10] 可见: ${visible.length}/23, 缺失: ${missing.length}/23`)

    // === Step 11: 最终全屏截图 ===
    await page.screenshot({
      path: 'tests/visual/desktop/screenshots/team-shared-D-final.png',
      fullPage: true,
    })

    // === Step 12: 期望 23/23 ===
    expect(visible.length, '团队共享盘应包含 23 个成员命名子文件夹').toBe(23)
  })
})