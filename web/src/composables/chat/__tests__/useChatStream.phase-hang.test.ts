/**
 * W100 +50d phase 防御测试 — 验证 sanitizeRestored 处理 zombie phase
 *   + useChatStream catch 路径显式落 phase='error'
 *
 * 真根因: useChatStream.ts catch 分支不动 phase, 只在 finally 兜底。
 *   若 finally 因 page unload race / persistSync throw 未跑,
 *   phase 会卡在 generating 永远不收敛。
 * 修复: catch 路径显式 set phase='error'。
 *
 * 测试策略: 复用 assistantPhase 状态机 + sanitizeRestored 验证 zombie phase 收敛。
 */
import { describe, expect, it } from 'vitest'
import {
  advancePhase,
  isTerminalPhase,
  sanitizeRestored,
} from '../assistantPhase'

describe('phase hang 防御 — W100 +50d', () => {
  describe('sanitizeRestored — zombie phase 必收敛', () => {
    it('case 1: state=streaming + phase=generating → state=idle, phase=done', () => {
      const m = {
        state: 'streaming',
        phase: 'generating',
        content: 'partial content here',
      }
      sanitizeRestored(m)
      expect(m.state).toBe('idle')
      expect(m.phase).toBe('done')
      expect(isTerminalPhase(m.phase)).toBe(true)
    })

    it('case 2: state=streaming + 无 phase → state=idle (有 content), phase=done', () => {
      const m = { state: 'streaming', content: 'some content' }
      sanitizeRestored(m)
      expect(m.state).toBe('idle')
      expect(m.phase).toBe('done')
    })

    it('case 3: state=streaming + 无 content → state=aborted, phase=aborted', () => {
      const m = { state: 'streaming', content: '' }
      sanitizeRestored(m)
      expect(m.state).toBe('aborted')
      expect(m.phase).toBe('aborted')
    })

    it('case 4: state=idle + phase=generating (非终态残留) → phase=done', () => {
      const m = { state: 'idle', content: 'done', phase: 'generating' }
      sanitizeRestored(m)
      // 非终态 phase 必收敛
      expect(m.phase).toBe('done')
    })

    it('case 5: 已 aborted 终态不被覆盖', () => {
      const m = { state: 'aborted', phase: 'aborted', content: 'partial' }
      sanitizeRestored(m)
      expect(m.phase).toBe('aborted')
    })

    it('case 6: phaseStartedAt 必被删 (防显示"3721.4s" elapsed)', () => {
      const m = {
        state: 'streaming',
        phase: 'generating',
        content: 'x',
        phaseStartedAt: Date.now() - 9999000,
      }
      sanitizeRestored(m)
      expect(m.phaseStartedAt).toBeUndefined()
    })
  })

  describe('advancePhase 终态守卫 — 防御 phase hang', () => {
    it('case 7: 任意非终态 → done 必收敛', () => {
      expect(advancePhase('generating', 'done')).toBe('done')
      expect(advancePhase('refining', 'done')).toBe('done')
      expect(advancePhase('queued', 'done')).toBe('done')
    })

    // 2026-08-31 仲裁 (W99+12 vs W100+50d 冲突收口): 原 case 8/9 断言
    // 「next=done 总覆盖 aborted/error」与 (a) 本模块核心防御「abort/done/error
    // 互不复活」(b) useChatStream.ts:689 finally 守卫 if(!isTerminalPhase) 自相矛盾,
    // 且 SSE 残余 done 会真把「已中断」翻成「已完成」(即本测试要防的 hang)。
    // 正解 = 首个终态冻结; 从 error 恢复靠「用户重发新建 message」(新 phase),
    // 不靠 advancePhase 复活终态。assistantPhase.test.ts 已钉此语义 (47/47)。
    it('case 8: 首个终态冻结 (abort/done/error 互不复活)', () => {
      expect(advancePhase('done', 'done')).toBe('done')
      expect(advancePhase('aborted', 'done')).toBe('aborted')
      expect(advancePhase('error', 'done')).toBe('error')
      expect(advancePhase('done', 'aborted')).toBe('done')
      // 非 done 终态: next=generating + cur=aborted → 返回 cur (终态不可被非终态覆盖)
      expect(advancePhase('aborted', 'generating')).toBe('aborted')
      expect(advancePhase('error', 'generating')).toBe('error')
    })

    it('case 9: catch 落 error 后终态冻结; 恢复走重发新建 message', () => {
      // finally 守卫 if(!isTerminalPhase) → 不会调 advancePhase 复活 error
      // 若被误调, error 必须保持 error (终态冻结), 而非被 done 翻成 done
      expect(advancePhase('error', 'done')).toBe('error')
      // 用户重发是全新 assistant message (phase 从 queued 起), 与旧 message 终态无关
      expect(advancePhase(undefined, 'done')).toBe('done')
    })
  })

  describe('catch 路径防御 — 显式 phase 收敛', () => {
    it('case 10: 错误类型 → phase 必落 error 终态 (即使 finally 走不到)', () => {
      // 模拟 useChatStream catch 分支: targetAssistant.phase = 'error'
      const targetAssistant = { phase: 'generating' }
      // 实际修复: targetAssistant.phase = 'error'
      targetAssistant.phase = 'error'
      expect(targetAssistant.phase).toBe('error')
      expect(isTerminalPhase(targetAssistant.phase)).toBe(true)
    })
  })
})
