// M6-2 交付物 1 — CI workflow 静态自检（node:fs 读文件做基本校验，不引第三方 YAML 解析）
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// tests/unit → tests → apps/desktop → apps → 仓库根（4 级）
const REPO_ROOT = resolve(__dirname, '../../../..')
const WORKFLOW = resolve(REPO_ROOT, '.github/workflows/desktop-release.yml')

function readWorkflow(): string {
  return existsSync(WORKFLOW) ? readFileSync(WORKFLOW, 'utf8') : ''
}

describe('desktop-release.yml — 存在性与触发条件', () => {
  it('文件存在，且触发条件为 push tag v* + workflow_dispatch', () => {
    const yml = readWorkflow()
    expect(yml.length, '缺少 .github/workflows/desktop-release.yml').toBeGreaterThan(0)

    expect(yml).toMatch(/^on:/m)
    expect(yml).toMatch(/^\s{2}push:/m)
    expect(yml).toMatch(/^\s{4}tags:/m)
    expect(yml).toMatch(/^\s{6}-\s*'v\*'/m)
    expect(yml).toMatch(/^\s{2}workflow_dispatch:/m)
  })

  it('权限仅需内置 GITHUB_TOKEN（contents: write），不依赖额外 secrets', () => {
    const yml = readWorkflow()
    expect(yml).toMatch(/^permissions:/m)
    expect(yml).toMatch(/^\s{2}contents:\s*write\s*$/m)
    // 除 GITHUB_TOKEN 外不得出现其他 secrets 引用
    const secrets = [...yml.matchAll(/secrets\.([A-Za-z0-9_]+)/g)].map((m) => m[1])
    expect([...new Set(secrets)]).toEqual(['GITHUB_TOKEN'])
  })
})

describe('desktop-release.yml — 运行环境与构建范围', () => {
  it('windows-latest + Node 22（node:sqlite 需 ≥22.5）+ pnpm 9.15.9', () => {
    const yml = readWorkflow()
    expect(yml).toMatch(/runs-on:\s*windows-latest/)
    expect(yml).toMatch(/node-version:\s*'22'/)
    expect(yml).toMatch(/version:\s*9\.15\.9/)
  })

  it('只构建 apps/desktop：门禁与打包均在 apps/desktop 下执行，不触碰 web/ 等非桌面路径', () => {
    const yml = readWorkflow()
    expect(yml).toMatch(/working-directory:\s*apps\/desktop/)
    expect(yml).toMatch(/node scripts\/release\.mjs/)
    // 只在"可执行内容"上断言，排除注释（注释里说明范围约束是合理的）
    const code = yml
      .split('\n')
      .filter((l) => !/^\s*#/.test(l))
      .join('\n')
    for (const forbidden of ['web/', 'alembic/', 'docker-compose', 'nginx/', 'desktop-conversion']) {
      expect(code.includes(forbidden), `workflow 步骤不应涉及 ${forbidden}`).toBe(false)
    }
  })
})

describe('desktop-release.yml — 步骤链与产物', () => {
  it('含 checkout / setup-node / setup-pnpm / frozen-lockfile / 三件套上传', () => {
    const yml = readWorkflow()
    expect(yml).toMatch(/actions\/checkout@v4/)
    expect(yml).toMatch(/actions\/setup-node@v4/)
    expect(yml).toMatch(/pnpm\/action-setup@v4/)
    expect(yml).toMatch(/pnpm install --frozen-lockfile/)
    expect(yml).toMatch(/gh release (create|upload)/)
    expect(yml).toContain('MicroBubbleWorkbench-${VER}-setup.exe')
    expect(yml).toContain('${EXE}.blockmap')
    expect(yml).toContain('latest.yml')
  })

  it('发布脚本与本地一致：version/clean/native/gates/package/smoke/latest/verify 八步全用', () => {
    const yml = readWorkflow()
    const step = /node scripts\/release\.mjs ([^\n]+)/.exec(yml)
    expect(step).not.toBeNull()
    const steps = (step?.[1] ?? '').trim().split(/\s+/)
    expect(steps).toEqual(['version', 'clean', 'native', 'gates', 'package', 'smoke', 'latest', 'verify'])
  })

  it('tag 解析支持 push tag / 手动指定 / 兜底 ci.<run_number>', () => {
    const yml = readWorkflow()
    expect(yml).toMatch(/github\.ref_name/)
    expect(yml).toMatch(/inputs\.tag/)
    expect(yml).toMatch(/-ci\.\$\{\{\s*github\.run_number\s*\}\}/)
    expect(yml).toMatch(/gh release view/)
  })
})
