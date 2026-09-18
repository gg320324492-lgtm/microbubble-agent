// M6-2 清账④ — OSS listObjects 分页（continuation token 循环，离线假 HTTP）
import { describe, expect, it, vi } from 'vitest'
import { OssClient, parseListPage, type OssObjectSummary } from '@main/services/backup/oss.client'
import type { OssHttpRequest, OssHttpResponse } from '@main/services/backup/oss-sig'

const CFG = {
  bucket: 'mnb-test',
  endpoint: 'https://oss-cn-hangzhou.aliyuncs.com',
  prefix: 'backups/',
  accessKeyId: 'ak',
  accessKeySecret: 'sk'
}

function pageXml(keys: string[], opts: { truncated: boolean; nextMarker?: string }): string {
  const contents = keys
    .map(
      (k, i) =>
        `<Contents><Key>${k}</Key><LastModified>2026-09-19T00:00:0${i}.000Z</LastModified><Size>${100 + i}</Size></Contents>`
    )
    .join('')
  const marker = opts.nextMarker ? `<NextMarker>${opts.nextMarker}</NextMarker>` : ''
  return `<?xml version="1.0" encoding="UTF-8"?><ListBucketResult><Name>mnb-test</Name><Prefix>backups/</Prefix><MaxKeys>1000</MaxKeys><IsTruncated>${opts.truncated}</IsTruncated>${marker}${contents}</ListBucketResult>`
}

/** 假 HTTP：按序返回预置页，并记录每次请求 URL */
function makeHttp(pages: string[]): { http: (req: OssHttpRequest) => Promise<OssHttpResponse>; urls: string[] } {
  const urls: string[] = []
  let i = 0
  return {
    urls,
    http: async (req) => {
      urls.push(req.url)
      const body = pages[Math.min(i, pages.length - 1)]
      i++
      return { status: 200, body: Buffer.from(body, 'utf8') }
    }
  }
}

describe('OSS listObjects 分页 — 多页循环', () => {
  it('两页：第二页请求带 marker=首页末键，结果合并', async () => {
    const { http, urls } = makeHttp([
      pageXml(['backups/a.mnbbak', 'backups/b.mnbbak'], { truncated: true }),
      pageXml(['backups/c.mnbbak'], { truncated: false })
    ])
    const client = new OssClient(CFG, http)
    const items = await client.listObjects('backups/')

    expect(items.map((i: OssObjectSummary) => i.key)).toEqual([
      'backups/a.mnbbak',
      'backups/b.mnbbak',
      'backups/c.mnbbak'
    ])
    expect(urls.length).toBe(2)
    // 首页不带 marker；次页用「本页最后一条 key」作 marker（无 delimiter 时服务端不返回 NextMarker）
    expect(urls[0]).not.toContain('marker=')
    expect(urls[1]).toContain('marker=backups%2Fb.mnbbak')
    expect(urls[1]).toContain('max-keys=1000')
  })

  it('三页：显式 NextMarker 优先，逐页推进直至 IsTruncated=false', async () => {
    const { http, urls } = makeHttp([
      pageXml(['k1', 'k2'], { truncated: true, nextMarker: 'k2' }),
      pageXml(['k3', 'k4'], { truncated: true, nextMarker: 'k4' }),
      pageXml(['k5'], { truncated: false })
    ])
    const client = new OssClient(CFG, http)
    const items = await client.listObjects('')

    expect(items.map((i: OssObjectSummary) => i.key)).toEqual(['k1', 'k2', 'k3', 'k4', 'k5'])
    expect(urls.length).toBe(3)
    expect(urls[1]).toContain('marker=k2')
    expect(urls[2]).toContain('marker=k4')
  })

  it('末页空 continuation：截断但无更多条目时停止，且不重复请求', async () => {
    const { http, urls } = makeHttp([
      pageXml(['only'], { truncated: true }),
      pageXml([], { truncated: false })
    ])
    const client = new OssClient(CFG, http)
    const items = await client.listObjects('backups/')

    expect(items.map((i: OssObjectSummary) => i.key)).toEqual(['only'])
    expect(urls.length).toBe(2)
  })

  it('<1000 条单页行为不变；marker 未推进时不死循环', async () => {
    const single = makeHttp([pageXml(['x', 'y'], { truncated: false })])
    const c1 = new OssClient(CFG, single.http)
    expect((await c1.listObjects('')).length).toBe(2)
    expect(single.urls.length).toBe(1)
    expect(single.urls[0]).not.toContain('marker=')

    // 服务端异常：一直 truncated 且 marker 原地踏步 → 必须收敛（否则死循环）
    const stuck = makeHttp([pageXml(['same'], { truncated: true, nextMarker: 'same' })])
    const c2 = new OssClient(CFG, stuck.http)
    const items = await c2.listObjects('')
    expect(items.length).toBe(1)
    expect(stuck.urls.length).toBe(2) // 第一次无 marker，第二次 marker=same，随后 token 未推进即停止
  })

  it('HTTP 非 2xx 仍抛错（错误路径未被分页逻辑吞掉）', async () => {
    const http = vi.fn(async (): Promise<OssHttpResponse> => ({ status: 403, body: Buffer.from('AccessDenied') }))
    const client = new OssClient(CFG, http)
    await expect(client.listObjects('backups/')).rejects.toThrow(/403/)
  })
})

describe('parseListPage 纯解析', () => {
  it('解析条目/截断标志/显式 token；无显式 token 时用末键兜底', () => {
    const withMarker = parseListPage(pageXml(['a', 'b'], { truncated: true, nextMarker: 'b' }))
    expect(withMarker.isTruncated).toBe(true)
    expect(withMarker.nextMarker).toBe('b')
    expect(withMarker.items[0]).toEqual({ key: 'a', size: 100, lastModified: '2026-09-19T00:00:00.000Z' })

    const noMarker = parseListPage(pageXml(['a', 'b'], { truncated: true }))
    expect(noMarker.nextMarker).toBe('b')

    const v2 = parseListPage(
      '<?xml version="1.0"?><ListBucketResult><IsTruncated>true</IsTruncated><NextContinuationToken>tok-2</NextContinuationToken><Contents><Key>z</Key><Size>1</Size><LastModified>t</LastModified></Contents></ListBucketResult>'
    )
    expect(v2.nextMarker).toBe('tok-2')

    const done = parseListPage(pageXml(['a'], { truncated: false }))
    expect(done.isTruncated).toBe(false)
    expect(done.nextMarker).toBeNull()
  })
})
