// 阿里云 OSS V1 签名 + 客户端（M5-2）— 零依赖（node:crypto + 注入 HTTP）。
// V1 签名规范: Authorization: OSS AccessKeyId:signature
//   signature = base64(HMAC-SHA1(secret, VERB\nContent-MD5\nContent-Type\nDate\nCanonicalizedOSSHeaders\nCanonicalizedResource))
import { createHash, createHmac } from 'node:crypto'

export interface OssConfig {
  bucket: string
  endpoint: string
  prefix: string
  accessKeyId: string
  accessKeySecret: string
}

export interface OssHttpRequest {
  method: string
  url: string
  headers: Record<string, string>
  body?: Buffer
}

export interface OssHttpResponse {
  status: number
  body: Buffer
}

// ---------- V1 签名 ----------

/** 构造 GMT 时间字符串 */
export function ossDate(): string {
  return new Date().toUTCString()
}

/** 计算 Content-MD5（base64） */
export function contentMd5(body: Buffer): string {
  return createHash('md5').update(body).digest('base64')
}

/**
 * V1 签名（纯函数可离线单测）
 * StringToSign = VERB\nContent-MD5\nContent-Type\nDate\nCanonicalizedOSSHeaders + CanonicalizedResource
 */
export function signOssV1(opts: {
  verb: string
  contentMd5?: string
  contentType?: string
  date: string
  canonicalizedOssHeaders?: string
  canonicalizedResource: string
  accessKeySecret: string
}): string {
  const parts = [
    opts.verb.toUpperCase(),
    opts.contentMd5 ?? '',
    opts.contentType ?? '',
    opts.date,
    (opts.canonicalizedOssHeaders ?? '') + opts.canonicalizedResource
  ]
  const stringToSign = parts.join('\n')
  return createHmac('sha1', opts.accessKeySecret).update(stringToSign).digest('base64')
}

/** 构造 Authorization 头 */
export function ossAuthorization(accessKeyId: string, signature: string): string {
  return `OSS ${accessKeyId}:${signature}`
}

/** CanonicalizedResource: /bucket/key（key 需 URL 编码已在调用方处理） */
export function canonicalResource(bucket: string, key: string): string {
  return `/${bucket}/${key}`
}
