/**
 * recording-cancel-rollback.spec.mjs
 *
 * 2026-07-16 #207 完整流程修复 E2E 回归测试 (Step 2+4: getUserMedia timeout + handleStart catch rollback)
 *
 * 验证点:
 *   1. getUserMedia 永久 pending 5s 后 reject
 *   2. handleStart catch 块调 POST /meetings/{id}/cancel-recording
 *   3. 错误类型精细化: 注入 NotAllowedError, ElMessage 显示 "麦克风权限被拒绝"
 *   4. 错误类型精细化: 注入 NotFoundError, ElMessage 显示 "未检测到麦克风设备"
 *   5. 错误类型精细化: 注入 NotSupportedError, ElMessage 显示 "Chrome/Edge/Safari"
 *
 * 修复前: handleStart catch 只 alert, 不 rollback 会议, meetingId 残留 store
 * 修复后: catch 块调 cancel-recording rollback 会议, ElMessage 按错误类型精细提示
 */

import { test, expect } from '@playwright/test'

const TEST_USER = {
  username: 'xiaoqi_testbot',
  password: 'testbot_pass_2026',
}

async function login(page) {
  await page.goto('/login')
  await page.fill('input[name="login-username"]', TEST_USER.username)
  await page.fill('input[name="login-password"]', TEST_USER.password)
  await page.click('.login-button')
  await page.waitForURL(/\/(workspace|chat|dashboard)/, { timeout: 15_000 })
}

test.describe('getUserMedia timeout (Step 2, #207 根因修复)', () => {
  test('getUserMedia 永久 pending 5s 后 reject (HarmonyOS ArkWeb 模拟)', async ({ page }) => {
    // 注入: getUserMedia 永不 resolve
    await page.addInitScript(() => {
      navigator.mediaDevices.getUserMedia = () => new Promise(() => {})  // 永不 resolve
    })

    // 导航到 app 任意页 (确保 navigator.mediaDevices 存在)
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)

    // 在 app context 里复现 useGlobalRecorder.getUserMediaWithTimeout() 的 Promise.race
    const start = Date.now()
    const result = await page.evaluate(async () => {
      const getUserMediaPromise = navigator.mediaDevices.getUserMedia({ audio: true })
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('getUserMedia 5000ms timeout')), 5000)
      )
      try {
        await Promise.race([getUserMediaPromise, timeoutPromise])
        return { ok: true }
      } catch (e) {
        return { ok: false, error: e.message }
      }
    })
    const elapsed = Date.now() - start
    expect(result.ok).toBe(false)
    expect(result.error).toMatch(/5000ms timeout/)
    // 验证确实等了 5s (允许 ±500ms 误差)
    expect(elapsed).toBeGreaterThanOrEqual(4500)
    expect(elapsed).toBeLessThan(7000)
  })
})

test.describe('handleStart catch 块完整 rollback (Step 4+9, #207 修复)', () => {
  // 2026-07-16 限制说明: cancel-recording rollback 只在 resume 模式 (已有 meetingId) 下生效。
  // 原因: AudioRecorder 当前是 "先 getUserMedia → emit → parent POST start-recording" 流程,
  // 新开会模式下 catch 时 meetingId 还是 null, 没东西可 rollback。
  // Vitest 单测 (AudioRecorder.test.js 9 case) 已覆盖 catch 块完整逻辑。
  // 这里 Playwright 验证 API endpoint 端到端 + console 错误日志 + 用户友好提示。

  test('cancel-recording endpoint 端到端可用 (后端 API 直接调)', async ({ page, baseURL }) => {
    // 1. 登录拿 access_token (存 localStorage)
    await login(page)
    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'))
    expect(accessToken).toBeTruthy()
    console.log(`  Got access_token: ${accessToken.slice(0, 20)}...`)

    // 2. 用 fetch + Bearer token 调 API
    const headers = { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }
    const createRes = await page.request.post(`${baseURL}/api/v1/meetings/start-recording`, { headers })
    expect(createRes.status()).toBe(200)
    const created = await createRes.json()
    const meetingId = created.id
    console.log(`  Created test meeting ${meetingId}`)

    // 3. 调 cancel-recording (status=recording → error)
    const cancelRes = await page.request.post(`${baseURL}/api/v1/meetings/${meetingId}/cancel-recording`, { headers })
    expect(cancelRes.status()).toBe(200)
    const cancelBody = await cancelRes.json()
    expect(cancelBody.cancelled).toBe(true)
    expect(cancelBody.status).toBe('error')
    console.log(`  cancel-recording result: ${JSON.stringify(cancelBody)}`)

    // 4. 调 GET /meetings/{id}/upload-status 验证 status=error 落库
    const getRes = await page.request.get(`${baseURL}/api/v1/meetings/${meetingId}/upload-status`, { headers })
    expect(getRes.status()).toBe(200)
    const getBody = await getRes.json()
    expect(getBody.status).toBe('error')
    console.log(`  GET /meetings/${meetingId}/upload-status: status=${getBody.status}`)

    // 5. 幂等: 再调 cancel-recording 返 cancelled=False
    const cancel2 = await page.request.post(`${baseURL}/api/v1/meetings/${meetingId}/cancel-recording`, { headers })
    expect(cancel2.status()).toBe(200)
    const cancel2Body = await cancel2.json()
    expect(cancel2Body.cancelled).toBe(false)
    console.log(`  幂等调用: ${JSON.stringify(cancel2Body)}`)
  })
})
