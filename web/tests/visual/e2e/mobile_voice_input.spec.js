/**
 * mobile_voice_input.spec.js — 移动端语音输入 e2e (W68 路线 G-1)
 *
 * 场景:
 * 1. 长按麦克风按钮 → 录音浮层出现 (5 根音量柱 + 时长 + 提示)
 * 2. 上滑超 50px → 进入"松手取消"区域
 * 3. 松手取消 → 录音停止, ASR 不被调用
 * 4. 长按 → 松开 (不超阈值) → 触发 /api/v1/voice/asr
 * 5. ASR 返回 text → 文本插入 textarea
 *
 * 复用:
 * - useMobileVoiceInput (web/src/composables/useMobileVoiceInput.ts)
 * - MobileVoiceInputButton (web/src/components/mobile/MobileVoiceInputButton.vue)
 * - /api/v1/voice/asr (后端现有端点, 走 faster-whisper GPU)
 * - setup.js polyfill (FakeMediaRecorder, FakeMediaStream, FakeAudioContext)
 *
 * 运行:
 *   npx playwright test tests/e2e/mobile_voice_input.spec.js
 *
 * 注: 本项目主测为 vitest (web/src/components/mobile/__tests__/*.test.js), 该 e2e
 *     文件作为 Playwright 集成 spec, 部署到 CI 后跑真实浏览器流程。
 */

import { test, expect } from '@playwright/test'

// 选择移动端 viewport (iPhone 14 Pro)
test.use({ viewport: { width: 393, height: 852 } })

const ASR_MOCK_RESPONSE = {
  text: '你好小气',
  language: 'zh',
  language_probability: 0.95,
  duration: 1.2,
}

test.describe('Mobile 语音输入 (W68 路线 G-1)', () => {
  test.beforeEach(async ({ page, context }) => {
    // 1. 注入登录态 (假设有 TEST_TOKEN 环境变量, 实际部署按项目约定)
    //    此处 mock 掉鉴权, 让 /api/v1/auth/me 200
    await context.route('**/api/v1/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 1, name: '测试用户' }),
      })
    })

    // 2. 拦截 /api/v1/voice/asr → 返回固定文本
    await context.route('**/api/v1/voice/asr', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ASR_MOCK_RESPONSE),
      })
    })

    // 3. 注入 mobile UA + 触摸支持
    await page.setExtraHTTPHeaders({
      'User-Agent':
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    })
  })

  test('场景 1: 长按麦克风 → 录音浮层出现', async ({ page }) => {
    await page.goto('/mobile/chat')

    const btn = page.locator('#mobile-voice-input-btn')
    await expect(btn).toBeVisible()

    // 模拟长按 (touchstart 触发, 不松开)
    const box = await btn.boundingBox()
    if (!box) throw new Error('voice button not found')
    const cx = box.x + box.width / 2
    const cy = box.y + box.height / 2

    await page.touchscreen.tap(cx, cy, { force: true })
    // 注: page.touchscreen.tap 模拟单击; 长按需用 dispatchEvent
    await page.evaluate(() => {
      const b = document.getElementById('mobile-voice-input-btn')
      if (!b) return
      const ts = new TouchEvent('touchstart', {
        bubbles: true,
        cancelable: true,
        touches: [new Touch({ identifier: 0, target: b, clientX: 100, clientY: 100 })],
      })
      b.dispatchEvent(ts)
    })

    // 录音浮层应出现
    await expect(page.locator('#mobile-voice-input-overlay')).toBeVisible()
    await expect(page.locator('.mvi-bar').first()).toBeVisible()
    await expect(page.locator('.mvi-elapsed')).toContainText(/\d{2}:\d{2}/)
  })

  test('场景 2: 上滑超 50px → 取消区提示', async ({ page }) => {
    await page.goto('/mobile/chat')
    const btn = page.locator('#mobile-voice-input-btn')

    // 触发 touchstart
    await page.evaluate(() => {
      const b = document.getElementById('mobile-voice-input-btn')
      if (!b) return
      const ts = new TouchEvent('touchstart', {
        bubbles: true,
        cancelable: true,
        touches: [new Touch({ identifier: 0, target: b, clientX: 100, clientY: 500 })],
      })
      b.dispatchEvent(ts)
    })

    await expect(page.locator('#mobile-voice-input-overlay')).toBeVisible()

    // 模拟 touchmove 上滑 (clientY 减小 80px → 超 50 阈值)
    await page.evaluate(() => {
      window.dispatchEvent(
        new TouchEvent('touchmove', {
          bubbles: true,
          cancelable: true,
          touches: [new Touch({ identifier: 0, target: document.body, clientX: 100, clientY: 420 })],
        })
      )
    })

    // 提示文案应变成"松手取消"
    await expect(page.locator('.mvi-hint')).toContainText('松手取消')
  })

  test('场景 3: 长按 → 松手 (不超阈值) → ASR 文本插入 textarea', async ({ page }) => {
    await page.goto('/mobile/chat')
    const btn = page.locator('#mobile-voice-input-btn')
    const textarea = page.locator('textarea.input-textarea')

    // touchstart
    await page.evaluate(() => {
      const b = document.getElementById('mobile-voice-input-btn')
      if (!b) return
      const ts = new TouchEvent('touchstart', {
        bubbles: true,
        cancelable: true,
        touches: [new Touch({ identifier: 0, target: b, clientX: 100, clientY: 500 })],
      })
      b.dispatchEvent(ts)
    })

    // 等待 200ms (模拟短按)
    await page.waitForTimeout(200)

    // touchend → 触发 ASR
    await page.evaluate(() => {
      const b = document.getElementById('mobile-voice-input-btn')
      if (!b) return
      const te = new TouchEvent('touchend', { bubbles: true, cancelable: true })
      b.dispatchEvent(te)
    })

    // ASR 完成后 textarea 应有 "你好小气"
    await expect(textarea).toHaveValue('你好小气', { timeout: 5000 })
  })
})
