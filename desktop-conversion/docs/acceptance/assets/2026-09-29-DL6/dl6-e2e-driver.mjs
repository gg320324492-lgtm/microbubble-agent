// DL-6 验收驱动：Part A 发送乐观上屏瞬间态 + Part B 侧栏五项/命令面板
// 用法：node dl6-e2e.mjs <shotsDir>
import { createRequire } from 'node:module'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const require = createRequire('E:/microbubble-agent/web/package.json')
const { _electron } = require('playwright')

const SHOTS = process.argv[2]
if (!SHOTS) {
  console.error('usage: node dl6-e2e.mjs <shotsDir>')
  process.exit(2)
}

const APP_ROOT = 'E:/microbubble-agent/apps/desktop'
const PROFILE = 'C:/Users/pc/AppData/Local/Temp/dl6-e2e/profile'
rmSync(PROFILE, { recursive: true, force: true })
mkdirSync(SHOTS, { recursive: true })

const report = {}
const app = await _electron.launch({
  executablePath: join(APP_ROOT, 'node_modules/electron/dist/electron.exe'),
  args: [join(APP_ROOT, 'out/main/index.js')],
  cwd: APP_ROOT,
  env: { ...process.env, MNB_USER_DATA: PROFILE }
})

try {
  const win = await app.firstWindow()
  await win.waitForLoadState('domcontentloaded')
  await win.waitForTimeout(1200)

  // 首启注册（IPC 通道，断网可走）→ 重载进工作台
  report.who = await win.evaluate(async () => {
    const st = await window.api.auth.status()
    if (st.userCount === 0) {
      const s = await window.api.auth.registerAdmin({ username: 'dl6probe', displayName: 'DL6 验收', password: 'dl6-probe-12345' })
      return s.user.username
    }
    const s = await window.api.auth.restore()
    return s ? s.user.username : null
  })
  await win.reload()
  await win.waitForSelector('.workbench', { timeout: 30000 })

  // ===== Part B 证据 1：侧栏五项 =====
  report.navItems = await win.evaluate(() =>
    [...document.querySelectorAll('.rail-item')].map((b) => b.getAttribute('aria-label'))
  )
  await win.screenshot({ path: join(SHOTS, 'b-sidebar-5items.png') })

  // ===== Part B 证据 2：Ctrl+K 命令面板无两模块条目 =====
  await win.keyboard.press('Control+k')
  await win.waitForSelector('[data-testid="palette-input"]', { timeout: 5000 })
  await win.waitForTimeout(300)
  report.paletteItems = await win.evaluate(() =>
    [...document.querySelectorAll('[data-testid^="palette-item-"]')].map((n) => n.textContent.trim()))
  await win.fill('[data-testid="palette-input"]', '实验')
  await win.waitForTimeout(300)
  report.paletteFilterShiyan = await win.evaluate(() =>
    [...document.querySelectorAll('[data-testid^="palette-item-"]')].map((n) => n.textContent.trim()))
  await win.keyboard.press('Escape')
  await win.waitForTimeout(200)
  // 打开空查询面板截图
  await win.keyboard.press('Control+k')
  await win.waitForSelector('[data-testid="palette-input"]', { timeout: 5000 })
  await win.waitForTimeout(300)
  await win.screenshot({ path: join(SHOTS, 'b-palette.png') })
  await win.keyboard.press('Escape')
  await win.waitForTimeout(200)

  // ===== Part A：新建会话 → 主进程侧伪造慢 CHAT_SEND（8s，模拟真实模型悬置）→ 发送 → 瞬间态 =====
  await win.locator('.sessions-new').click()
  await win.waitForSelector('.composer-input', { timeout: 10000 })

  await app.evaluate(({ ipcMain }, chan) => {
    // 摘除真实 CHAT_SEND 后注册慢速伪造版（8s，模拟真实模型悬置窗口）
    ipcMain.removeHandler(chan)
    ipcMain.handle(chan, async (_e, p) => {
      await new Promise((r) => setTimeout(r, 8000))
      const now = Date.now()
      return {
        ok: true,
        data: {
          userMessage: { id: 'm-fake-u', sessionId: String(p?.sessionId ?? ''), role: 'user', content: String(p?.content ?? ''), meta: null, createdAt: now - 8000 },
          assistantMessage: { id: 'm-fake-a', sessionId: String(p?.sessionId ?? ''), role: 'assistant', content: '（模拟真实模型回复）你好！我是科研助手。', meta: null, createdAt: now }
        }
      }
    })
  }, 'chat:send')

  await win.fill('.composer-input', '你好')
  await win.locator('.composer-send').click()
  await win.waitForTimeout(1500) // 落在 8s 悬置窗口内

  report.partA = await win.evaluate(() => {
    const q = (s) => document.querySelector(s)
    const msgs = [...document.querySelectorAll('.msg')]
    return {
      draftValue: q('.composer-input') ? q('.composer-input').value : null,
      sendBtnText: q('.composer-send') ? q('.composer-send').textContent.trim() : null,
      sendBtnDisabled: q('.composer-send') ? q('.composer-send').disabled : null,
      msgCount: msgs.length,
      firstMsgRole: msgs[0]?.className ?? null,
      firstMsgText: msgs[0]?.textContent.slice(0, 60) ?? null,
      firstMsgIdTemp: msgs[0]?.getAttribute('class')?.includes('msg-user') ?? null
    }
  })
  await win.screenshot({ path: join(SHOTS, 'a-sending-instant.png') })

  // 悬置结束：乐观条目被真实结果原位替换 + 回复追加
  await win.waitForFunction(() => document.querySelectorAll('.msg').length >= 2, undefined, { timeout: 20000 })
  await win.waitForTimeout(400)
  report.partAAfter = await win.evaluate(() => {
    const msgs = [...document.querySelectorAll('.msg')]
    return {
      msgCount: msgs.length,
      texts: msgs.map((m) => m.textContent.slice(0, 30))
    }
  })
  await win.screenshot({ path: join(SHOTS, 'a-after-replace.png') })
} finally {
  await app.close()
}

writeFileSync(join(SHOTS, 'report.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
