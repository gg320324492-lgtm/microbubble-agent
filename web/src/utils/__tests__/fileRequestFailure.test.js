// fileRequestFailure.test.js — 匿名收件页失败文案映射的单测 (2026-11-09)
//
// 这里守的是**用户能不能据此行动**: 同一个 HTTP 码在不同语义下必须给出不同的话
// (409 既可能是"链接收满了"也可能是"片没传齐" —— 前者要联系发起人, 后者点重试就行)。
import { describe, it, expect } from 'vitest'
import {
  FR_FAILURE_ACTION,
  FR_FAILURE_CODE,
  describeFileRequestFailure,
  detailOf,
  statusOf,
} from '@/utils/fileRequestFailure'

/** 造一个 axios 风格的错误 */
function httpError(status, detail) {
  return { response: { status, data: { detail } }, message: `Request failed with status code ${status}` }
}

describe('statusOf / detailOf', () => {
  it('statusOf: 无 response ⇒ 0 (网络层失败)', () => {
    expect(statusOf(new Error('Network Error'))).toBe(0)
    expect(statusOf(null)).toBe(0)
  })
  it('statusOf: 字符串状态码也要认 (某些 mock 给的是字符串)', () => {
    expect(statusOf({ response: { status: '413' } })).toBe(413)
  })
  it('detailOf: 优先 HTTPException 的 detail, 再退到统一异常格式', () => {
    expect(detailOf(httpError(410, '这个收件链接已过期'))).toBe('这个收件链接已过期')
    expect(detailOf({ response: { data: { error: { message: 'X' } } } })).toBe('X')
    // "Network Error" 必须翻成空, 否则会被当后端文案显示给用户
    expect(detailOf(new Error('Network Error'))).toBe('')
  })
})

