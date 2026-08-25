#!/usr/bin/env node
// write-build-metadata.mjs — R0 reproducible build metadata
//
// Writes desktop/resources/build-metadata.json after electron-vite build.
// Captures git commit + tree, package version, ISO timestamp, and SHA-256
// fingerprints of every artifact under desktop/out/ so a release can later be
// reproduced from this single JSON.
//
// CLI:
//   write-build-metadata.mjs [--out=<path>] [--electron-builder=<true|false>] [--artifacts-dir=<path>]
//
//   --out=<path>                Defaults to resources/build-metadata.json
//                               relative to the script's repo root.
//   --electron-builder=<bool>   Defaults to false. Set true when invoked from
//                               build:release-win so the JSON records that
//                               the installer was produced.
//   --artifacts-dir=<path>      Defaults to desktop/out/. Pass an explicit
//                               path when packaging from a different directory.

import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { dirname, extname, isAbsolute, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolve(__dirname, '..', '..', '..')
const DEFAULT_OUT = resolve(REPO_ROOT, 'desktop', 'resources', 'build-metadata.json')
const DEFAULT_ARTIFACTS = resolve(REPO_ROOT, 'desktop', 'out')
const PACKAGE_JSON = resolve(REPO_ROOT, 'desktop', 'package.json')

function parseArgs(argv) {
  const out = {
    out: DEFAULT_OUT,
    electronBuilder: false,
    artifactsDir: DEFAULT_ARTIFACTS
  }
  for (const arg of argv.slice(2)) {
    if (arg.startsWith('--out=')) {
      out.out = arg.slice('--out='.length)
    } else if (arg.startsWith('--electron-builder=')) {
      out.electronBuilder = arg.slice('--electron-builder='.length) === 'true'
    } else if (arg.startsWith('--artifacts-dir=')) {
      out.artifactsDir = arg.slice('--artifacts-dir='.length)
    }
  }
  return out
}

function gitHead(cwd) {
  return execFileSync('git', ['rev-parse', 'HEAD'], { cwd, encoding: 'utf8' }).trim()
}

function gitHeadTree(cwd) {
  return execFileSync('git', ['rev-parse', 'HEAD^{tree}'], { cwd, encoding: 'utf8' }).trim()
}

function readPackageVersion() {
  const raw = readFileSync(PACKAGE_JSON, 'utf8')
  const pkg = JSON.parse(raw)
  return typeof pkg.version === 'string' ? pkg.version : '0.0.0'
}

function sha256(buf) {
  return createHash('sha256').update(buf).digest('hex')
}

function listFilesRecursive(root) {
  const out = []
  const stack = [root]
  while (stack.length > 0) {
    const dir = stack.pop()
    let entries
    try {
      entries = readdirSync(dir, { withFileTypes: true })
    } catch {
      continue
    }
    for (const entry of entries) {
      const full = join(dir, entry.name)
      if (entry.isDirectory()) {
        stack.push(full)
      } else if (entry.isFile()) {
        out.push(full)
      }
    }
  }
  out.sort()
  return out
}

function collectArtifacts(artifactsDir) {
  if (!existsSync(artifactsDir)) return []
  const stat = statSync(artifactsDir)
  if (!stat.isDirectory()) return []
  const files = listFilesRecursive(artifactsDir)
  return files.map((full) => {
    const buf = readFileSync(full)
    return {
      path: relative(artifactsDir, full).replace(/\\/g, '/'),
      size: buf.length,
      sha256: sha256(buf),
      extension: extname(full).toLowerCase()
    }
  })
}

function main() {
  const args = parseArgs(process.argv)
  const cwd = REPO_ROOT

  const outPath = isAbsolute(args.out) ? args.out : resolve(cwd, args.out)
  const artifactsDir = isAbsolute(args.artifactsDir) ? args.artifactsDir : resolve(cwd, args.artifactsDir)

  const metadata = {
    buildTime: new Date().toISOString(),
    gitCommit: gitHead(cwd),
    gitTree: gitHeadTree(cwd),
    packageVersion: readPackageVersion(),
    electronBuilder: args.electronBuilder,
    artifacts: collectArtifacts(artifactsDir)
  }

  writeFileSync(outPath, JSON.stringify(metadata, null, 2) + '\n', 'utf8')
  process.stdout.write(
    `[build-metadata] wrote ${outPath} (${metadata.artifacts.length} artifact(s), commit=${metadata.gitCommit.slice(0, 12)})\n`
  )
}

main()
