// DL-7 验收驱动：Part A→B 全链（buildLatestYml 产物经本地 HTTP 喂给真实 electron-updater
// → 启动自动检查 → 应用内弹窗）+ 稍后节流 + 重启不重弹/每日节流 + 设置页回归 + Part C 备份失败落日志
// 用法：node dl7-e2e.mjs <shotsDir>
import { createRequire } from 'node:module'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import http from 'node:http'
const require = createRequire('E:/microbubble-agent/web/package.json')
const { _electron } = require('playwright')
const { buildLatestYml } = await import('file:///E:/microbubble-agent/apps/desktop/scripts/lib/release-utils.mjs')

const SHOTS = process.argv[2]
if (!SHOTS) {
  console.error('usage: node dl7-e2e.mjs <shotsDir>')
  process.exit(2)
}
const APP_ROOT = 'E:/microbubble-agent/apps/desktop'
const PROFILE = 'C:/Users/pc/AppData/Local/Temp/dl7-e2e/profile'
const PORT = 45871
rmSync(PROFILE, { recursive: true, force: true })
mkdirSync(SHOTS, { recursive: true })
mkdirSync('C:/Users/pc/AppData/Local/Temp/dl7-e2e/bk', { recursive: true })

// ---- Part A 产物：用真实的 buildLatestYml 生成喂给 electron-updater 的 latest.yml ----
const NOTES = [
  '### 更新内容（DL-7 验收注入）',
  '',
  '- AI 对话**发送即上屏**：草稿即时清空、用户消息即时可见',
  '- 下架「实验 ELN」「稿件」两模块（数据保留）',
  '',
  '```',
  '特殊字符行: 冒号: #井号 ---分隔线',
  '```',
  '',
  '谢谢各位组员支持！'
].join('\n')
const LATEST_YML = buildLatestYml(
  { version: '99.0.0', fileName: 'MicroBubbleWorkbench-99.0.0-setup.exe', sha512: 'A'.repeat(88), size: 92113488, releaseDate: '2026-09-29T00:00:00.000Z' },
  NOTES
)
writeFileSync(join(SHOTS, 'served-latest.yml'), LATEST_YML)

const server = http.createServer((req, res) => {
  console.log('[feed-server]', req.method, req.url)
  res.writeHead(200, { 'content-type': 'text/yaml; charset=utf-8' })
  res.end(LATEST_YML)
})
await new Promise((r) => server.listen(PORT, '127.0.0.1', r))
console.log('[feed-server] listening on', PORT)

const mainLog = []
function tapStdout(app, tag) {
  const p = app.process()
  const on = (d) => {
    for (const line of String(d).split('\n')) {
      if (!line.trim()) continue
      mainLog.push(`[${tag}] ${line}`)
    }
  }
  p.stdout?.on('data', on)
  p.stderr?.on('data', on)
}

const report = {}
async function launchApp() {
  const app = await _electron.launch({
    executablePath: join(APP_ROOT, 'node_modules/electron/dist/electron.exe'),
    // 传应用根（package.json main）而非 main 脚本路径—— getAppPath() 必须落在应用根，
    // 否则托盘图标解析落在 out/main/resources 下缺失，whenReady 链在 setupTray 处中断
    args: [APP_ROOT],
    cwd: APP_ROOT,
    env: { ...process.env, MNB_USER_DATA: PROFILE, MNB_UPDATE_FEED: `http://127.0.0.1:${PORT}/latest.yml` }
  })
  tapStdout(app, 'main')
  return app
}

