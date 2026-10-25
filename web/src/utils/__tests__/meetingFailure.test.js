/**
 * meetingFailure 回归测试 (2026-10-25)
 *
 * 背景: 会议 258 的失败态在前端只显示裸技术串
 *   「录音超过 30min 未 stop, (last_chunk_index=-1, total_chunks=None), [UA: Mozilla/5.0 (iPhone...)]」
 * ⇒ 用户既看不懂也不知道能做什么。本模块把状态字段翻译成可读文案 + 可执行的补救动作。
 *
 * 用例覆盖:
 * ① 258 真实 error_reason → 归类 recording_interrupted, 无音频 ⇒ 动作=重新上传
 * ② 「未收到任何音频」→ no_audio
 * ③ 「merge failed: ...」→ merge_failed
 * ④ 未知错误 → pipeline_failed
 * ⑤ 规则顺序: no_audio 的判据里含 last_chunk_index=-1, 不得被 interrupted 规则抢先
 * ⑥ 有音频(error + audio_url) ⇒ recoverable, 动作=重新处理
 * ⑦ 有分片(last_chunk_index=0) ⇒ recoverable
 * ⑧ last_chunk_index=null ⇒ 不可补救(与后端 `is not None` 守卫一致; Number(null)===0 的坑)
 * ⑨ error_reason 缺失 ⇒ unknown, 但仍给出可读标题
 * ⑩ null meeting 不抛异常
 * ⑪ shouldShowFailure 认 error/failed, 不认 completed
 */
import { describe, expect, it } from 'vitest'
import {
  FAILURE_ACTION,
  FAILURE_CODE,
  describeMeetingFailure,
  hasRecoverableAudio,
  shouldShowFailure,
} from '../meetingFailure'

/** 会议 258 的真实 error_reason (2026-10-19, iPhone Safari) */
const REASON_258 =
  '录音超过 30min 未 stop, (last_chunk_index=-1, total_chunks=None), ' +
  '[UA: Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 ' +
  '(KHTML, like Gecko) Version/26.6 Mobile/15E148 Safari/604.1]'

describe('describeMeetingFailure 失败态可读化', () => {
  it('① 258 真实 error_reason → recording_interrupted, 无音频 ⇒ 重新上传', () => {
    const info = describeMeetingFailure({
      status: 'error',
      error_reason: REASON_258,
      audio_url: null,
      last_chunk_index: -1,
    })
    expect(info.code).toBe(FAILURE_CODE.RECORDING_INTERRUPTED)
    expect(info.recoverable).toBe(false)
    expect(info.action).toBe(FAILURE_ACTION.REUPLOAD)
    expect(info.actionLabel).toBe('重新上传录音')
    expect(info.hint).toContain('听会')
    // technical 保留原文供排查, 但不作为主文案
    expect(info.technical).toBe(REASON_258)
    expect(info.detail).not.toContain('last_chunk_index')
  })

  it('② 「未收到任何音频」→ no_audio', () => {
    const info = describeMeetingFailure({
      status: 'error',
      error_reason: '录音结束但未收到任何音频（last_chunk_index=-1）',
      last_chunk_index: -1,
    })
    expect(info.code).toBe(FAILURE_CODE.NO_AUDIO)
    expect(info.recoverable).toBe(false)
  })

  it('③ 「merge failed: ...」→ merge_failed', () => {
    const info = describeMeetingFailure({
      status: 'error',
      error_reason: 'merge failed: ffmpeg exited 1',
      audio_url: 'recordings/259/merged.m4a',
      last_chunk_index: 2,
    })
    expect(info.code).toBe(FAILURE_CODE.MERGE_FAILED)
    expect(info.recoverable).toBe(true)
    expect(info.action).toBe(FAILURE_ACTION.REPROCESS)
  })

  it('④ 未知错误 → pipeline_failed, 仍给出可读标题与补救动作', () => {
    const info = describeMeetingFailure({
      status: 'error',
      error_reason: 'something went sideways',
      last_chunk_index: -1,
    })
    expect(info.code).toBe(FAILURE_CODE.PIPELINE_FAILED)
    expect(info.title).toBe('会议处理失败')
    expect(info.detail.length).toBeGreaterThan(0)
    expect(info.action).toBe(FAILURE_ACTION.REUPLOAD)
  })

  it('⑤ 规则顺序: 含 last_chunk_index=-1 的 no_audio 不得被 interrupted 规则抢先', () => {
    const info = describeMeetingFailure({
      status: 'error',
      error_reason: '录音结束但未收到任何音频（last_chunk_index=-1）',
      last_chunk_index: -1,
    })
    expect(info.code).toBe(FAILURE_CODE.NO_AUDIO)
  })
})

describe('hasRecoverableAudio 与后端 reprocess 守卫对齐', () => {
  it('⑥ 有 audio_url ⇒ 可补救', () => {
    expect(hasRecoverableAudio({ audio_url: 'recordings/259/merged.m4a', last_chunk_index: -1 })).toBe(true)
  })

  it('⑦ 有分片(last_chunk_index=0) ⇒ 可补救', () => {
    expect(hasRecoverableAudio({ audio_url: null, last_chunk_index: 0 })).toBe(true)
  })

  it('⑧ last_chunk_index=null ⇒ 不可补救(Number(null)===0 的坑)', () => {
    expect(hasRecoverableAudio({ audio_url: null, last_chunk_index: null })).toBe(false)
    expect(hasRecoverableAudio({ audio_url: null, last_chunk_index: undefined })).toBe(false)
    expect(hasRecoverableAudio({ audio_url: null, last_chunk_index: -1 })).toBe(false)
  })

  it('⑩ null meeting 不抛异常, 返回不可补救', () => {
    expect(hasRecoverableAudio(null)).toBe(false)
    const info = describeMeetingFailure(null)
    expect(info).toBeTruthy()
    expect(info.recoverable).toBe(false)
    expect(info.action).toBe(FAILURE_ACTION.REUPLOAD)
  })
})

describe('error_reason 缺失与失败态判定', () => {
  it('⑨ error_reason 缺失 ⇒ unknown, 但仍给出可读标题', () => {
    const info = describeMeetingFailure({ status: 'error', last_chunk_index: -1 })
    expect(info.code).toBe(FAILURE_CODE.UNKNOWN)
    expect(info.title).toBe('会议处理失败')
    expect(info.technical).toBe('')
  })

  it('⑪ shouldShowFailure 认 error/failed, 不认 completed/recording', () => {
    expect(shouldShowFailure({ status: 'error' })).toBe(true)
    expect(shouldShowFailure({ status: 'failed' })).toBe(true)
    expect(shouldShowFailure({ status: 'completed' })).toBe(false)
    expect(shouldShowFailure({ status: 'recording' })).toBe(false)
    expect(shouldShowFailure({ status: 'processing' })).toBe(false)
    expect(shouldShowFailure(null)).toBe(false)
  })
})
