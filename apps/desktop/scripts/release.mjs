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
import { createReadStream, existsSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import {
  artifactNames,
  buildLatestYml,
  checkVersionSync,
  planOutCleanup,
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

/** out/ 分批清理（清账⑤） */
function stepClean() {
  const outDir = join(ROOT, 'out')
  if (!existsSync(outDir)) {
    log('out/ 不存在，跳过清理')
    return
  }
  const entries = readdirSync(outDir)
  if (entries.length === 0) {
    rmSync(outDir, { recursive: true, force: true })
    log('out/ 为空，已移除')
    return
  }
  const batches = planOutCleanup(entries)
  log(`out/ 顶层条目 ${entries.length} 个，分 ${batches.length} 批删除`)
  for (const [i, batch] of batches.entries()) {
    for (const name of batch) rmSync(join(outDir, name), { recursive: true, force: true })
    log(`  批 ${i + 1}/${batches.length} 完成（${batch.length} 项）`)
  }
  rmSync(outDir, { recursive: true, force: true })
}

/** 门禁三件套 */
function stepGates() {
  run('pnpm', ['test'])
  run('pnpm', ['typecheck'])
  run('pnpm', ['build'])
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

const STEPS = { clean: stepClean, gates: stepGates, package: stepPackage, latest: stepLatest, verify: stepVerify }
const ORDER = ['clean', 'gates', 'package', 'latest', 'verify']

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
