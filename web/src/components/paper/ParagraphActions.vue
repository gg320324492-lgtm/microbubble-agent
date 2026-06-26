<template>
  <div class="paragraph-actions" v-if="visible">
    <el-tooltip content="翻译这段" placement="top">
      <el-button
        :icon="Promotion"
        size="small"
        text
        @click="handleTranslate"
        :loading="loading"
      />
    </el-tooltip>
    <el-tooltip content="复制原文" placement="top">
      <el-button :icon="CopyDocument" size="small" text @click="handleCopy" />
    </el-tooltip>
    <el-tooltip content="高亮标注" placement="top">
      <el-button :icon="Brush" size="small" text @click="handleHighlight" />
    </el-tooltip>
    <el-tooltip content="问这篇论文" placement="top">
      <el-button :icon="ChatLineRound" size="small" text @click="handleAsk" />
    </el-tooltip>

    <div v-if="translation" class="paragraph-translation">
      <div class="translation-label">译文</div>
      <div class="translation-text">{{ translation }}</div>
    </div>
  </div>
</template>

<script setup>
/**
 * ParagraphActions - 段落级操作（阶段 4 预留）
 *
 * 功能：
 * - 翻译这段：调用后端翻译 API，显示译文
 * - 复制原文：复制段落文本
 * - 高亮标注：标记段落颜色（等待学习辅助功能）
 * - 问这篇论文：跳转到 chat 并填入段落内容
 */
import { ref } from 'vue'
import { Promotion, CopyDocument, Brush, ChatLineRound } from '@element-plus/icons-vue'

const props = defineProps({
  paragraph: { type: Object, required: true },
})

const visible = ref(false)  // 鼠标悬停才显示
const loading = ref(false)
const translation = ref(null)

async function handleTranslate() {
  if (translation.value) {
    translation.value = null
    return
  }
  loading.value = true
  try {
    // TODO: 接入后端翻译 API
    // const r = await axios.post(`/api/v1/papers/${paperId}/translate`, { text: props.paragraph.content })
    // translation.value = r.data.translation
    // 当前 mock：等待后端 API
    translation.value = '[翻译功能待接入后端 API]'
  } finally {
    loading.value = false
  }
}

function handleCopy() {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(props.paragraph.content || '').catch(() => {})
  }
}

function handleHighlight() {
  // TODO: 接入高亮存储（localStorage / 后端）
  console.log('[ParagraphActions] highlight paragraph:', props.paragraph.id)
}

function handleAsk() {
  // TODO: 跳转到 chat 并填入段落内容
  console.log('[ParagraphActions] ask about paragraph:', props.paragraph.id)
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
