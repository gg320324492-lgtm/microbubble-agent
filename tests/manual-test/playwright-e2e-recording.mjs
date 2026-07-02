// tests/manual-test/playwright-e2e-recording.mjs
// 端到端测试听会上传：启动 chromium + fake audio + 登录 + 跳 /meetings/room + 模拟录音
// 用法: BASE_URL=https://agent.mnb-lab.cn node tests/manual-test/playwright-e2e-recording.mjs

import { chromium } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const USERNAME = process.env.E2E_USERNAME || 'xiaoqi_testbot'
const PASSWORD = process.env.E2E_PASSWORD || 'testbot_pass_2026'

const networkLog = []
const consoleLog = []
const pageErrors = []

async function main() {
  console.log('[1] 启动 chromium...')
  const browser = await chromium.launch({
    headless: true,
    args: [
      '--use-fake-ui-for-media-stream',  // 自动允许 getUserMedia
      '--use-fake-device-for-media-stream', // 提供 fake audio device
      '--autoplay-policy=no-user-gesture-required',
    ],
  })

  const context = await browser.newContext({
    permissions: ['microphone'],
  })

  // 拦截 console + pageerror + network
  const page = await context.newPage()
  page.on('console', msg => {
    consoleLog.push(`[${msg.type()}] ${msg.text()}`)
  })
  page.on('pageerror', err => {
    pageErrors.push(err.message)
  })
  page.on('request', req => {
    if (req.url().includes('/api/v1/meetings/')) {
      networkLog.push(`→ ${req.method()} ${req.url()}`)
    }
  })
  page.on('response', res => {
    if (res.url().includes('/api/v1/meetings/')) {
      networkLog.push(`← ${res.status()} ${res.url()}`)
    }
  })

  console.log(`[2] 打开 ${BASE_URL} ...`)
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(2000)

  console.log('[3] 登录...')
  // 检查是否在 login 页
  const loginUrl = page.url()
  console.log(`  当前 URL: ${loginUrl}`)

  if (loginUrl.includes('/login')) {
    // 找输入框（桌面 LoginView 用 name="login-username"/"login-password"）
    let usernameInput = page.locator('input[name="login-username"]').first()
    let passwordInput = page.locator('input[name="login-password"]').first()
    if (await usernameInput.count() === 0) {
      // fallback: 移动端或简化登录
      usernameInput = page.locator('input[autocomplete="username"], input[placeholder*="用户名"], input[placeholder*="账"]').first()
      passwordInput = page.locator('input[type="password"]').first()
    }
    await usernameInput.fill(USERNAME)
    await passwordInput.fill(PASSWORD)
    await page.locator('button:has-text("登录"), .login-button').first().click()
    await page.waitForTimeout(3000)
  }

  console.log(`  登录后 URL: ${page.url()}`)

  console.log('[4] 跳到 /meetings/room ...')
  await page.goto(`${BASE_URL}/meetings/room`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000)

  console.log(`  当前 URL: ${page.url()}`)

  console.log('[5] 看 page title 和 "开始听会" 按钮:')
  const title = await page.title()
  console.log(`  title: ${title}`)

  const startButton = page.locator('button:has-text("开始听会"), button:has-text("开始")').first()
  const hasStart = await startButton.count()
  console.log(`  "开始听会" 按钮存在: ${hasStart > 0 ? 'YES' : 'NO'}`)

  if (hasStart > 0) {
    console.log('[6] 点击 "开始听会" 按钮...')
    await startButton.click()
    await page.waitForTimeout(2000)

    // 听会开始后，状态应变化
    const state = await page.evaluate(() => {
      return {
        recorderState: window.__recorderState || 'unknown',
        mediaRecorderState: navigator.mediaDevices ? 'has-mediadevices' : 'no-mediadevices',
        audioContextState: typeof AudioContext !== 'undefined' ? 'has-AudioContext' : 'no-AudioContext',
      }
    })
    console.log(`  page state:`, JSON.stringify(state))

    // 等 6 秒收集 chunk (MediaRecorder.start(1000) 1s 间隔)
    console.log('[7] 等 6 秒录音 (期望 5-6 个 audio-chunk PUT 请求)...')
    await page.waitForTimeout(6000)

    // 抓 upload status badge 数据
    const uploadInfo = await page.evaluate(() => {
      // 尝试拿 UploadStatusBadge 渲染的值
      const elements = document.querySelectorAll('[class*="upload"]')
      const result = []
      for (const el of elements) {
        const text = el.textContent?.trim()
        if (text && text.length < 100) {
          result.push(text)
        }
      }
      return result
    })
    console.log(`  UI upload status: ${JSON.stringify(uploadInfo)}`)

    console.log('[8] 找 "结束听会" / "停止" 按钮...')
    const stopButton = page.locator('button:has-text("结束听会"), button:has-text("停止")').first()
    const hasStop = await stopButton.count()
    console.log(`  "结束听会" 按钮存在: ${hasStop > 0 ? 'YES' : 'NO'}`)

    if (hasStop > 0) {
      await stopButton.click()
      await page.waitForTimeout(2000)
      // 弹确认框, 点确定
      const confirmBtn = page.locator('.el-message-box__btns button:has-text("确定"), button:has-text("确定")').first()
      if (await confirmBtn.count() > 0) {
        await confirmBtn.click()
      }
      await page.waitForTimeout(8000) // 等上传 + 后处理
    }
  }

  console.log('\n========== NETWORK LOG ==========')
  for (const log of networkLog) console.log('  ' + log)

  console.log('\n========== CONSOLE LOG ==========')
  for (const log of consoleLog.slice(-50)) console.log('  ' + log)

  console.log('\n========== PAGE ERRORS ==========')
  for (const err of pageErrors) console.log('  ' + err)

  await browser.close()
}

main().catch(err => {
  console.error('TEST FAILED:', err)
  process.exit(1)
})
