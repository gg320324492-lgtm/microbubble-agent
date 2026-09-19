// R-7 国内分发上传脚本 — 纯函数契约（全部离线，不触网、不读真实凭据）
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'

// R-8 说明：上传脚本是纯 Node ESM（.mjs + shebang，供 node 直跑）。
// 这里**在运行时动态 import**，而不是静态 import —— 静态 import 会让 vitest 在收集阶段
// 转换该 .mjs，在 CI 环境触发 SyntaxError（本地同内容同版本不复现）；动态 import 走 Node
// 原生 ESM 加载器，绕开该路径。类型来自同目录的 upload-release-oss.d.mts。
let M: typeof import('../../scripts/upload-release-oss.mjs')
beforeAll(async () => {
  M = await import('../../scripts/upload-release-oss.mjs')
})

const VALID = JSON.stringify({
  bucket: 'mnb-workbench-releases',
  endpoint: 'https://oss-cn-beijing.aliyuncs.com',
  accessKeyId: 'AKIDEXAMPLE',
  accessKeySecret: 'secret-example'
})

describe('凭据解析 — 结构校验且不回显敏感值', () => {
  it('四字段齐备时解析成功，endpoint 归一化', () => {
    const c = M.parseCreds(VALID)
    expect(c.bucket).toBe('mnb-workbench-releases')
    expect(c.endpoint).toBe('https://oss-cn-beijing.aliyuncs.com')
    expect(c.accessKeyId).toBe('AKIDEXAMPLE')
    expect(c.accessKeySecret).toBe('secret-example')
  })

  it('缺字段 / 非法 JSON / 空值 一律抛错，且错误信息不含 Secret', () => {
    expect(() => M.parseCreds(JSON.stringify({ bucket: 'b' }))).toThrow(/缺少字段/)
    expect(() => M.parseCreds('not json')).toThrow(/合法 JSON/)
    expect(() => M.parseCreds(JSON.stringify({ ...JSON.parse(VALID), accessKeySecret: '  ' }))).toThrow(/accessKeySecret/)
    try {
      M.parseCreds(JSON.stringify({ bucket: 'b', endpoint: 'e', accessKeyId: 'a', accessKeySecret: 'SUPERSECRET' }))
      // 缺字段不会走到这里
    } catch (e) {
      expect(String(e instanceof Error ? e.message : e)).not.toContain('SUPERSECRET')
    }
  })
})

describe('endpoint / key / URL 构造', () => {
  it('M.normalizeEndpoint：补 scheme、去尾斜杠', () => {
    expect(M.normalizeEndpoint('oss-cn-beijing.aliyuncs.com')).toBe('https://oss-cn-beijing.aliyuncs.com')
    expect(M.normalizeEndpoint('https://oss-cn-beijing.aliyuncs.com/')).toBe('https://oss-cn-beijing.aliyuncs.com')
    expect(M.normalizeEndpoint('  ')).toBe('')
  })

  it('M.ossKey：<version>/<file>，v 前缀被剥离；非法输入抛错', () => {
    expect(M.ossKey('1.0.0', 'a.exe')).toBe('1.0.0/a.exe')
    expect(M.ossKey('v1.0.0', 'a.exe')).toBe('1.0.0/a.exe')
    expect(() => M.ossKey('', 'a.exe')).toThrow(/版本号/)
    expect(() => M.ossKey('1.0.0', 'a/b.exe')).toThrow(/非法文件名/)
  })

  it('M.objectUrl：bucket 作子域，虚拟主机风格直连地址', () => {
    expect(M.objectUrl('https://oss-cn-beijing.aliyuncs.com', 'mnb-workbench-releases', '1.0.0/x.exe')).toBe(
      'https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com/1.0.0/x.exe'
    )
    // 无 scheme 的 endpoint 也能得到同样结果
    expect(M.objectUrl('oss-cn-beijing.aliyuncs.com', 'b', 'k')).toBe('https://b.oss-cn-beijing.aliyuncs.com/k')
  })
})

