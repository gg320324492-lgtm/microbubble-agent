/**
 * 转录条目状态机
 * pending → polishing → polished | error
 * 提供 key_points 匹配 polished entry 的工具方法
 */
import { ref, computed } from 'vue'

export function useTranscript() {
  const entries = ref([])

  function addOriginal({ segment_id, speaker, text, ts }) {
    entries.value.push({
      id: segment_id,
      speaker,
      text,
      originalText: text,
      ts,
      status: 'pending',
      keyPoints: [],
    })
  }

  function applyPolished({ segment_id, polished, key_points }) {
    const entry = entries.value.find((e) => e.id === segment_id)
    if (!entry) return
    if (polished && polished.length > 0) {
      entry.text = polished[0].text
    }
    entry.status = 'polished'
    // 匹配 key_points（按 ts 在 0.5s 内）
    entry.keyPoints = (key_points || []).filter((kp) =>
      Math.abs(kp.ts - entry.ts) < 0.5
    )
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

  const fontSize = computed(() => {
    const n = entries.value.length
    if (n < 5) return { size: '22px', lineHeight: 1.8 }
    if (n < 10) return { size: '18px', lineHeight: 1.6 }
    return { size: '15px', lineHeight: 1.4 }
  })

  return {
    entries,
    addOriginal,
    applyPolished,
    markError,
    clear,
    fontSize,
  }
}
