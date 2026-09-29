// M2-3b 远程知识库 —— 全部离线，HTTP 注入式（契约来自 app/api/v1/knowledge.py 只读调研）
import { describe, expect, it } from 'vitest'
import { CloudApiClient, type CloudHttpFn, type CloudHttpRequest, type CloudHttpResponse, type CloudTokens } from '@main/services/cloud/api-client'
import {
  RemoteKnowledgeService,
  inaccessibleMessage,
  knowledgeErrorMessage,
  knowledgeGuidance,
  knowledgeSourceState,
  normalizeKnowledgeDetail,
  normalizeKnowledgeItem,
  normalizeKnowledgePage,
  normalizeSearchResults
} from '@main/services/cloud/knowledge'

function res(status: number, json: unknown, headers: Record<string, string> = {}): CloudHttpResponse {
  return { status, headers, text: typeof json === 'string' ? json : JSON.stringify(json) }
}

/** 按脚本回应的注入式 HTTP（记录请求） */
function harness(
  script: ((req: CloudHttpRequest) => CloudHttpResponse | Promise<CloudHttpResponse>)[],
  tokens: CloudTokens | null = { accessToken: 'AT1', refreshToken: 'RT1' }
): { svc: RemoteKnowledgeService; requests: CloudHttpRequest[]; refreshed: CloudTokens[] } {
  const requests: CloudHttpRequest[] = []
  let i = 0
  const http: CloudHttpFn = async (req) => {
    requests.push(req)
    const step = script[Math.min(i, script.length - 1)]!
    i += 1
    return step(req)
  }
  const refreshed: CloudTokens[] = []
  const svc = new RemoteKnowledgeService({
    client: new CloudApiClient({ http, baseUrl: 'https://agent.mnb-lab.cn' }),
    tokens: () => tokens,
    onTokensRefreshed: (t) => refreshed.push(t)
  })
  return { svc, requests, refreshed }
}

// 服务端真实形状样例（字段名按 schemas/knowledge.py，不含任何真实科研内容）
const item = (id: number, over: Record<string, unknown> = {}): Record<string, unknown> => ({
  id,
  title: `条目 ${id}`,
  category: '实验方法',
  tags: ['臭氧', '微纳米气泡'],
  summary: '摘要占位',
  snippet: '正文前 200 字占位',
  visibility: 'team',
  created_at: '2026-09-01T10:00:00',
  updated_at: '2026-09-02T11:00:00',
  ...over
})

// ---------------------------------------------------------------- 1 适配回放（≥5）

