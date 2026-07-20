<template>
  <div class="paragraph-actions">
    <el-tooltip content="翻译这段" placement="top">
      <el-button
        :icon="Promotion"
        size="small"
        text
        @click="handleTranslate"
        :loading="loading"
        data-test="translate-btn"
      />
    </el-tooltip>
    <el-tooltip content="复制原文" placement="top">
      <el-button :icon="CopyDocument" size="small" text @click="handleCopy" data-test="copy-btn" />
    </el-tooltip>
    <el-tooltip content="高亮标注" placement="top">
      <el-button
        :icon="Brush"
        size="small"
        text
        :type="isHighlighted ? 'warning' : 'default'"
        @click="handleHighlight"
        data-test="highlight-btn"
      />
    </el-tooltip>
    <el-tooltip content="问这篇论文" placement="top">
      <el-button :icon="ChatLineRound" size="small" text @click="handleAsk" data-test="ask-btn" />
    </el-tooltip>

    <div v-if="translation" class="paragraph-translation">
      <div class="translation-label">译文</div>
      <div class="translation-text">{{ translation }}</div>
    </div>
  </div>
</template>

<script setup>
/**
 * ParagraphActions - 段落级操作（2026-07-20 实装）
 *
 * 功能：
 * - 翻译这段：调用后端翻译 API (POST /api/v1/translation/translate)
 * - 复制原文：复制段落文本
 * - 高亮标注：localStorage 存 (key=`paper_highlights_<file_id>`, value=Set<paragraph_id>)
 * - 问这篇论文：跳转到 chat 并填入段落内容 (router.push `/chat?preset=...`)
 */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Promotion, CopyDocument, Brush, ChatLineRound } from '@element-plus/icons-vue'
import { translateText } from '@/api/translation'

const props = defineProps({
  paragraph: { type: Object, required: true },
  // 2026-07-20 注入: paper.file_id 作 localStorage key 后缀 + chat 路由 query
  fileId: { type: [Number, String], default: null },
  // chat 路由跳转目标 (默认 /chat)
  chatRoute: { type: String, default: '/chat' },
})

const router = useRouter()
const loading = ref(false)
const translation = ref(null)

// 2026-07-20: 高亮状态从 localStorage 读, 每次 hover 重读
const isHighlighted = computed(() => {
  if (!props.fileId) return false
  try {
    const raw = localStorage.getItem(`paper_highlights_${props.fileId}`)
    if (!raw) return false
    const arr = JSON.parse(raw)
    return Array.isArray(arr) && arr.includes(props.paragraph.id)
  } catch {
    return false
  }
})

async function handleTranslate() {
  if (translation.value) {
    // 已翻译 → toggle 收起
    translation.value = null
    return
  }
  loading.value = true
  try {
    const r = await translateText({ text: props.paragraph.content, target_lang: 'en' })
    translation.value = r.translated_text
  } catch (e) {
    ElMessage.error(e.message || '翻译失败')
    translation.value = null
  } finally {
    loading.value = false
  }
}

async function handleCopy() {
  const text = props.paragraph.content || ''
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text)
      ElMessage.success('已复制原文')
    } catch {
      ElMessage.warning('复制失败，请手动复制')
    }
  } else {
    ElMessage.warning('浏览器不支持剪贴板 API')
  }
}

function handleHighlight() {
  if (!props.fileId) {
    ElMessage.warning('未关联 paper file_id，无法保存高亮')
    return
  }
  const key = `paper_highlights_${props.fileId}`
  let arr = []
  try {
    const raw = localStorage.getItem(key)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) arr = parsed
    }
  } catch {
    // ignore, reset to empty
  }
  const idx = arr.indexOf(props.paragraph.id)
  if (idx >= 0) {
    // 取消高亮
    arr.splice(idx, 1)
    ElMessage.success('已取消高亮')
  } else {
    arr.push(props.paragraph.id)
    ElMessage.success('已高亮标注')
  }
  localStorage.setItem(key, JSON.stringify(arr))
}

function handleAsk() {
  // 2026-07-20: 跳转到 chat 并填入段落内容
  // chat 页面 useChatStream 支持 ?preset= query (与 #043 持久化兼容, 自动建 session + 注入首条 user message)
  const text = (props.paragraph.content || '').slice(0, 2000)  // 防超长
  const query = { preset: `请帮我分析这段: ${text}` }
  router.push({ path: props.chatRoute, query }).catch(() => {
    ElMessage.warning('跳转 chat 失败')
  })
}
</script>

<style scoped>
.paragraph-actions {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 4px 0;
  padding: 2px 4px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.9);
  opacity: 0;
  transition: opacity 0.2s;
  /* pointer-events: 配合 opacity 0 防止透明 div 拦截 hover (Chrome 默认透明 div 也响应 hover) */
  pointer-events: none;
}

.paper-section:hover .paragraph-actions {
  opacity: 1;
  pointer-events: auto;
}

.paper-section:hover .paragraph-actions {
  opacity: 1;
}

.paragraph-translation {
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--color-primary-bg);
  border-left: 3px solid var(--color-primary);
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-primary);
}

.translation-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary);
  margin-bottom: 4px;
}
</style>
