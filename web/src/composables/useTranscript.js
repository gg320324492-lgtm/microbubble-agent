/**
 * 转录条目状态机（2026-06-02 三级润色改造）
 * - L1 实时：addOriginal() 入队，status='raw'，显示原文
 * - L2 聚批：applyBatchPolished() 按 segment_ids 匹配写 polishedText，status='batch_polished'
 * - L3 全文：applyFullPolished() 写 fullPolishedText + removed，status='full_polished'
 * - 兼容旧 API：applyPolished() 旧单条润色（保持 status='polished'）
 *
 * 显示策略（displayEntries computed）：
 * - viewMode='raw'：用 originalText
 * - viewMode='polished'：优先 fullPolishedText ?? polishedText ?? originalText
 */
import { ref, computed } from 'vue'

export function useTranscript() {
  const entries = ref([])
  // 视图模式：'raw'（默认实时原文） / 'polished'（AI 润色版）
  const viewMode = ref('raw')

  function addOriginal({ segment_id, speaker, text, ts }) {
    entries.value.push({
      id: segment_id,
      speaker,
      text,                 // 当前显示文本（按 viewMode 计算）
      originalText: text,   // L1 原文
      polishedText: '',     // L2 聚批润色后
      fullPolishedText: '', // L3 全文精润色后
      ts,
      status: 'raw',        // 'raw' | 'batch_polished' | 'full_polished' | 'polished' (兼容) | 'error'
      removed: false,       // L3 标记为已过滤幻觉
      polishFailed: false,  // L3 chunk 失败标记
      keyPoints: [],
    })
  }

  function applyPolished({ segment_id, polished, key_points }) {
    // 兼容旧 API：单条 L2 润色
    const entry = entries.value.find((e) => e.id === segment_id)
    if (!entry) return
    if (polished && polished.length > 0) {
      entry.polishedText = polished[0].text
    }
    entry.status = 'polished'
    entry.keyPoints = (key_points || []).filter((kp) =>
      Math.abs(kp.ts - entry.ts) < 0.5
    )
  }

  function applyBatchPolished({ segment_ids, polished, key_points, summary }) {
    // L2 聚批润色：按 segment_ids[i] ↔ polished[i] 写 polishedText
    if (!Array.isArray(segment_ids) || !Array.isArray(polished)) return
    for (let i = 0; i < segment_ids.length; i++) {
      const entry = entries.value.find((e) => e.id === segment_ids[i])
      if (!entry) continue
      if (polished[i] && polished[i].text) {
        entry.polishedText = polished[i].text
      }
      entry.status = 'batch_polished'
      // 全局 key_points 匹配（按 ts 在 0.5s 内）
      if (Array.isArray(key_points)) {
        entry.keyPoints = key_points.filter((kp) =>
          Math.abs(kp.ts - entry.ts) < 0.5
        )
      }
    }
  }

  function applyFullPolished(polishedSegments) {
    // L3 全文精润色：polishedSegments = [{segment_id, speaker, text, removed, reason}]
    if (!Array.isArray(polishedSegments)) return
    for (const ps of polishedSegments) {
      const entry = entries.value.find((e) => e.id === ps.segment_id)
      if (!entry) continue
      if (ps.text) {
        entry.fullPolishedText = ps.text
      }
      if (ps.removed) {
        entry.removed = true
        if (ps.reason) entry.removeReason = ps.reason
      }
      if (ps.polish_failed) {
        entry.polishFailed = true
      }
      entry.status = 'full_polished'
    }
  }

  function markError({ segment_id, error }) {
    const entry = entries.value.find((e) => e.id === segment_id)
    if (!entry) return
    entry.status = 'error'
    entry.error = error || '润色失败'
  }

  function clear() {
    entries.value = []
  }

  // 计算每个 entry 的 displayText（按 viewMode 选字段）
  const displayEntries = computed(() => {
    return entries.value.map((e) => {
      let displayText
      if (viewMode.value === 'raw') {
        displayText = e.originalText
      } else {
        // polished 模式：优先 L3 > L2 > L1
        displayText = e.fullPolishedText || e.polishedText || e.originalText
      }
      return { ...e, displayText }
    })
  })

  // 是否有任何 L2/L3 润色结果（用于 tab 启用判断）
  const hasAnyPolished = computed(() => {
    return entries.value.some(
      (e) => e.fullPolishedText || e.polishedText || e.status === 'batch_polished' || e.status === 'full_polished' || e.status === 'polished'
    )
  })

  const fontSize = computed(() => {
    const n = entries.value.length
    if (n < 5) return { size: '22px', lineHeight: 1.8 }
    if (n < 10) return { size: '18px', lineHeight: 1.6 }
    return { size: '15px', lineHeight: 1.4 }
  })

  return {
    entries,
    viewMode,
    displayEntries,
    hasAnyPolished,
    addOriginal,
    applyPolished,        // 兼容旧 API
    applyBatchPolished,   // L2
    applyFullPolished,    // L3
    markError,
    clear,
    fontSize,
  }
}
