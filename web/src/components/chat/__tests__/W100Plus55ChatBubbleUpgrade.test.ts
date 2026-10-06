/**
 * W100 +55 Chat Bubble 全面升级测试
 *
 * 覆盖:
 * ① 气泡 base class 渲染 + ::before/::after (CSS 在 ChatViewSSE)
 * ② 打字机 --reveal 进度 (length=40→50%, length=80→100%)
 * ③ formatTimeDivider 三档 (今天/昨天/7天前) — sanity import
 * ④ 时间分隔符渲染规则 (file-source 断言 ChatMessageRow 调用 formatTimeDivider)
 * ⑤ plan_step 视觉升级 (done line-through + running border-left)
 * ⑥ plan_step `__plan_summary__` 不被显示 (placeholder 过滤)
 * ⑦ 按钮 hover scale (send-btn) — file-source 断言 CSS
 * ⑧ 输入区 focus 边框 ring — file-source 断言 CSS
 *
 * 注意: 不 import ChatMessageRow (FollowUpChips.vue 已有 pre-existing Vue 3
 * parse error: <Transition> 2 个 sibling children, 不在 +55 范围, 沿用不动,
 * 详见 memory/W100+55 沉淀)
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import PlanSteps from '../PlanSteps.vue'
import { formatTimeDivider } from '@/utils/timeDivider'

const CHAT_VIEW = resolve(__dirname, '../../../views/chat/ChatViewSSE.vue')
// 2026-10-05 (CSS 抽出): ① ①b ①c ② ④c ⑦ ⑧ 的 CSS 断言随 <style scoped src>
// 迁到 chatview-scoped.css (逐条实测: 这些选择器在 scoped 块, 且 scoped 是 global 的超集)。
// ⑧b (模板文案) 仍读 .vue —— 目标在 template, L-1 script 拆分不动 template。
// 2026-10-07 (L-1 阶段 1): 原 ④b "ChatViewSSE 源码含 formatTimeDivider" 已迁移 ——
// 该钉实为钉 import 行 (script 物理位置), 且 formatTimeDivider 在 ChatViewSSE 里是
// 零调用死 import (真正渲染时间分隔线的是 ChatMessageRow, ④ 仍在盯它)。行为断言由
// views/chat/__tests__/ChatViewSSE.behavior.test.js
//   "每条消息以 msg + prev-timestamp 接入 ChatMessageRow" 接住 (比源码正则更强)。
const CHAT_VIEW_CSS = resolve(__dirname, '../../../views/chat/chatview-scoped.css')
const CHAT_ROW = resolve(__dirname, '../ChatMessageRow.vue')

describe('W100 +55 Chat Bubble 全面升级', () => {
  it('① 气泡 ::before/::after CSS 规则在 ChatViewSSE 中', () => {
    const src = readFileSync(CHAT_VIEW_CSS, 'utf-8')
    expect(src).toMatch(/\.user-bubble::before/)
    expect(src).toMatch(/position:\s*absolute/)
    expect(src).toMatch(/clip-path:\s*polygon/)
    expect(src).toMatch(/\.bot-bubble::before/)
    expect(src).toMatch(/\.bot-bubble::after/)
  })

  it('①b 气泡 padding 14-18px + border-radius 4px (锐) + 其余 16px', () => {
    const src = readFileSync(CHAT_VIEW_CSS, 'utf-8')
    expect(src).toMatch(/padding:\s*14px\s+18px/)
    // 2026-08-31: 桌面气泡后续波次把 W100+55 的单角 longhand 重写为 4 值简写
    // (18px 18px 18px 4px / 18px 18px 4px 18px) — 视觉等价 (右下/左下锐角 4px)。
    // 原测试正则只认 longhand → 源码合法演进后变脆红。改为接受两种写法之一。
    const hasBrCorner =
      /border-bottom-right-radius:\s*4px/.test(src) ||
      /border-radius:\s*[\d.]+px\s+[\d.]+px\s+4px\s+[\d.]+px/.test(src)
    const hasBlCorner =
      /border-bottom-left-radius:\s*4px/.test(src) ||
      /border-radius:\s*[\d.]+px\s+[\d.]+px\s+[\d.]+px\s+4px/.test(src)
    expect(hasBrCorner).toBe(true)
    expect(hasBlCorner).toBe(true)
    expect(src).toMatch(/border-radius:\s*16px/)
  })

  it('①c 气泡 hover lift (translateY -1px + shadow)', () => {
    const src = readFileSync(CHAT_VIEW_CSS, 'utf-8')
    expect(src).toMatch(/\.bubble:hover/)
    expect(src).toMatch(/transform:\s*translateY\(-1px\)/)
    // 2026-08-31: hover 阴影从 var(--shadow-lg) 改为定制值 (bot 中性黑 / user 珊瑚色),
    // 防护语义「hover 时加深阴影」保留 → 接受 token 或定制 box-shadow
    const hasShadow =
      /var\(--shadow-lg/.test(src) || /\.bubble:hover[\s\S]{0,120}box-shadow:/.test(src)
    expect(hasShadow).toBe(true)
  })

  it('② 打字机 --reveal 进度 CSS 规则在 ChatViewSSE 中', () => {
    const src = readFileSync(CHAT_VIEW_CSS, 'utf-8')
    expect(src).toMatch(/\.msg-content-typing/)
    expect(src).toMatch(/--reveal:\s*0%/)
    expect(src).toMatch(/mask-image:\s*linear-gradient/)
    expect(src).toMatch(/transition:\s*--reveal\s+250ms\s+linear/)
    // @supports not fallback
    expect(src).toMatch(/@supports not/)
  })

  it('②b ChatMessageRow 含 revealProgress ref + watch', () => {
    const src = readFileSync(CHAT_ROW, 'utf-8')
    expect(src).toMatch(/revealProgress/)
    expect(src).toMatch(/watch/)
    expect(src).toMatch(/msg-content-typing/)
  })

  it('③ formatTimeDivider 三档 sanity (同 util test file)', () => {
    const now = new Date(2026, 7, 3, 14, 30, 0)
    expect(formatTimeDivider(new Date(2026, 7, 3, 9, 15, 0), now)).toMatch(/^今天/)
    expect(formatTimeDivider(new Date(2026, 7, 2, 22, 5, 0), now)).toMatch(/^昨天/)
    const out7 = formatTimeDivider(new Date(2026, 6, 27, 8, 0, 0), now)
    expect(out7).not.toMatch(/^今天/)
    expect(out7).not.toMatch(/^昨天/)
  })

  it('④ ChatMessageRow 用 formatTimeDivider 渲染时间分隔线', () => {
    const src = readFileSync(CHAT_ROW, 'utf-8')
    expect(src).toMatch(/formatTimeDivider/)
    // 2026-09-30 S3.4 修正: 本断言写于 08-31, 当时假设"组件内不得自行格式化时间"。
    // 但 09-03「档案对话」重设计 (commit feat(web): 智能对话页重设计) 新增了 userTime ——
    // 问条的**具体时刻** (14:30), 与 formatTimeDivider 的**日期分隔线** (今天/昨天)
    // 是两个不同场景, 各自需要自己的格式化。源码晚于测试 3 天, 以源码为准。
    // 因此收窄为: formatTimeDivider 必须在场; 不再禁止 userTime 的时刻格式化。
  })

  it('④c time-divider CSS 升级 (居中 + 两侧横线)', () => {
    const src = readFileSync(CHAT_VIEW_CSS, 'utf-8')
    expect(src).toMatch(/\.time-divider::before/)
    expect(src).toMatch(/\.time-divider::after/)
    expect(src).toMatch(/max-width:\s*80px/)
  })

  it('⑤ plan_step 视觉升级: done line-through + running border-left + tool 胶囊', () => {
    const steps = [
      { step: '查询知识库', tool: 'search_knowledge', status: 'done' as const },
      { step: '提取公式', tool: 'extract_formulas', status: 'running' as const },
      { step: '生成回答', status: 'pending' as const },
    ]
    const wrapper = mount(PlanSteps, { props: { steps } })
    expect(wrapper.find('.plan-step-done').exists()).toBe(true)
    expect(wrapper.find('.plan-step-running').exists()).toBe(true)
  })

  it('⑤b plan_step CSS: done line-through + running border-left 2px + tool 圆角胶囊', () => {
    const src = readFileSync(resolve(__dirname, '../PlanSteps.vue'), 'utf-8')
    expect(src).toMatch(/text-decoration:\s*line-through/)
    expect(src).toMatch(/border-left:\s*2px\s+solid\s+var\(--color-primary\)/)
    expect(src).toMatch(/--radius-full/)
  })

  it('⑥ plan_step `__plan_summary__` placeholder 不显示 (startsWith __ 过滤)', () => {
    const steps = [
      { step: '__plan_summary__', status: 'pending' as const },
      { step: 'search_knowledge', tool: 'search_knowledge', status: 'running' as const },
      { step: 'query_members', tool: 'query_members', status: 'pending' as const },
    ]
    const wrapper = mount(PlanSteps, { props: { steps } })
    // 实际显示的是 2 个真实 step (placeholder 隐藏) — 只数 li.plan-step
    const liCount = wrapper.findAll('li.plan-step').length
    expect(liCount).toBe(2)
    // placeholder 不可见, 第 0 个 li 应是 search_knowledge
    const firstStep = wrapper.find('li.plan-step')
    expect(firstStep.text()).toContain('search_knowledge')
    expect(firstStep.text()).not.toContain('__plan_summary__')
  })

  it('⑥b placeholder 过滤后 total 计数正确 (visibleSteps.length, 非原 steps.length)', () => {
    const steps = [
      { step: '__plan_summary__', status: 'pending' as const },
      { step: 'search_knowledge', tool: 'search_knowledge', status: 'done' as const },
      { step: 'query_members', tool: 'query_members', status: 'pending' as const },
    ]
    const wrapper = mount(PlanSteps, { props: { steps } })
    // summary 应基于 visibleSteps (2 个), 1/2
    const summary = wrapper.find('[data-testid="plan-steps-summary-static"]')
    expect(summary.text()).toMatch(/计划中:\s*[01]\s*\/2\s*步骤/)
  })

  it('⑦ send-btn hover scale CSS 规则存在', () => {
    const src = readFileSync(CHAT_VIEW_CSS, 'utf-8')
    expect(src).toMatch(/\.send-btn:hover:not\(:disabled\)/)
    expect(src).toMatch(/transform:\s*scale\(1\.05\)/)
    expect(src).toMatch(/\.send-btn:active:not\(:disabled\)/)
    expect(src).toMatch(/transform:\s*scale\(0\.96\)/)
  })

  it('⑧ input-core:focus-within 边框 + 3px ring', () => {
    const src = readFileSync(CHAT_VIEW_CSS, 'utf-8')
    expect(src).toMatch(/\.input-core:focus-within/)
    expect(src).toMatch(/border-color:\s*var\(--color-primary/)
    expect(src).toMatch(/box-shadow:\s*0\s+0\s+0\s+3px/)
  })

  it('⑧b 输入区 .input-hint 模板文案存在', () => {
    const src = readFileSync(CHAT_VIEW, 'utf-8')
    expect(src).toMatch(/Enter 发送 · Shift\+Enter 换行/)
  })
})
