<template>
  <div class="translation-panel" v-if="visible">
    <div class="panel-header">
      <span class="panel-title">📖 全文翻译</span>
      <el-select v-model="targetLang" size="small" style="width: 120px" @change="doTranslate">
        <el-option label="English" value="en" />
        <el-option label="中文" value="zh" />
        <el-option label="日本語" value="ja" />
        <el-option label="한국어" value="ko" />
        <el-option label="Français" value="fr" />
        <el-option label="Deutsch" value="de" />
      </el-select>
      <el-button size="small" text @click="doTranslate" :loading="loading">重新翻译</el-button>
      <span class="panel-status" v-if="loading">翻译中...</span>
      <el-button text size="small" @click="$emit('close')" :icon="Close" />
    </div>
    <div class="panel-body" v-loading="loading">
      <el-empty v-if="!loading && !translations.length" description="打开面板自动开始翻译" />
      <div v-else class="translation-list">
        <div v-for="t in translations" :key="t.id" class="translation-item">
          <div class="original-text">{{ t.original }}</div>
          <div v-if="t.error" class="translated-text translation-error">{{ t.error }}</div>
          <div v-else class="translated-text">{{ t.translated || '...' }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * TranslationPanel - 全文翻译面板（2026-07-20 实装 API）
 *
 * 后端 API: POST /api/v1/translation/translate
 *   body: { text: string, target_lang: string }
 *   response: { translated_text: string, target_lang: string, source_length: number }
 *
 * 行为：逐 section 调 translateText，target_lang 默认 'en'（论文最常翻译成英文）
 *       失败时 section.translated 留空 + section.error 存错误信息（前端不显示空白）
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import { translateText } from '@/api/translation'

const props = defineProps({
  paper: { type: Object, default: () => ({}) },
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const loading = ref(false)
const translations = ref([])
const targetLang = ref('en')  // 默认翻译成英文

async function doTranslate() {
  const sections = props.paper?.sections || []
  if (!sections.length) {
    ElMessage.warning('当前论文没有可翻译的段落')
    return
  }
  loading.value = true
  translations.value = sections.map((s) => ({
    id: s.id,
    original: s.content,
    translated: '',
    error: null,
  }))
  try {
    // 串行翻译避免 LLM 限流 (parallel 会触发 429)
    for (let i = 0; i < sections.length; i++) {
      try {
        const r = await translateText({
          text: sections[i].content,
          target_lang: targetLang.value,
        })
        translations.value[i].translated = r.translated_text
      } catch (e) {
        translations.value[i].error = e.message || '翻译失败'
      }
    }
  } finally {
    loading.value = false
  }
}

// 打开面板时自动翻译
import { watch } from 'vue'
watch(
  () => props.visible,
  (v) => { if (v) doTranslate() },
  { immediate: false }
)
</script>

<style scoped>
.translation-panel {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 12px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border-light);
  background: var(--color-bg-card);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.panel-status {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-right: 8px;
}

.panel-body {
  padding: 20px;
  max-height: 60vh;
  overflow-y: auto;
}

.translation-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.translation-item {
  padding: 12px 16px;
  background: var(--color-primary-bg);
  border-left: 3px solid var(--color-primary);
  border-radius: 4px;
}

.original-text {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
  font-style: italic;
}

.translated-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-primary);
}
</style>
