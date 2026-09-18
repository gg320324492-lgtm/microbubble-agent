#!/usr/bin/env node
// 桌面端发布脚本（M6-2）— 本地与 CI 共用同一套步骤，消灭手工补 latest.yml。
//
// 用法:
//   node scripts/release.mjs                 # 全流程：clean → gates → package → latest → verify
//   node scripts/release.mjs clean           # 分批清理 out/（绕开本地沙箱批量删除阈值）
//   node scripts/release.mjs gates           # test + typecheck + build
//   node scripts/release.mjs package         # electron-builder -p never（禁止自行上传）
//   node scripts/release.mjs latest          # 生成并校验 latest.yml
//   node scripts/release.mjs verify          # 版本同步 + 三件套一致性自验
//
// 说明：out/ 分批清理仅本地需要（沙箱对单次 rmSync 有 50 文件阈值）；CI 无此限制但共用同一脚本。
import { createHash } from 'node:crypto'
import { createReadStream, existsSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
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
function stepNative() {
  const require = createRequire(import.meta.url)
  const electronVersion = JSON.parse(readFileSync(require.resolve('electron/package.json'), 'utf8')).version
  const bsqPkgPath = require.resolve('better-sqlite3/package.json')
  const bsqDir = dirname(bsqPkgPath)
  const binary = join(bsqDir, 'build', 'Release', 'better_sqlite3.node')

  const bsqRequire = createRequire(join(bsqDir, 'package.json'))
  const prebuildBin = join(dirname(bsqRequire.resolve('prebuild-install/package.json')), 'bin.js')

  // 探测必须在**子进程**里做：在当前进程 require(.node) 会持有文件句柄，
  // 随后 prebuild-install 覆盖同一文件会 EBUSY（CI 实测踩到）。
  const probe = () => {
    const r = spawnSync(process.execPath, ['-e', `require(${JSON.stringify(binary)})`], { encoding: 'utf8' })
    return { ok: r.status === 0, error: `${r.stderr ?? ''}${r.stdout ?? ''}` }
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
  if (after !== 'electron') die(`原生模块 ABI 仍不是 Electron（${after}）——拒绝发布`)
  log('原生模块已对齐 Electron ABI')
}

/** 打包（-p never：发布由 gh/CI 显式完成，禁止 electron-builder 自行上传） */
function stepPackage() {
  run('npx', ['electron-builder', '--win', 'nsis', '-c.npmRebuild=false', '-p', 'never'])
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
  const yml = buildLatestYml({ version, fileName: names.exe, sha512, size })
  writeFileSync(join(RELEASE_DIR, names.latestYml), yml)
  log(`latest.yml 已生成：version=${version} size=${size}`)
  const check = verifyLatestYml(yml, { version, fileName: names.exe, sha512, size })
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

const STEPS = { clean: stepClean, native: stepNative, gates: stepGates, package: stepPackage, latest: stepLatest, verify: stepVerify }
const ORDER = ['clean', 'native', 'gates', 'package', 'latest', 'verify']

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
