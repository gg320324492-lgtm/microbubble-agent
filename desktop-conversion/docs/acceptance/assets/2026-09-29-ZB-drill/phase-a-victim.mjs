// 恢复演练 Phase A：受害者档案 —— cismoke 真实登录 → 零感备份自动点火 → 附件+聊天数据上云
// 用法：node phase-a-victim.mjs
import { createRequire } from 'node:module'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join } from 'node:path'

const require = createRequire('E:/microbubble-agent/web/package.json')
const { _electron } = require('playwright')

const APP_ROOT = 'E:/microbubble-agent/apps/desktop'
const BASE = 'C:/Users/pc/.zcode/tmp/dl-drill'
const PROFILE = join(BASE, 'profile-A')
rmSync(PROFILE, { recursive: true, force: true })
mkdirSync(join(PROFILE, 'data', 'files', 'knowledge', 'drill'), { recursive: true })

// 附件样本：2MB 可辨识内容（发布前就位 → 随首个容器上云）
const sample = Buffer.alloc(2 * 1024 * 1024)
for (let i = 0; i < sample.length; i++) sample[i] = (i * 7 + (i % 251)) & 0xff
const samplePath = join(PROFILE, 'data', 'files', 'knowledge', 'drill', '附件-演练样本.bin')
writeFileSync(samplePath, sample)
const sampleSha = createHash('sha256').update(sample).digest('hex')
console.log('[drill] 附件样本就位:', samplePath, 'sha256=' + sampleSha.slice(0, 16) + '…')

const app = await _electron.launch({
  executablePath: join(APP_ROOT, 'node_modules/electron/dist/electron.exe'),
  args: [join(APP_ROOT, 'out/main/index.js')],
  cwd: APP_ROOT,
  env: { ...process.env, MNB_USER_DATA: PROFILE }
})
const mainLogs = []
app.process().stdout.on('data', (d) => mainLogs.push(d.toString()))
app.process().stderr.on('data', (d) => mainLogs.push(d.toString()))

const report = { sampleSha, steps: [] }
try {
  const win = await app.firstWindow()
  await win.waitForLoadState('domcontentloaded')
  await win.waitForTimeout(1000)

  // 1. 真实云端登录（cismoke 无任何既有备份配置 → 四探针全空 → 自动配置点火 + 立即首备）
  report.login = await win.evaluate(async () => {
    const r = await window.api.auth.cloudLogin({ username: 'cismoke', password: 'CiSmoke2026', remember: false })
    return r
  })
  report.steps.push('login ok, cloudUsername=' + (report.login?.cloudUsername ?? JSON.stringify(report.login).slice(0, 80)))
  console.log('[drill] 登录成功:', report.login?.cloudUsername)

  // 2. 造一条聊天数据（无模型 → 本地回声，链路真实）
  const sess = await win.evaluate(async () => {
    const s = await window.api.chat.sessionCreate('演练会话')
    await window.api.chat.send(s.id, 'DRILL-恢复演练标记-20260929')
    return s.id
  })
  report.chatSessionId = sess
  report.steps.push('chat data created: ' + sess)
  console.log('[drill] 聊天标记数据已写入:', sess)

  // 3. 等零感备份完成（登录触发的立即首备；主进程日志确认）
  let backupDone = false
  for (let i = 0; i < 60 && !backupDone; i++) {
    await new Promise((r) => setTimeout(r, 2000))
    const all = mainLogs.join('')
    backupDone = all.includes('云端备份完成')
    if (!backupDone && all.includes('云端备份失败')) {
      console.log('[drill][FATAL] 备份失败日志:', all.slice(all.indexOf('云端备份失败') - 200, all.indexOf('云端备份失败') + 200))
      break
    }
  }
  const allLogs = mainLogs.join('')
  const m = allLogs.match(/\[backup\] 云端备份完成：[^\n]*/)
  report.backupDone = backupDone
  report.backupLog = m ? m[0] : allLogs.slice(-600)
  console.log('[drill] 备份完成?', backupDone, m ? m[0] : '')
  if (!backupDone) {
    console.log('[drill] 尾部日志:\n' + mainLogs.join('').split('\n').filter((l) => l.includes('[backup]') || l.includes('[auth]') || l.includes('[drive]')).slice(-15).join('\n'))
  }
} catch (e) {
  report.error = String(e && e.stack || e)
  console.error('[drill][ERROR]', e)
} finally {
  writeFileSync(join(BASE, 'phase-a-report.json'), JSON.stringify(report, null, 2))
  await app.close()
}
console.log('[drill] Phase A 结束:', JSON.stringify({ ok: report.backupDone === true, chat: report.chatSessionId }))
process.exit(report.backupDone === true ? 0 : 1)
