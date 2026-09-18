// 阿里云 OSS 客户端（M5-2）— 纯逻辑 + 注入 HTTP，零 Electron import。
// 操作: putObject / getObject / listObjects / deleteObject。
// V1 签名: HMAC-SHA1（oss-sig.ts 纯函数），secret 由调用方解密后传入、客户端不落盘。
import type { OssConfig, OssHttpRequest, OssHttpResponse } from './oss-sig'
export type { OssConfig }
import { contentMd5, canonicalResource, ossAuthorization, ossDate, signOssV1 } from './oss-sig'

export type HttpFn = (req: OssHttpRequest) => Promise<OssHttpResponse>

export interface OssObjectSummary {
  key: string
  size: number
  lastModified: string
}

/** 单页列举结果（纯解析，可离线单测） */
export interface OssListPage {
  items: OssObjectSummary[]
  /** 下一页 token；null = 无更多页 */
  nextMarker: string | null
  isTruncated: boolean
}

/** 单页拉取上限（OSS 上限 1000；不显式指定时服务端默认仅 100） */
export const OSS_LIST_PAGE_SIZE = 1000
/** 翻页硬上限，防服务端异常导致死循环 */
export const OSS_LIST_MAX_PAGES = 1000

/**
 * 解析一页 ListObjects 响应（M6-2 清账④）— 纯函数。
 *
 * 关键细节：OSS/S3 的 V1 ListObjects **只在带 delimiter 时**才返回 <NextMarker>；
 * 未带 delimiter（本客户端即如此）时必须用本页最后一条 key 作为下一页 marker，
 * 否则第二页会从头再来 → 死循环。V2 的 <NextContinuationToken> 一并兼容解析。
 */
export function parseListPage(xml: string): OssListPage {
  const items: OssObjectSummary[] = []
  const contents = String(xml ?? '').match(/<Contents>[\s\S]*?<\/Contents>/g) ?? []
  for (const block of contents) {
    const key = block.match(/<Key>([^<]+)<\/Key>/)?.[1] ?? ''
    const size = parseInt(block.match(/<Size>(\d+)<\/Size>/)?.[1] ?? '0')
    const lastModified = block.match(/<LastModified>([^<]+)<\/LastModified>/)?.[1] ?? ''
    if (key) items.push({ key, size, lastModified })
  }

  const isTruncated = /<IsTruncated>\s*true\s*<\/IsTruncated>/i.test(xml)
  const explicit =
    xml.match(/<NextMarker>([^<]*)<\/NextMarker>/)?.[1] ??
    xml.match(/<NextContinuationToken>([^<]*)<\/NextContinuationToken>/)?.[1] ??
    ''
  const trimmed = explicit.trim()
  const nextMarker = trimmed ? trimmed : isTruncated && items.length > 0 ? items[items.length - 1].key : null

  return { items, nextMarker, isTruncated }
}

export class OssClient {
  constructor(
    private readonly config: OssConfig,
    private readonly http: HttpFn
  ) {}

  /** virtual-hosted 风格对象 URL — https://<bucket>.<endpoint-host>/<key>（真机联调整改：路径风格被 OSS SecondLevelDomainForbidden 拒绝） */
  private objectUrl(key: string): string {
    const u = new URL(this.config.endpoint)
    u.hostname = `${this.config.bucket}.${u.hostname}`
    u.pathname = `/${key.split('/').map(encodeURIComponent).join('/')}`
    return u.toString()
  }

  /** virtual-hosted 风格 bucket 列举 URL — https://<bucket>.<endpoint-host>/?prefix=...&marker=...&max-keys=... */
  private bucketListUrl(prefix: string, marker?: string | null, maxKeys?: number): string {
    const u = new URL(this.config.endpoint)
    u.hostname = `${this.config.bucket}.${u.hostname}`
    const params = new URLSearchParams()
    params.set('prefix', prefix)
    if (marker) params.set('marker', marker)
    if (maxKeys) params.set('max-keys', String(maxKeys))
    u.search = params.toString()
    return u.toString()
  }

