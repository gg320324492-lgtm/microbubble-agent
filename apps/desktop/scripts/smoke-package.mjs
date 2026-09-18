#!/usr/bin/env node
// 产物可运行性门禁（M7 随车必办②，M6-2 转办）
//
// 背景：M6-2 首航出现过「CI 全绿 + 产物上传成功 + Release 公开可见，但装到机器上应用启动即崩」
// （better-sqlite3 为 Node ABI 而非 Electron ABI）。当时 CI 只验到"打包成功"，没有验"能跑"。
// 本脚本补上这一环：静默启动打包产物 → 走完首启注册（真正打开 SQLite）→ CDP 断言状态栏版本号。
//
// 断言链覆盖：主进程启动 → 原生模块（better-sqlite3/Electron ABI）→ IPC → 渲染进程 → 版本一致性。
// 任一步失败即非 0 退出，CI 直接 fail。
import { spawn } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const PORT = Number(process.env.MNB_SMOKE_PORT || 9333)
const USER = 'cismoke'
const PASS = 'CiSmoke2026'
const log = (m) => console.log(`[smoke] ${m}`)
const die = (m) => {
  console.error(`[smoke][FATAL] ${m}`)
  process.exit(1)
}

const version = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).version
const exe = join(ROOT, 'release', 'win-unpacked', 'MicroBubbleWorkbench.exe')
if (!existsSync(exe)) die(`未找到打包产物：${exe}（请先执行 package）`)
log(`待验证产物：${exe}（期望版本 ${version}）`)

const userData = mkdtempSync(join(tmpdir(), 'mnb-smoke-'))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const child = spawn(exe, ['--no-sandbox', '--disable-gpu-sandbox', `--remote-debugging-port=${PORT}`], {
  env: { ...process.env, MNB_USER_DATA: userData },
  stdio: ['ignore', 'pipe', 'pipe']
})
let appLog = ''
child.stdout.on('data', (d) => (appLog += d.toString()))
child.stderr.on('data', (d) => (appLog += d.toString()))

function cleanup() {
  try {
    child.kill()
  } catch {
    /* 忽略 */
  }
  try {
    rmSync(userData, { recursive: true, force: true })
  } catch {
    /* 忽略 */
  }
}

/** 等 CDP page target（应用起不来时这里超时 → 正是要抓的失败） */
async function waitForPage(timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
      const page = list.find((t) => t.type === 'page' && t.url && !t.url.startsWith('devtools://'))
      if (page) return page
    } catch {
      /* 还没起来 */
    }
    if (child.exitCode !== null) {
      die(`应用进程提前退出（exit ${child.exitCode}）——产物不可运行\n--- 应用输出 ---\n${appLog.slice(-2000)}`)
    }
    await sleep(1000)
  }
  die(`等待 CDP page target 超时（${timeoutMs}ms）——产物未渲染出界面\n--- 应用输出 ---\n${appLog.slice(-2000)}`)
}

function connect(url) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(url)
    let id = 0
    const pending = new Map()
    ws.addEventListener('open', () =>
      res({
        send: (method, params) =>
          new Promise((ok, no) => {
            const m = ++id
            pending.set(m, { ok, no })
            ws.send(JSON.stringify({ id: m, method, params }))
          }),
        close: () => ws.close()
      })
    )
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id && pending.has(msg.id)) {
        const { ok, no } = pending.get(msg.id)
        pending.delete(msg.id)
        msg.error ? no(new Error(JSON.stringify(msg.error))) : ok(msg.result)
      }
    })
    ws.addEventListener('error', rej)
  })
}

const SET_INPUT = `
  const set = (sel, v) => {
    const el = document.querySelector(sel)
    if (!el) return false
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v)
    el.dispatchEvent(new Event('input', { bubbles: true }))
    return true
  }
`

try {
  const page = await waitForPage()
  log(`渲染进程已就绪：${page.url}`)
  const cdp = await connect(page.webSocketDebuggerUrl)
  await cdp.send('Runtime.enable')

  const ev = async (expression) => {
    const r = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? 'eval failed')
    return r.result.value
  }
  const waitFor = async (expr, tries, tag) => {
    for (let i = 0; i < tries; i++) {
      if (await ev(expr)) return true
      await sleep(1000)
    }
    log(`[等待超时] ${tag}`)
    return false
  }

  if (!(await waitFor(`document.querySelector('#app') && document.querySelector('#app').children.length > 0`, 60, '#app 渲染'))) {
    die(`渲染进程未挂载 #app\n--- 应用输出 ---\n${appLog.slice(-2000)}`)
  }
  log('渲染进程已挂载 #app')

  // 首启注册：这一步会真正写入 SQLite —— 原生模块 ABI 不对时在此必然失败
  if (await ev(`!!document.querySelector('#setup-username')`)) {
    await ev(`(() => { ${SET_INPUT}
      set('#setup-username','${USER}'); set('#setup-display','CI 冒烟')
      set('#setup-password','${PASS}'); set('#setup-confirm','${PASS}')
      document.querySelector('form button[type=submit]').click(); return true })()`)
    log('已提交首启注册（写入 SQLite）')
  } else if (await ev(`!!document.querySelector('#login-username')`)) {
    await ev(`(() => { ${SET_INPUT}
      set('#login-username','${USER}'); set('#login-password','${PASS}')
      document.querySelector('form button[type=submit]').click(); return true })()`)
    log('已提交登录')
  } else {
    die('既非首启注册页也非登录页 —— 界面未按预期启动')
  }

  if (!(await waitFor(`location.hash.includes('/app/')`, 60, '进入工作台'))) {
    die(`未进入工作台（#/app/*）——数据库或 IPC 初始化失败\n--- 应用输出 ---\n${appLog.slice(-2000)}`)
  }

  const statusBar = await ev(`document.querySelector('.statusbar')?.innerText?.replace(/\\s+/g,' ').trim() ?? null`)
  log(`状态栏：${JSON.stringify(statusBar)}`)
  if (!statusBar) die('未找到状态栏元素')
  if (!statusBar.includes(`v${version}`)) {
    die(`状态栏版本与期望不符：期望包含 v${version}，实际 ${JSON.stringify(statusBar)}`)
  }

  // 原生模块 ABI 事故的特征串——出现即判定失败（双保险）
  if (/NODE_MODULE_VERSION|was compiled against a different Node\.js version/.test(appLog)) {
    die(`应用日志出现原生模块 ABI 错误：\n${appLog.slice(-1500)}`)
  }

  log(`✓ 产物可运行性门禁通过（状态栏含 v${version}）`)
  cdp.close()
  cleanup()
  process.exit(0)
} catch (e) {
  cleanup()
  die(`${e instanceof Error ? e.message : String(e)}\n--- 应用输出 ---\n${appLog.slice(-2000)}`)
}
