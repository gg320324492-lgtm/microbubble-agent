// DL-5 验收驱动：真实 Electron 渲染 + 布局数值断言 + 截图
// 用法：node dl5-e2e.mjs <before|after> <shotsDir>
import { createRequire } from 'node:module'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const require = createRequire('E:/microbubble-agent/web/package.json')
const { _electron } = require('playwright')

const MODE = process.argv[2] ?? 'after'
const SHOTS = process.argv[3]
if (!SHOTS) {
  console.error('usage: node dl5-e2e.mjs <before|after> <shotsDir>')
  process.exit(2)
}

const APP_ROOT = 'E:/microbubble-agent/apps/desktop'
// 每次独立 scratch 档案，绝不触碰用户安装版数据（主进程 MNB_USER_DATA 钩子）
const PROFILE = 'C:/Users/pc/AppData/Local/Temp/dl5-e2e/profile-' + MODE
rmSync(PROFILE, { recursive: true, force: true })
mkdirSync(SHOTS, { recursive: true })

// 长文本：课题组主题句 × 3 为一段，× n 段
const LONG = (n) => {
  const s =
    '微纳米气泡体系的比表面积与界面传质效率显著高于常规鼓泡，实验中需控制曝气强度、温度与 pH 三组变量，并对降解率随时间变化采样记录。'
  const paras = []
  for (let i = 0; i < n; i++) paras.push(`第 ${i + 1} 段：` + s.repeat(3))
  return paras.join('\n\n')
}
const MSGS = [LONG(6), LONG(6), LONG(6), LONG(6)]

const app = await _electron.launch({
  executablePath: join(APP_ROOT, 'node_modules/electron/dist/electron.exe'),
  args: [join(APP_ROOT, 'out/main/index.js')],
  cwd: APP_ROOT,
  env: { ...process.env, MNB_USER_DATA: PROFILE }
})

const report = { mode: MODE, steps: [] }
try {
  const win = await app.firstWindow()
  await win.waitForLoadState('domcontentloaded')
  await win.waitForTimeout(1200)

  // 首启零用户 → IPC 首启注册管理员（本地建号 UI 已退役，通道保留，断网可走）
  report.who = await win.evaluate(async () => {
    const st = await window.api.auth.status()
    if (st.userCount === 0) {
      const s = await window.api.auth.registerAdmin({
        username: 'dl5probe',
        displayName: 'DL5 验收',
        password: 'dl5-probe-12345'
      })
      return s.user.username
    }
    const s = await window.api.auth.restore()
    return s ? s.user.username : null
  })

  // 重载 → 路由守卫 auth.init/restore → 直接进工作台
  await win.reload()
  await win.waitForSelector('.workbench', { timeout: 30000 })

  // 新建会话（store.create 自动 select）
  await win.locator('.sessions-new').click()
  await win.waitForSelector('.composer-input', { timeout: 10000 })

  // 灌长对话（未配置模型 → 本地回声，断网闭环）
  // 注意：发送成功后 draft 被清空，按钮因 !draft.trim() 仍 disabled —— 等待信号是消息数 +2
  for (let i = 0; i < MSGS.length; i++) {
    const before = await win.locator('.msg').count()
    await win.fill('.composer-input', MSGS[i])
    await win.locator('.composer-send').click()
    await win.waitForFunction(
      (n) => document.querySelectorAll('.msg').length >= n,
      before + 2,
      { timeout: 60000 }
    )
    await win.waitForTimeout(150)
  }
  report.msgCount = await win.locator('.msg').count()

  const metrics = () =>
    win.evaluate(() => {
      const q = (s) => document.querySelector(s)
      if (!q('.shell-main')) return null
      const r = (el) => {
        const b = el.getBoundingClientRect()
        return { top: Math.round(b.top), bottom: Math.round(b.bottom), height: Math.round(b.height) }
      }
      const m = q('.shell-main')
      const body = q('.chat-body')
      const comp = q('.chat-composer')
      const ses = q('.sessions')
      return {
        innerHeight: window.innerHeight,
        shellMain: {
          scrollHeight: m.scrollHeight,
          clientHeight: m.clientHeight,
          scrollTop: m.scrollTop,
          overflowY: getComputedStyle(m).overflowY
        },
        chatBody: {
          scrollHeight: body ? body.scrollHeight : null,
          clientHeight: body ? body.clientHeight : null,
          scrollTop: body ? body.scrollTop : null,
          overflowY: body ? getComputedStyle(body).overflowY : null
        },
        composer: comp ? r(comp) : null,
        sessions: ses ? r(ses) : null
      }
    })

  // (a) 滚到最顶
  await win.evaluate(() => {
    const m = document.querySelector('.shell-main')
    if (m) m.scrollTop = 0
    const b = document.querySelector('.chat-body')
    if (b) b.scrollTop = 0
  })
  await win.waitForTimeout(300)
  report.a_top = await metrics()
  await win.screenshot({ path: join(SHOTS, 'a-top.png') })

  // (b) 滚到最底（before：整页滚到底；after：消息区内滚到底）
  await win.evaluate(() => {
    const m = document.querySelector('.shell-main')
    if (m) m.scrollTop = m.scrollHeight
    const b = document.querySelector('.chat-body')
    if (b) b.scrollTop = b.scrollHeight
  })
  await win.waitForTimeout(300)
  report.b_bottom = await metrics()
  await win.screenshot({ path: join(SHOTS, 'b-bottom.png') })

  // (c) 矮窗口：应用 minHeight=640，工单 ~600px 取可达下限 640
  await app.evaluate(({ BrowserWindow }) => {
    BrowserWindow.getAllWindows()[0].setBounds({ x: 40, y: 40, width: 1100, height: 640 })
  })
  await win.waitForTimeout(500)
  await win.evaluate(() => {
    const m = document.querySelector('.shell-main')
    if (m) m.scrollTop = 0
    const b = document.querySelector('.chat-body')
    if (b) b.scrollTop = 0
  })
  await win.waitForTimeout(200)
  report.c_chat = await metrics()
  await win.screenshot({ path: join(SHOTS, 'c-chat-640.png') })

  // 设置页外滚（M7 无回归检查）
  await win.evaluate(() => {
    location.hash = '#/app/settings'
  })
  await win.waitForTimeout(800)
  report.c_settings = await win.evaluate(() => {
    const m = document.querySelector('.shell-main')
    return m
      ? {
          scrollHeight: m.scrollHeight,
          clientHeight: m.clientHeight,
          scrollable: m.scrollHeight > m.clientHeight
        }
      : null
  })
  await win.screenshot({ path: join(SHOTS, 'c-settings-640.png') })
} finally {
  await app.close()
}

writeFileSync(join(SHOTS, 'report.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
