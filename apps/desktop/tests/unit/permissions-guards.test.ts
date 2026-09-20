// M8-3 权限三值 × 作用域梯度 + runaway guard + AbortSource/steering（全部离线）
import { describe, expect, it } from 'vitest'
import {
  DEFAULT_CATEGORY_VALUES,
  EMPTY_STORE,
  PERMISSION_VALUES,
  SCOPE_ORDER,
  applyRule,
  categoryOfPermissionLevel,
  clearRule,
  denyMessage,
  normalizeStore,
  permissionLabel,
  resolvePermission,
  ruleFromChoice,
  scopeLabel,
  type PermissionStore
} from '@main/agent/permissions/policy'
import {
  NO_PROGRESS_THRESHOLD,
  REPEAT_THRESHOLD,
  callSignature,
  evaluateRunaway,
  trailingNoProgressRounds,
  trailingRepeatCount
} from '@main/agent/guards'
import { AbortRegistry, AbortSource, SteeringBuffer, abortMessage } from '@main/agent/abort'

// ---------------------------------------------------------------- 1 权限判定矩阵（≥6）

describe('权限三值 × 作用域梯度 — 判定矩阵', () => {
  it('默认值 = 现行为（只读 allow、写类 ask），三层无规则时落默认', () => {
    expect(DEFAULT_CATEGORY_VALUES).toEqual({ readonly: 'allow', write: 'ask' })
    const r = resolvePermission(EMPTY_STORE, 'write')
    expect(r).toEqual({ value: 'ask', scope: 'default', isDefault: true })
    expect(resolvePermission(EMPTY_STORE, 'readonly').value).toBe('allow')
    // 类别映射沿用现确认流分组
    expect(categoryOfPermissionLevel('auto')).toBe('readonly')
    expect(categoryOfPermissionLevel('confirm')).toBe('write')
  })

  it('单层规则生效并标注来源作用域', () => {
    const s = applyRule(EMPTY_STORE, { category: 'write', value: 'allow', scope: 'session' })
    expect(resolvePermission(s, 'write')).toEqual({ value: 'allow', scope: 'session', isDefault: false })
    const g = applyRule(EMPTY_STORE, { category: 'readonly', value: 'ask', scope: 'global' })
    expect(resolvePermission(g, 'readonly')).toEqual({ value: 'ask', scope: 'global', isDefault: false })
  })

  it('近覆盖远：session > workspace > global', () => {
    let s: PermissionStore = EMPTY_STORE
    s = applyRule(s, { category: 'write', value: 'deny', scope: 'global' })
    s = applyRule(s, { category: 'write', value: 'ask', scope: 'workspace' })
    // workspace 比 global 近 → 取 workspace（但注意 deny 否决规则见下一例）
    const onlyNonDeny = applyRule(EMPTY_STORE, { category: 'write', value: 'allow', scope: 'global' })
    const withNear = applyRule(onlyNonDeny, { category: 'write', value: 'ask', scope: 'workspace' })
    expect(resolvePermission(withNear, 'write')).toEqual({ value: 'ask', scope: 'workspace', isDefault: false })
    const withNearest = applyRule(withNear, { category: 'write', value: 'allow', scope: 'session' })
    expect(resolvePermission(withNearest, 'write')).toEqual({ value: 'allow', scope: 'session', isDefault: false })
  })

  it('**deny 否决**：任一作用域 deny 一律 deny，更近的 allow 无法覆盖', () => {
    let s: PermissionStore = EMPTY_STORE
    s = applyRule(s, { category: 'write', value: 'deny', scope: 'global' })
    s = applyRule(s, { category: 'write', value: 'allow', scope: 'session' })
    const r = resolvePermission(s, 'write')
    expect(r.value).toBe('deny')
    expect(r.deniedBy).toBe('global') // 指出否决来自哪一层（证据链用）
    // 反向：近端 deny 压远端 allow
    let s2: PermissionStore = EMPTY_STORE
    s2 = applyRule(s2, { category: 'readonly', value: 'allow', scope: 'global' })
    s2 = applyRule(s2, { category: 'readonly', value: 'deny', scope: 'session' })
    expect(resolvePermission(s2, 'readonly').value).toBe('deny')
  })

  it('类别互不影响（改写类不动只读类）', () => {
    const s = applyRule(EMPTY_STORE, { category: 'write', value: 'allow', scope: 'workspace' })
    expect(resolvePermission(s, 'write').value).toBe('allow')
    expect(resolvePermission(s, 'readonly')).toEqual({ value: 'allow', scope: 'default', isDefault: true })
  })

  it('规则写入不可变（不污染入参）且可清除', () => {
    const base = applyRule(EMPTY_STORE, { category: 'write', value: 'allow', scope: 'global' })
    const next = applyRule(base, { category: 'write', value: 'deny', scope: 'session' })
    expect(base.session.write).toBeUndefined() // 原对象未被改动
    expect(next.session.write).toBe('deny')
    const cleared = clearRule(next, 'write', 'session')
    expect(cleared.session.write).toBeUndefined()
    expect(cleared.global.write).toBe('allow')
  })

  it('归一化丢弃非法值/未知键（坏配置不把权限算歪）', () => {
    const n = normalizeStore({
      session: { write: 'yes', readonly: 'allow', bogus: 'deny' },
      workspace: { write: 123 },
      global: { write: 'deny' },
      extra: { write: 'allow' }
    })
    expect(n.session).toEqual({ readonly: 'allow' })
    expect(n.workspace).toEqual({})
    expect(n.global).toEqual({ write: 'deny' })
    expect(resolvePermission(n, 'write').value).toBe('deny')
  })

  it('确认弹窗三选项 → 落库规则映射（仅本次不落库）', () => {
    expect(ruleFromChoice('write', 'allow', 'once')).toBeNull()
    expect(ruleFromChoice('write', 'allow', 'workspace')).toEqual({ category: 'write', value: 'allow', scope: 'workspace' })
    expect(ruleFromChoice('write', 'deny', 'global')).toEqual({ category: 'write', value: 'deny', scope: 'global' })
  })

  it('文案：deny 回喂中性说明；标签齐全', () => {
    const msg = denyMessage('write', 'write_file')
    expect(msg).toContain('write_file')
    expect(msg).toContain('设置')
    expect(msg).not.toMatch(/Error|stack|undefined/)
    expect(PERMISSION_VALUES.map(permissionLabel)).toEqual(['允许', '每次询问', '禁止'])
    expect([...SCOPE_ORDER].map((s) => scopeLabel(s))).toEqual(['本次会话', '此工作区', '全局'])
    expect(scopeLabel('default')).toBe('默认')
  })
})

