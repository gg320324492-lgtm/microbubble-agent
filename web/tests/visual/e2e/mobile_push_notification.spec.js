/**
 * mobile_push_notification.spec.js — 移动端 PWA 推送通知 e2e (W68 路线 5 第 3 批)
 *
 * 场景:
 * 1. 推送设置项存在 → 点击 → 权限申请弹窗出现
 * 2. 拒绝后 → 7 天 TTL 标记写入 localStorage, 弹窗不再重复弹出
 *
 * 复用:
 * - useMobilePushNotification (web/src/composables/useMobilePushNotification.ts)
 * - MobilePushPermissionDialog (web/src/components/mobile/MobilePushPermissionDialog.vue)
 * - MobileSettingsView (web/src/views/mobile/MobileSettingsView.vue)
 * - setup.js polyfill (Notification / navigator.serviceWorker stub)
 *
 * 运行:
 *   npx playwright test tests/e2e/mobile_push_notification.spec.js
 *
 * 注: 本项目主测为 vitest (web/src/components/mobile/__tests__/*.test.js), 该 e2e
 *     文件作为 Playwright 集成 spec, 部署到 CI 后跑真实浏览器流程。
 */

import { test, expect } from '@playwright/test'

// 选择移动端 viewport (iPhone 14 Pro - 验证 iOS Safari 16.4+ standalone PWA 场景)
test.use({ viewport: { width: 393, height: 852 }, isMobile: true, hasTouch: true })

const LS_DISMISS_KEY = 'mobile_push_dismissed_at'
const LS_SUBSCRIBED_KEY = 'mobile_push_subscribed_at'

test.describe('Mobile 推送通知 (W68 路线 5 第 3 批)', () => {
  test.beforeEach(async ({ page, context }) => {
    // 1. 注入登录态 (mock 鉴权, 让 /api/v1/auth/me 200)
    await context.route('**/api/v1/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          name: '测试用户',
          email: 'test@lab.cn',
          role: 'member',
        }),
      })
    })
    // 2. mock notification preferences
    await context.route('**/api/v1/members/me/notification-preferences', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ enabled: true, digest_time: '11:00' }),
      })
    })
    // 3. 注入 push-subscribe 端点 (项目目前无 VAPID, mock 200 即可)
    await context.route('**/api/v1/notifications/push-subscribe', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
    })
    await context.route('**/api/v1/notifications/push-unsubscribe', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
    })
    // 4. 清空 localStorage 中的 push TTL (避免上次跑留下状态)
    await context.addInitScript(() => {
      try {
        localStorage.removeItem('mobile_push_dismissed_at')
        localStorage.removeItem('mobile_push_subscribed_at')
        localStorage.removeItem('mobile_push_endpoint')
      } catch {}
    })
  })

  test('场景 1: 推送设置项存在 → 点击 → 弹窗出现', async ({ page }) => {
    // 导航到设置页
    await page.goto('/mobile/settings')

    // 等待推送设置项渲染
    const pushItem = page.getByTestId('push-toggle-item')
    await expect(pushItem).toBeVisible()
    await expect(pushItem).toContainText('推送通知')

    // 点击
    await pushItem.click()

    // 弹窗出现
    const dialog = page.getByRole('dialog', { name: '启用推送通知？' })
    await expect(dialog).toBeVisible()

    // 弹窗内有允许 / 暂不开启按钮
    const allowBtn = dialog.getByRole('button', { name: '允许通知' })
    const dismissBtn = dialog.getByRole('button', { name: /暂不开启|不再提醒/ })
    await expect(allowBtn).toBeVisible()
    await expect(dismissBtn).toBeVisible()

    // 弹窗显示文案 (含 3 项 benefit)
    await expect(dialog).toContainText('第一时间通知您')
    await expect(dialog).toContainText('11:00')

    // 关闭弹窗 (后续测试不依赖)
    await dismissBtn.click()
  })

  test('场景 2: 拒绝后 7 天 TTL 标记写入 + 弹窗不再重复弹出', async ({ page, context }) => {
    await page.goto('/mobile/settings')

    // 第一次点击 → 弹窗
    const pushItem = page.getByTestId('push-toggle-item')
    await pushItem.click()
    const dialog = page.getByRole('dialog', { name: '启用推送通知？' })
    await expect(dialog).toBeVisible()

    // 点击 "暂不开启" → 写入 localStorage TTL
    await dialog.getByRole('button', { name: /暂不开启/ }).click()
    await expect(dialog).not.toBeVisible()

    // 验证 localStorage 写入
    const dismissedAt = await page.evaluate((key) => localStorage.getItem(key), LS_DISMISS_KEY)
    expect(dismissedAt).toBeTruthy()
    const ts = Number(dismissedAt)
    expect(Number.isFinite(ts)).toBe(true)
    // 7 天 TTL: ts 应是最近 5 秒内
    expect(Date.now() - ts).toBeLessThan(5000)

    // 再次点击 → 弹窗**不**出现 (composable.shouldPrompt 短路)
    await pushItem.click()
    // 第二次点击 → shouldPrompt 仍 false (TTL 内 dismissed)
    await expect(page.getByRole('dialog', { name: '启用推送通知？' })).not.toBeVisible()
  })

  test('场景 3: 弹窗内 iOS Safari 引导文案 (添加到主屏)', async ({ page, context }) => {
    // mock iOS Safari UA + 非 standalone (URL bar 场景)
    await context.setExtraHTTPHeaders({})
    await page.setExtraHTTPHeaders({})
    await page.addInitScript(() => {
      // 覆盖 navigator.userAgent 为 iOS Safari 16.4+
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1',
        configurable: true,
      })
      // 覆盖 standalone 检测为 false (URL bar Safari, 非 PWA)
      Object.defineProperty(window.navigator, 'standalone', { value: false, configurable: true })
      // mock matchMedia (iOS Safari 16.4+ 在 test runner 中可能缺失)
      if (!window.matchMedia) {
        window.matchMedia = (q) => ({
          matches: false,
          media: q,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
        })
      }
    })

    await page.goto('/mobile/settings')
    const pushItem = page.getByTestId('push-toggle-item')
    await pushItem.click()

    // 弹窗出现 + 显示 iOS 引导文案
    const dialog = page.getByRole('dialog', { name: '启用推送通知？' })
    await expect(dialog).toBeVisible()
    // 允许按钮 disabled (iOS Safari standalone 限制)
    const allowBtn = dialog.getByRole('button', { name: '允许通知' })
    await expect(allowBtn).toBeDisabled()
    // 含"添加到主屏"提示
    await expect(dialog).toContainText('添加到主屏')

    // 关闭
    await dialog.getByRole('button', { name: /暂不开启/ }).click()
  })
})