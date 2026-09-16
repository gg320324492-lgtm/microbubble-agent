// @vitest-environment jsdom
// R-1 打磨项 UI 契约 — Key 失效重填引导 / 清除工作区 / 回滚二次确认文案
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ModelServiceSection from '@renderer/components/settings/ModelServiceSection.vue'
import WorkspaceSection from '@renderer/components/settings/WorkspaceSection.vue'
import { ROLLBACK_CONFIRM_TEXT } from '@renderer/stores/chat-events'
import type { ModelProvider } from '@shared/types'

beforeEach(() => {
  // 清理上一用例挂到 window 的 stub
  // (Object.assign 覆盖即可，无需还原)
})

const provider = (keyState: 'ok' | 'invalid'): ModelProvider => ({
  id: 'p1',
  name: 'MiMo (小米)',
  protocol: 'anthropic',
  baseUrl: 'https://token-plan-cn.xiaomimimo.com/anthropic',
  model: 'mimo-v2.5',
  apiKeyMasked: '••••••••',
  isDefault: true,
  keyState
})

describe('打磨① — Key 失效重填引导', () => {
  it('keyState=invalid 时显示「Key 失效」标记与「重填 Key」入口', async () => {
    Object.assign(window, { api: { model: { list: vi.fn().mockResolvedValue([provider('invalid')]) } } })
    const w = mount(ModelServiceSection)
    await flushPromises()
    expect(w.get('[data-testid="key-invalid"]').text()).toBe('Key 失效')
    expect(w.get('[data-testid="btn-refill"]').text()).toContain('重填 Key')
    expect(w.text()).toContain('本机解密失败')
  })

  it('keyState=ok 时不显示失效标记与重填入口', async () => {
    Object.assign(window, { api: { model: { list: vi.fn().mockResolvedValue([provider('ok')]) } } })
    const w = mount(ModelServiceSection)
    await flushPromises()
    expect(w.find('[data-testid="key-invalid"]').exists()).toBe(false)
    expect(w.find('[data-testid="btn-refill"]').exists()).toBe(false)
  })
})

describe('打磨② — 清除工作区', () => {
  function stubWorkspace(root: string | null, clear: ReturnType<typeof vi.fn>): void {
    Object.assign(window, {
      api: {
        workspace: {
          get: vi.fn().mockResolvedValueOnce({ root }).mockResolvedValue({ root: null }),
          set: vi.fn(),
          clear,
          auditList: vi.fn().mockResolvedValue([])
        },
        model: { list: vi.fn().mockResolvedValue([]) }
      }
    })
  }

  it('已设置时显示「清除」；确认后调用 clear 并回到未设置态', async () => {
    const clear = vi.fn().mockResolvedValue(undefined)
    stubWorkspace('E:\\microbubble-agent\\desktop-conversion', clear)
    const w = mount(WorkspaceSection)
    await flushPromises()
    expect(w.findAll('[data-testid="btn-clear-ws"]')).toHaveLength(1)
    await w.get('[data-testid="btn-clear-ws"]').trigger('click')
    await flushPromises()
    // ElMessageBox 二次确认 → 点确认按钮
    const confirmBtn = document.querySelector<HTMLElement>('.el-message-box__btns .el-button--primary')
    expect(confirmBtn).not.toBeNull()
    confirmBtn?.click()
    await flushPromises()
    expect(clear).toHaveBeenCalledTimes(1)
    await flushPromises()
    expect(w.text()).toContain('未设置')
  })

  it('未设置时不显示「清除」按钮', async () => {
    const clear = vi.fn()
    stubWorkspace(null, clear)
    const w = mount(WorkspaceSection)
    await flushPromises()
    expect(w.findAll('[data-testid="btn-clear-ws"]')).toHaveLength(0)
  })
})

describe('打磨⑤ — 回滚二次确认文案契约', () => {
  it('文案明确说明将恢复备份并覆盖当前内容', () => {
    expect(ROLLBACK_CONFIRM_TEXT).toContain('备份')
    expect(ROLLBACK_CONFIRM_TEXT).toContain('覆盖')
    expect(ROLLBACK_CONFIRM_TEXT).toContain('当前内容')
  })
})