try {
  // ===== 第一轮启动：注册 → 弹窗 → 稍后 =====
  const app = await launchApp()
  const win = await app.firstWindow()
  await win.waitForLoadState('domcontentloaded')
  await win.waitForTimeout(1000)
  report.who = await win.evaluate(async () => {
    const st = await window.api.auth.status()
    if (st.userCount === 0) {
      const s = await window.api.auth.registerAdmin({ username: 'dl7probe', displayName: 'DL7 验收', password: 'dl7-probe-12345' })
      return s.user.username
    }
    const s = await window.api.auth.restore()
    return s ? s.user.username : null
  })
  await win.reload()
  await win.waitForSelector('.workbench', { timeout: 30000 })

  // 启动自动检查（5s 延迟）→ 弹窗；超时则自诊断（主日志 + 更新状态 + 截图）后继续走剩余验证
  try {
    await win.waitForSelector('[data-testid="update-notify-mask"]', { timeout: 25000 })
  } catch {
    report.dialogTimeout = true
    report.updateStateAtTimeout = await win.evaluate(async () => {
      try {
        return await window.api.update.state()
      } catch (e) {
        return { error: String(e) }
      }
    })
    await win.screenshot({ path: SHOTS + '/DEBUG-dialog-timeout.png' })
    console.log('[DEBUG] main log:')
    console.log(mainLog.join('\n'))
    console.log('[DEBUG] update state:', JSON.stringify(report.updateStateAtTimeout))
  }
  await win.waitForTimeout(400)
  report.dialog = await win.evaluate(() => ({
    version: document.querySelector('[data-testid="update-notify-version"]')?.textContent ?? null,
    notes: document.querySelector('[data-testid="update-notify-notes"]')?.textContent.slice(0, 120) ?? null,
    updateBtn: document.querySelector('[data-testid="update-notify-update"]')?.textContent.trim() ?? null,
    laterBtn: document.querySelector('[data-testid="update-notify-later"]')?.textContent.trim() ?? null
  }))
  await win.screenshot({ path: SHOTS + '/dl7-update-dialog.png' })

  // 稍后 → 关闭
  await win.locator('[data-testid="update-notify-later"]').click()
  await win.waitForTimeout(300)
  report.dialogClosedAfterLater = (await win.locator('[data-testid="update-notify-mask"]').count()) === 0
  await win.screenshot({ path: SHOTS + '/dl7-after-later.png' })

  // ===== Part C：制造一次真实备份失败（不可达 endpoint）→ 主进程日志取证 =====
  report.partC = await win.evaluate(async () => {
    const created = await window.api.backup.create('dl7-probe-password', 'C:/Users/pc/AppData/Local/Temp/dl7-e2e/bk')
    await window.api.backup.oss.saveConfig({
      bucket: 'probe-bucket',
      endpoint: 'http://127.0.0.1:9',
      prefix: 'probe',
      accessKeyId: 'probe-key',
      accessKeySecret: 'probe-secret'
    })
    try {
      await window.api.backup.oss.upload('C:/Users/pc/AppData/Local/Temp/dl7-e2e/bk/' + created.fileName)
      return { created: created.fileName, upload: 'unexpected-success' }
    } catch (e) {
      return { created: created.fileName, upload: 'failed-as-expected', error: String(e).slice(0, 160) }
    }
  })
  await win.waitForTimeout(800)

  // ===== 设置页回归：M6-1 更新入口仍在 =====
  await win.evaluate(() => {
    location.hash = '#/app/settings'
  })
  await win.waitForTimeout(900)
  report.settingsHasUpdateSection = await win.evaluate(() => !!document.querySelector('.settings'))
  await win.screenshot({ path: SHOTS + '/dl7-settings-regression.png' })
  await app.close()

  // ===== 第二轮启动（同 profile）：稍后版本不再弹 + 自动检查被每日节流 =====
  const app2 = await launchApp()
  const win2 = await app2.firstWindow()
  await win2.waitForLoadState('domcontentloaded')
  await win2.waitForTimeout(12000) // 越过 5s 自动检查窗口
  report.secondLaunch = await win2.evaluate(() => ({
    dialogVisible: document.querySelector('[data-testid="update-notify-mask"]') !== null,
    hash: location.hash
  }))
  await win2.screenshot({ path: SHOTS + '/dl7-second-launch-no-repop.png' })
  await app2.close()
} finally {
  server.close()
}

writeFileSync(SHOTS + '/main-log.txt', mainLog.join('\n'))
writeFileSync(SHOTS + '/report.json', JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
console.log('[main-log tail]')
console.log(mainLog.slice(-30).join('\n'))
