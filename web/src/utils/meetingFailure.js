/**
 * meetingFailure.js — 会议失败态的可读化 + 补救动作判定 (2026-10-25)
 *
 * 背景: 会议 258 的 error_reason 是裸技术串
 *   「录音超过 30min 未 stop, (last_chunk_index=-1, total_chunks=None), [UA: Mozilla/5.0 (iPhone...)]」
 * 前端只把它当纯文本甩给用户 → 既看不懂, 也不知道下一步该做什么。
 * 而后端其实早就有补救能力 (POST /api/v1/meetings/{id}/reprocess; audio-chunk 已放宽到接受
 * status='error' 的补传 → merge-chunks → reprocess 三步链), 但前端一处都没调用
 * ⇒ 用户看到失败会议完全无法自救。
 *
 * 本模块是「后端状态字段 → 用户能看懂的下一步」的**唯一切换点**, 桌面端与移动端共用:
 * 两个页面各写一份文案必然漂移 (类 20.220 —— 两个页面说法不一致, 等于状态字段在骗人)。
 *
 * 契约:
 * - describeMeetingFailure(meeting) 永远返回对象, 不抛异常, 不返回 null
 *   ⇒ 调用方只需 v-if="meeting.status === 'error'" 即可, 无需再做空值防御
 * - technical 字段保留原始 error_reason, 供折叠展示与事后排查, 不直接当主文案
 */

/** 失败类型编码 —— 与后端 error_reason 的取值无关, 是前端自己的语义分类 */
export const FAILURE_CODE = {
  /** 录音被系统挂起 / 未正常 stop */
  RECORDING_INTERRUPTED: 'recording_interrupted',
  /** 录音结束但一个音频分片都没收到 */
  NO_AUDIO: 'no_audio',
  /** 分片合并失败 */
  MERGE_FAILED: 'merge_failed',
  /** 流水线中后段出错(转写/声纹/摘要) */
  PIPELINE_FAILED: 'pipeline_failed',
  /** 没有任何错误信息 */
  UNKNOWN: 'unknown',
}

/** 补救动作 */
export const FAILURE_ACTION = {
  /** 音频还在(已合并或有分片) → 可以直接重跑流水线 */
  REPROCESS: 'reprocess',
  /** 音频没了 → 只能重新上传 */
  REUPLOAD: 'reupload',
}

/**
 * 会议是否还留着可补救的音频数据。
 * 判据与后端 reprocess 守卫完全一致 (app/api/v1/meeting_recording.py):
 *   has_audio = bool(audio_url) or (last_chunk_index is not None and last_chunk_index >= 0)
 * 两边不一致就会出现「前端显示可重试, 后端回 400」的错位。
 */
export function hasRecoverableAudio(meeting) {
  if (!meeting) return false
  if (meeting.audio_url) return true
  const raw = meeting.last_chunk_index
  // ⚠️ 不能直接 Number(raw): Number(null) === 0 → 会被误判成"有分片可补救",
  // 而后端守卫是 `last_chunk_index is not None and >= 0` (null → False)。
  // 两边判据必须一致, 否则前端显示"可重新处理"、后端回 400 (类 20.220)。
  if (raw === null || raw === undefined || raw === '') return false
  const idx = Number(raw)
  return Number.isFinite(idx) && idx >= 0
}

/**
 * 规则表 —— 顺序敏感: 先具体后通用。
 * 每条规则的 detail 是**用户能据此行动**的话, 不是状态字段的复述 (类 20.229:
 * 只写「别信 X」不够, 必须写明「那该怎么做」)。
 */
const RULES = [
  {
    code: FAILURE_CODE.RECORDING_INTERRUPTED,
    match: (r) => /未\s*stop|超过\s*30\s*min|未正常结束|被系统挂起|中断/i.test(r),
    title: '录音没有正常结束',
    detail:
      '录音过程中手机息屏或切到后台，被系统挂起后没有发出结束信号，音频也没能上传。' +
      '如果录音文件还在手机里，重新上传一次就能正常处理。',
  },
  {
    code: FAILURE_CODE.NO_AUDIO,
    match: (r) => /未收到任何音频|never_uploaded|未收到任何分片|last_chunk_index=-1/i.test(r),
    title: '录音没有上传成功',
    detail:
      '录音结束了，但没有收到任何音频数据，通常是网络中断或页面被关闭导致分片没传上来。' +
      '重新上传这段录音即可继续处理。',
  },
  {
    code: FAILURE_CODE.MERGE_FAILED,
    match: (r) => /merge failed|合并失败/i.test(r),
    title: '音频合并失败',
    detail:
      '上传的分片没能合并成一个可播放的音频文件。可以重试一次；若仍然失败，请重新上传录音。',
  },
]

const PIPELINE_TITLE = '会议处理失败'
const PIPELINE_DETAIL =
  '处理这条会议时发生了错误。可以重试一次；若仍然失败，请重新上传录音后再次处理。'

/**
 * 把一条失败会议翻译成 { code, title, detail, recoverable, action, actionLabel, hint, technical }
 *
 * @param {object|null} meeting 会议对象(至少含 status / error_reason / audio_url / last_chunk_index)
 * @returns {object} 永远非 null
 */
export function describeMeetingFailure(meeting) {
  const raw = typeof meeting?.error_reason === 'string' ? meeting.error_reason.trim() : ''
  const recoverable = hasRecoverableAudio(meeting)
  const rule = raw ? RULES.find((r) => r.match(raw)) : null

  const code = rule ? rule.code : raw ? FAILURE_CODE.PIPELINE_FAILED : FAILURE_CODE.UNKNOWN
  const title = rule ? rule.title : PIPELINE_TITLE
  const detail = rule ? rule.detail : PIPELINE_DETAIL
  const action = recoverable ? FAILURE_ACTION.REPROCESS : FAILURE_ACTION.REUPLOAD

  return {
    code,
    title,
    detail,
    /** 音频是否还在 —— 决定能不能直接重跑流水线 */
    recoverable,
    action,
    actionLabel: recoverable ? '重新处理' : '重新上传录音',
    /** 无音频时给出去处; 有音频时为空串 */
    hint: recoverable ? '' : '请回到「听会」页面重新上传这段录音，处理会自动重新开始。',
    /** 原始技术串, 供折叠展示/排查, 不作为主文案 */
    technical: raw,
  }
}

/**
 * 是否应展示失败态 UI。
 * 判据 = status 为 error/error-like, 而不是「有没有 error_reason」——
 * 后端在极端情况下会只置 status 不写 error_reason (类 20.220: 状态字段会单独缺失)。
 */
export function shouldShowFailure(meeting) {
  const s = meeting?.status
  return s === 'error' || s === 'failed'
}