describe('契约适配回放', () => {
  it('列表：GET /api/v1/knowledge 分页参数正确，解析 {items,total}', async () => {
    const { svc, requests } = harness([() => res(200, { items: [item(1), item(2)], total: 42 })])
    const r = await svc.list({ page: 2, pageSize: 20, category: '实验方法' })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.total).toBe(42)
      expect(r.data.items).toHaveLength(2)
      expect(r.data.items[0]).toMatchObject({ id: 1, title: '条目 1', visibility: 'team' })
      expect(r.data.page).toBe(2)
    }
    const url = new URL(requests[0]!.url)
    expect(url.pathname).toBe('/api/v1/knowledge')
    expect(url.searchParams.get('page')).toBe('2')
    expect(url.searchParams.get('page_size')).toBe('20')
    expect(url.searchParams.get('category')).toBe('实验方法')
    expect(requests[0]!.headers['authorization']).toBe('Bearer AT1')
  })

  it('检索：走**服务端**检索端点（不用本地 bigram），q/top_k 正确', async () => {
    const { svc, requests } = harness([() => res(200, [item(7, { score: 0.91 })])])
    const r = await svc.search('微纳米气泡', 5)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data[0]).toMatchObject({ id: 7, title: '条目 7' })
    const url = new URL(requests[0]!.url)
    expect(url.pathname).toBe('/api/v1/knowledge/search/semantic')
    expect(url.searchParams.get('q')).toBe('微纳米气泡')
    expect(url.searchParams.get('top_k')).toBe('5')
  })

  it('空检索词不发请求（本地短路）', async () => {
    const { svc, requests } = harness([() => res(200, [])])
    const r = await svc.search('   ')
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toEqual([])
    expect(requests).toHaveLength(0)
  })

  it('详情：GET /knowledge/{id}，解析正文与格式化正文', async () => {
    const { svc, requests } = harness([
      () => res(200, item(9, { content: '正文占位', formatted_content: '# 格式化占位', source_type: 'paper' }))
    ])
    const r = await svc.get(9)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toMatchObject({ id: 9, content: '正文占位', formattedContent: '# 格式化占位', sourceType: 'paper' })
    expect(requests[0]!.url).toBe('https://agent.mnb-lab.cn/api/v1/knowledge/9')
  })

  it('新建：POST 携带 title/content，201 解析返回体', async () => {
    const { svc, requests } = harness([() => res(201, item(100, { title: '新条目' }))])
    const r = await svc.create({ title: '新条目', content: '正文', category: '实验方法', tags: ['a'] })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.id).toBe(100)
    expect(requests[0]!.method).toBe('POST')
    expect(JSON.parse(String(requests[0]!.body))).toEqual({ title: '新条目', content: '正文', category: '实验方法', tags: ['a'] })
  })

  it('编辑：PUT 只带传入字段（不改的字段不下发）', async () => {
    const { svc, requests } = harness([() => res(200, item(5, { title: '改后标题' }))])
    const r = await svc.update(5, { title: '改后标题' })
    expect(r.ok).toBe(true)
    expect(requests[0]!.method).toBe('PUT')
    expect(requests[0]!.url).toBe('https://agent.mnb-lab.cn/api/v1/knowledge/5')
    expect(JSON.parse(String(requests[0]!.body))).toEqual({ title: '改后标题' })
  })

  it('删除：DELETE 204 空体不解析 JSON 也不报错', async () => {
    const { svc, requests } = harness([() => res(204, '')])
    const r = await svc.remove(3)
    expect(r.ok).toBe(true)
    expect(requests[0]!.method).toBe('DELETE')
  })
})

// ---------------------------------------------------------------- 2 可见性（≥2）

describe('可见性语义（沿用服务端，不自造权限）', () => {
  it('visibility 字段原样透传（private/team/public 都照实给 UI，不做本地过滤）', async () => {
    const { svc } = harness([
      () => res(200, { items: [item(1, { visibility: 'private' }), item(2, { visibility: 'team' }), item(3, { visibility: 'public' })], total: 3 })
    ])
    const r = await svc.list()
    expect(r.ok).toBe(true)
    if (r.ok) {
      // ★ 三条都保留：客户端**不得**因 private 而本地剔除（服务端已按 visibility IN ('team','public') 过滤）
      expect(r.data.items.map((x) => x.visibility)).toEqual(['private', 'team', 'public'])
      expect(r.data.items).toHaveLength(3)
    }
  })

  it('403 不可见：中性文案，不暴露服务端原文', async () => {
    const { svc } = harness([() => res(403, { error: { code: 'FORBIDDEN', message: 'no permission on knowledge 12' } })])
    const r = await svc.get(12)
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.kind).toBe('auth')
      const msg = knowledgeErrorMessage(r.error)
      expect(msg).not.toMatch(/FORBIDDEN|no permission|12/)
      // 403 走不可见中性文案（detail 含 forbidden 时）
      expect(knowledgeErrorMessage({ kind: 'client', message: 'x', detail: '403 forbidden' })).toBe(inaccessibleMessage())
    }
  })
})

// ---------------------------------------------------------------- 3 链路（≥3）

