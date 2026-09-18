// OSS 签名与客户端契约（M5-2）— 签名/请求形状/XML 解析/上传下载往返。全部注入假 HTTP。
import { describe, expect, it, vi } from 'vitest'
import { contentMd5, ossDate, signOssV1, canonicalResource, ossAuthorization, normalizeEndpoint } from '@main/services/backup/oss-sig'
import { OssClient } from '@main/services/backup/oss.client'
import type { OssConfig, OssHttpRequest, OssHttpResponse } from '@main/services/backup/oss-sig'

const CONFIG: OssConfig = {
  bucket: 'test-bucket',
  endpoint: 'https://oss-cn-hangzhou.aliyuncs.com',
  prefix: 'desktop-backup/',
  accessKeyId: 'AKID-test',
  accessKeySecret: 'SK-test-secret'
}

function fakeHttp(status = 200, body = Buffer.alloc(0)) {
  const calls: OssHttpRequest[] = []
  const fn = vi.fn(async (req: OssHttpRequest): Promise<OssHttpResponse> => {
    calls.push(req)
    return { status, body }
  })
  return { fn: fn as unknown as (req: OssHttpRequest) => Promise<OssHttpResponse>, calls }
}

describe('OSS V1 签名', () => {
  it('固定输入 → 期望 signature（HMAC-SHA1 base64）', () => {
    const sig = signOssV1({
      verb: 'GET', date: 'Wed, 17 Sep 2026 12:00:00 GMT',
      canonicalizedResource: '/test-bucket/desktop-backup/test.mnbbak',
      accessKeySecret: 'test-secret'
    })
    // 签名为 base64 字符串且长度合理（HMAC-SHA1 → 20B → base64 ≈ 28 chars）
    expect(sig).toBeTruthy()
    expect(sig.length).toBeGreaterThan(20)
    // 同输入同输出
    const sig2 = signOssV1({
      verb: 'GET', date: 'Wed, 17 Sep 2026 12:00:00 GMT',
      canonicalizedResource: '/test-bucket/desktop-backup/test.mnbbak',
      accessKeySecret: 'test-secret'
    })
    expect(sig).toBe(sig2)
  })

  it('不同 secret 产生不同签名', () => {
    const s1 = signOssV1({ verb: 'GET', date: 'D', canonicalizedResource: '/b/k', accessKeySecret: 'secret-a' })
    const s2 = signOssV1({ verb: 'GET', date: 'D', canonicalizedResource: '/b/k', accessKeySecret: 'secret-b' })
    expect(s1).not.toBe(s2)
  })

  it('contentMd5 — 输入 body 生成 base64 MD5', () => {
    const md5 = contentMd5(Buffer.from('hello'))
    expect(md5).toBeTruthy()
    expect(md5.length).toBe(24) // base64 of 16-byte MD5
  })

  it('canonicalResource — /bucket/key 格式', () => {
    expect(canonicalResource('my-bucket', 'desktop-backup/file.mnbbak')).toBe('/my-bucket/desktop-backup/file.mnbbak')
  })

  it('ossAuthorization — OSS AKID:sig 格式', () => {
    expect(ossAuthorization('my-ak', 'my-sig')).toBe('OSS my-ak:my-sig')
  })

  it('ossDate — 含 GMT', () => {
    expect(ossDate()).toContain('GMT')
  })
})

describe('OssClient 请求形状', () => {
  it('putObject — PUT 方法 + Content-MD5 + Authorization 头', async () => {
    const { fn, calls } = fakeHttp()
    const client = new OssClient(CONFIG, fn)
    await client.putObject('desktop-backup/test.mnbbak', Buffer.from('data'))
    expect(calls).toHaveLength(1)
    expect(calls[0].method).toBe('PUT')
    expect(calls[0].url).toContain('desktop-backup/test.mnbbak')
    expect(calls[0].headers['Content-MD5']).toBeTruthy()
    expect(calls[0].headers['Authorization']).toMatch(/^OSS /)
  })

  it('getObject — GET 方法返回 body', async () => {
    const { fn } = fakeHttp(200, Buffer.from('backup-content'))
    const client = new OssClient(CONFIG, fn)
    const data = await client.getObject('desktop-backup/test.mnbbak')
    expect(data.toString()).toBe('backup-content')
    expect(fn).toHaveBeenCalled()
  })

  it('deleteObject — DELETE 方法', async () => {
    const { fn, calls } = fakeHttp()
    const client = new OssClient(CONFIG, fn)
    await client.deleteObject('desktop-backup/old.mnbbak')
    expect(calls[0].method).toBe('DELETE')
  })

  it('HTTP ≥300 抛错含状态码', async () => {
    const { fn } = fakeHttp(403)
    const client = new OssClient(CONFIG, fn)
    await expect(client.putObject('k', Buffer.alloc(0))).rejects.toThrow('403')
  })
})