// ---------------------------------------------------------------- 2 runaway guard（≥3）

describe('runaway guard', () => {
  it('签名稳定：参数键顺序不影响判定', () => {
    expect(callSignature('read_file', { b: 1, a: 2 })).toBe(callSignature('read_file', { a: 2, b: 1 }))
    expect(callSignature('read_file', { a: 1 })).not.toBe(callSignature('read_file', { a: 2 }))
    expect(callSignature('read_file', { a: 1 })).not.toBe(callSignature('grep', { a: 1 }))
    expect(callSignature('grep', undefined)).toContain('grep')
  })

  it('同工具同参数连续 ≥3 次 → abort（含中性提示与命中次数）', () => {
    const sig = callSignature('read_file', { path: 'a.md' })
    expect(evaluateRunaway({ callSignatures: [sig, sig], roundProgress: [] }).action).toBe('none')
    const v = evaluateRunaway({ callSignatures: [sig, sig, sig], roundProgress: [] })
    expect(v.action).toBe('abort')
    expect(v.kind).toBe('repeat-calls')
    expect(v.count).toBe(REPEAT_THRESHOLD)
    expect(v.message).toContain('read_file')
    expect(v.message).toContain('自动停止')
  })

  it('穿插了别的调用 → 不算连击（不误伤正常工作）', () => {
    const a = callSignature('read_file', { path: 'a.md' })
    const b = callSignature('read_file', { path: 'b.md' })
    expect(trailingRepeatCount([a, a, b, a])).toBe(1)
    expect(evaluateRunaway({ callSignatures: [a, a, b, a], roundProgress: [] }).action).toBe('none')
  })

  it('连续 ≥3 轮无写入进展 → 只 warn 不 abort（交用户决定）', () => {
    const v = evaluateRunaway({ callSignatures: [], roundProgress: [true, false, false, false] })
    expect(v.action).toBe('warn')
    expect(v.kind).toBe('no-progress')
    expect(v.count).toBe(NO_PROGRESS_THRESHOLD)
    expect(v.message).toContain('没有产生任何文件改动')
    // 中间有落盘 → 归零
    expect(trailingNoProgressRounds([false, false, true, false])).toBe(1)
    expect(evaluateRunaway({ callSignatures: [], roundProgress: [false, false, true, false] }).action).toBe('none')
  })

  it('硬中止优先于软提示（同时命中时选 abort）', () => {
    const sig = callSignature('write_file', { path: 'x' })
    const v = evaluateRunaway({ callSignatures: [sig, sig, sig], roundProgress: [false, false, false] })
    expect(v.action).toBe('abort')
    expect(v.kind).toBe('repeat-calls')
  })

  it('阈值可配（测试/特殊场景）', () => {
    const sig = callSignature('grep', { pattern: 'x' })
    expect(evaluateRunaway({ callSignatures: [sig, sig], roundProgress: [] }, { repeatThreshold: 2 }).action).toBe('abort')
    expect(evaluateRunaway({ callSignatures: [], roundProgress: [false] }, { noProgressThreshold: 1 }).action).toBe('warn')
  })
})