describe('链路：续期 / 未绑定 / 断网', () => {
  it('401 → 自动续期 → 重放列表请求，并把新令牌回写', async () => {
    const { svc, requests, refreshed } = harness([
      () => res(401, { error: { code: 'AUTH_ERROR', message: 'expired' } }),
      () => res(200, { access_token: 'AT2', token_type: 'bearer' }),
      () => res(200, { items: [item(1)], total: 1 })
    ])
    const r = await svc.list()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.total).toBe(1)
    expect(requests.map((q) => new URL(q.url).pathname)).toEqual([
      '/api/v1/knowledge',
      '/api/v1/auth/refresh',
      '/api/v1/knowledge'
    ])
    expect(requests[2]!.headers['authorization']).toBe('Bearer AT2')
    expect(refreshed).toEqual([{ accessToken: 'AT2', refreshToken: 'RT1' }])
  })

  it('未绑定：不发任何请求，直接给出引导态', async () => {
    const { svc, requests } = harness([() => res(200, { items: [], total: 0 })], null)
    const r = await svc.list()
    expect(r.ok).toBe(false)
    expect(requests).toHaveLength(0) // ★ 未绑定不该打服务器
    if (!r.ok) expect(r.error.message).toContain('尚未绑定')
  })

  it('断网：连接类错误 → 状态判为 offline，引导文案指向网络', async () => {
    const { svc } = harness([
      () => {
        throw new Error('getaddrinfo ENOTFOUND agent.mnb-lab.cn')
      }
    ])
    const r = await svc.list()
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.kind).toBe('network')
      const state = knowledgeSourceState({ status: 'bound' }, r.error)
      expect(state).toBe('offline')
      const g = knowledgeGuidance(state)
      expect(g.title).toBe('当前离线')
      expect(g.canOpenSettings).toBe(false)
    }
  })

  it('绑定状态 → 数据源状态与引导文案（unbound/expired/ready 全覆盖）', () => {
    expect(knowledgeSourceState({ status: 'unbound' })).toBe('unbound')
    expect(knowledgeSourceState({ status: 'expired' })).toBe('expired')
    expect(knowledgeSourceState({ status: 'bound' })).toBe('ready')
    expect(knowledgeGuidance('unbound').canOpenSettings).toBe(true)
    expect(knowledgeGuidance('unbound').hint).toContain('设置')
    expect(knowledgeGuidance('expired').title).toContain('失效')
    expect(knowledgeGuidance('ready').title).toBe('')
  })
})

// ---------------------------------------------------------------- 4 协议健壮（≥2）

describe('畸形响应不崩溃', () => {
  it('列表响应缺 items / 类型错乱 → 空列表 + total 兜底（不抛）', () => {
    expect(normalizeKnowledgePage(null, 1, 20)).toMatchObject({ items: [], total: 0, page: 1, pageSize: 20 })
    expect(normalizeKnowledgePage({ items: 'oops', total: 'x' }, 1, 20).items).toEqual([])
    expect(normalizeKnowledgePage([item(1)], 1, 20).items).toHaveLength(1) // 容忍裸数组
    expect(normalizeKnowledgePage({ items: [item(1)], total: 9 }, 1, 20).total).toBe(9)
  })

  it('单条畸形：缺 id 或 title 的项被丢弃，不污染列表', () => {
    expect(normalizeKnowledgeItem({ title: '无 id' })).toBeNull()
    expect(normalizeKnowledgeItem({ id: 1 })).toBeNull()
    expect(normalizeKnowledgeItem('string')).toBeNull()
    expect(normalizeKnowledgeItem(null)).toBeNull()
    // 字符串数字 id 可接受
    expect(normalizeKnowledgeItem({ id: '7', title: 'x' })?.id).toBe(7)
    const page = normalizeKnowledgePage({ items: [{ id: 1, title: 'ok' }, { title: 'bad' }, null], total: 2 }, 1, 20)
    expect(page.items).toHaveLength(1)
  })

  it('详情响应非对象 / 检索响应非数组 → 明确报错或空数组，不抛异常', async () => {
    const { svc } = harness([() => res(200, '"just a string"')])
    const r = await svc.get(1)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.kind).toBe('malformed')
    expect(normalizeSearchResults(null)).toEqual([])
    expect(normalizeSearchResults({ items: [item(2)] })).toHaveLength(1)
    expect(normalizeKnowledgeDetail(123)).toBeNull()
  })
})

