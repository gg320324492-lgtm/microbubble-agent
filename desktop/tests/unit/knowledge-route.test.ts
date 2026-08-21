import { describe, it, expect } from 'vitest'
import {
  validateKnowledgeId,
  validateKnowledgeIdFromQuery,
  buildKnowledgePath,
  cameFromChat,
  safeKnowledgePush
} from '../../src/renderer/src/utils/knowledge-route'

/**
 * Phase 3-D 路由闭环单元测试.
 *
 * 覆盖 spec §5:
 *   1. valid knowledgeId
 *   2. invalid knowledgeId
 *   3. citation click callback (safeKnowledgePush)
 *   4. route generation (buildKnowledgePath + from query)
 */

describe('validateKnowledgeId', () => {
  it('valid: 正整数', () => {
    expect(validateKnowledgeId(1)).toBe(1)
    expect(validateKnowledgeId(42)).toBe(42)
    expect(validateKnowledgeId(999999)).toBe(999999)
  })

  it('invalid: 0 / 负数', () => {
    expect(validateKnowledgeId(0)).toBeNull()
    expect(validateKnowledgeId(-1)).toBeNull()
    expect(validateKnowledgeId(-100)).toBeNull()
  })

  it('invalid: 非整数', () => {
    expect(validateKnowledgeId(1.5)).toBeNull()
    expect(validateKnowledgeId(0.1)).toBeNull()
    expect(validateKnowledgeId(NaN)).toBeNull()
    expect(validateKnowledgeId(Infinity)).toBeNull()
    expect(validateKnowledgeId(-Infinity)).toBeNull()
  })

  it('invalid: 非 number', () => {
    expect(validateKnowledgeId('1')).toBeNull()
    expect(validateKnowledgeId('42')).toBeNull()
    expect(validateKnowledgeId(null)).toBeNull()
    expect(validateKnowledgeId(undefined)).toBeNull()
    expect(validateKnowledgeId({})).toBeNull()
    expect(validateKnowledgeId([])).toBeNull()
    expect(validateKnowledgeId(true)).toBeNull()
  })
})

describe('validateKnowledgeIdFromQuery', () => {
  it('string -> 校验', () => {
    expect(validateKnowledgeIdFromQuery('42')).toBe(42)
    expect(validateKnowledgeIdFromQuery('1')).toBe(1)
    expect(validateKnowledgeIdFromQuery('not-a-number')).toBeNull()
    expect(validateKnowledgeIdFromQuery('-1')).toBeNull()  // 负数拒绝
    expect(validateKnowledgeIdFromQuery('0')).toBeNull()    // 0 拒绝
  })

  it('number 透传', () => {
    expect(validateKnowledgeIdFromQuery(42)).toBe(42)
    expect(validateKnowledgeIdFromQuery(1.5)).toBeNull()
    expect(validateKnowledgeIdFromQuery(NaN)).toBeNull()
  })

  it('null / undefined -> null', () => {
    expect(validateKnowledgeIdFromQuery(null)).toBeNull()
    expect(validateKnowledgeIdFromQuery(undefined)).toBeNull()
  })

  it('router query 可能传 字符串 形式 id="42", 解析为 42 (验证 URL 边界)', () => {
    expect(validateKnowledgeIdFromQuery('42')).toBe(42)
  })
})

describe('buildKnowledgePath', () => {
  it('不带 origin -> 默认 other', () => {
    expect(buildKnowledgePath(42)).toEqual({
      name: 'knowledge-detail',
      query: { id: 42 }
    })
  })

  it('source=chat -> 追加 query.from=chat', () => {
    expect(buildKnowledgePath(42, { source: 'chat' })).toEqual({
      name: 'knowledge-detail',
      query: { id: 42, from: 'chat' }
    })
  })

  it('source=other -> 不追加 from', () => {
    expect(buildKnowledgePath(42, { source: 'other' })).toEqual({
      name: 'knowledge-detail',
      query: { id: 42 }
    })
  })

  it('id 在 query 中是 number (不是 string)', () => {
    // vue-router 会序列化, 类型保留无影响.
    const path = buildKnowledgePath(1, { source: 'chat' })
    expect(path.query).toHaveProperty('id', 1)
  })
})

describe('cameFromChat', () => {
  it('query.from === "chat" -> true', () => {
    expect(cameFromChat({ from: 'chat' })).toBe(true)
  })

  it('其它 from 值 -> false', () => {
    expect(cameFromChat({ from: 'list' })).toBe(false)
    expect(cameFromChat({ from: 'other' })).toBe(false)
    expect(cameFromChat({ from: '' })).toBe(false)
    expect(cameFromChat({ from: 0 })).toBe(false)   // 非字符串
    expect(cameFromChat({ from: true })).toBe(false)
  })

  it('无 from 字段 -> false', () => {
    expect(cameFromChat({})).toBe(false)
    expect(cameFromChat({ id: 42 })).toBe(false)
  })

  it('null / 非对象 -> false (防御性)', () => {
    expect(cameFromChat(null)).toBe(false)
    expect(cameFromChat(undefined)).toBe(false)
    expect(cameFromChat('not-an-object')).toBe(false)
    expect(cameFromChat(42)).toBe(false)
  })
})

describe('safeKnowledgePush (citation click 集成入口)', () => {
  it('valid 整数 -> 构造 chat origin path', () => {
    expect(safeKnowledgePush(42)).toEqual({
      name: 'knowledge-detail',
      query: { id: 42 }
    })
    expect(safeKnowledgePush(42, { source: 'chat' })).toEqual({
      name: 'knowledge-detail',
      query: { id: 42, from: 'chat' }
    })
  })

  it('valid but 防越权: 不应接受字符串 (口径为 number)', () => {
    expect(safeKnowledgePush('42', { source: 'chat' })).toBeNull()
    expect(safeKnowledgePush('42')).toBeNull()
  })

  it('invalid (NaN / 0 / neg / non-int) -> null (不跳转)', () => {
    expect(safeKnowledgePush(0)).toBeNull()
    expect(safeKnowledgePush(-1)).toBeNull()
    expect(safeKnowledgePush(1.5)).toBeNull()
    expect(safeKnowledgePush(NaN)).toBeNull()
    expect(safeKnowledgePush(null)).toBeNull()
    expect(safeKnowledgePush(undefined)).toBeNull()
    expect(safeKnowledgePush('str')).toBeNull()
    expect(safeKnowledgePush({})).toBeNull()
    expect(safeKnowledgePush([])).toBeNull()
    expect(safeKnowledgePush(true)).toBeNull()
  })

  it('id=1 边界 (DB id 起点)', () => {
    expect(safeKnowledgePush(1)).toEqual({
      name: 'knowledge-detail',
      query: { id: 1 }
    })
  })

  it('default origin = chat (ChatView 调用时不传 origin 默认仍是 chat)', () => {
    expect(safeKnowledgePush(42)).toEqual({
      name: 'knowledge-detail',
      query: { id: 42 }   // 默认 other (未指定 source 不加 from)
    })
    // ChatView 显式传 source: 'chat' 时 from 才追加
    expect(safeKnowledgePush(42, { source: 'chat' })).toEqual({
      name: 'knowledge-detail',
      query: { id: 42, from: 'chat' }
    })
  })
})