// ---------------------------------------------------------------- 3 AbortSource + steering（≥3）

describe('AbortSource 统一中止源', () => {
  it('四类原因都能记录，且**首个原因胜出**（幂等）', () => {
    for (const reason of ['user', 'permission', 'runaway', 'shutdown'] as const) {
      const s = new AbortSource(() => 1000)
      expect(s.aborted).toBe(false)
      expect(s.abort(reason, 'd')).toBe(true)
      expect(s.aborted).toBe(true)
      expect(s.abortReason()).toBe(reason)
      expect(s.snapshot()).toEqual({ reason, at: 1000, detail: 'd' })
      // 幂等：第二次不再生效，原因不变
      expect(s.abort('user')).toBe(false)
      expect(s.abortReason()).toBe(reason)
    }
  })

  it('reset 后可复用（下一次任务）', () => {
    const s = new AbortSource(() => 1)
    s.abort('runaway')
    s.reset()
    expect(s.aborted).toBe(false)
    expect(s.abortReason()).toBeNull()
    expect(s.abort('user')).toBe(true)
  })

  it('runaway 触发经 AbortSource 中止（真实联动路径）', () => {
    const s = new AbortSource()
    const sig = callSignature('read_file', { path: 'a' })
    const verdict = evaluateRunaway({ callSignatures: [sig, sig, sig], roundProgress: [] })
    if (verdict.action === 'abort') s.abort('runaway', `repeat=${verdict.count}`)
    expect(s.abortReason()).toBe('runaway')
    expect(s.snapshot()?.detail).toContain('repeat=3')
  })

  it('注册表：按会话取源、退出时中止全部', () => {
    const reg = new AbortRegistry(() => 5)
    const a = reg.for('s1')
    const b = reg.for('s2')
    expect(reg.for('s1')).toBe(a) // 同会话同源
    expect(a).not.toBe(b)
    expect(reg.size()).toBe(2)
    a.abort('user')
    const hit = reg.abortAll('shutdown')
    expect(hit).toEqual(['s2']) // s1 已中止，不重复计入
    expect(b.abortReason()).toBe('shutdown')
    reg.release('s1')
    expect(reg.size()).toBe(1)
  })

  it('四类原因都有面向用户的中性文案', () => {
    for (const r of ['user', 'permission', 'runaway', 'shutdown'] as const) {
      const m = abortMessage(r)
      expect(m.length).toBeGreaterThan(4)
      expect(m).not.toMatch(/Error|undefined|stack/)
    }
  })
})

describe('steering 轮边界注入', () => {
  it('push/drain：取走即清空，不重复注入；空白忽略', () => {
    const buf = new SteeringBuffer()
    buf.push('s1', '先看 b.md', 10)
    buf.push('s1', '   ', 11) // 空白忽略
    buf.push('s1', '别改 a.md', 12)
    expect(buf.pending('s1')).toBe(2)
    const got = buf.drain('s1')
    expect(got.map((m) => m.text)).toEqual(['先看 b.md', '别改 a.md'])
    expect(buf.pending('s1')).toBe(0)
    expect(buf.drain('s1')).toEqual([])
  })

  it('格式化注入文本含来源说明；会话隔离', () => {
    const buf = new SteeringBuffer()
    buf.push('s1', 'A', 1)
    buf.push('s2', 'B', 1)
    const text = SteeringBuffer.format(buf.drain('s1'))
    expect(text).toContain('任务进行中补充')
    expect(text).toContain('A')
    expect(text).not.toContain('B')
    expect(SteeringBuffer.format([])).toBe('')
  })
})
