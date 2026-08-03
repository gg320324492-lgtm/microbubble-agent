<script setup>
/**
 * TranscriptBlock.vue — 会议转录块（折叠/展开）
 * W100 +49b RICHTEXT-UNFOLD 沿用:
 *  - 默认 (block.collapsed_by_default != true) 直接渲染全 transcript, 不显示 toggle
 *  - LLM 显式 collapsed_by_default=true 时保留 ▼ 展开/▲ 收起 切换 UI (协议兼容)
 *
 * 接收 block.data = {meeting_id, title, transcript_text, entries_count, truncated}
 */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({ block: { type: Object, required: true } })

/** LLM-controlled 折叠模式时初始折叠；默认模式永远展开 */
const shouldBeCollapsed = computed(() => props.block.collapsed_by_default === true)
const expanded = ref(!shouldBeCollapsed.value)
const router = useRouter()

const data = computed(() => props.block.data || {})
const text = computed(() => data.value.transcript_text || '')

// 简单按行解析：每行格式 "【speaker】text"
const parsedLines = computed(() => {
  if (!text.value) return []
  return text.value.split('\n').map((line) => {
    const m = line.match(/^【(.+?)】(.*)$/)
    if (m) return { speaker: m[1], text: m[2] }
    return { speaker: '', text: line }
  })
})

const previewLines = computed(() => parsedLines.value.slice(0, 3))
/** 当前是否展开（LLM-controlled 折叠模式下受 toggle 控制；默认模式恒 true） */
const isShown = computed(() => !shouldBeCollapsed.value || expanded.value)

const goToMeeting = () => {
  if (data.value.meeting_id) router.push(`/meetings/${data.value.meeting_id}`)
}

function toggle() {
  expanded.value = !expanded.value
}
</script>

<template>
  <div
    class="transcript-block rich-card"
    :data-testid="'transcript-block'"
    :data-collapsed-by-default="shouldBeCollapsed ? 'true' : 'false'"
  >
    <div class="card-header" @click="shouldBeCollapsed && toggle()">
      <span class="icon">📝</span>
      <span class="title">{{ data.title || '会议转录' }}</span>
      <span class="meta">
        {{ data.entries_count || 0 }} 段
        <span v-if="data.truncated" class="truncated-badge">已截断</span>
      </span>
      <!-- 默认模式不渲染 toggle；LLM 显式折叠时保留 -->
      <span v-if="shouldBeCollapsed" class="toggle" data-testid="transcript-toggle">
        {{ expanded ? '▲ 收起' : '▼ 展开' }}
      </span>
    </div>
    <!-- 默认模式：始终渲染全 transcript；折叠模式：折叠时显示预览，否则全显示 -->
    <div v-if="!shouldBeCollapsed" class="full-transcript">
      <div
        v-for="(line, i) in parsedLines"
        :key="i"
        class="dialogue-line"
      >
        <span v-if="line.speaker" class="speaker">{{ line.speaker }}</span>
        <span class="text">{{ line.text }}</span>
      </div>
    </div>
    <template v-else>
      <div v-if="!isShown" class="preview">
        <div v-for="(line, i) in previewLines" :key="i" class="preview-line">
          <span v-if="line.speaker" class="speaker">{{ line.speaker }}：</span>
          <span class="text">{{ line.text }}</span>
        </div>
        <div v-if="parsedLines.length > 3" class="more">
          ... 共 {{ parsedLines.length }} 行，点击展开
        </div>
      </div>
      <div v-else class="full-transcript">
        <div
          v-for="(line, i) in parsedLines"
          :key="i"
          class="dialogue-line"
        >
          <span v-if="line.speaker" class="speaker">{{ line.speaker }}</span>
          <span class="text">{{ line.text }}</span>
        </div>
      </div>
    </template>
    <div class="card-footer">
      <el-button size="small" @click="goToMeeting" v-if="data.meeting_id">查看会议详情</el-button>
    </div>
  </div>
</template>

<style scoped>
.rich-card { background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.card-header { display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
.icon { font-size: 18px; }
.title { flex: 1; font-weight: 600; font-size: 14px; color: var(--color-primary); }
.meta { font-size: 11px; color: var(--color-text-secondary); display: flex; gap: 6px; align-items: center; }
.truncated-badge { background: var(--color-danger-bg); color: var(--color-danger); padding: 1px 6px; border-radius: 8px; font-size: 10px; }
.toggle { font-size: 12px; color: var(--color-text-secondary); }
.preview { margin-top: 8px; padding: 8px 12px; background: var(--color-bg-warm); border-radius: 6px; }
.preview-line { font-size: 12px; color: var(--color-text-regular); line-height: 1.7; }
.preview-line .speaker { color: var(--color-primary); font-weight: 500; }
.more { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; text-align: center; }
.full-transcript { margin-top: 8px; max-height: 400px; overflow-y: auto; padding: 4px 0; }
.dialogue-line { padding: 6px 0; font-size: 13px; line-height: 1.7; border-bottom: 1px dashed var(--color-border-light); }
.dialogue-line:last-child { border-bottom: none; }
.dialogue-line .speaker { display: inline-block; min-width: 80px; color: var(--color-primary); font-weight: 500; margin-right: 8px; }
.dialogue-line .text { color: var(--color-text-primary); }
.card-footer { margin-top: 8px; text-align: right; }

/* v77 P2.5.3: dark mode 适配 */
[data-theme="dark"] .preview {
  /* light 下 --color-bg-warm 与 --color-bg-hover 同色（#f5f7fa），dark 下变 --color-bg-hover 区分外层卡片 */
  background: var(--color-bg-hover);
}
[data-theme="dark"] .dialogue-line:hover {
  background: var(--color-bg-hover);
}
</style>
