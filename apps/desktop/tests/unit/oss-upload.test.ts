// R-7 国内分发上传脚本 — 纯函数契约（全部离线，不触网、不读真实凭据）
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  authHeader,
  canonicalResource,
  contentMd5,
  formatBytes,
  normalizeEndpoint,
  objectUrl,
  ossKey,
  parseCreds,
  signV1,
  verifySha256,
  verifySize
} from '../../scripts/upload-release-oss.mjs'

const VALID = JSON.stringify({
  bucket: 'mnb-workbench-releases',
  endpoint: 'https://oss-cn-beijing.aliyuncs.com',
  accessKeyId: 'AKIDEXAMPLE',
  accessKeySecret: 'secret-example'
})

describe('凭据解析 — 结构校验且不回显敏感值', () => {
  it('四字段齐备时解析成功，endpoint 归一化', () => {
    const c = parseCreds(VALID)
    expect(c.bucket).toBe('mnb-workbench-releases')
    expect(c.endpoint).toBe('https://oss-cn-beijing.aliyuncs.com')
    expect(c.accessKeyId).toBe('AKIDEXAMPLE')
    expect(c.accessKeySecret).toBe('secret-example')
  })

  it('缺字段 / 非法 JSON / 空值 一律抛错，且错误信息不含 Secret', () => {
    expect(() => parseCreds(JSON.stringify({ bucket: 'b' }))).toThrow(/缺少字段/)
    expect(() => parseCreds('not json')).toThrow(/合法 JSON/)
    expect(() => parseCreds(JSON.stringify({ ...JSON.parse(VALID), accessKeySecret: '  ' }))).toThrow(/accessKeySecret/)
    try {
      parseCreds(JSON.stringify({ bucket: 'b', endpoint: 'e', accessKeyId: 'a', accessKeySecret: 'SUPERSECRET' }))
      // 缺字段不会走到这里
    } catch (e) {
      expect(String(e instanceof Error ? e.message : e)).not.toContain('SUPERSECRET')
    }
  })
})

describe('endpoint / key / URL 构造', () => {
  it('normalizeEndpoint：补 scheme、去尾斜杠', () => {
    expect(normalizeEndpoint('oss-cn-beijing.aliyuncs.com')).toBe('https://oss-cn-beijing.aliyuncs.com')
    expect(normalizeEndpoint('https://oss-cn-beijing.aliyuncs.com/')).toBe('https://oss-cn-beijing.aliyuncs.com')
    expect(normalizeEndpoint('  ')).toBe('')
  })

  it('ossKey：<version>/<file>，v 前缀被剥离；非法输入抛错', () => {
    expect(ossKey('1.0.0', 'a.exe')).toBe('1.0.0/a.exe')
    expect(ossKey('v1.0.0', 'a.exe')).toBe('1.0.0/a.exe')
    expect(() => ossKey('', 'a.exe')).toThrow(/版本号/)
    expect(() => ossKey('1.0.0', 'a/b.exe')).toThrow(/非法文件名/)
  })

  it('objectUrl：bucket 作子域，虚拟主机风格直连地址', () => {
    expect(objectUrl('https://oss-cn-beijing.aliyuncs.com', 'mnb-workbench-releases', '1.0.0/x.exe')).toBe(
      'https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com/1.0.0/x.exe'
    )
    // 无 scheme 的 endpoint 也能得到同样结果
    expect(objectUrl('oss-cn-beijing.aliyuncs.com', 'b', 'k')).toBe('https://b.oss-cn-beijing.aliyuncs.com/k')
  })
})

