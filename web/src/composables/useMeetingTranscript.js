import { computed, ref } from 'vue'

/**
 * useMeetingTranscript — 会议转录展示统一 composable
 *
 * 2026-08-04 P0: 桌面端 / 移动端之前各自维护转录展示逻辑, 但
 * 1) 字段语义不一致 (mobile 只读 `transcript`, 桌面读 `transcript_polished`)
 * 2) 后端 `transcript_polished[i]` 用 `ts` 字段, mobile 误读 `timestamp` 永远 undefined
 * 3) 591+ 段一次性渲染会爆栈 / 卡顿
 * 4) 没有空/错误/degraded 状态区分
 *
 * 此 composable 统一:
 * - polished || raw 优先逻辑
 * - ts/start 字段兼容
 * - 增量分页 (移动端 30 / 桌面 50)
 * - 失败原因露出
 *
 * 用法:
 *   const { displaySegments, totalSegments, hasMoreSegments, loadMoreSegments } =
 *     useMeetingTranscript(meeting, pageSize)
 *
 * 注意: meeting 是 ref<Meeting|null>, 会响应式跟随会议详情 fetch.
 */
export function useMeetingTranscript(meetingRef, pageSize = 50) {
  const visibleCount = ref(pageSize)

  function tsOf(seg) {
    if (!seg) return null
    if (typeof seg.ts === 'number') return seg.ts
    if (typeof seg.start === 'number') return seg.start
    if (typeof seg.timestamp === 'number') return seg.timestamp
    return null
  }

  const displaySegments = computed(() => {
    const m = meetingRef.value
    if (!m) return []
    const polished = Array.isArray(m.transcript_polished) ? m.transcript_polished : null
    const raw = Array.isArray(m.transcript) ? m.transcript : null
    const list = polished && polished.length ? polished : raw || []
    return list.slice(0, visibleCount.value)
  })

  const totalSegments = computed(() => {
    const m = meetingRef.value
    if (!m) return 0
    const polished = Array.isArray(m.transcript_polished) ? m.transcript_polished : null
    const raw = Array.isArray(m.transcript) ? m.transcript : null
    const list = polished && polished.length ? polished : raw || []
    return list.length
  })

  const hasMoreSegments = computed(() => visibleCount.value < totalSegments.value)

  function loadMoreSegments() {
    visibleCount.value = Math.min(visibleCount.value + pageSize, totalSegments.value)
  }

  function resetPagination() {
    visibleCount.value = pageSize
  }

  return {
    displaySegments,
    totalSegments,
    hasMoreSegments,
    loadMoreSegments,
    resetPagination,
    tsOf,
  }
}