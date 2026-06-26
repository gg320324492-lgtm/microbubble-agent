<template>
  <div class="translation-panel" v-if="visible">
    <div class="panel-header">
      <span class="panel-title">📖 全文翻译</span>
      <span class="panel-status" v-if="loading">翻译中...</span>
      <el-button text size="small" @click="$emit('close')" :icon="Close" />
    </div>
    <div class="panel-body" v-loading="loading">
      <el-empty v-if="!loading && !translations.length" description="翻译功能待接入后端 API" />
      <div v-else class="translation-list">
        <div v-for="t in translations" :key="t.id" class="translation-item">
          <div class="original-text">{{ t.original }}</div>
          <div class="translated-text">{{ t.translated }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * TranslationPanel - 全文翻译面板（阶段 3 预留）
 *
 * 后端 API: POST /api/v1/papers/{id}/translate
 *   body: { mode: 'full' | 'section' | 'paragraph', targetId?: string }
 *   response: { translations: [{ id, original, translated }] }
 *
 * 当前为前端组件结构预留，显示"翻译功能待接入后端 API"空态。
 */
import { ref } from 'vue'
import { Close } from '@element-plus/icons-vue'

const props = defineProps({
  paper: { type: Object, default: () => ({}) },
  visible: { type: Boolean, default: false },
})

defineEmits(['close'])

const loading = ref(false)
const translations = ref([])

// TODO: 接入后端翻译 API
// async function translate() {
//   loading.value = true
//   try {
//     const r = await axios.post(`/api/v1/papers/${props.paper.id}/translate`)
//     translations.value = r.data.translations
//   } finally {
//     loading.value = false
//   }
// }
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
