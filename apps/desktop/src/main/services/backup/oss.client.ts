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

export class OssClient {
  constructor(
    private readonly config: OssConfig,
    private readonly http: HttpFn
  ) {}

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
    const url = `${this.config.endpoint}/${key}`
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
  async listObjects(prefix: string): Promise<OssObjectSummary[]> {
    const listKey = '' // bucket 根（list 操作 key 为空）
    const date = ossDate()
    const res = canonicalResource(this.config.bucket, listKey)
    const signature = signOssV1({
      verb: 'GET', date, canonicalizedResource: res,
      accessKeySecret: this.config.accessKeySecret
    })
    const url = `${this.config.endpoint}?prefix=${encodeURIComponent(prefix)}`
    const httpRes = await this.http({
      method: 'GET', url,
      headers: { Date: date, Authorization: ossAuthorization(this.config.accessKeyId, signature) }
    })
    if (httpRes.status >= 300) throw new Error(`OSS listObjects → HTTP ${httpRes.status}`)

    // 手动解析 XML（简单正则——不含 continuation/ISO8601 时区高级场景）
    const xml = httpRes.body.toString('utf8')
    const results: OssObjectSummary[] = []
    const contents = xml.match(/<Contents>[\s\S]*?<\/Contents>/g) ?? []
    for (const block of contents) {
      const key = block.match(/<Key>([^<]+)<\/Key>/)?.[1] ?? ''
      const size = parseInt(block.match(/<Size>(\d+)<\/Size>/)?.[1] ?? '0')
      const lastModified = block.match(/<LastModified>([^<]+)<\/LastModified>/)?.[1] ?? ''
      if (key) results.push({ key, size, lastModified })
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