describe('OSS V1 签名 — 与固定夹具逐字节一致', () => {
  it('PUT 签名（含 Content-MD5 / Content-Type）', () => {
    const sig = M.signV1({
      verb: 'PUT',
      contentMd5: 'Q2hlY2s=',
      contentType: 'application/octet-stream',
      date: 'Mon, 01 Jan 2024 00:00:00 GMT',
      canonicalizedResource: M.canonicalResource('b', 'k.exe'),
      accessKeySecret: 'testsecret'
    })
    expect(sig).toBe('euvNvqHIQL2/tsA5sQ5Lh2ja9h4=')
  })

  it('GET 签名（Content-MD5/Content-Type 为空串占位）', () => {
    const sig = M.signV1({
      verb: 'GET',
      date: 'Mon, 01 Jan 2024 00:00:00 GMT',
      canonicalizedResource: M.canonicalResource('b', 'k.exe'),
      accessKeySecret: 'testsecret'
    })
    expect(sig).toBe('s2/bV6GknXXtgZ4ZezaIiI2vanI=')
  })

  it('桶级子资源（?website）签名与 Authorization 头格式', () => {
    const sig = M.signV1({
      verb: 'PUT',
      contentMd5: 'AAAA',
      contentType: 'application/xml',
      date: 'Mon, 01 Jan 2024 00:00:00 GMT',
      canonicalizedResource: '/b/?website',
      accessKeySecret: 'testsecret'
    })
    expect(sig).toBe('VEbnfv3FwJkWSAdEQiTZTXjkjF8=')
    expect(M.authHeader('AKID', sig)).toBe(`OSS AKID:${sig}`)
    expect(M.authHeader('AKID', sig)).toMatch(/^OSS [^:]+:.+$/)
  })

  it('Content-MD5 为 body 的 base64 md5', () => {
    // md5('Check') 的 base64（注意不是 base64('Check')）
    expect(M.contentMd5(Buffer.from('Check'))).toBe('Bgvy1YeZHY8JChMJsoUpHA==')
  })

  it('StringToSign 构造与独立实现（openssl）逐字节一致', () => {
    // 期望值由 openssl 独立算出，交叉验证本实现的 StringToSign 拼装：
    //   printf '<6 行>' | openssl dgst -sha1 -hmac <secret> -binary | openssl base64
    const secret = 'OtxrzxIsfpFjA7SwPzILwy8Bw21TLhquhboDYROV'
    // ① 带 CanonicalizedOSSHeaders（OSS 头各占一行，最后拼 CanonicalizedResource）
    expect(
      M.signV1({
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
      M.signV1({
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
    expect(M.verifySize(100, 100).ok).toBe(true)
    expect(M.verifySize(99, 100).ok).toBe(false)
    expect(M.verifySize(99, 100).reason).toContain('99')
    expect(M.verifySize(Number.NaN, 100).ok).toBe(false)
  })

  it('sha256 比对（大小写不敏感），不一致时回报实际值', () => {
    const buf = Buffer.from('hello')
    const hex = createHash('sha256').update(buf).digest('hex')
    expect(M.verifySha256(buf, hex).ok).toBe(true)
    expect(M.verifySha256(buf, hex.toUpperCase()).ok).toBe(true)
    const bad = M.verifySha256(buf, 'deadbeef')
    expect(bad.ok).toBe(false)
    expect(bad.actual).toBe(hex)
    expect(M.verifySha256(buf, '').ok).toBe(false)
  })

  it('M.formatBytes 可读化（落地页展示大小用）', () => {
    expect(M.formatBytes(512)).toBe('512 B')
    expect(M.formatBytes(2048)).toBe('2.0 KB')
    expect(M.formatBytes(92193290)).toBe('87.9 MB')
    expect(M.formatBytes(0)).toBe('0 B')
  })
})

describe('凭据双模式 — 文件 / 环境变量（CI Secrets）', () => {
  it('环境变量齐备 → 解析成功，bucket/endpoint 走默认值', () => {
    const c = M.parseCredsFromEnv({ [M.ENV_AK]: 'AKID', [M.ENV_SK]: 'SECRET' })
    expect(c).toEqual({
      bucket: M.DEFAULT_BUCKET,
      endpoint: M.DEFAULT_ENDPOINT,
      accessKeyId: 'AKID',
      accessKeySecret: 'SECRET'
    })
  })

  it('环境变量可覆盖 bucket / endpoint（无 scheme 自动补 https）', () => {
    const c = M.parseCredsFromEnv({
      [M.ENV_AK]: 'AKID',
      [M.ENV_SK]: 'SECRET',
      [M.ENV_BUCKET]: 'other-bucket',
      [M.ENV_ENDPOINT]: 'oss-cn-shanghai.aliyuncs.com'
    })
    expect(c?.bucket).toBe('other-bucket')
    expect(c?.endpoint).toBe('https://oss-cn-shanghai.aliyuncs.com')
  })

  it('AK 或 SK 任一缺失 → null（调用方据此跳过并警告，不 fail）', () => {
    expect(M.parseCredsFromEnv({})).toBeNull()
    expect(M.parseCredsFromEnv({ [M.ENV_AK]: 'AKID' })).toBeNull()
    expect(M.parseCredsFromEnv({ [M.ENV_SK]: 'SECRET' })).toBeNull()
    expect(M.parseCredsFromEnv({ [M.ENV_AK]: '  ', [M.ENV_SK]: 'SECRET' })).toBeNull()
    expect(M.parseCredsFromEnv(undefined as never)).toBeNull()
  })

  it('凭据来源描述不含任何凭据值', () => {
    const c = M.parseCredsFromEnv({ [M.ENV_AK]: 'AKID', [M.ENV_SK]: 'SECRET' })
    const desc = M.describeCredsSource(c!, '环境变量')
    expect(desc).toContain('环境变量')
    expect(desc).not.toContain('AKID')
    expect(desc).not.toContain('SECRET')
  })
})

describe('对象 key — releases/ 稳定路径（R-8 CI 上传）', () => {
  it('给 prefix → <prefix>/<fileName>（与版本号无关）', () => {
    expect(M.ossObjectKey({ prefix: 'releases', version: '1.0.1', fileName: 'latest.yml' })).toBe('releases/latest.yml')
    expect(M.ossObjectKey({ prefix: 'releases/', version: '1.0.1', fileName: 'a.exe' })).toBe('releases/a.exe')
    expect(M.ossObjectKey({ prefix: '/releases/', version: '1.0.1', fileName: 'a.exe' })).toBe('releases/a.exe')
  })

  it('不给 prefix → 退回 <version>/<fileName>（R-7 行为不变）', () => {
    expect(M.ossObjectKey({ version: '1.0.0', fileName: 'a.exe' })).toBe('1.0.0/a.exe')
    expect(M.ossObjectKey({ prefix: '  ', version: 'v1.0.0', fileName: 'a.exe' })).toBe('1.0.0/a.exe')
    expect(M.ossObjectKey({ prefix: '', version: '1.0.1', fileName: 'a.exe' })).toBe('1.0.1/a.exe')
  })

  it('非法文件名一律抛错（防路径穿越）', () => {
    expect(() => M.ossObjectKey({ prefix: 'releases', version: '1.0.1', fileName: '../x.exe' })).toThrow(/非法文件名/)
    expect(() => M.ossObjectKey({ prefix: 'releases', version: '1.0.1', fileName: '' })).toThrow(/非法文件名/)
  })
})

describe('OSS 错误分诊 — 错误码 → 可执行建议', () => {
  const xml = (code: string, msg = 'm') =>
    `<?xml version="1.0"?><Error><Code>${code}</Code><Message>${msg}</Message><RequestId>RID1</RequestId><HostId>h</HostId></Error>`

  it('M.parseOssError 提取四字段；非 XML 时全空', () => {
    expect(M.parseOssError(xml('InvalidAccessKeyId', 'not exist'))).toEqual({
      code: 'InvalidAccessKeyId',
      message: 'not exist',
      requestId: 'RID1',
      hostId: 'h'
    })
    expect(M.parseOssError('<html>502</html>')).toEqual({ code: '', message: '', requestId: '', hostId: '' })
  })

  it('四类根因各给专属建议（凭据/签名/权限/bucket 不混为一谈）', () => {
    expect(M.explainOssError('InvalidAccessKeyId')).toMatch(/AK ID 是否完整/)
    expect(M.explainOssError('SignatureDoesNotMatch')).toMatch(/时间|偏差/)
    expect(M.explainOssError('AccessDenied')).toMatch(/权限|PutObject/)
    expect(M.explainOssError('NoSuchBucket')).toMatch(/bucket 名|region/)
    expect(M.explainOssError('')).toMatch(/不是 OSS 标准错误 XML/)
    expect(M.explainOssError('WeirdCode')).toMatch(/未收录/)
  })

  it('M.describeOssFailure 汇总状态码 + Message + 建议 + RequestId', () => {
    const s = M.describeOssFailure(403, xml('InvalidAccessKeyId', 'not exist'))
    expect(s).toContain('HTTP 403 InvalidAccessKeyId')
    expect(s).toContain('not exist')
    expect(s).toContain('建议')
    expect(s).toContain('RID1')
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
      // ② 绝不整体打印 creds 对象。白名单：非敏感访问、CLI 参数名/文件名，
      //    以及 describeCredsSource()——它本身有独立断言保证只输出 bucket/endpoint。
      const rest = l
        .replace(/creds\.(bucket|endpoint)/g, '')
        .replace(/--creds/g, '')
        .replace(/creds\.json/g, '')
        .replace(/describeCredsSource\(creds, credsFrom\)/g, '')
      expect(rest, `日志行打印了凭据对象：${l.trim()}`).not.toMatch(/\bcreds\b/)
    }
  })
})
