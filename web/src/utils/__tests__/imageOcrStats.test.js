/**
 * computeImageOcrStats 单测 (2026-10-09 agent33 —— done_no_text 统计口径修复)
 *
 * 背景：后端 `c9dc3f484`(agent31) 把 ocr_status='done' 拆成 done / done_no_text。
 * 旧口径只 filter 'done'/'failed'/'pending'/'skipped'，其余枚举在 UI 上蒸发
 * （实测全库 5446 张里 done_no_text=3317，占 61%）。
 *
 * 跑法: npx vitest run src/utils/__tests__/imageOcrStats.test.js
 */
import { describe, it, expect } from 'vitest'
import { computeImageOcrStats, OCR_STATUS } from '@/utils/imageOcrStats'

const img = (ocr_status) => ({ id: Math.random(), ocr_status })

describe('computeImageOcrStats', () => {
  it('空列表 → 全零', () => {
    expect(computeImageOcrStats([])).toEqual({
      total: 0, done: 0, doneNoText: 0, failed: 0, pending: 0, skipped: 0, other: 0,
    })
  })

  it('done_no_text 单列一桶，不并入 done（本次修复的核心）', () => {
    const s = computeImageOcrStats([img('done'), img('done'), img('done_no_text'), img('done_no_text')])
    expect(s.done).toBe(2)
    expect(s.doneNoText).toBe(2)
    // 关键断言：并入 done 会让 done=4，把「没产出文本」说成「完成」
    expect(s.done).not.toBe(4)
  })

  it('真实分布还原：5446 张 → done 2050 / done_no_text 3317 / failed 79', () => {
    const images = [
      ...Array(2050).fill(null).map(() => img('done')),
      ...Array(3317).fill(null).map(() => img('done_no_text')),
      ...Array(79).fill(null).map(() => img('failed')),
    ]
    const s = computeImageOcrStats(images)
    expect(s.total).toBe(5446)
    expect(s.done).toBe(2050)
    expect(s.doneNoText).toBe(3317)
    expect(s.failed).toBe(79)
  })

  it('不变量：各桶之和恒等于 total（任何一张图都不许消失）', () => {
    // 掺入两个未列举状态：partial + 一个未来枚举 + null
    const images = [
      img('done'), img('done_no_text'), img('failed'), img('pending'),
      img('skipped'), img('partial'), img('brand_new_status'), img(null),
    ]
    const s = computeImageOcrStats(images)
    const sum = s.done + s.doneNoText + s.failed + s.pending + s.skipped + s.other
    expect(sum).toBe(s.total)
    expect(s.total).toBe(8)
    expect(s.other).toBe(3) // partial + brand_new_status + null
  })

  it('skipped 是终态，单列而不混进「处理中」', () => {
    const s = computeImageOcrStats([img('skipped'), img('pending')])
    expect(s.skipped).toBe(1)
    expect(s.pending).toBe(1)
    // 混进 pending 会让用户以为装饰横幅还在排队，实际 OCR 永远不会再跑
    expect(s.pending).not.toBe(2)
  })

  it('缺失 / null / undefined 输入安全', () => {
    expect(computeImageOcrStats(null)).toEqual({
      total: 0, done: 0, doneNoText: 0, failed: 0, pending: 0, skipped: 0, other: 0,
    })
    expect(computeImageOcrStats(undefined).total).toBe(0)
    expect(computeImageOcrStats('not-an-array').total).toBe(0)
    expect(computeImageOcrStats([]).total).toBe(0)
  })

  it('数组含 null 元素不抛异常（计入 other）', () => {
    const s = computeImageOcrStats([null, undefined, img('done')])
    expect(s.total).toBe(3)
    expect(s.other).toBe(2)
    expect(s.done).toBe(1)
  })

  it('导出的 OCR_STATUS 常量与后端枚举字面量一致', () => {
    // 这几个字符串必须与 app/models/knowledge_multimodal.py 的落库值一致，
    // 拼错会让整桶静默归入 other（正是本文件要防的那类 bug）
    expect(OCR_STATUS.DONE).toBe('done')
    expect(OCR_STATUS.DONE_NO_TEXT).toBe('done_no_text')
    expect(OCR_STATUS.FAILED).toBe('failed')
    expect(OCR_STATUS.PENDING).toBe('pending')
    expect(OCR_STATUS.SKIPPED).toBe('skipped')
  })
})