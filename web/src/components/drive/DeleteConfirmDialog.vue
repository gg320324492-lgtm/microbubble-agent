<!--
  DeleteConfirmDialog.vue — 批次⑩.73 (2026-09-07 选型 A 轻确认卡片)
  替换通用 ElMessageBox 删除确认: 文件名列表 (前 3 项 + 等共 N 项)
  + 「移入回收站 · 3 天内可随时恢复」说明, 主按钮深青 (可恢复操作不用红色恐吓)。
-->
<template>
  <el-dialog
    :model-value="modelValue"
    width="460px"
    align-center
    :close-on-click-modal="false"
    :close-on-press-escape="!loading"
    @update:model-value="v => emit('update:modelValue', v)"
  >
    <template #header>
      <span class="dcd-title">{{ title }}</span>
    </template>
    <div class="dcd-body">
      确定删除以下 <b>{{ items.length }}</b> 项{{ extraText }}？
      <div class="dcd-files">
        <div v-for="(it, i) in shown" :key="i" class="dcd-row">
          <span class="dot" :style="{ background: it.isFolder ? '#909399' : dotColor(it.name) }"></span>
          <span class="nm" :title="it.name">{{ it.name }}</span>
          <span class="sz">{{ it.isFolder ? '文件夹' : fmtSize(it.size) }}</span>
        </div>
        <div v-if="items.length > 3" class="dcd-more">等共 {{ items.length }} 项</div>
      </div>
      <div class="dcd-recycle">
        <svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-6.4 2.6L3 8"/><path d="M3 3v5h5"/></svg>
        <span>文件将移入回收站，<b>3 天内可随时恢复</b>，不会立即丢失</span>
      </div>
    </div>
    <template #footer>
      <button class="dcd-btn" :disabled="loading" @click="emit('update:modelValue', false)">取消</button>
      <button class="dcd-btn dcd-primary" :disabled="loading" @click="emit('confirm')">
        {{ loading ? '删除中…' : '移入回收站' }}
      </button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  items: { type: Array, default: () => [] },          // [{name, size, isFolder?}]
  extraText: { type: String, default: '' },            // 如 "（含 2 个文件夹, 其内容将一并移入回收站）"
  title: { type: String, default: '删除文件' },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'confirm'])

const shown = computed(() => props.items.slice(0, 3))

const EXT_DOT = {
  pdf: '#F56C6C', doc: '#4A89DC', docx: '#4A89DC', ppt: '#E6A23C', pptx: '#E6A23C',
  xls: '#198754', xlsx: '#198754', csv: '#198754', tsv: '#198754',
  png: '#9B59D0', jpg: '#9B59D0', jpeg: '#9B59D0', gif: '#9B59D0', webp: '#9B59D0',
  mp4: '#F56C6C', mov: '#F56C6C', webm: '#F56C6C', m4a: '#E6A23C', mp3: '#E6A23C', wav: '#E6A23C',
  zip: '#909399', txt: '#909399', md: '#909399', json: '#909399', log: '#909399',
}
function dotColor(name) {
  const ext = (name || '').split('.').pop().toLowerCase()
  return EXT_DOT[ext] || '#C0C4CC'
}
function fmtSize(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return n + ' B'
  const u = ['KB', 'MB', 'GB', 'TB']
  let v = n / 1024, i = 0
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
  return (v >= 100 ? Math.round(v) : v.toFixed(1)) + ' ' + u[i]
}
</script>

<style scoped>
.dcd-title { font-size: 15px; font-weight: 600; color: var(--color-text-primary); }
.dcd-body { font-size: 13px; color: var(--color-text-regular); }
.dcd-files { margin: 10px 0 4px; border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
.dcd-row { display: flex; align-items: center; gap: 9px; padding: 8px 12px; font-size: 12.5px; color: var(--color-text-regular); }
.dcd-row:nth-child(even) { background: #fafbfa; }
.dot { flex: none; width: 8px; height: 8px; border-radius: 50%; }
.dcd-row .nm { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dcd-row .sz { flex: none; color: var(--color-text-placeholder); font-family: var(--font-family-mono, monospace); font-size: 10.5px; }
.dcd-more { padding: 6px 12px; font-size: 11.5px; color: var(--color-text-secondary); background: #fafbfa; border-top: 1px dashed var(--color-border); }
.dcd-recycle {
  display: flex; align-items: center; gap: 7px; margin-top: 10px;
  background: #f0f9f7; border: 1px solid #cbe4dc; border-radius: 7px;
  padding: 7px 11px; font-size: 12px; color: #0b5c43;
}
.dcd-recycle svg { width: 14px; height: 14px; flex: none; stroke: #0b5c43; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.dcd-btn {
  font: inherit; font-size: 13px; border-radius: 6px; padding: 8px 18px; cursor: pointer;
  border: 1px solid var(--color-border); background: var(--color-bg-card);
  color: var(--color-text-regular); transition: all 0.15s;
}
.dcd-btn:disabled { opacity: 0.55; cursor: default; }
.dcd-btn:hover:not(:disabled) { border-color: #b8e0db; color: var(--teal, #0e766e); }
.dcd-primary {
  background: linear-gradient(135deg, #0e766e, #12897c); border: none; color: #fff;
  font-weight: 600; box-shadow: 0 2px 8px rgba(14, 118, 110, 0.3);
}
.dcd-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(14, 118, 110, 0.32); color: #fff; }
</style>
