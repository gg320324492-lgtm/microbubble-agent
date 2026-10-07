// web/scripts/build-id.mjs — BUILD_ID 单一真源 (类 20.133 / W100 R-5)
//
// 本文件是 SOURCE_INPUTS 清单 + sha256 内容哈希算法的**唯一实现**:
//   - web/vite.config.js  import 本模块, 从**磁盘**派生 BUILD_ID (构建时);
//   - scripts/check-dist-before-commit.sh 用 `node ... --from-index` 从**暂存区**
//     重算 BUILD_ID (pre-commit 两段式硬校验, 2026-10-07 收尾规划 §4.11 遗留③)。
// 严禁在任何其他地方再写一份清单或哈希逻辑 —— 两处各写一份 = 漂移 = 校验形同虚设。
//
// 两种模式只在「文件字节从哪来」上有区别, 排序/过滤/哈希流完全共用:
//   - deriveSourceTreeHash(webRoot)          磁盘字节 (vite 构建路径, 含未提交工作区改动)
//   - deriveSourceTreeHashFromIndex(repo)    git index 字节 (只含已提交/已暂存状态)
// 同一源状态下两种模式必须产出逐字一致的 12 hex (验收 #12, 防漂移实证)。
//
// 算法 (与 R-5 落地时逐字一致, 见 web/vite.config.js 顶部注释):
//   sha256(按相对路径全序排序的 [rel + '\0' + 字节内容 + '\0'] 流) 前 12 hex。
//   dist 永不入清单 (反循环论证见 vite.config.js 顶部)。
//
// CLI (pre-commit 钩子调用, 亦可手动调试):
//   node web/scripts/build-id.mjs --from-index            # 从暂存区重算, stdout 打 12 hex
//   node web/scripts/build-id.mjs --from-disk             # 从磁盘重算 (等价 vite 路径)
//   node web/scripts/build-id.mjs --staged-build-inputs   # 列出暂存区里的构建源输入 (一行一个)
// vite.config.js import 本模块时 process.argv 不含上述 flag, CLI 不会执行。

import { readdirSync, lstatSync, readFileSync } from 'fs'
import { dirname, join, relative, resolve, sep } from 'path'
import { createHash } from 'crypto'
import { execFileSync, execSync } from 'child_process'

// 构建源输入允许清单 (相对 web/)。判据 = 该文件的字节能改变 `npm run build` 产物:
//   - src/ index.html public/            vite 打包图 + 静态拷贝
//   - vite.config.js                     构建配置本体 (define/patch/postcss/manualChunks)
//   - scripts/build-id.mjs               本文件: SOURCE_INPUTS 与哈希算法自身即构建输入
//                                        (vite.config import 它 → 改它会改 BUILD_ID → 改产物)
//   - scripts/postbuild-fix-manifest.js  npm run build 命令链的后半段
//   - package.json / package-lock.json   依赖锁定版本 (npm ci 安装的 node_modules 代理)
// 明确**不**入清单 (别加):
//   - dist/                    自身入库, 入清单即哈希循环 (见 vite.config.js 反循环论证)
//   - src/**/__tests__/, *.test.* / *.spec.* — vitest 用, 不进 build 产物
//   - .stylelintrc.json / .hintrc.json / playwright*.config.js / vitest.config.js /
//     tests/ / tools/ / design-showcase/ / Dockerfile / nginx.conf
//                              lint / 测试 / 部署面, 不参与 build
export const SOURCE_INPUTS = [
  'index.html',
  'package.json',
  'package-lock.json',
  'public',
  'scripts/build-id.mjs',
  'scripts/postbuild-fix-manifest.js',
  'src',
  'vite.config.js',
]

