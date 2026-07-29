/**
 * mobile_build_validation.spec.js — W68 第 12 批 C-1 前端构建回归验证
 *
 * 背景:
 * MobileFileCommentsView.vue 曾在同一 <script setup> 中重复声明
 * tabsWithCounts，导致 Vite 在生产构建阶段报错。组件级测试可能不会覆盖
 * 完整 Rollup 模块图，因此这里把唯一合法的生产构建命令作为端到端门禁。
 *
 * 场景:
 * 1. 从 web/ 目录执行 npm run build，进程必须以状态码 0 退出。
 *
 * 运行:
 * npx vitest run tests/e2e/mobile_build_validation.spec.js
 */

import { spawnSync } from 'node:child_process'
import { describe, expect, it } from 'vitest'

// Vitest 由 web/ 作为 root 启动；使用 cwd 也避免 jsdom 重写 import.meta.url。
const WEB_ROOT = process.cwd()
const BUILD_TIMEOUT_MS = 240_000

/**
 * 优先复用当前 npm CLI 的真实入口。
 *
 * 这样 Windows 下无需依赖 npm.cmd 的 shell 解析，Linux/macOS 下也保持
 * 一致。若测试不是由 npm/npx 启动，再回退到平台对应的 npm 可执行文件。
 */
function npmBuildCommand() {
  if (process.env.npm_execpath) {
    return {
      command: process.execPath,
      args: [process.env.npm_execpath, 'run', 'build'],
      shell: false,
    }
  }

  return {
    command: process.platform === 'win32' ? 'npm.cmd' : 'npm',
    args: ['run', 'build'],
    shell: process.platform === 'win32',
  }
}

function runProductionBuild() {
  const { command, args, shell } = npmBuildCommand()

  return spawnSync(command, args, {
    cwd: WEB_ROOT,
    encoding: 'utf8',
    env: {
      ...process.env,
      FORCE_COLOR: '0',
      NO_COLOR: '1',
    },
    maxBuffer: 20 * 1024 * 1024,
    shell,
    timeout: BUILD_TIMEOUT_MS,
  })
}

function buildFailureMessage(result) {
  return [
    `npm run build 未正常退出 (status=${String(result.status)}, signal=${String(result.signal)})`,
    result.error ? `error:\n${result.error.stack || result.error.message}` : '',
    result.stdout ? `stdout:\n${result.stdout}` : '',
    result.stderr ? `stderr:\n${result.stderr}` : '',
  ]
    .filter(Boolean)
    .join('\n\n')
}

describe('MobileFileCommentsView production build regression', () => {
  it(
    '场景 1: npm run build exit 0',
    () => {
      const result = runProductionBuild()
      const failure = buildFailureMessage(result)

      expect(result.error, failure).toBeUndefined()
      expect(result.signal, failure).toBeNull()
      expect(result.status, failure).toBe(0)
    },
    BUILD_TIMEOUT_MS + 10_000,
  )
})
