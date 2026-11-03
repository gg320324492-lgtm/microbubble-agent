/**
 * meeting-player-card-2026-11-04.spec.mjs
 *
 * 2026-11-04 选型⑤「融于卡片」播放条替换验证
 *
 * 改动: MeetingDetailView 的墨绿胶囊通栏播放条 → 播放器住进英雄卡
 *       (.hero-player 控制行 + .hero-progress 卡片下边缘 2px 进度线)
 *
 * 验证点:
 *   1. 结构: .hero-player 存在于 .detail-hero 内; 旧 .player-bar 已移除
 *   2. 播放/暂停: 点击 .hp-play → ⏸ (isPlaying) → .hero-progress i 宽度 > 0
 *   3. 进度条 seek: 点击 .hp-track 30% 处 → audio.currentTime 跳变
 *   4. 时间戳联动: 转录记录 tab 点 .transcript-ts.ts-seek → currentTime 跳到该时间
 *   5. 无 pageerror / console error
 *
 * 运行 (web 目录):
 *   MB_E2E_TOKEN=<jwt> BASE_URL=http://127.0.0.1 \
 *   npx playwright test tests/visual/desktop/meeting-player-card-2026-11-04.spec.mjs \
 *     --project=desktop-chrome --reporter=list
 *
 * token 签发 (不落仓库):
 *   docker exec microbubble-agent-app-1 python -c \
 *     "from app.core.security import create_access_token; print(create_access_token({'sub':'58'}))"
 */

import { test, expect } from '@playwright/test'

const MEETING_ID = Number(process.env.MB_E2E_MEETING_ID || 265)

test('会议详情页播放条「融于卡片」: 结构 + 播放 + seek + 时间戳联动', async ({ page }) => {
  const token = process.env.MB_E2E_TOKEN
  if (!token) throw new Error('缺少 MB_E2E_TOKEN 环境变量')
  const pageErrors = []
  const consoleErrors = []
  page.on('pageerror', (err) => pageErrors.push(String(err)))
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })

  // token 注入 (app 的 request.js 读 localStorage.access_token)
  await page.addInitScript((t) => localStorage.setItem('access_token', t), token)

  await page.goto(`/meetings/${MEETING_ID}`, { waitUntil: 'domcontentloaded' })

  // ---- 1. 结构 ----
  const hero = page.locator('.detail-hero')
  await expect(hero).toBeVisible()
  const player = page.locator('.detail-hero .hero-player')
  await expect(player).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('.player-bar')).toHaveCount(0)
  await expect(player.locator('.hp-play')).toBeVisible()
  await expect(page.locator('.detail-hero .hero-progress')).toHaveCount(1)

  // 无 pageerror 的提前闸 (后面统一断言)
  expect(pageErrors, 'pageerror').toEqual([])

  // ---- 2. 播放/暂停 ----
  await player.locator('.hp-play').click()
  await expect(player.locator('.hp-play')).toHaveText(/⏸/, { timeout: 5_000 })
  // timeupdate 驱动卡片下边缘进度
  await expect
    .poll(async () => page.locator('.hero-progress i').evaluate((el) => el.style.width), {
      timeout: 8_000,
      message: 'hero-progress 应随播放推进',
    })
    .not.toBe('0%')

  // ---- 3. 进度条 seek ----
  const before = await page.evaluate(
    () => document.querySelector('.hero-player audio')?.currentTime ?? -1,
  )
  const track = player.locator('.hp-track')
  const box = await track.boundingBox()
  await page.mouse.click(box.x + box.width * 0.3, box.y + box.height / 2)
  await expect
    .poll(async () => page.evaluate(
      () => document.querySelector('.hero-player audio')?.currentTime ?? -1,
    ), { timeout: 5_000, message: 'currentTime 应跳到 ~30% 处' })
    .toBeGreaterThan(before + 30)

  // ---- 4. 时间戳点击联动 (转录记录 tab) ----
  await page.locator('.tabstrip, .tab-strip').getByText('转录记录').click()
  const ts = page.locator('.transcript-ts.ts-seek').first()
  await expect(ts).toBeVisible({ timeout: 15_000 })
  const tsText = (await ts.textContent()) || ''
  const m = tsText.match(/(\d{1,2}):(\d{2})/)
  const tsSec = m ? Number(m[1]) * 60 + Number(m[2]) : 0
  await ts.click()
  await expect
    .poll(async () => page.evaluate(
      () => document.querySelector('.hero-player audio')?.currentTime ?? -1,
    ), { timeout: 5_000, message: '点时间戳后 currentTime 应落在时间戳附近' })
    .toBeGreaterThan(Math.max(0, tsSec - 3))

  // ---- 5. 截图 (证据) ----
  await page.locator('.detail-hero').screenshot({
    path: 'tests/visual/desktop/screenshots/meeting-player-card-2026-11-04.png',
  })

  // ---- 6. console error 收口 ----
  // 排除两类与本改动无关的已知噪音:
  //   a. ERR_ABORTED: 页面切换时的正常资源中止
  //   b. /ws/notifications 404: 本地 nginx 未代理通知 WebSocket (全局功能, 与播放条无关)
  const fatal = consoleErrors.filter((t) =>
    !/Failed to load resource.*net::ERR_ABORTED/.test(t) &&
    !/ws\/notifications.*404/.test(t))
  expect(fatal, 'console error').toEqual([])
  expect(pageErrors, 'pageerror').toEqual([])
})
