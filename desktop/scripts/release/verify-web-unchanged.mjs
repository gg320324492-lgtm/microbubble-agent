#!/usr/bin/env node
// verify-web-unchanged.mjs — R0 zero-impact release guard
//
// Rejects any change-set that touches the protected paths of the web/system
// stack. The protected list is part of the formal release program
// (docs/superpowers/plans/2026-08-26-desktop-formal-release-program.md)
// and is intentionally hard-coded here so the guard fails closed if anyone
// edits the project context to remove entries.
//
// Exit codes:
//   0 — all changed files are outside the protected set AND baseline tree
//       IDs match HEAD for every protected path
//   1 — at least one changed file is in the protected set, OR a protected
//       path's tree ID no longer matches the recorded baseline
//   2 — the baseline file is missing or malformed (cannot make a decision)
//
// CLI:
//   verify-web-unchanged.mjs [--changed=<p1,p2,...>] [--baseline=<path>] [--refresh-baseline]
//
//   --changed=<paths>       Comma-separated change list. If omitted, the
//                           script reads from `git diff --name-only HEAD`.
//   --baseline=<path>       Path to the baseline JSON. Defaults to
//                           desktop/resources/release-protected-baseline.json
//                           relative to the script's repo root.
//   --refresh-baseline     Rewrite the baseline file from the current HEAD
//                           tree IDs and exit 0. Used by `npm run release:baseline`.

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve, isAbsolute } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

// Repo root is detected at runtime from the calling cwd via `git rev-parse
// --show-toplevel`. This lets the guard work both in the real project and
// from a temporary fixture repo in tests.
function detectRepoRoot(cwd) {
  try {
    return execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd, encoding: 'utf8' }).trim()
  } catch {
    throw new Error('[release-guard] not inside a git working tree (cwd=' + cwd + ')')
  }
}

// The baseline lives at desktop/resources/release-protected-baseline.json
// inside the repo. Computed after the repo root is known.
function defaultBaselinePath(repoRoot) {
  return resolve(repoRoot, 'desktop', 'resources', 'release-protected-baseline.json')
}

// Protected paths. The web stack is the single source of truth for these;
// any change is a release-blocking event.
const PROTECTED_DIRS = ['app', 'web', 'alembic', 'nginx']
const PROTECTED_GLOBS_FILE = ['.env']

function parseArgs(argv) {
  // baseline=null means "use defaultBaselinePath(repoRoot)" — resolved in main().
  const out = { changed: null, baseline: null, refreshBaseline: false }
  for (const arg of argv.slice(2)) {
    if (arg.startsWith('--changed=')) {
      out.changed = arg.slice('--changed='.length).split(',').map((s) => s.trim()).filter(Boolean)
    } else if (arg.startsWith('--baseline=')) {
      out.baseline = arg.slice('--baseline='.length)
    } else if (arg === '--refresh-baseline') {
      out.refreshBaseline = true
    }
  }
  return out
}

function git(args, cwd) {
  return execFileSync('git', args, { cwd, encoding: 'utf8' })
}

function gitHead(cwd) {
  return git(['rev-parse', 'HEAD'], cwd).trim()
}

function gitLsTreeHead(pathSpec, cwd) {
  // Returns the tree/blob hash for the path at HEAD, or null if not present.
  const out = git(['ls-tree', 'HEAD', pathSpec], cwd).trim()
  if (!out) return null
  // Format: "<mode> <type> <hash>\t<name>"
  const parts = out.split(/\s+/)
  if (parts.length < 3) return null
  return { type: parts[1], hash: parts[2] }
}

function gitDiffNameOnly(cwd) {
  return git(['diff', '--name-only', 'HEAD'], cwd)
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
}

function isDockerComposeFile(name) {
  return /^docker-compose(..+)?\.yml$/.test(name) || name === 'docker-compose.yml'
}

function isProtectedPath(file) {
  // Normalize backslashes for matching (Windows-friendly).
  const f = file.replace(/\\/g, '/')
  for (const dir of PROTECTED_DIRS) {
    if (f === dir || f.startsWith(dir + '/')) return dir
  }
  for (const exact of PROTECTED_GLOBS_FILE) {
    if (f === exact) return exact
  }
  const base = f.split('/').pop()
  if (base && isDockerComposeFile(base)) return 'docker-compose'
  return null
}

