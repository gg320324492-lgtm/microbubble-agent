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

/** CI 用环境变量名（GitHub Actions Secrets） */
export const ENV_AK = 'OSS_UPLOAD_AK'
export const ENV_SK = 'OSS_UPLOAD_SK'
export const ENV_BUCKET = 'OSS_UPLOAD_BUCKET'
export const ENV_ENDPOINT = 'OSS_UPLOAD_ENDPOINT'
/** 默认 bucket / endpoint（与 R-7 一致；CI 只需注入 AK/SK） */
export const DEFAULT_BUCKET = 'mnb-workbench-releases'
export const DEFAULT_ENDPOINT = 'https://oss-cn-beijing.aliyuncs.com'

/**
 * 从环境变量解析凭据（CI 模式）。
 * AK/SK 任一缺失 → 返回 null（调用方据此「跳过并警告、不 fail」）。
 * 绝不回显任何值。
 */
export function parseCredsFromEnv(env) {
  const ak = String(env?.[ENV_AK] ?? '').trim()
  const sk = String(env?.[ENV_SK] ?? '').trim()
  if (!ak || !sk) return null
  return {
    bucket: String(env?.[ENV_BUCKET] ?? '').trim() || DEFAULT_BUCKET,
    endpoint: normalizeEndpoint(String(env?.[ENV_ENDPOINT] ?? '').trim() || DEFAULT_ENDPOINT),
    accessKeyId: ak,
    accessKeySecret: sk
  }
}

/** 凭据来源描述（供日志，不含任何凭据值） */
export function describeCredsSource(creds, from) {
  return `bucket=${creds.bucket} endpoint=${creds.endpoint} 来源=${from}（凭据已加载，值不回显）`
}

/** 对象 key：<version>/<fileName>（version 去 v 前缀） */
export function ossKey(version, fileName) {
  const v = String(version ?? '').trim().replace(/^v/i, '')
  if (!v) throw new Error('版本号为空')
  if (!fileName || /[/\\]/.test(String(fileName))) throw new Error(`非法文件名：${fileName}`)
  return `${v}/${fileName}`
}

/**
 * 带前缀的对象 key（R-8）——CI 上传到 feed 稳定路径 `releases/`。
 * prefix 为空/未给 → 退回 <version>/<fileName>（R-7 行为不变）。
 */