// 源输入里不参与构建产物的路径 (即使它在允许清单目录下):
//   __tests__ / *.test.* / *.spec.*  vitest 用例
//   .DS_Store / Thumbs.db / desktop.ini  编辑器/系统垃圾 (误入会让 ID 随机器漂移)
export function isNonBuildInput(relPath) {
  const segs = relPath.split('/')
  if (segs.includes('__tests__')) return true
  if (/\.(test|spec)\.[cm]?[jt]sx?$/.test(relPath)) return true
  if (segs.some((s) => s === '.DS_Store' || s === 'Thumbs.db' || s === 'desktop.ini')) return true
  return false
}

function collectSourceFiles(absDir, relBase, out) {
  // readdirSync(...).sort(): 默认 UTF-16 码元序, 与 locale 无关 → 跨机器顺序稳定
  for (const name of readdirSync(absDir).sort()) {
    const abs = join(absDir, name)
    const rel = relBase ? `${relBase}/${name}` : name
    if (isNonBuildInput(rel)) continue
    const st = lstatSync(abs)
    if (st.isDirectory()) collectSourceFiles(abs, rel, out)
    else if (st.isFile()) out.push({ rel, abs })  // 符号链接跳过 (Windows/本仓库无)
  }
}

// 最终按相对路径全序排序 (码元比较, 不用 localeCompare —— locale 依赖排序不稳定)
function sortByRel(a, b) {
  return a.rel < b.rel ? -1 : a.rel > b.rel ? 1 : 0
}

// 内容指纹: sha256(排序后的 [rel + '\0' + bytes + '\0'] 流) 前 12 hex。
// 只读 SOURCE_INPUTS, 不碰 dist → 与 dist 提交次数、与 HEAD 全部解耦。
function hashEntries(entries) {
  entries.sort(sortByRel)
  if (entries.length === 0) {
    throw new Error('[vite] 构建源输入清单收集到 0 个文件 — fail-loud (类 20.133)')
  }
  const hash = createHash('sha256')
  for (const { rel, bytes } of entries) {
    hash.update(rel, 'utf8')
    hash.update('\0')
    hash.update(bytes)
    hash.update('\0')
  }
  return hash.digest('hex').slice(0, 12)
}

// ---- 模式 1: 磁盘 (vite 构建路径, 原 deriveSourceTreeHash 逐字迁移) ----
export function deriveSourceTreeHash(webRoot) {
  const files = []
  for (const input of SOURCE_INPUTS) {
    const abs = join(webRoot, input)
    let st
    try {
      st = lstatSync(abs)
    } catch {
      throw new Error(`[vite] 构建源输入缺失: web/${input} — 源输入清单与仓库不符, fail-loud (类 20.133)`)
    }
    if (st.isDirectory()) collectSourceFiles(abs, input, files)
    else if (st.isFile()) files.push({ rel: input, abs })
  }
  return hashEntries(files.map(({ rel, abs }) => ({ rel, bytes: readFileSync(abs) })))
}

