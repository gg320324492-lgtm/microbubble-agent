import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * Release guard test — R0 zero-impact guard
 *
 * Verifies that `verify-web-unchanged.mjs` returns:
 *   - exit 0 when only desktop/ files change
 *   - exit 1 when any protected web/app/alembic/... file appears in the change list
 *
 * Each test creates an isolated temporary git repository so the real worktree is
 * never touched. The script under test is invoked with --changed=<paths> and
 * --baseline=<baseline.json> so we never depend on cwd or live git state.
 */

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolve(__dirname, '..', '..')
const SCRIPT_PATH = join(REPO_ROOT, 'scripts', 'release', 'verify-web-unchanged.mjs')

interface GuardResult {
  status: number
  stdout: string
  stderr: string
}

function runGuard(changed: string[], options: { baselinePath?: string; cwd?: string } = {}): GuardResult {
  const args = [SCRIPT_PATH]
  if (changed.length > 0) {
    args.push(`--changed=${changed.join(',')}`)
  }
  if (options.baselinePath) {
    args.push(`--baseline=${options.baselinePath}`)
  }

  try {
    const stdout = execFileSync('node', args, {
      cwd: options.cwd ?? REPO_ROOT,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe']
    })
    return { status: 0, stdout, stderr: '' }
  } catch (err: unknown) {
    const e = err as { status?: number; stdout?: string; stderr?: string }
    return {
      status: e.status ?? 1,
      stdout: e.stdout ?? '',
      stderr: e.stderr ?? ''
    }
  }
}

/**
 * Create an isolated git repo with the protected paths stubbed as commits so the
 * baseline tree-ID verification succeeds. Returns { dir, baselinePath }.
 */
function setupIsolatedRepo(): { dir: string; baselinePath: string } {
  const dir = mkdtempSync(join(tmpdir(), 'release-guard-'))
  const run = (cmd: string, args: string[]): void => {
    execFileSync(cmd, args, { cwd: dir, stdio: 'ignore' })
  }

  // Init a tiny repo. The script only needs `git ls-tree HEAD <path>` to work,
  // and it only does so for paths present in the baseline JSON.
  run('git', ['init', '--initial-branch=main', '-q'])
  run('git', ['config', 'user.email', 'r0@test.local'])
  run('git', ['config', 'user.name', 'R0 Test'])

  // Create stub content for each protected path so `git ls-tree HEAD <path>` returns a tree.
  const protectedDirs = ['app', 'web', 'alembic', 'nginx']
  for (const d of protectedDirs) {
    mkdirSync(join(dir, d), { recursive: true })
    writeFileSync(join(dir, d, '.keep'), '')
  }
  writeFileSync(join(dir, 'docker-compose.yml'), '# stub\n')
  writeFileSync(join(dir, 'docker-compose.dev.yml'), '# stub\n')
  writeFileSync(join(dir, '.env'), '# stub\n')

  run('git', ['add', '-A'])
  run('git', ['commit', '-q', '-m', 'init'])

  // Compute the baseline JSON from the live repo's tree IDs.
  const baseline: {
    capturedAt: string
    capturedBy: string
    capturedCommit: string
    protectedPaths: Record<string, string>
  } = {
    capturedAt: new Date().toISOString(),
    capturedBy: 'R0 test fixture',
    capturedCommit: 'stub',
    protectedPaths: {}
  }

  for (const p of [...protectedDirs, 'docker-compose.yml', 'docker-compose.dev.yml', '.env']) {
    const out = execFileSync('git', ['ls-tree', 'HEAD', p], { cwd: dir, encoding: 'utf8' }).trim()
    // Format: "<mode> <type> <hash>\t<name>"
    const parts = out.split(/\s+/)
    baseline.protectedPaths[p] = parts[2]
  }

  const baselinePath = join(dir, 'baseline.json')
  writeFileSync(baselinePath, JSON.stringify(baseline, null, 2))

  return { dir, baselinePath }
}

describe('verify-web-unchanged.mjs (R0 release guard)', () => {
  let fixture: ReturnType<typeof setupIsolatedRepo>

  beforeEach(() => {
    fixture = setupIsolatedRepo()
  })

  afterEach(() => {
    rmSync(fixture.dir, { recursive: true, force: true })
  })

  it('allows changes that touch only desktop/ files', () => {
    const result = runGuard(['desktop/src/main/index.ts', 'desktop/package.json'], {
      baselinePath: fixture.baselinePath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(0)
  })

  it('rejects changes that touch web/ files', () => {
    const result = runGuard(['web/src/main.ts'], {
      baselinePath: fixture.baselinePath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('网页端受保护路径发生变更')
  })

  it('rejects changes that touch app/ files', () => {
    const result = runGuard(['app/main.py'], {
      baselinePath: fixture.baselinePath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('app')
  })

  it('rejects changes that touch alembic/ files', () => {
    const result = runGuard(['alembic/versions/abc.py'], {
      baselinePath: fixture.baselinePath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('alembic')
  })

  it('rejects changes that touch docker-compose*.yml', () => {
    const result = runGuard(['docker-compose.yml'], {
      baselinePath: fixture.baselinePath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('docker-compose')
  })

  it('rejects changes that touch nginx/ files', () => {
    const result = runGuard(['nginx/conf.d/tunnel.conf'], {
      baselinePath: fixture.baselinePath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('nginx')
  })

  it('rejects changes that touch .env', () => {
    const result = runGuard(['.env'], {
      baselinePath: fixture.baselinePath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('.env')
  })

  it('reports the offending paths on stderr', () => {
    const result = runGuard(['web/foo.ts', 'app/bar.py'], {
      baselinePath: fixture.baselinePath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('web/foo.ts')
    expect(result.stderr).toContain('app/bar.py')
  })

  it('returns status 2 when baseline file is missing', () => {
    const result = runGuard(['desktop/a.ts'], {
      baselinePath: join(fixture.dir, 'does-not-exist.json'),
      cwd: fixture.dir
    })
    expect(result.status).toBe(2)
    expect(result.stderr).toContain('baseline')
  })

  it('returns status 1 when a baseline protectedPath tree ID no longer matches HEAD', () => {
    const baselineRaw = execFileSync(
      'node',
      ['-e', `console.log(require('fs').readFileSync(${JSON.stringify(fixture.baselinePath)},'utf8'))`],
      { encoding: 'utf8' }
    )
    const tampered = JSON.parse(baselineRaw) as { protectedPaths: Record<string, string> }
    tampered.protectedPaths['app'] = '0'.repeat(40)
    const tamperedPath = join(fixture.dir, 'tampered.json')
    writeFileSync(tamperedPath, JSON.stringify(tampered, null, 2))

    const result = runGuard(['desktop/a.ts'], {
      baselinePath: tamperedPath,
      cwd: fixture.dir
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain('app')
  })
})
