/**
 * recording-harmonyos-ua.spec.mjs
 *
 * 2026-07-16 #207 完整流程修复 E2E 回归测试 (Step 6: user_agent 落库)
 *
 * 验证点 (用 harmonyos-arkweb project + 真实 HarmonyOS UA):
 *   1. 用真 HarmonyOS 6.1 + ArkWeb 6.0 UA 调 POST /start-recording
 *   2. 后端 meetings.user_agent 字段正确落库 UA (含 "ArkWeb/" + "OpenHarmony" 关键字)
 *   3. cancel-recording 在 harmonyos UA 下也能工作
 *
 * 修复前: meetings 表无 user_agent 字段, 事后无法反推设备
 * 修复后: alembic 060 加 user_agent VARCHAR(500), start-recording route 接收
 *         User-Agent header 截断 500 字符落库
 *
 * 实现说明: 不走 mobile login UI (字段名不同, 加载 NutUI 组件), 直接用
 *   request fixture + 真 HarmonyOS UA 调 API 端到端验证。
 */

import { test, expect } from '@playwright/test'

const TEST_USER = {
  username: 'xiaoqi_testbot',
  password: 'testbot_pass_2026',
}

test('harmonyos-arkweb UA: start-recording 落库 user_agent 字段 (Step 6, #207 修复)', async ({
  request,
  baseURL,
}) => {
  // 1. 用真 HarmonyOS UA 登录拿 token
  const harmonyosUA = 'Mozilla/5.0 (Phone; OpenHarmony 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 ArkWeb/6.0.0.46SP3 Mobile'
  const loginRes = await request.post(`${baseURL}/api/v1/auth/login`, {
    headers: { 'User-Agent': harmonyosUA, 'Content-Type': 'application/json' },
    data: TEST_USER,
  })
  expect(loginRes.status()).toBe(200)
  const { access_token } = await loginRes.json()
  expect(access_token).toBeTruthy()
  console.log(`  Login OK with HarmonyOS UA`)

  // 2. 用真 HarmonyOS UA 调 POST /start-recording
  const startRes = await request.post(`${baseURL}/api/v1/meetings/start-recording`, {
    headers: { 'Authorization': `Bearer ${access_token}`, 'User-Agent': harmonyosUA },
  })
  expect(startRes.status()).toBe(200)
  const { id: meetingId } = await startRes.json()
  console.log(`  Created meeting ${meetingId} via HarmonyOS UA`)

  // 3. PSQL 验证落库 user_agent 包含 "ArkWeb/" 关键字
  const { execSync } = await import('child_process')
  const psqlOutput = execSync(
    `docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -t -c "SELECT user_agent FROM meetings WHERE id = ${meetingId};"`,
    { encoding: 'utf-8' }
  ).trim()
  console.log(`  DB user_agent: ${psqlOutput}`)

  // 验证: 落库的 UA 包含 HarmonyOS 关键字
  expect(psqlOutput).toMatch(/ArkWeb/)
  expect(psqlOutput).toMatch(/OpenHarmony/)

  // 4. cleanup: cancel-recording 避免留孤儿
  const cancelRes = await request.post(`${baseURL}/api/v1/meetings/${meetingId}/cancel-recording`, {
    headers: { 'Authorization': `Bearer ${access_token}`, 'User-Agent': harmonyosUA },
  })
  expect(cancelRes.status()).toBe(200)
  const cancelBody = await cancelRes.json()
  expect(cancelBody.cancelled).toBe(true)
  console.log(`  cancel-recording OK: ${JSON.stringify(cancelBody)}`)
})
