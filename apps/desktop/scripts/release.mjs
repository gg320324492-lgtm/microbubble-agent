#!/usr/bin/env node
// 桌面端发布脚本（M6-2）— 本地与 CI 共用同一套步骤，消灭手工补 latest.yml。
//
// 用法:
//   node scripts/release.mjs                 # 全流程：version → clean → native → gates → package → smoke → latest → verify
//   node scripts/release.mjs version         # 版本两处同步校验（package.json ↔ constants.ts）
//   node scripts/release.mjs clean           # 分批清理 out/（绕开本地沙箱批量删除阈值）
//   node scripts/release.mjs gates           # test + typecheck + build
//   node scripts/release.mjs package         # electron-builder -p never（禁止自行上传）
//   node scripts/release.mjs smoke           # 产物可运行性门禁（启动产物 + CDP 断言状态栏版本）
//   node scripts/release.mjs latest          # 生成并校验 latest.yml
//   node scripts/release.mjs verify          # 版本同步 + 三件套一致性自验
//
// 说明：out/ 分批清理仅本地需要（沙箱对单次 rmSync 有 50 文件阈值）；CI 无此限制但共用同一脚本。
import { createHash } from 'node:crypto'
import { copyFileSync, createReadStream, existsSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { cleanOutDir } from './lib/clean-out.mjs'
import {
  artifactNames,
  buildLatestYml,
  checkVersionSync,
  classifyNativeAbi,
  electronTarget,
  extractChangelogSection,
  verifyLatestYml
} from './lib/release-utils.mjs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const RELEASE_DIR = join(ROOT, 'release')

const log = (msg) => console.log(`[release] ${msg}`)
const die = (msg) => {
  console.error(`[release][FATAL] ${msg}`)
  process.exit(1)
}

function run(cmd, args, opts = {}) {
  log(`$ ${cmd} ${args.join(' ')}`)
  const res = spawnSync(cmd, args, { cwd: ROOT, stdio: 'inherit', shell: process.platform === 'win32', ...opts })
  if (res.status !== 0) die(`命令失败（exit ${res.status}）：${cmd} ${args.join(' ')}`)
}

// ---------- 版本读取 ----------

function readVersions() {
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'))
  const constantsSource = readFileSync(join(ROOT, 'src/shared/constants.ts'), 'utf8')
  return { pkgVersion: pkg.version, constantsSource }
}

/** 版本两处同步校验（R-1 类翻车防线） */
function assertVersionSync() {
  const { pkgVersion, constantsSource } = readVersions()
  const res = checkVersionSync({ pkgVersion, constantsSource })
  if (!res.ok) die(res.reason)
  log(`版本同步 OK：${res.version}`)
  return res.version
}

// ---------- 步骤 ----------

/** 递归收集文件路径（不含目录） */
/**
 * out/ 分批清理（清账⑤）— 实现见 lib/clean-out.mjs（守卫友好分批 + 回退）。
 */
function stepClean() {
  cleanOutDir(join(ROOT, 'out'), log)
}

/**
 * 版本同步一致性门禁（M7 随车必办③）— package.json ↔ src/shared/constants.ts。
 * 放最前面：版本不一致是最廉价的失败，不该等到打包完才发现（R-1 类翻车防线）。
 */
function stepVersion() {
  assertVersionSync()
}

/** 门禁三件套 */
function stepGates() {
  run('pnpm', ['test'])
  run('pnpm', ['typecheck'])
  run('pnpm', ['build'])
}

/**
 * 原生依赖 ABI 对齐（M6-2 修复）— 打包前必须保证 .node 是 Electron ABI。
 *
 * 背景：`better-sqlite3` 是原生模块。CI 全新 `pnpm install` 会装到 **Node ABI(127)** 预编译包，
 * 而 Electron 32 需要 **NODE_MODULE_VERSION 128**；若直接打包，应用启动即
 * "was compiled against a different Node.js version" 崩溃（v0.1.5-alpha 首航实测踩到）。
 * 本地 node_modules 恰已是 128 所以长期未暴露。
 *
 * 这里用 prebuild-install 拉 Electron 预编译包（**无需 VS 工具链**，CI/本地一致）；
 * 若拉取失败则直接终止发布——绝不产出 ABI 不匹配的安装包。
 */
async function stepNative() {
  const require = createRequire(import.meta.url)
  const electronVersion = JSON.parse(readFileSync(require.resolve('electron/package.json'), 'utf8')).version
  const bsqPkgPath = require.resolve('better-sqlite3/package.json')
  const bsqDir = dirname(bsqPkgPath)
  const binary = join(bsqDir, 'build', 'Release', 'better_sqlite3.node')

  const bsqRequire = createRequire(join(bsqDir, 'package.json'))
  const prebuildBin = join(dirname(bsqRequire.resolve('prebuild-install/package.json')), 'bin.js')

  // 探测必须在**子进程**里做：在当前进程 require(.node) 会持有文件句柄，
  // 随后 prebuild-install 覆盖同一文件会 EBUSY（CI 实测踩到）。
  //
  // ★ 用**临时脚本文件**而不是 `node -e`：本机实测 `-e` 形式下子进程可能被环境
  //   静默终止（status=null、stderr/stdout 均为空）→ 探测得空串 → 误判 `unknown`
  //   → 发布被错误拒绝。文件式探测在同一环境下稳定返回真实错误文本。
  //   两种形式都不改写在探测失败时的行为：拿不到有效信息仍按 unknown 处理。
  const probe = () => {
    const probeFile = join(tmpdir(), `mnb-abi-probe-${process.pid}.cjs`)
    try {
      writeFileSync(
        probeFile,
        // ★ catch 路径必须 process.exit(1)：否则 require 失败也被吞成正常退出（status 0），
        //   探针恒判 'node'（v1.3.0-ci.1~ci.7 连环红跑的真凶——343a7bf27 引入的回归）
        `try { require(${JSON.stringify(binary)}); console.log('NODE_ABI_OK') } catch (e) { console.error(String(e && e.message || e)); process.exit(1) }\n`
      )
      const r = spawnSync(process.execPath, [probeFile], { encoding: 'utf8' })
      const text = `${r.stderr ?? ''}${r.stdout ?? ''}`
      // 子进程被信号终止（status=null）或毫无输出 ⇒ 探测不可信，明确标记
      if (r.status === null || text.trim() === '') {
        return { ok: false, error: '', inconclusive: true }
      }
      return { ok: r.status === 0, error: text }
    } finally {
      try {
        rmSync(probeFile, { force: true })
      } catch {
        /* 清理失败不影响判定 */
      }
    }
  }

  const before = classifyNativeAbi(probe())
  log(`原生模块 ABI 探测：${before}（Electron ${electronVersion} 需要 128）`)
  if (before === 'electron') {
    log('已是 Electron ABI，跳过')
    return
  }

  log('拉取 Electron 预编译包（无需 VS 工具链）…')
  run('node', [prebuildBin, '--runtime=electron', `--target=${electronTarget(electronVersion)}`, '--arch=x64'], {
    cwd: bsqDir
  })

  const after = classifyNativeAbi(probe())
  if (after !== 'electron') {
    // CI 2026-09-28 实测：prebuild-install 可能 exit 0、零输出、且不替换二进制（静默空转）。
    // 兜底一：显式下载官方 electron 预编译包并替换，每一步硬失败——绝不静默。
    log(`prebuild-install 通道未生效（ABI 仍 ${after}），走直连下载兜底…`)
    await prebuiltDirectFetch(electronVersion, bsqDir, binary)
  }
  if (classifyNativeAbi(probe()) !== 'electron') {
    // 兜底二（终极）：CI 2026-09-28 实测上游 better-sqlite3 v12.11.1 的 electron-v128 资产内容
    // 被污染为 node-ABI 构建（解包哈希=node 预编译哈希）。预编译资产不可信时，
    // 用 Electron 官方头文件本地编译——CI (windows-2022) 自带 MSVC + Python，确定性达成 ABI。
    log('直连兜底未达成 Electron ABI（上游资产疑似污染），用 Electron 头文件本地编译…')
    // node-gyp@12：runner 镜像已升 VS 18（2026），9.4.1 报 unknown version "undefined"
    run('npx', ['node-gyp@12.1.0', 'rebuild', '--runtime=electron', `--target=${electronTarget(electronVersion)}`, '--arch=x64', '--dist-url=https://electronjs.org/headers'], {
      cwd: bsqDir
    })
  }
  const final = classifyNativeAbi(probe())
  if (final !== 'electron') {
    // 终极诊断：路径、实体、哈希、探针原始输出全量回显（CI 2026-09-28 系列实测定案用）
    const hashOf = (p) => { try { return createHash('sha256').update(readFileSync(p)).digest('hex').slice(0, 16) } catch (e) { return 'ERR:' + e.message } }
    let realPath = '', symlink = ''
    try { realPath = realpathSync(binary); symlink = realPath === binary ? 'realpath=same' : 'REALPATH-DIFFERS' } catch (e) { realPath = 'ERR:' + e.message }
    const p2 = probe()
    die([
      `原生模块 ABI 仍不是 Electron（${final}）——拒绝发布。终极诊断：`,
      `  target : ${binary}`,
      `  realpath: ${realPath}（${symlink}）`,
      `  sha256  : ${hashOf(binary)} | size: ${statSync(binary).size}`,
      `  复测探针: status=${p2.ok ? '0(require成功)' : '非0'} raw=${JSON.stringify((p2.error || '').slice(0, 200))}`
    ].join('\n'))
  }
  log('原生模块已对齐 Electron ABI')
}

/**
 * 直连兜底：从 better-sqlite3 官方 GitHub Release 下载 electron 预编译包，解包替换二进制。
 * Electron 主版本 → NODE_MODULE_VERSION 映射在此固化；升 Electron 时必须同步本表，
 * 脚本会在未知主版本上硬失败并提示（绝不猜）。
 */
const ELECTRON_MODULE_VERSIONS = { 32: 128 }

async function prebuiltDirectFetch(electronVersion, bsqDir, binary) {
  const major = Number(String(electronVersion).split('.')[0])
  const abi = ELECTRON_MODULE_VERSIONS[major]
  if (!abi) die(`直连兜底缺 Electron ${major} 的 ABI 映射——请在 release.mjs ELECTRON_MODULE_VERSIONS 补表后重试`)
  const bsqVersion = JSON.parse(readFileSync(join(bsqDir, 'package.json'), 'utf8')).version
  const url = `https://github.com/WiseLibs/better-sqlite3/releases/download/v${bsqVersion}/better-sqlite3-v${bsqVersion}-electron-v${abi}-win32-x64.tar.gz`
  log(`直连下载：${url}`)
  let res
  try {
    res = await fetch(url, { redirect: 'follow' })
  } catch (e) {
    die(`直连下载网络失败：${String(e && e.cause ? e.cause.code || e.cause : e)} —— ${url}`)
  }
  if (!res.ok) die(`直连下载失败 HTTP ${res.status}：${url}`)
  const tgz = Buffer.from(await res.arrayBuffer())
  if (tgz.length < 100_000) die(`直连下载体积异常（${tgz.length} B），疑似损坏：${url}`)
  const dir = mkdtempSync(join(tmpdir(), 'mnb-prebuilt-'))
  writeFileSync(join(dir, 'prebuilt.tar.gz'), tgz)
  // 相对路径 + cwd：GNU tar 会把「C:\」当作远程主机名（force-local 不可移植），bsdtar 无此问题
  const r = spawnSync('tar', ['-xzf', 'prebuilt.tar.gz', '-C', '.', 'build/Release/better_sqlite3.node'], { cwd: dir, encoding: 'utf8' })
  if (r.status !== 0) die(`tar 解包失败（exit ${r.status}）：${r.stderr ?? ''}`)
  const extracted = join(dir, 'build', 'Release', 'better_sqlite3.node')
  if (!existsSync(extracted)) die(`解包产物缺失：${extracted}`)
  // 先 unlink 断开 pnpm 硬链接再写入——直写硬链接会穿透到内容寻址存储（该文件可能被锁/只读）
  try {
    rmSync(binary, { force: true })
  } catch (e) {
    die(`删除旧二进制失败（疑似被占用）：${String(e && e.message || e)}`)
  }
  copyFileSync(extracted, binary)
  const hash = (p) => createHash('sha256').update(readFileSync(p)).digest('hex').slice(0, 16)
  log(`诊断：extracted=${statSync(extracted).size}B/${hash(extracted)} target=${statSync(binary).size}B/${hash(binary)}（两者应为同值）`)
  rmSync(dir, { recursive: true, force: true })
  log(`已替换二进制（${tgz.length} B ← better-sqlite3 v${bsqVersion} electron-v${abi}）`)
}

/** 打包（-p never：发布由 gh/CI 显式完成，禁止 electron-builder 自行上传） */
function stepPackage() {
  run('npx', ['electron-builder', '--win', 'nsis', '-c.npmRebuild=false', '-p', 'never'])
}

/**
 * 产物可运行性门禁（M7 随车必办②）— 静默启动打包产物 + CDP 断言状态栏版本号。
 * 放在 latest/verify 之前：产物跑不起来就没有必要生成更新信息、更不该发布。
 * 覆盖：主进程 → 原生模块（Electron ABI）→ IPC → 渲染进程 → 版本一致性。
 */
function stepSmoke() {
  run('node', [join(ROOT, 'scripts', 'smoke-package.mjs')])
}

function sha512Base64(file) {
  return new Promise((res, rej) => {
    const h = createHash('sha512')
    createReadStream(file)
      .on('data', (c) => h.update(c))
      .on('end', () => res(h.digest('base64')))
      .on('error', rej)
  })
}

/** 生成 latest.yml（清账①）— 以实际产物为准计算 sha512/size */
async function stepLatest() {
  const version = assertVersionSync()
  const names = artifactNames(version)
  const exePath = join(RELEASE_DIR, names.exe)
  if (!existsSync(exePath)) die(`未找到安装包：${exePath}（请先执行 package）`)
  const sha512 = await sha512Base64(exePath)
  const size = statSync(exePath).size
  // DL-7 Part A：CHANGELOG 对应版本段落注入 releaseNotes（应用内更新弹窗的日志正文，
  // 经国内 CDN 直达，不依赖 GitHub Release notes）。命中/未命中都必须显式留痕。
  const changelogPath = join(ROOT, 'CHANGELOG.md')
  let releaseNotes = null
  if (existsSync(changelogPath)) {
    releaseNotes = extractChangelogSection(readFileSync(changelogPath, 'utf8'), `v${version}`)
    if (releaseNotes) log(`更新日志命中：CHANGELOG v${version} 段落 ${releaseNotes.length} 字符`)
    else log(`[warn] CHANGELOG.md 未找到 v${version} 段落，latest.yml 不含 releaseNotes（发布前请补齐章节）`)
  } else {
    log(`[warn] 未找到 ${changelogPath}，latest.yml 不含 releaseNotes`)
  }
  const yml = buildLatestYml({ version, fileName: names.exe, sha512, size }, releaseNotes)
  writeFileSync(join(RELEASE_DIR, names.latestYml), yml)
  log(`latest.yml 已生成：version=${version} size=${size}${releaseNotes ? ` releaseNotes=${releaseNotes.length} 字符` : '（无更新日志）'}`)
  const check = verifyLatestYml(yml, { version, fileName: names.exe, sha512, size, ...(releaseNotes ? { releaseNotes } : {}) })
  if (!check.ok) die(`latest.yml 自校验失败：\n  ${check.issues.join('\n  ')}`)
  log('latest.yml 自校验通过')
}

/** 三件套一致性自验 */
async function stepVerify() {
  const version = assertVersionSync()
  const names = artifactNames(version)
  const exePath = join(RELEASE_DIR, names.exe)
  const blockmapPath = join(RELEASE_DIR, names.blockmap)
  const ymlPath = join(RELEASE_DIR, names.latestYml)
  for (const p of [exePath, blockmapPath, ymlPath]) {
    if (!existsSync(p)) die(`三件套缺失：${p}`)
  }
  const sha512 = await sha512Base64(exePath)
  const size = statSync(exePath).size
  const check = verifyLatestYml(readFileSync(ymlPath, 'utf8'), { version, fileName: names.exe, sha512, size })
  if (!check.ok) die(`三件套一致性失败：\n  ${check.issues.join('\n  ')}`)
  log(`三件套一致性 OK：${names.exe} (${size} B) / ${names.blockmap} / ${names.latestYml}`)
}

// ---------- 入口 ----------

const STEPS = {
  version: stepVersion,
  clean: stepClean,
  native: stepNative,
  gates: stepGates,
  package: stepPackage,
  smoke: stepSmoke,
  latest: stepLatest,
  verify: stepVerify
}
const ORDER = ['version', 'clean', 'native', 'gates', 'package', 'smoke', 'latest', 'verify']

const args = process.argv.slice(2).filter((a) => !a.startsWith('-'))
const selected = args.length ? args : ORDER
for (const name of selected) {
  if (!STEPS[name]) die(`未知步骤：${name}（可选：${ORDER.join(' / ')}）`)
}

for (const name of selected) {
  log(`===== ${name} =====`)
  await STEPS[name]()
}
log('全部完成')
