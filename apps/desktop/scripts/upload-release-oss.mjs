#!/usr/bin/env node
// 国内分发上传脚本（工单 R-7）— 零依赖，node 直跑，不动业务代码。
//
// 复用 M5-2 的 OSS V1 签名模式（HMAC-SHA1），把发布产物上传到公共读 bucket 的
// <version>/ 前缀下，上传后逐个 GET 校验字节数，最后输出国内直连 URL。
//
// 用法：
//   node scripts/upload-release-oss.mjs --version 1.0.0 \
//        --dir release --creds C:\Users\pc\Desktop\oss-creds.json
//   node scripts/upload-release-oss.mjs --version 1.0.0 --dir <dir> \
//        --creds <file> --page scripts/download-page.html     # 额外部署落地页
//
// 凭据安全：Secret 只从文件读取并留在内存；本脚本**不打印、不写日志、不回显**任何凭据值。
import { createHash, createHmac } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// ============================================================
// 纯函数层（离线可单测）
// ============================================================

/** 解析凭据文件 JSON → 四字段校验（缺字段直接抛错，绝不回显值） */
export function parseCreds(text) {
  let raw
  try {
    raw = JSON.parse(String(text ?? ''))
  } catch {
    throw new Error('凭据文件不是合法 JSON')
  }
  const need = ['bucket', 'endpoint', 'accessKeyId', 'accessKeySecret']
  const missing = need.filter((k) => !raw?.[k] || typeof raw[k] !== 'string' || !raw[k].trim())
  if (missing.length) throw new Error(`凭据文件缺少字段：${missing.join(', ')}`)
  return {
    bucket: raw.bucket.trim(),
    endpoint: normalizeEndpoint(raw.endpoint),
    accessKeyId: raw.accessKeyId.trim(),
    accessKeySecret: raw.accessKeySecret.trim()
  }
}

/** endpoint 归一化：无 scheme 补 https://；去掉尾部斜杠 */
export function normalizeEndpoint(endpoint) {
  const t = String(endpoint ?? '').trim().replace(/\/+$/, '')
  if (!t) return ''
  return /^https?:\/\//i.test(t) ? t : `https://${t}`
}

/** 对象 key：<version>/<fileName>（version 去 v 前缀） */
export function ossKey(version, fileName) {
  const v = String(version ?? '').trim().replace(/^v/i, '')
  if (!v) throw new Error('版本号为空')
  if (!fileName || /[/\\]/.test(String(fileName))) throw new Error(`非法文件名：${fileName}`)
  return `${v}/${fileName}`
}

/** CanonicalizedResource：/<bucket>/<key> */
export function canonicalResource(bucket, key) {
  return `/${bucket}/${key}`
}

/** V1 签名：base64(HMAC-SHA1(secret, VERB\nContent-MD5\nContent-Type\nDate\nCanonicalizedResource)) */
export function signV1({ verb, contentMd5 = '', contentType = '', date, canonicalizedResource, accessKeySecret }) {
  const stringToSign = [String(verb).toUpperCase(), contentMd5, contentType, date, canonicalizedResource].join('\n')
  return createHmac('sha1', accessKeySecret).update(stringToSign).digest('base64')
}

/** Authorization 头 */
export function authHeader(accessKeyId, signature) {
  return `OSS ${accessKeyId}:${signature}`
}

/** Content-MD5（base64） */
export function contentMd5(buf) {
  return createHash('md5').update(buf).digest('base64')
}

/** 对象直连 URL（公共读 bucket 的国内直连地址） */
export function objectUrl(endpoint, bucket, key) {
  const host = normalizeEndpoint(endpoint).replace(/^https?:\/\//i, '')
  return `https://${bucket}.${host}/${key}`
}

/** 字节数可读化（落地页展示用） */
export function formatBytes(n) {
  const v = typeof n === 'number' && Number.isFinite(n) && n > 0 ? n : 0
  if (v < 1024) return `${v} B`
  if (v < 1024 * 1024) return `${(v / 1024).toFixed(1)} KB`
  return `${(v / 1024 / 1024).toFixed(1)} MB`
}

/** 校验字节数一致 */
export function verifySize(actual, expected) {
  if (!Number.isFinite(actual)) return { ok: false, reason: `下载字节数非法：${actual}` }
  if (actual !== expected) return { ok: false, reason: `字节数不一致：远端 ${actual} vs 本地 ${expected}` }
  return { ok: true }
}

/** 校验 sha256（hex，大小写不敏感） */
export function verifySha256(buf, expectedHex) {
  const actual = createHash('sha256').update(buf).digest('hex')
  const want = String(expectedHex ?? '').trim().toLowerCase()
  if (!want) return { ok: false, actual, reason: '未提供期望 sha256' }
  if (actual !== want) return { ok: false, actual, reason: `sha256 不一致：${actual} vs ${want}` }
  return { ok: true, actual }
}

// ============================================================
// CLI
// ============================================================

const ARTIFACTS = ['MicroBubbleWorkbench-{v}-setup.exe', 'MicroBubbleWorkbench-{v}-setup.exe.blockmap', 'latest.yml']

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback
}

/** 构造带签名的请求头（PUT / GET 共用） */
function signedHeaders(creds, verb, key, { contentType = '', md5 = '', date }) {
  const resource = canonicalResource(creds.bucket, key)
  const signature = signV1({
    verb,
    contentMd5: md5,
    contentType,
    date,
    canonicalizedResource: resource,
    accessKeySecret: creds.accessKeySecret
  })
  return { resource, signature }
}