function loadBaseline(path) {
  if (!existsSync(path)) {
    return { ok: false, reason: 'missing', path }
  }
  let raw
  try {
    raw = readFileSync(path, 'utf8')
  } catch (err) {
    return { ok: false, reason: 'unreadable', path, err }
  }
  try {
    const data = JSON.parse(raw)
    if (!data || typeof data !== 'object' || !data.protectedPaths) {
      return { ok: false, reason: 'malformed', path }
    }
    return { ok: true, data }
  } catch (err) {
    return { ok: false, reason: 'malformed', path, err }
  }
}

function resolveBaselineAbs(baselineArg, cwd) {
  return isAbsolute(baselineArg) ? baselineArg : resolve(cwd, baselineArg)
}

function collectChangedFiles(args, cwd) {
  if (args.changed !== null) return args.changed
  return gitDiffNameOnly(cwd)
}

function checkChangedFiles(changed) {
  const offenders = []
  for (const f of changed) {
    const tag = isProtectedPath(f)
    if (tag) offenders.push({ path: f, reason: tag })
  }
  return offenders
}

function checkBaselineTrees(baseline, cwd) {
  // For each entry in baseline.protectedPaths, compare the recorded hash with
  // `git ls-tree HEAD <path>`. A mismatch means the protected area moved since
  // the baseline was captured — that is itself a release-blocking event.
  const mismatches = []
  for (const [path, expected] of Object.entries(baseline.protectedPaths)) {
    const actual = gitLsTreeHead(path, cwd)
    if (!actual) {
      mismatches.push({ path, expected, actual: null, reason: 'missing-at-HEAD' })
      continue
    }
    if (actual.hash !== expected) {
      mismatches.push({ path, expected, actual: actual.hash, reason: 'tree-id-changed' })
    }
  }
  return mismatches
}

function writeBaseline(path, captured) {
  writeFileSync(path, JSON.stringify(captured, null, 2) + '\n', 'utf8')
}

function captureBaseline(cwd) {
  const captured = {
    capturedAt: new Date().toISOString(),
    capturedBy: 'R0 baseline (refresh)',
    capturedCommit: gitHead(cwd),
    protectedPaths: {}
  }
  for (const p of [...PROTECTED_DIRS, 'docker-compose.yml', 'docker-compose.dev.yml', 'docker-compose.test.yml', 'docker-compose.prod.yml', '.env']) {
    const entry = gitLsTreeHead(p, cwd)
    if (entry) captured.protectedPaths[p] = entry.hash
  }
  return captured
}

function main() {
  const args = parseArgs(process.argv)
  const cwd = detectRepoRoot(process.cwd())
  const baselinePath = args.baseline
    ? resolveBaselineAbs(args.baseline, cwd)
    : defaultBaselinePath(cwd)

  if (args.refreshBaseline) {
    try {
      const captured = captureBaseline(cwd)
      writeBaseline(baselinePath, captured)
      process.stdout.write(`[release-guard] baseline refreshed at ${baselinePath}\n`)
      process.exit(0)
    } catch (err) {
      process.stderr.write(`[release-guard] failed to refresh baseline: ${err && err.stack ? err.stack : err}\n`)
      process.exit(2)
    }
  }

  const baselineResult = loadBaseline(baselinePath)
  if (!baselineResult.ok) {
    process.stderr.write(
      `[release-guard] cannot load baseline file '${baselinePath}' (reason=${baselineResult.reason}).\n` +
      'Run \'npm run release:baseline\' to (re)create it.\n'
    )
    process.exit(2)
  }
  const baseline = baselineResult.data

  // 1) Reject any change that touches a protected path.
  const changed = collectChangedFiles(args, cwd)
  const offenders = checkChangedFiles(changed)

  // 2) Reject any drift between baseline tree IDs and current HEAD.
  const mismatches = checkBaselineTrees(baseline, cwd)

  if (offenders.length === 0 && mismatches.length === 0) {
    process.stdout.write(`[release-guard] OK — ${changed.length} changed file(s), none touch the protected web stack.\n`)
    process.exit(0)
  }

  if (offenders.length > 0) {
    const list = offenders.map((o) => `  - ${o.path}  (protected: ${o.reason})`).join('\n')
    process.stderr.write(`[release-guard] 网页端受保护路径发生变更:\n${list}\n`)
  }
  if (mismatches.length > 0) {
    const list = mismatches
      .map((m) => `  - ${m.path}  baseline=${m.expected}  HEAD=${m.actual ?? '<missing>'}  reason=${m.reason}`)
      .join('\n')
    process.stderr.write(`[release-guard] 受保护路径的 git tree ID 已偏离 R0 基线:\n${list}\n`)
  }
  process.exit(1)
}

main()
