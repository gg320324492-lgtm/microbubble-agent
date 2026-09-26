// @vitest-environment jsdom
// DL-4 预设 ↔ 模型 ID 双向绑定冲突修复 —— 预设单向化（纯快捷填充器）
//
// 病根（用户真机反馈）：预设 <select> 的显示值绑死在 form.name（用户可编辑的「名称」
//   字段）上——选预设只回填 protocol/baseUrl/model 不写 name → 下拉显示弹回；
//   改名称/模型 ID 又牵动下拉显示 → 用户感知「互相覆盖」，预设清单之外的自定义
//   模型（mimo-v2.6-flash）无法稳定停留。
// 修复：预设改为独立选择态（单向快捷填充）；手改任一字段 → 下拉清空、永不回写。
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ModelServiceSection from '@renderer/components/settings/ModelServiceSection.vue'
import type { ModelProvider } from '@shared/types'

/** 已保存列表（save 后 list 回读，供「重开弹窗」用例） */
const saved: ModelProvider[] = []
let saveMock: ReturnType<typeof vi.fn>

function stubModelApi(): void {
  saved.length = 0
  saveMock = vi.fn(async (p: Record<string, unknown>) => {
    saved.push({
      id: 'p1',
      name: String(p.name ?? ''),
      protocol: (p.protocol ?? 'openai') as ModelProvider['protocol'],
      baseUrl: String(p.baseUrl ?? ''),
      model: String(p.model ?? ''),
      apiKeyMasked: '••••abcd',
      isDefault: false,
      keyState: 'ok'
    })
  })
  Object.assign(window, {
    api: {
      model: {
        list: vi.fn(async () => saved),
        save: saveMock,
        test: vi.fn(async () => ({ ok: true, message: '连接正常' })),
        remove: vi.fn(async () => undefined),
        setDefault: vi.fn(async () => undefined)
      }
    }
  })
}

const MIMO_BASEURL = 'https://token-plan-cn.xiaomimimo.com/anthropic'

type SectionWrapper = VueWrapper<{ preset: string }>

function inputValue(w: SectionWrapper, testid: string): string {
  return (w.get(`[data-testid="${testid}"]`).element as HTMLInputElement).value
}

function selectValue(w: SectionWrapper, testid: string): string {
  return (w.get(`[data-testid="${testid}"]`).element as HTMLSelectElement).value
}

beforeEach(() => {
  stubModelApi()
})

describe('DL-4 预设单向化 — 快捷填充器契约', () => {
  it('★ 选预设 → 一次性回填协议/Base URL/模型 ID（单向第一段）', async () => {
    const w = mount(ModelServiceSection) as unknown as SectionWrapper
    await flushPromises()
    await w.get('[data-testid="btn-add"]').trigger('click')
    await w.get('[data-testid="model-preset"]').setValue('MiMo (小米)')
    expect(selectValue(w, 'model-protocol')).toBe('anthropic')
    expect(inputValue(w, 'model-baseurl')).toBe(MIMO_BASEURL)
    expect(inputValue(w, 'model-modelid')).toBe('mimo-v2.5')
  })

  it('★ 手改模型 ID → 预设下拉清空且不回写（自定义模型可稳定停留）', async () => {
    const w = mount(ModelServiceSection) as unknown as SectionWrapper
    await flushPromises()
    await w.get('[data-testid="btn-add"]').trigger('click')
    await w.get('[data-testid="model-preset"]').setValue('MiMo (小米)')
    await w.get('[data-testid="model-modelid"]').setValue('mimo-v2.6-flash')
    // 下拉已清空；模型 ID 保持手填值不被预设覆盖
    expect(selectValue(w, 'model-preset')).toBe('')
    expect(inputValue(w, 'model-modelid')).toBe('mimo-v2.6-flash')
    // 再改 Base URL 同理：预设保持空，字段不被回写
    await w.get('[data-testid="model-baseurl"]').setValue('https://my-gateway.example.com/anthropic')
    expect(selectValue(w, 'model-preset')).toBe('')
    expect(inputValue(w, 'model-baseurl')).toBe('https://my-gateway.example.com/anthropic')
    expect(inputValue(w, 'model-modelid')).toBe('mimo-v2.6-flash')
  })

  it('★ 自定义模型全流程：填 mimo-v2.6-flash + Anthropic + MiMo URL → 保存 → 重开各字段原样、预设空', async () => {
    const w = mount(ModelServiceSection) as unknown as SectionWrapper
    await flushPromises()
    await w.get('[data-testid="btn-add"]').trigger('click')
    await w.get('[data-testid="model-preset"]').setValue('MiMo (小米)')
    await w.get('[data-testid="model-name"]').setValue('MiMo 自定义')
    await w.get('[data-testid="model-modelid"]').setValue('mimo-v2.6-flash')
    await w.get('[data-testid="model-apikey"]').setValue('sk-test-1')
    await w.findAll('button').find((b) => b.text() === '保存')!.trigger('click')
    await flushPromises()
    // 保存载荷与手填完全一致
    expect(saveMock).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'MiMo 自定义', protocol: 'anthropic', baseUrl: MIMO_BASEURL, model: 'mimo-v2.6-flash' })
    )
    // 重开编辑：各字段原样，预设保持空（无反向匹配回填）
    await w.findAll('button').find((b) => b.text() === '编辑')!.trigger('click')
    await flushPromises()
    expect(selectValue(w, 'model-preset')).toBe('')
    expect(inputValue(w, 'model-name')).toBe('MiMo 自定义')
    expect(selectValue(w, 'model-protocol')).toBe('anthropic')
    expect(inputValue(w, 'model-baseurl')).toBe(MIMO_BASEURL)
    expect(inputValue(w, 'model-modelid')).toBe('mimo-v2.6-flash')
  })

  it('弹窗内元素唯一（LoginView 勾选框 ×2 教训）：预设下拉/模型 ID 输入各 1 处', async () => {
    const w = mount(ModelServiceSection) as unknown as SectionWrapper
    await flushPromises()
    await w.get('[data-testid="btn-add"]').trigger('click')
    expect(w.findAll('[data-testid="model-preset"]')).toHaveLength(1)
    expect(w.findAll('[data-testid="model-modelid"]')).toHaveLength(1)
    expect(w.findAll('label').filter((l) => l.text() === '模型 ID')).toHaveLength(1)
  })
})