  /** 通用签名请求发送 */
  private async request(verb: string, key: string, body?: Buffer, contentType?: string): Promise<OssHttpResponse> {
    const date = ossDate()
    const res = canonicalResource(this.config.bucket, key)
    const md5 = body ? contentMd5(body) : ''
    const ct = contentType ?? (body ? 'application/octet-stream' : '')
    const signature = signOssV1({
      verb, contentMd5: md5, contentType: ct, date,
      canonicalizedResource: res, accessKeySecret: this.config.accessKeySecret
    })
    const url = this.objectUrl(key)
    const headers: Record<string, string> = {
      Date: date,
      Authorization: ossAuthorization(this.config.accessKeyId, signature)
    }
    if (md5) headers['Content-MD5'] = md5
    if (ct) headers['Content-Type'] = ct
    const httpRes = await this.http({ method: verb, url, headers, body })
    if (httpRes.status >= 300) {
      const errText = httpRes.body.toString('utf8').slice(0, 300)
      throw new Error(`OSS ${verb} ${key} → HTTP ${httpRes.status}: ${errText}`)
    }
    return httpRes
  }

  async putObject(key: string, data: Buffer): Promise<void> {
    await this.request('PUT', key, data)
  }

  async getObject(key: string): Promise<Buffer> {
    const res = await this.request('GET', key)
    return res.body
  }

  async deleteObject(key: string): Promise<void> {
    await this.request('DELETE', key)
  }

  /**
   * 列出前缀下全部对象（GET bucket + prefix 参数）。
   * prefix 由调用方传全量前缀（如 desktop-backup/）——client 不再内部拼 config.prefix（整改：防双拼）。
   * XML 手动正则解析——只提取 Key/Size/LastModified，不含 CommonPrefixes 等高级结构（局限已注明）。
   */
  /**
   * 列举对象（M6-2 清账④）— continuation token 循环翻页，直到服务端不再截断。
   * <1000 条快照时行为与旧实现一致（单页返回全部）；>1000 条时不再丢数据。
   */
  async listObjects(prefix: string): Promise<OssObjectSummary[]> {
    const results: OssObjectSummary[] = []
    // 按 key 去重：服务端异常（marker 不推进）时可能重复返回同一页，备份列表绝不能出现重复条目
    const seen = new Set<string>()
    let marker: string | null = null
    for (let page = 0; page < OSS_LIST_MAX_PAGES; page++) {
      const listKey = '' // bucket 根（list 操作 key 为空）
      const date = ossDate()
      const res = canonicalResource(this.config.bucket, listKey)
      const signature = signOssV1({
        verb: 'GET', date, canonicalizedResource: res,
        accessKeySecret: this.config.accessKeySecret
      })
      const url = this.bucketListUrl(prefix, marker, OSS_LIST_PAGE_SIZE)
      const httpRes = await this.http({
        method: 'GET', url,
        headers: { Date: date, Authorization: ossAuthorization(this.config.accessKeyId, signature) }
      })
      if (httpRes.status >= 300) {
        const errText = httpRes.body.toString('utf8').slice(0, 200)
        throw new Error(`OSS listObjects → HTTP ${httpRes.status}: ${errText}`)
      }

      const parsed = parseListPage(httpRes.body.toString('utf8'))
      for (const item of parsed.items) {
        if (seen.has(item.key)) continue
        seen.add(item.key)
        results.push(item)
      }

      // 停止条件：未截断 / 无下一页 token / token 未推进（防服务端异常死循环）
      if (!parsed.isTruncated || !parsed.nextMarker) break
      if (parsed.nextMarker === marker) break
      marker = parsed.nextMarker
    }
    return results
  }

  /** listObjects 探测连通性（取前缀前 1 条即证明凭据+网络通） */
  async testConnection(): Promise<{ ok: boolean; error?: string }> {
    try {
      await this.listObjects('')
      return { ok: true }
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) }
    }
  }
}