async function putObject(creds, key, body, contentType) {
  const date = new Date().toUTCString()
  const md5 = contentMd5(body)
  const { signature } = signedHeaders(creds, 'PUT', key, { contentType, md5, date })
  const url = objectUrl(creds.endpoint, creds.bucket, key)
  const res = await fetch(url, {
    method: 'PUT',
    headers: {
      Date: date,
      'Content-MD5': md5,
      'Content-Type': contentType,
      'Content-Length': String(body.length),
      Authorization: authHeader(creds.accessKeyId, signature)
    },
    body
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`PUT ${key} 失败：HTTP ${res.status} ${text.slice(0, 300)}`)
  }
  return { url, md5 }
}

async function getObject(creds, key) {
  const date = new Date().toUTCString()
  const { signature } = signedHeaders(creds, 'GET', key, { date })
  const url = objectUrl(creds.endpoint, creds.bucket, key)
  // 公共读 bucket 其实无需签名；带上签名对私有读也兼容
  const res = await fetch(url, { headers: { Date: date, Authorization: authHeader(creds.accessKeyId, signature) } })
  if (!res.ok) throw new Error(`GET ${key} 失败：HTTP ${res.status}`)
  const buf = Buffer.from(await res.arrayBuffer())
  return { buf, headers: res.headers }
}

/** 尽力开启静态网站（索引文档 download-page.html）；无权限则降级为直链 */
async function tryPutBucketWebsite(creds, indexDoc) {
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<WebsiteConfiguration><IndexDocument><Suffix>${indexDoc}</Suffix></IndexDocument>` +
    `<ErrorDocument><Key>${indexDoc}</Key><HttpStatus>404</HttpStatus></ErrorDocument></WebsiteConfiguration>`
  const date = new Date().toUTCString()
  const md5 = contentMd5(Buffer.from(xml))
  const resource = `/${creds.bucket}/?website`
  const signature = signV1({
    verb: 'PUT',
    contentMd5: md5,
    contentType: 'application/xml',
    date,
    canonicalizedResource: resource,
    accessKeySecret: creds.accessKeySecret
  })
  const host = normalizeEndpoint(creds.endpoint).replace(/^https?:\/\//i, '')
  const res = await fetch(`https://${creds.bucket}.${host}/?website`, {
    method: 'PUT',
    headers: {
      Date: date,
      'Content-MD5': md5,
      'Content-Type': 'application/xml',
      Authorization: authHeader(creds.accessKeyId, signature)
    },
    body: xml
  })
  return { ok: res.ok, status: res.status }
}

async function main() {
  const version = arg('version')
  const dir = resolve(arg('dir', 'release'))
  const credsPath = arg('creds')
  const pagePath = arg('page')
  if (!version || !credsPath) {
    console.error('用法：node scripts/upload-release-oss.mjs --version <v> --dir <dir> --creds <creds.json> [--page <html>]')
    process.exit(2)
  }
  const creds = parseCreds(readFileSync(credsPath, 'utf8'))
  console.log(`[oss] bucket=${creds.bucket} endpoint=${creds.endpoint}（凭据已加载，值不回显）`)

  const results = []
  for (const tpl of ARTIFACTS) {
    const name = tpl.replace('{v}', version)
    const local = join(dir, name)
    if (!existsSync(local)) {
      console.log(`[oss] 跳过（本地不存在）：${name}`)
      continue
    }
    const body = readFileSync(local)
    const key = ossKey(version, name)
    const localSha = verifySha256(body, '').actual
    console.log(`[oss] 上传 ${name}（${formatBytes(body.length)}）→ ${key}`)
    await putObject(creds, key, body, name.endsWith('.yml') ? 'text/yaml; charset=utf-8' : 'application/octet-stream')

    const back = await getObject(creds, key)
    const sizeCheck = verifySize(back.buf.length, body.length)
    const shaCheck = verifySha256(back.buf, localSha)
    if (!sizeCheck.ok || !shaCheck.ok) {
      throw new Error(`上传后校验失败：${sizeCheck.reason ?? ''} ${shaCheck.reason ?? ''}`)
    }
    const url = objectUrl(creds.endpoint, creds.bucket, key)
    console.log(`[oss] ✓ 校验一致（${back.buf.length} bytes, sha256 ${localSha.slice(0, 16)}…）`)
    results.push({ name, key, url, size: body.length, sha256: localSha })
  }

  let pageUrl = null
  if (pagePath) {
    if (!existsSync(pagePath)) throw new Error(`落地页不存在：${pagePath}`)
    const body = readFileSync(pagePath)
    for (const key of ['download-page.html', 'index.html']) {
      await putObject(creds, key, body, 'text/html; charset=utf-8')
      const back = await getObject(creds, key)
      const chk = verifySize(back.buf.length, body.length)
      if (!chk.ok) throw new Error(`落地页校验失败（${key}）：${chk.reason}`)
      console.log(`[oss] ✓ 落地页已部署：${key}（${formatBytes(body.length)}）`)
    }
    pageUrl = objectUrl(creds.endpoint, creds.bucket, 'download-page.html')
    const site = await tryPutBucketWebsite(creds, 'index.html').catch((e) => ({ ok: false, status: String(e.message) }))
    console.log(
      site.ok
        ? '[oss] ✓ 静态网站已开启（索引文档 index.html）'
        : `[oss] 静态网站未开启（HTTP ${site.status}）→ 用对象直链访问落地页`
    )
  }

  console.log('\n===== 国内直连 URL =====')
  for (const r of results) console.log(`${r.name}\n  ${r.url}\n  ${r.size} bytes  sha256 ${r.sha256}`)
  if (pageUrl) console.log(`落地页\n  ${pageUrl}`)
}

const invokedDirectly = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))
if (invokedDirectly) {
  main().catch((e) => {
    console.error(`[oss][FATAL] ${e instanceof Error ? e.message : String(e)}`)
    process.exit(1)
  })
}
