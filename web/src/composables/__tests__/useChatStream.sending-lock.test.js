/**
 * 发送锁响应性回归测试 (2026-09-10 停止按钮卡死修复)
 *
 * 事故: sendingSessions 是纯 Set (非响应式), add/delete 不触发 Vue 依赖,
 * isCurrentSessionSending computed 只 track sessionId.value → 永久缓存旧值,
 * 生成结束后"停止"按钮不回弹, 再点 stopGeneration 也因守卫跳过删锁无效。
 * 类 20.189 (ref(Set) 不 triggerRef 同样 stale)。
 *
 * 跑法: npx vitest run src/composables/__tests__/useChatStream.sending-lock.test.js
 */
import { describe, it, expect } from 'vitest'
import { ref, shallowRef, triggerRef, computed, effect } from 'vue'

// ---- 复刻 useChatStream 的锁模式 (纯逻辑, 不拉重组件) ----
function makeLockModule() {
  const sessionId = ref('s1')
  const sendingSessions = shallowRef(new Set())
  const isSending = (sid) => sendingSessions.value.has(sid)
  const markSending = (sid) => { sendingSessions.value.add(sid); triggerRef(sendingSessions) }
  const clearSending = (sid) => { sendingSessions.value.delete(sid); triggerRef(sendingSessions) }
  const isCurrentSessionSending = computed(() => isSending(sessionId.value))
  // stopGeneration 2026-09-10 修复后语义: clearSending 移出 state 守卫, 无条件清锁
  const stopGeneration = (assistant) => {
    if (assistant && assistant.state === 'streaming') assistant.state = 'aborted'
    clearSending(sessionId.value)
  }
  return { sessionId, isCurrentSessionSending, markSending, clearSending, stopGeneration }
}

describe('发送锁响应性 (停止按钮卡死回归)', () => {
  it('markSending/clearSending 驱动 computed 翻转; 纯 Set 模式会失效', async () => {
    const m = makeLockModule()
    let seen = []
    effect(() => { seen.push(m.isCurrentSessionSending.value) })
    expect(seen).toEqual([false])

    m.markSending('s1')
    await Promise.resolve()
    expect(seen[seen.length - 1]).toBe(true)

    m.clearSending('s1')
    await Promise.resolve()
    expect(seen[seen.length - 1]).toBe(false)

    // 反证: 无 triggerRef 的裸 Set (老实现) 不会触发 effect
    const bare = shallowRef(new Set())
    const bareFlag = computed(() => bare.value.has('x'))
    let bareSeen = []
    effect(() => { bareSeen.push(bareFlag.value) })
    bare.value.add('x')
    await Promise.resolve()
    expect(bareSeen[bareSeen.length - 1]).toBe(false) // 缓存未刷新 = 事故重现
  })

  it('stopGeneration 无条件清锁 (state 卡在非 streaming 也能恢复按钮)', async () => {
    const m = makeLockModule()
    m.markSending('s1')
    await Promise.resolve()
    // 事故形态: assistant.state 不是 'streaming' (如已是 idle), 旧守卫会跳过删锁
    m.stopGeneration({ state: 'idle' })
    await Promise.resolve()
    expect(m.isCurrentSessionSending.value).toBe(false)
    // 正常中断路径同样清锁
    m.markSending('s1')
    const a = { state: 'streaming' }
    m.stopGeneration(a)
    expect(a.state).toBe('aborted')
    expect(m.isCurrentSessionSending.value).toBe(false)
  })
})