// ---- 模式 2: git 暂存区 (pre-commit 两段式校验路径) ----
// 字节来源 = index (git add 后 / commit 内容), 不看工作树:
//   - 源已提交 + dist 待提交 → 重算值即「已提交源」的指纹 → 与 dist 内嵌 id 比对 (规则 2);
//   - 工作树里未暂存的改动不影响重算 → 不会把「没进这次 commit 的东西」算进来。
export function deriveSourceTreeHashFromIndex(repoRoot) {
  const webRoot = join(repoRoot, 'web')
  const webPrefix = relative(repoRoot, webRoot).split(sep).join('/')
  const pathspecs = SOURCE_INPUTS.map((i) => `${webPrefix}/${i}`)

  // ls-files -s -z: "<mode> <oid> <stage>\t<path>\0" — oid 一次拿齐 (避免逐文件 spawn)
  const lsOut = execFileSync('git', ['ls-files', '-s', '-z', '--', ...pathspecs], {
    cwd: repoRoot,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  })
  const entries = []
  for (const rec of lsOut.split('\0')) {
    if (!rec) continue
    const tab = rec.indexOf('\t')
    const meta = rec.slice(0, tab).split(' ')
    const stage = meta[2]
    const path = rec.slice(tab + 1)
    if (stage !== '0') {
      throw new Error(
        `[build-id] index 存在未解决冲突条目 (stage ${stage}): ${path} — fail-loud, 请先解决合并冲突再提交 (类 20.133)`
      )
    }
    const rel = path.startsWith(`${webPrefix}/`) ? path.slice(webPrefix.length + 1) : path
    if (isNonBuildInput(rel)) continue
    entries.push({ rel, oid: meta[1] })
  }
  if (entries.length === 0) {
    throw new Error('[build-id] 暂存区未找到任何构建源输入 — fail-loud (类 20.133)')
  }
  entries.sort(sortByRel)

  // cat-file --batch: 一次进程读全部 blob (逐文件 git show = 数百次 spawn, 钩子 2s 预算扛不住)
  const stdin = entries.map((e) => e.oid).join('\n') + '\n'
  const out = execFileSync('git', ['cat-file', '--batch'], {
    cwd: repoRoot,
    input: stdin,
    maxBuffer: 256 * 1024 * 1024,
    windowsHide: true,
  })
  const files = []
  let off = 0
  for (const e of entries) {
    const nl = out.indexOf(0x0a, off)
    if (nl < 0) throw new Error('[build-id] cat-file --batch 输出解析失败 — fail-loud (类 20.133)')
    const header = out.toString('utf8', off, nl)
    const size = parseInt(header.split(' ')[2], 10)
    if (!Number.isFinite(size)) throw new Error(`[build-id] cat-file 头异常: ${header}`)
    const start = nl + 1
    files.push({ rel: e.rel, bytes: out.subarray(start, start + size) })
    off = start + size + 1  // 内容后的换行符
  }
  return hashEntries(files)
}

// ---- 模式 3: 暂存区里的「构建源输入」清单 (规则 1 禁原子 src+dist 用) ----
// 判据与哈希同源: git pathspec 由 SOURCE_INPUTS 生成, 再过 isNonBuildInput 过滤。
// 返回 repo-root 相对路径数组 (含删除项 — 删源文件 + 提 dist 同样是原子违规)。
export function stagedBuildInputs(repoRoot) {
  const webRoot = join(repoRoot, 'web')
  const webPrefix = relative(repoRoot, webRoot).split(sep).join('/')
  const pathspecs = SOURCE_INPUTS.map((i) => `${webPrefix}/${i}`)
  const out = execFileSync(
    'git',
    ['diff', '--cached', '--name-only', '-z', '--', ...pathspecs],
    { cwd: repoRoot, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }
  )
  const inputs = []
  for (const p of out.split('\0')) {
    if (!p) continue
    const rel = p.startsWith(`${webPrefix}/`) ? p.slice(webPrefix.length + 1) : p
    if (isNonBuildInput(rel)) continue
    inputs.push(p)
  }
  return inputs.sort()
}

// ============================ CLI ============================
const ARGS = process.argv.slice(2)
const IS_CLI =
  ARGS.includes('--from-index') ||
  ARGS.includes('--from-disk') ||
  ARGS.includes('--staged-build-inputs')

if (IS_CLI) {
  try {
    const scriptPath = resolve(process.argv[1])
    const webRoot = dirname(dirname(scriptPath))  // web/scripts/build-id.mjs → web/
    const repoRoot = execSync('git rev-parse --show-toplevel', {
      cwd: webRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim()

    if (ARGS.includes('--staged-build-inputs')) {
      for (const p of stagedBuildInputs(repoRoot)) process.stdout.write(`${p}\n`)
    } else if (ARGS.includes('--from-index')) {
      process.stdout.write(`${deriveSourceTreeHashFromIndex(repoRoot)}\n`)
    } else {
      process.stdout.write(`${deriveSourceTreeHash(webRoot)}\n`)
    }
    process.exit(0)
  } catch (err) {
    process.stderr.write(`${err && err.message ? err.message : String(err)}\n`)
    process.exit(1)
  }
}
