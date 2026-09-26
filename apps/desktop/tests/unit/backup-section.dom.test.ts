// R-9 R 阶段守护 —— 备份区块必须能真实挂载（模板结构性错误不能只靠 typecheck）
//
// 背景：R 阶段重构模板时漏了一个 </details>，`pnpm typecheck` 与既有测试**全部通过**，
// 但 vite 在运行时抛 `Element is missing end tag`，设置页整块渲染失败 —— 只有真机才暴露。
// 本测试用 jsdom 真挂载组件，把这类结构错误前移到单测。
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import BackupSection from '@renderer/components/settings/BackupSection.vue'

function stubApi(): void {
  const noop = (): Promise<unknown> => Promise.resolve(null)
  const settings: Record<string, unknown> = {}
  ;(window as unknown as { api: unknown }).api = {
    settings: {
      get: (k: string): Promise<unknown> => Promise.resolve(settings[k] ?? null),
      set: (k: string, v: unknown): Promise<void> => {
        settings[k] = v
        return Promise.resolve()
      }
    },
    backup: {
      create: noop,
      restore: noop,
      list: (): Promise<unknown[]> => Promise.resolve([]),
      deleteLocal: noop,
      dailyGet: (): Promise<unknown> =>
        Promise.resolve({
          config: { enabled: false, mode: 'first-launch', delayMinutes: 10, atTime: '03:00', keep: 7 },
          last: null,
          targetDir: '',
          passwordConfigured: false,
          lastRunDate: null,
          nextRunAt: null
        }),
      dailySet: (): Promise<unknown> => Promise.resolve(null),
      dailyRun: (): Promise<unknown> => Promise.resolve({ ok: true, fileName: 'x', size: 1 }),
      oss: { saveConfig: noop, test: noop, upload: noop, listRemote: (): Promise<unknown[]> => Promise.resolve([]), download: noop, deleteRemote: noop }
    },
    auth: { me: (): Promise<unknown> => Promise.resolve(null) }
  }
}

beforeEach(() => {
  stubApi()
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
})

describe('备份区块 — 结构可挂载（R 阶段回归防线）', () => {
  it('能挂载且默认只露「四项」：密码 / 备份到 / 立即备份 / 状态行', async () => {
    const w = mount(BackupSection, { global: { stubs: { teleport: true } } })
    await new Promise((r) => setTimeout(r, 30))
    expect(w.find('[data-testid="backup-password"]').exists()).toBe(true)
    expect(w.find('[data-testid="backup-password-confirm"]').exists()).toBe(true)
    expect(w.find('[data-testid="daily-target"]').exists()).toBe(true)
    expect(w.find('[data-testid="btn-backup"]').exists()).toBe(true)
    expect(w.find('[data-testid="backup-status"]').exists()).toBe(true)
  })

  it('默认界面不暴露术语（R4）', async () => {
    const w = mount(BackupSection, { global: { stubs: { teleport: true } } })
    await new Promise((r) => setTimeout(r, 30))
    const text = w.text()
    for (const jargon of ['safeStorage', 'AES-256-GCM', 'mnbbak', 'Endpoint']) {
      expect(text, `默认界面出现术语：${jargon}`).not.toContain(jargon)
    }
  })

  it('高级选项与云端区块默认收起（R3），且均为 details 可展开', async () => {
    const w = mount(BackupSection, { global: { stubs: { teleport: true } } })
    await new Promise((r) => setTimeout(r, 30))
    const advs = w.findAll('details.adv')
    expect(advs.length).toBeGreaterThanOrEqual(3)
    for (const d of advs) expect(d.attributes('open')).toBeUndefined()
  })

  it('定时备份控件位于「高级选项」内（默认不可见）', async () => {
    const w = mount(BackupSection, { global: { stubs: { teleport: true } } })
    await new Promise((r) => setTimeout(r, 30))
    const adv = w.find('details.adv')
    expect(adv.find('[data-testid="daily-switch"]').exists()).toBe(true)
    expect(adv.find('[data-testid="daily-keep"]').exists()).toBe(true)
    expect(adv.find('[data-testid="daily-mode"]').exists()).toBe(true)
  })

  it('全页只有一个「立即备份」按钮（R2 一个动作）', async () => {
    const w = mount(BackupSection, { global: { stubs: { teleport: true } } })
    await new Promise((r) => setTimeout(r, 30))
    const btns = w.findAll('button').filter((b) => /^立即备份/.test(b.text().trim()))
    expect(btns.length).toBe(1)
  })

  it('DL-3：状态行旁有云端备份指引，点击直达网盘页（保护状态可见可达）', async () => {
    const w = mount(BackupSection, { global: { stubs: { teleport: true } } })
    await new Promise((r) => setTimeout(r, 30))
    const guide = w.find('[data-testid="backup-cloud-guide"]')
    expect(guide.exists()).toBe(true)
    expect(guide.text()).toContain('备份保存在你的云端网盘')
    expect(guide.text()).toContain('backups/')
    expect(guide.text()).toContain('查看')
    // 点击「查看」→ 跳网盘页（hash 路由）
    await guide.get('a').trigger('click')
    expect(window.location.hash).toBe('#/app/drive')
  })
})