export function ossObjectKey({ prefix, version, fileName }) {
  const name = String(fileName ?? '')
  if (!name || /[/\\]/.test(name)) throw new Error(`非法文件名：${fileName}`)
  const p = String(prefix ?? '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
  if (!p) return ossKey(version, name)
  return `${p}/${name}`
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

/** 解析 OSS 标准错误 XML */
export function parseOssError(text) {
  const pick = (tag) => new RegExp(`<${tag}>([^<]*)</${tag}>`).exec(String(text ?? ''))?.[1]?.trim() ?? ''
  return {
    code: pick('Code'),
    message: pick('Message'),
    requestId: pick('RequestId'),
    hostId: pick('HostId')
  }
}

/**
 * OSS 错误码 → 可执行建议。
 * 排障顺序：先看 Code 再动手——四类根因（凭据 / 签名 / 权限 / bucket）各有专属错误码，
 * 混为一谈会白跑很多趟。
 */
export function explainOssError(code) {
  switch (String(code ?? '')) {
    case 'InvalidAccessKeyId':
      return 'AccessKeyId 不被 OSS 认可。核对：① AK ID 是否完整（RAM AK 通常 24 字符、LTAI 开头，抄漏/截断会直接报此错）② 该 AK 是否已被禁用或删除 ③ 是否误用了另一个账号的凭据'
    case 'SignatureDoesNotMatch':
      return '签名不匹配。核对：① 本机时间与 OSS 偏差需 <15 分钟（Date 头为 GMT）② Content-MD5 / Content-Type 是否与实际请求体一致'
    case 'AccessDenied':
      return '凭据有效但无权限。为该 RAM 子账号授予本 bucket 的 PutObject / GetObject / ListObjects（若要开静态网站还需 PutBucketWebsite）'
    case 'NoSuchBucket':
      return 'bucket 不存在或不在该 region。核对 bucket 名与 endpoint 区域是否匹配'
    case 'RequestTimeTooSkewed':
      return '本机时间与 OSS 偏差过大，校准系统时间后重试'
    case 'InvalidBucketName':
      return 'bucket 名非法：仅允许小写字母、数字、连字符，长度 3-63'
    case '':
      return '响应不是 OSS 标准错误 XML（可能是网络层/代理返回）。检查网络与代理设置'
    default:
      return `未收录的错误码 ${code}，请按 <Message> 原文排查`
  }
}

/** 组合成一段可读的失败说明 */
export function describeOssFailure(status, text) {
  const e = parseOssError(text)
  const hint = explainOssError(e.code)
  return [
    `HTTP ${status} ${e.code || '(无 Code)'}`,
    e.message ? `Message: ${e.message}` : '',
    `建议: ${hint}`,
    e.requestId ? `RequestId: ${e.requestId}` : ''
  ]
    .filter(Boolean)
    .join('\n         ')
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
  const prefix = arg('prefix') // 例：releases（CI 稳定路径）；缺省则用 <version>/
  const skipIfMissing = process.argv.includes('--skip-if-missing')

  if (!version) {
    console.error('用法：node scripts/upload-release-oss.mjs --version <v> --dir <dir> [--creds <creds.json>] [--prefix releases] [--page <html>] [--skip-if-missing]')
    process.exit(2)
  }

  // 凭据双模式：--creds 文件优先；否则读环境变量（CI Secrets）
  let creds = null
  let credsFrom = ''
  if (credsPath) {
    if (!existsSync(credsPath)) {
      console.error(`[oss][FATAL] 凭据文件不存在：${credsPath}`)
      process.exit(2)
    }
    creds = parseCreds(readFileSync(credsPath, 'utf8'))
    credsFrom = '凭据文件'
  } else {
    creds = parseCredsFromEnv(process.env)
    credsFrom = '环境变量'
    if (!creds) {
      const msg = `未提供凭据（--creds 文件或环境变量 ${ENV_AK}/${ENV_SK} 均未设置）`
      if (skipIfMissing) {
        console.log(`[oss][WARN] ${msg} —— 按 --skip-if-missing 跳过 OSS 上传，不影响本次发布`)
        return
      }
      console.error(`[oss][FATAL] ${msg}`)
      process.exit(2)
    }
  }
  console.log(`[oss] ${describeCredsSource(creds, credsFrom)}`)

  // 上传前自检：先打一发轻量签名请求，避免 88MB 传完才发现凭据/权限问题
  await preflight(creds)

  const results = []
  for (const tpl of ARTIFACTS) {
    const name = tpl.replace('{v}', version)
    const local = join(dir, name)
    if (!existsSync(local)) {
      console.log(`[oss] 跳过（本地不存在）：${name}`)
      continue
    }
    const body = readFileSync(local)
    const key = ossObjectKey({ prefix, version, fileName: name })
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

/**
 * 上传前自检（R-8）：一发签名 ListObjects。
 * 目的是把「凭据/权限」类问题在动 88MB 之前就暴露出来，并给出可执行建议。
 */
async function preflight(creds) {
  const date = new Date().toUTCString()
  const signature = signV1({
    verb: 'GET',
    date,
    canonicalizedResource: `/${creds.bucket}/`,
    accessKeySecret: creds.accessKeySecret
  })
  const host = normalizeEndpoint(creds.endpoint).replace(/^https?:\/\//i, '')
  const res = await fetch(`https://${creds.bucket}.${host}/?max-keys=1`, {
    headers: { Date: date, Authorization: authHeader(creds.accessKeyId, signature) }
  })
  if (res.ok) {
    console.log('[oss] ✓ 自检通过：凭据有效且具备 ListObjects 权限')
    return
  }
  const text = await res.text().catch(() => '')
  console.error(`[oss][FATAL] 自检失败（未开始上传）：\n         ${describeOssFailure(res.status, text)}`)
  process.exit(2)
}

// 仅在「被 node 直接执行」时跑 main；被 import（如单测）时不跑。
// 不用 import.meta.url —— 该表达式在 vitest 的 CJS 转换下不可用，会连带把
// import 本模块的测试文件一起弄成解析失败（R-8 首航实测）。argv 判定对 ESM/CJS 均安全。
const invokedDirectly = /upload-release-oss\.mjs$/.test(String(process.argv[1] ?? ''))
if (invokedDirectly) {
  main().catch((e) => {
    console.error(`[oss][FATAL] ${e instanceof Error ? e.message : String(e)}`)
    process.exit(1)
  })
}