describe('OSS V1 签名 — 与固定夹具逐字节一致', () => {
  it('PUT 签名（含 Content-MD5 / Content-Type）', () => {
    const sig = signV1({
      verb: 'PUT',
      contentMd5: 'Q2hlY2s=',
      contentType: 'application/octet-stream',
      date: 'Mon, 01 Jan 2024 00:00:00 GMT',
      canonicalizedResource: canonicalResource('b', 'k.exe'),
      accessKeySecret: 'testsecret'
    })
    expect(sig).toBe('euvNvqHIQL2/tsA5sQ5Lh2ja9h4=')
  })

  it('GET 签名（Content-MD5/Content-Type 为空串占位）', () => {
    const sig = signV1({
      verb: 'GET',
      date: 'Mon, 01 Jan 2024 00:00:00 GMT',
      canonicalizedResource: canonicalResource('b', 'k.exe'),
      accessKeySecret: 'testsecret'
    })
    expect(sig).toBe('s2/bV6GknXXtgZ4ZezaIiI2vanI=')
  })

  it('桶级子资源（?website）签名与 Authorization 头格式', () => {
    const sig = signV1({
      verb: 'PUT',
      contentMd5: 'AAAA',
      contentType: 'application/xml',
      date: 'Mon, 01 Jan 2024 00:00:00 GMT',
      canonicalizedResource: '/b/?website',
      accessKeySecret: 'testsecret'
    })
    expect(sig).toBe('VEbnfv3FwJkWSAdEQiTZTXjkjF8=')
    expect(authHeader('AKID', sig)).toBe(`OSS AKID:${sig}`)
    expect(authHeader('AKID', sig)).toMatch(/^OSS [^:]+:.+$/)
  })

  it('Content-MD5 为 body 的 base64 md5', () => {
    // md5('Check') 的 base64（注意不是 base64('Check')）
    expect(contentMd5(Buffer.from('Check'))).toBe('Bgvy1YeZHY8JChMJsoUpHA==')
  })

  it('StringToSign 构造与独立实现（openssl）逐字节一致', () => {
    // 期望值由 openssl 独立算出，交叉验证本实现的 StringToSign 拼装：
    //   printf '<6 行>' | openssl dgst -sha1 -hmac <secret> -binary | openssl base64
    const secret = 'OtxrzxIsfpFjA7SwPzILwy8Bw21TLhquhboDYROV'
    // ① 带 CanonicalizedOSSHeaders（OSS 头各占一行，最后拼 CanonicalizedResource）
    expect(
      signV1({
        verb: 'PUT',
        contentMd5: 'eB5eJF1ptWaXm4bijSPyxw==',
        contentType: 'text/html',
        date: 'Thu, 17 Nov 2005 18:49:58 GMT',
        canonicalizedResource: 'x-oss-meta-author:foo@bar.com\n/oss-example/nelson',
        accessKeySecret: secret
      })
    ).toBe('4u31IfA8Z+t7ofztPQ2w8n2clic=')
    // ② 无 OSS 头（本上传脚本的实际形态）：Date 之后直接接 CanonicalizedResource
    expect(
      signV1({
        verb: 'PUT',
        contentMd5: 'eB5eJF1ptWaXm4bijSPyxw==',
        contentType: 'text/html',
        date: 'Thu, 17 Nov 2005 18:49:58 GMT',
        canonicalizedResource: '/oss-example/nelson',
        accessKeySecret: secret
      })
    ).toBe('LNAVCpRhoMq7+fL5OzU7sUkNHE8=')
  })
})

describe('上传后校验', () => {
  it('字节数一致通过，不一致给出原因', () => {
    expect(verifySize(100, 100).ok).toBe(true)
    expect(verifySize(99, 100).ok).toBe(false)
    expect(verifySize(99, 100).reason).toContain('99')
    expect(verifySize(Number.NaN, 100).ok).toBe(false)
  })

  it('sha256 比对（大小写不敏感），不一致时回报实际值', () => {
    const buf = Buffer.from('hello')
    const hex = createHash('sha256').update(buf).digest('hex')
    expect(verifySha256(buf, hex).ok).toBe(true)
    expect(verifySha256(buf, hex.toUpperCase()).ok).toBe(true)
    const bad = verifySha256(buf, 'deadbeef')
    expect(bad.ok).toBe(false)
    expect(bad.actual).toBe(hex)
    expect(verifySha256(buf, '').ok).toBe(false)
  })

  it('formatBytes 可读化（落地页展示大小用）', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(92193290)).toBe('87.9 MB')
    expect(formatBytes(0)).toBe('0 B')
  })
})

describe('凭据零明文 — 脚本源码契约', () => {
  const src = readFileSync(resolve(__dirname, '../../scripts/upload-release-oss.mjs'), 'utf8')

  it('脚本内不得出现任何疑似真实凭据的字面量', () => {
    // 真实 AK ID 为 22 位、Secret 为 30 位；脚本内不应出现长串大写字母数字字面量
    expect(src).not.toMatch(/['"][A-Za-z0-9]{24,}['"]/)
    expect(src).not.toMatch(/LTAI[A-Za-z0-9]{6,}/) // 阿里云 AK ID 常见前缀
  })

  it('不得把 accessKeySecret 交给任何日志/输出', () => {
    const logLines = src.split('\n').filter((l) => /console\.(log|error|warn)|process\.stdout/.test(l))
    // 先确认脚本确实有日志，避免断言空转
    expect(logLines.length).toBeGreaterThan(0)
    for (const l of logLines) {
      // ① 绝不引用敏感字段
      expect(l, `日志行引用了敏感字段：${l.trim()}`).not.toMatch(/accessKeySecret|accessKeyId/)
      // ② 绝不整体打印 creds 对象。白名单仅两项非敏感访问 + CLI 参数名/文件名：
      const rest = l
        .replace(/creds\.(bucket|endpoint)/g, '')
        .replace(/--creds/g, '')
        .replace(/creds\.json/g, '')
      expect(rest, `日志行打印了凭据对象：${l.trim()}`).not.toMatch(/\bcreds\b/)
    }
  })
})