// ---------------------------------------------------------------- 9 地址刷新（模拟 E2E 抓到的缺陷）

describe('服务器地址刷新（绑定后改地址必须生效）', () => {
  it('baseUrl 提供者每次请求前生效：构造时是默认地址，绑定后指向新地址', async () => {
    const requests: CloudHttpRequest[] = []
    const http: CloudHttpFn = async (req) => {
      requests.push(req)
      return res(200, { items: [], total: 0 })
    }
    let current = 'https://agent.mnb-lab.cn'
    const svc = new RemoteKnowledgeService({
      client: new CloudApiClient({ http, baseUrl: current }),
      tokens: () => ({ accessToken: 'AT', refreshToken: 'RT' }),
      baseUrl: () => current
    })
    await svc.list()
    expect(requests[0]!.url.startsWith('https://agent.mnb-lab.cn')).toBe(true)
    // 用户中途改绑定（如自建/局域网）→ 下一次请求必须打到新地址
    current = 'http://127.0.0.1:8899'
    await svc.list()
    expect(requests[1]!.url.startsWith('http://127.0.0.1:8899')).toBe(true)
  })
})

// ---------------------------------------------------------------- 10 分页拉全（真机数量对不上根因）

describe('列表分页：listAll 拉全所有页（防静默截断）', () => {
  /** 造一个「按页切片」的服务端脚本 */
  const pagedScript = (all: Record<string, unknown>[]) => (req: CloudHttpRequest): CloudHttpResponse => {
    const u = new URL(req.url)
    const page = Number(u.searchParams.get('page') ?? 1)
    const size = Number(u.searchParams.get('page_size') ?? 20)
    return res(200, { items: all.slice((page - 1) * size, page * size), total: all.length })
  }

  it('服务端 250 条 → 分 3 页取全，且按 total 提前停止（不多发第 4 页）', async () => {
    const all = Array.from({ length: 250 }, (_, i) => item(i + 1))
    const { svc, requests } = harness([pagedScript(all)])
    const r = await svc.listAll({ pageSize: 100 })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.items).toHaveLength(250)
      expect(r.data.total).toBe(250)
    }
    expect(requests.map((q) => new URL(q.url).searchParams.get('page'))).toEqual(['1', '2', '3'])
  })

  it('恰好整页 200 条 → 第 2 页达 total 即停（不多发一次空请求）', async () => {
    const all = Array.from({ length: 200 }, (_, i) => item(i + 1))
    const { svc, requests } = harness([pagedScript(all)])
    const r = await svc.listAll({ pageSize: 100 })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.items).toHaveLength(200)
    expect(requests).toHaveLength(2)
  })

  it('单页内（<100 条）→ 只请求 1 次', async () => {
    const all = Array.from({ length: 37 }, (_, i) => item(i + 1))
    const { svc, requests } = harness([pagedScript(all)])
    const r = await svc.listAll()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.items).toHaveLength(37)
    expect(requests).toHaveLength(1)
  })

  it('服务端 total 虚高（> 实有）→ 触到 maxPages 即停，不无限循环', async () => {
    const { svc, requests } = harness([() => res(200, { items: [item(1)], total: 99999 })])
    const r = await svc.listAll({ pageSize: 100, maxPages: 3 })
    expect(r.ok).toBe(true)
    // 每页都返回同一条（模拟异常服务端）→ 恰好请求 maxPages 次后停
    expect(requests).toHaveLength(3)
    if (r.ok) expect(r.data.total).toBe(99999) // 如实回传服务端 total，便于上层发现异常
  })

  it('中途某页失败 → 整体失败（不返回半截列表，避免用户以为「就这么多」）', async () => {
    const all = Array.from({ length: 250 }, (_, i) => item(i + 1))
    const script = [pagedScript(all), pagedScript(all), () => res(500, { error: { code: 'BOOM', message: 'x' } })]
    const { svc } = harness(script)
    const r = await svc.listAll({ pageSize: 100 })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error.kind).toBe('server')
  })
})