describe('listObjects XML 解析', () => {
  it('正常 XML — 提取 Key/Size/LastModified', async () => {
    const xml = Buffer.from(`<?xml version="1.0"?><ListBucketResult><Contents><Key>desktop-backup/a.mnbbak</Key><Size>100</Size><LastModified>2026-09-18T00:00:00Z</LastModified></Contents><Contents><Key>desktop-backup/b.mnbbak</Key><Size>200</Size><LastModified>2026-09-18T01:00:00Z</LastModified></Contents></ListBucketResult>`)
    const { fn } = fakeHttp(200, xml)
    const client = new OssClient(CONFIG, fn)
    const list = await client.listObjects('desktop-backup/')
    expect(list).toHaveLength(2)
    expect(list[0].key).toContain('a.mnbbak')
    expect(list[1].size).toBe(200)
  })

  it('空列表 — 无 Contents 返回空数组', async () => {
    const xml = Buffer.from('<?xml version="1.0"?><ListBucketResult></ListBucketResult>')
    const { fn } = fakeHttp(200, xml)
    const client = new OssClient(CONFIG, fn)
    expect(await client.listObjects('x/')).toEqual([])
  })

  it('异常 XML 容错 — 返回空数组不崩溃', async () => {
    const xml = Buffer.from('not-xml-at-all')
    const { fn } = fakeHttp(200, xml)
    const client = new OssClient(CONFIG, fn)
    expect(await client.listObjects('x/')).toEqual([])
  })
})

// 辅助：创建带 body 回传的 fake HTTP（上传下载往返测试用）
function echoHttp() {
  const store = new Map<string, Buffer>()
  return {
    fn: async (req: OssHttpRequest): Promise<OssHttpResponse> => {
      if (req.method === 'PUT' && req.body) { store.set(req.url, req.body); return { status: 200, body: Buffer.alloc(0) } }
      if (req.method === 'GET') {
        const data = store.get(req.url)
        return data ? { status: 200, body: data } : { status: 404, body: Buffer.from('NotFound') }
      }
      if (req.method === 'DELETE') { return { status: 204, body: Buffer.alloc(0) } }
      return { status: 200, body: Buffer.alloc(0) }
    },
    store
  }
}

describe('上传下载往返', () => {
  it('putObject → getObject 同 key 数据一致', async () => {
    const { fn, store } = echoHttp()
    const client = new OssClient(CONFIG, fn as unknown as (req: OssHttpRequest) => Promise<OssHttpResponse>)
    const data = Buffer.from('backup-roundtrip-data-0.1.3')
    await client.putObject('desktop-backup/rt.mnbbak', data)
    const got = await client.getObject('desktop-backup/rt.mnbbak')
    expect(got.equals(data)).toBe(true)
    expect(store.size).toBe(1)
  })
})

describe('整改回归（打回两项）', () => {
  it('listObjects prefix 单拼 — 请求参数精确等于调用方全量前缀，无 config.prefix 双拼', async () => {
    let capturedUrl = ''
    const fn = vi.fn(async (req: OssHttpRequest): Promise<OssHttpResponse> => {
      capturedUrl = req.url
      return { status: 200, body: Buffer.from('<?xml version="1.0"?><ListBucketResult></ListBucketResult>') }
    })
    const client = new OssClient(CONFIG, fn)
    await client.listObjects('desktop-backup/')
    const prefix = new URL(capturedUrl).searchParams.get('prefix')
    expect(prefix).toBe('desktop-backup/') // 精确相等 — 双拼 desktop-backup/desktop-backup/ 会在此失败
  })

  it('normalizeEndpoint — 无 scheme 自动补 https://，带 scheme 原样，空串归空', () => {
    expect(normalizeEndpoint('oss-cn-hangzhou.aliyuncs.com')).toBe('https://oss-cn-hangzhou.aliyuncs.com')
    expect(normalizeEndpoint('  oss-cn-hangzhou.aliyuncs.com ')).toBe('https://oss-cn-hangzhou.aliyuncs.com')
    expect(normalizeEndpoint('https://oss-cn-hangzhou.aliyuncs.com')).toBe('https://oss-cn-hangzhou.aliyuncs.com')
    expect(normalizeEndpoint('http://127.0.0.1:9000')).toBe('http://127.0.0.1:9000') // minio 类自建端点保留 http
    expect(normalizeEndpoint('')).toBe('')
  })

  it('virtual-hosted 风格 — 上传/列举 URL 主机名为 <bucket>.<endpoint-host>（真机联调锁死：路径风格被 SecondLevelDomainForbidden 拒绝）', async () => {
    const { fn, calls } = fakeHttp()
    const client = new OssClient(CONFIG, fn)
    await client.putObject('desktop-backup/x.mnbbak', Buffer.from('d'))
    const putUrl = new URL(calls[0].url)
    expect(putUrl.hostname).toBe('test-bucket.oss-cn-hangzhou.aliyuncs.com')
    expect(putUrl.pathname).toBe('/desktop-backup/x.mnbbak')
    await client.listObjects('desktop-backup/')
    const listCall = vi.mocked(fn).mock.calls[1][0]
    const listUrl = new URL(listCall.url)
    expect(listUrl.hostname).toBe('test-bucket.oss-cn-hangzhou.aliyuncs.com')
    expect(listUrl.searchParams.get('prefix')).toBe('desktop-backup/')
  })
})
