import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { StreamCitationEntry } from '../../src/shared/chat-types'

/**
 * Phase 4-A: KnowledgeService unit tests.
 *
 * 策略:
 * - 在 globalThis 上 mock window.api.api.request (Phase 3-D 同样的 sentinel 模式)
 * - 验证 service methods 委托给 IPC gateway 正确路径/payload
 * - 验证 success / error / 不合法 id 三种分支
 *
 * 注意: 不 mock api/knowledge 模块 (避免 module-level mock 副作用),
 * 直接 mock 最底层: window.api.api.request, service 的 transparent delegate 验证即可.
 */

const mockRequest = vi.fn()

beforeEach(() => {
  mockRequest.mockReset()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(globalThis as any).window = {
    api: {
      api: {
        request: mockRequest
      },
      auth: { /* unused */ },
      session: { /* unused */ },
      chat: { /* unused */ }
    }
  }
})

/** 动态 import (确保 mock 在 import 之前生效, 但因 mock 用 globalThis, 顺序不严) */
async function importService(): Promise<typeof import('../../src/renderer/src/services/knowledge.service')> {
  return await import('../../src/renderer/src/services/knowledge.service')
}

describe('KnowledgeService.getCategories', () => {
  it('成功: 转发到 GET /knowledge/categories', async () => {
    const fake: { name: string; count: number }[] = [
      { name: '微纳米气泡', count: 18 },
      { name: 'DFT 计算', count: 12 }
    ]
    mockRequest.mockResolvedValueOnce({ ok: true, data: fake })

    const { knowledgeService } = await importService()
    const r = await knowledgeService.getCategories()

    expect(mockRequest).toHaveBeenCalledOnce()
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        path: '/knowledge/categories'
      })
    )
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toEqual(fake)
  })

  it('错误: 上游返回 { ok: false } 透传', async () => {
    mockRequest.mockResolvedValueOnce({
      ok: false,
      error: { code: 'TIMEOUT', message: '服务端超时' }
    })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getCategories()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.code).toBe('TIMEOUT')
  })
})

describe('KnowledgeService.listKnowledge', () => {
  it('成功: 查询参数合并到 payload', async () => {
    mockRequest.mockResolvedValueOnce({
      ok: true,
      data: { items: [], total: 0 }
    })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.listKnowledge({
      category: '微纳米气泡',
      keyword: '机理',
      page: 2,
      pageSize: 10
    })
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        path: '/knowledge',
        query: expect.objectContaining({
          category: '微纳米气泡',
          keyword: '机理',
          page: 2,
          page_size: 10
        })
      })
    )
    expect(r.ok).toBe(true)
  })

  it('默认参数 (空对象) 时 page=1 page_size=20', async () => {
    mockRequest.mockResolvedValueOnce({
      ok: true,
      data: { items: [], total: 0 }
    })
    const { knowledgeService } = await importService()
    await knowledgeService.listKnowledge()
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        path: '/knowledge',
        query: expect.objectContaining({
          page: 1,
          page_size: 20
        })
      })
    )
  })
})

describe('KnowledgeService.getKnowledge', () => {
  it('成功: id=42 -> GET /knowledge/42', async () => {
    mockRequest.mockResolvedValueOnce({
      ok: true,
      data: { id: 42, title: 't', content: 'c' }
    })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledge(42)
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', path: '/knowledge/42' })
    )
    expect(r.ok).toBe(true)
  })

  it('IPC 错误透传 (不抛)', async () => {
    mockRequest.mockResolvedValueOnce({
      ok: false,
      error: { code: 'NOT_FOUND', message: '文档不存在' }
    })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledge(99999)
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.code).toBe('NOT_FOUND')
      expect(r.error.message).toContain('不存在')
    }
  })
})

describe('KnowledgeService.getKnowledgeForCitation (Phase 4-A NEW)', () => {
  function citationOf(knowledgeId: number): StreamCitationEntry {
    return {
      type: 'citation',
      knowledgeId,
      title: 't',
      snippet: 's',
      score: 0.9
    } as StreamCitationEntry
  }

  it('valid knowledgeId -> delegate GET /knowledge/{id}', async () => {
    mockRequest.mockResolvedValueOnce({
      ok: true,
      data: { id: 7, title: 'x', content: 'y' }
    })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledgeForCitation(citationOf(7))
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', path: '/knowledge/7' })
    )
    expect(r.ok).toBe(true)
  })

  it('invalid id (0) -> 返回 error, 不调 IPC', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledgeForCitation(citationOf(0))
    expect(mockRequest).not.toHaveBeenCalled()
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.code).toBe('INVALID_INPUT')
      expect(r.error.message).toContain('无效 knowledgeId')
    }
  })

  it('invalid id (负数) -> 返回 error', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledgeForCitation(citationOf(-5))
    expect(mockRequest).not.toHaveBeenCalled()
    expect(r.ok).toBe(false)
  })

  it('invalid id (NaN) -> 返回 error', async () => {
    const citation: StreamCitationEntry = {
      type: 'citation',
      knowledgeId: NaN,
      title: 't'
    } as StreamCitationEntry
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledgeForCitation(citation)
    expect(mockRequest).not.toHaveBeenCalled()
    expect(r.ok).toBe(false)
  })

  it('IPC error 透传 (NO_ACTIVE_SESSION from auth refresh fail)', async () => {
    mockRequest.mockResolvedValueOnce({
      ok: false,
      error: { code: 'NO_ACTIVE_SESSION', message: '会话已过期' }
    })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledgeForCitation(citationOf(42))
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.code).toBe('NO_ACTIVE_SESSION')
  })
})

describe('KnowledgeService Phase 4+ 留口 (Phase 4-A 必须 not implemented)', () => {
  it('getManyKnowledge 抛 NOT_IMPLEMENTED', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getManyKnowledge([1, 2, 3])
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.code).toBe('NOT_IMPLEMENTED')
  })

  it('listItems 抛 NOT_IMPLEMENTED', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.listItems(50)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.code).toBe('NOT_IMPLEMENTED')
  })

  it('cacheLookup 永远返回 null', async () => {
    const { knowledgeService } = await importService()
    expect(knowledgeService.cacheLookup(42)).toBeNull()
  })
})