// ---------------------------------------------------------------- 11 真机数量排查（8~9 vs 856）

describe('数量排查：856 条真实场景 + total 口径', () => {
  /** 服务端按页切片（形状照 app/api/v1/knowledge.py 的 KnowledgeList(items, total)） */
  const paged856 = (req: CloudHttpRequest): CloudHttpResponse => {
    const u = new URL(req.url)
    const page = Number(u.searchParams.get('page') ?? 1)
    const size = Number(u.searchParams.get('page_size') ?? 20)
    const all = Array.from({ length: 856 }, (_, i) => item(i + 1))
    return res(200, { items: all.slice((page - 1) * size, page * size), total: all.length })
  }

  it('★ 856 条：9 页取全（100×8 + 56），断言累计条数与请求页序', async () => {
    const { svc, requests } = harness([paged856])
    const r = await svc.listAll({ pageSize: 100 })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.items).toHaveLength(856)
      expect(r.data.total).toBe(856)
    }
    expect(requests).toHaveLength(9)
    expect(requests.map((q) => new URL(q.url).searchParams.get('page'))).toEqual([
      '1', '2', '3', '4', '5', '6', '7', '8', '9'
    ])
    // 参数形状与 web 端 useKnowledge.js 完全一致（只带 page / page_size）
    const u = new URL(requests[0]!.url)
    expect([...u.searchParams.keys()].sort()).toEqual(['page', 'page_size'])
    expect(u.searchParams.get('page_size')).toBe('100')
  })

  it('★ 请求形状与 web 端逐字对齐：路径 /api/v1/knowledge，无额外参数', async () => {
    const { svc, requests } = harness([paged856])
    await svc.listAll()
    const u = new URL(requests[0]!.url)
    expect(u.pathname).toBe('/api/v1/knowledge')
    // 不得带 has_file / category / source_type / keyword 等过滤（那会缩小集合）
    expect(u.searchParams.has('has_file')).toBe(false)
    expect(u.searchParams.has('category')).toBe(false)
    expect(u.searchParams.has('source_type')).toBe(false)
    expect(u.searchParams.has('keyword')).toBe(false)
  })

  it('响应用 pagination.total 包裹时也能取到（对齐 web 的读取优先级）', async () => {
    const { svc } = harness([
      () => res(200, { items: [item(1), item(2)], pagination: { total: 856, page: 1, page_size: 2 } }),
      () => res(200, { items: [], pagination: { total: 856 } })
    ])
    const r = await svc.list({ page: 1, pageSize: 2 })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.total).toBe(856) // ★ 不是本页条数 2
      expect(r.data.totalFromServer).toBe(true)
    }
  })

  it('响应完全没有 total 字段 → 退化为本页条数并标记 totalFromServer=false（可被上层发现）', async () => {
    const { svc } = harness([() => res(200, { items: [item(1), item(2), item(3)] })])
    const r = await svc.list()
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.total).toBe(3)
      expect(r.data.totalFromServer).toBe(false)
    }
  })

  it('诊断日志含页号/条数/total，且不含任何文档内容字段', async () => {
    const logs: string[] = []
    const requests: CloudHttpRequest[] = []
    let i = 0
    const http: CloudHttpFn = async (req) => {
      requests.push(req)
      i += 1
      return paged856(req)
    }
    const svc = new RemoteKnowledgeService({
      client: new CloudApiClient({ http, baseUrl: 'https://agent.mnb-lab.cn' }),
      tokens: () => ({ accessToken: 'AT', refreshToken: 'RT' }),
      log: (m) => logs.push(m)
    })
    await svc.listAll({ pageSize: 100 })
    expect(logs.some((l) => /page=1 page_size=100 → items=100 total=856/.test(l))).toBe(true)
    expect(logs.some((l) => /GET \/api\/v1\/knowledge\?page=1&page_size=100/.test(l))).toBe(true)
    // 隐私：日志只含数字与路径，不含 title/snippet/summary 等正文相关字段名
    expect(logs.join('\n')).not.toMatch(/title|snippet|summary|content/i)
  })
})
