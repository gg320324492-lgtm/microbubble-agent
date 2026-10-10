// 恢复演练 Phase C：新机器救援 —— 全新档案 → 登录 → 用取回的容器+托管密钥恢复 → 重启验证
import { createRequire } from 'node:module'
import { mkdirSync, rmSync, writeFileSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const require = createRequire('E:/microbubble-agent/web/package.json')
const { _electron } = require('playwright')

const APP_ROOT = 'E:/microbubble-agent/apps/desktop'
const BASE = 'C:/Users/pc/.zcode/tmp/dl-drill'
const PROFILE = join(BASE, 'profile-B')
rmSync(PROFILE, { recursive: true, force: true })
mkdirSync(PROFILE, { recursive: true })

const envelope = JSON.parse(readFileSync(join(BASE, 'key.json'), 'utf8'))
const containerPath = join(BASE, 'container.mnbbak')

const app = await _electron.launch({
  executablePath: join(APP_ROOT, 'node_modules/electron/dist/electron.exe'),
  args: [join(APP_ROOT, 'out/main/index.js')],
  cwd: APP_ROOT,
  env: { ...process.env, MNB_USER_DATA: PROFILE }
})
const logs = []
app.process().stdout.on('data', (d) => logs.push(d.toString()))
app.process().stderr.on('data', (d) => logs.push(d.toString()))

const report = { steps: [] }
try {
  const win = await app.firstWindow()
  await win.waitForLoadState('domcontentloaded')
  await win.waitForTimeout(1000)

  // 1. 登录（恢复 IPC 有登录守卫；新档案登录 cismoke）
  const login = await win.evaluate(async () => {
    const r = await window.api.auth.cloudLogin({ username: 'cismoke', password: 'CiSmoke2026', remember: false })
    return r?.cloudUsername ?? null
  })
  report.steps.push('login: ' + login)
  console.log('[drill] 登录:', login)

  // 2. 等登录触发的首备跑完（避免与恢复写盘并发）
  await new Promise((r) => setTimeout(r, 12000))

  // 3. 恢复：取回的容器 + 托管信封里的密钥
  const restored = await win.evaluate(async (args) => {
    return await window.api.backup.restore(args.key, args.containerPath)
  }, { key: envelope.key, containerPath })
  report.restore = restored
  report.steps.push('restore: ' + JSON.stringify(restored))
  console.log('[drill] 恢复完成, needRestart=', restored?.needRestart)
} catch (e) {
  report.error = String(e && e.stack || e)
  console.error('[drill][ERROR]', e)
} finally {
  writeFileSync(join(BASE, 'phase-c-report.json'), JSON.stringify(report, null, 2))
  await app.close()
}
console.log('[drill] Phase C 结束:', JSON.stringify({ ok: report.restore?.needRestart === true }))
process.exit(report.restore?.needRestart === true ? 0 : 1)