describe('describeFileRequestFailure —— 契约里列的 7 个码', () => {
  it('404 链接不存在 → 联系发起人 (与 404 会话不存在分开)', () => {
    const f = describeFileRequestFailure(httpError(404, '文件请求不存在'))
    expect(f.code).toBe(FR_FAILURE_CODE.LINK_NOT_FOUND)
    expect(f.action).toBe(FR_FAILURE_ACTION.CONTACT)
  })

  it('404 {"detail":"Not Found"} ⇒ 是"路由不存在"不是"链接不存在" (后端没部署)', () => {
    // 判据实测自 2026-11-09 运行中的 app 容器:
    //   POST /api/v1/file-requests/x/uploads (未注册) → {"detail":"Not Found"}
    //   GET  /api/v1/file-requests/x/info    (业务 404) → {"detail":"文件请求不存在"}
    // 两者都是 404。若不分家, 前端会叫外部人员"去要新链接", 而真正该做的是部署后端。
    const undeployed = describeFileRequestFailure(httpError(404, 'Not Found'))
    const badToken = describeFileRequestFailure(httpError(404, '文件请求不存在'))
    expect(undeployed.title).toMatch(/服务当前不可用|没有找到/)
    expect(undeployed.action).toBe(FR_FAILURE_ACTION.RETRY)
    expect(badToken.code).toBe(FR_FAILURE_CODE.LINK_NOT_FOUND)
    expect(badToken.action).toBe(FR_FAILURE_ACTION.CONTACT)
    expect(undeployed.title).not.toBe(badToken.title)
  })

  it('404 上传会话不存在 → 重选文件即可, 不许让人去联系发起人', () => {
    const f = describeFileRequestFailure(httpError(404, '上传会话不存在'))
    expect(f.code).toBe(FR_FAILURE_CODE.SESSION_GONE)
    expect(f.action).toBe(FR_FAILURE_ACTION.RESELECT)
  })

  it('409「片未传齐」≠ 409「已收满」—— 同一个码两种处置', () => {
    const incomplete = describeFileRequestFailure(httpError(409, '还有 3 片未上传 (示例: [1,2,3])'))
    const full = describeFileRequestFailure(httpError(409, '该收件链接已收满 5 个文件'))
    expect(incomplete.code).toBe(FR_FAILURE_CODE.CHUNKS_INCOMPLETE)
    expect(incomplete.action).toBe(FR_FAILURE_ACTION.RETRY)
    expect(full.code).toBe(FR_FAILURE_CODE.QUOTA_FULL)
    expect(full.action).toBe(FR_FAILURE_ACTION.CONTACT)
    // 两条话必须不同, 否则用户会拿"重试"去撞一个已经收满的链接
    expect(incomplete.detail).not.toBe(full.detail)
  })

  it('409 进行中上传数到顶 → 等一会儿, 不是"没份了"', () => {
    const f = describeFileRequestFailure(httpError(409, '该链接的进行中上传数已达上限，请等待当前上传完成或过期'))
    expect(f.action).toBe(FR_FAILURE_ACTION.WAIT)
    expect(f.title).not.toMatch(/收满/)
  })

  it('410 链接关闭/过期 → 联系发起人', () => {
    const f = describeFileRequestFailure(httpError(410, '这个收件链接已关闭，请联系发起人重新开启'))
    expect(f.code).toBe(FR_FAILURE_CODE.LINK_CLOSED)
    expect(f.action).toBe(FR_FAILURE_ACTION.CONTACT)
  })

  it('410 会话过期 → 重新上传, 且**不要求**联系人 (是自己走开了)', () => {
    const f = describeFileRequestFailure(httpError(410, '上传会话已过期'))
    expect(f.code).toBe(FR_FAILURE_CODE.SESSION_GONE)
    expect(f.action).toBe(FR_FAILURE_ACTION.RESELECT)
  })

  it('413 单文件超上限 vs 累计总量超上限 要分开', () => {
    const one = describeFileRequestFailure(httpError(413, '文件 9000 MB 超过单文件上限 8192 MB'))
    const total = describeFileRequestFailure(httpError(413, '本次收件已达总量上限：已用 28000 MB + 本次 3000 MB > 上限 30720 MB'))
    expect(one.code).toBe(FR_FAILURE_CODE.FILE_TOO_BIG)
    expect(total.code).toBe(FR_FAILURE_CODE.TOTAL_TOO_BIG)
    expect(one.detail).not.toBe(total.detail)
  })

  it('415 扩展名不允许 → 换文件', () => {
    const f = describeFileRequestFailure(httpError(415, '不允许的文件类型 .exe，仅支持 .mp4, .mov'))
    expect(f.code).toBe(FR_FAILURE_CODE.EXT_NOT_ALLOWED)
    expect(f.action).toBe(FR_FAILURE_ACTION.RESELECT)
  })

  it('422 逐片校验失败 → 可重试 (后端只拒这一片)', () => {
    const f = describeFileRequestFailure(httpError(422, '第 7 片校验失败（传输已损坏），请重传该片'))
    expect(f.code).toBe(FR_FAILURE_CODE.CHUNK_CORRUPT)
    expect(f.action).toBe(FR_FAILURE_ACTION.RETRY)
  })

  it('500 合并失败 → 说清"残缺对象已被丢弃、不会留半个文件"', () => {
    const f = describeFileRequestFailure(httpError(500, '分片合并失败'))
    expect(f.code).toBe(FR_FAILURE_CODE.MERGE_FAILED)
    expect(f.detail).toMatch(/丢弃/)
  })

  it('网络断了 → 强调已传部分还在, 能续传', () => {
    const f = describeFileRequestFailure(new Error('Network Error'))
    expect(f.code).toBe(FR_FAILURE_CODE.NETWORK)
    expect(f.action).toBe(FR_FAILURE_ACTION.RETRY)
    expect(f.detail).toMatch(/断点|接着传/)
  })
})

describe('契约: 永远返回对象 + 不许把裸状态码当主文案', () => {
  it('null / undefined / 空对象都不抛异常', () => {
    for (const input of [null, undefined, {}, new Error('x'), { response: {} }]) {
      const f = describeFileRequestFailure(input)
      expect(f).toBeTypeOf('object')
      expect(typeof f.title).toBe('string')
      expect(f.title.length).toBeGreaterThan(0)
      expect(typeof f.detail).toBe('string')
      expect(f.detail.length).toBeGreaterThan(0)
      expect(Object.values(FR_FAILURE_ACTION)).toContain(f.action)
    }
  })

  it('主文案里不许出现 HTTP 码或 axios 原始串 (technical 里才有)', () => {
    for (const st of [404, 409, 410, 413, 415, 422, 429, 500]) {
      const f = describeFileRequestFailure(httpError(st, '后端中文'))
      expect(f.title).not.toMatch(/HTTP|\d{3}/)
      expect(f.detail).not.toMatch(/Request failed with status/)
      expect(f.technical).toMatch(/HTTP/)   // 技术详情折叠区保留原文
    }
  })
})
