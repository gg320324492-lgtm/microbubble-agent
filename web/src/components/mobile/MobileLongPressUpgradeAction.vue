<!--
  MobileLongPressUpgradeAction.vue — W72 第 2 批 C-3 长按 ActionSheet 升级空间
  MobileFileList / MobileDriveView 长按文件时注入 "升级空间" action
  独立组件避免修改 MobileFileList / MobileDriveView 老路径 (符合 §3 例外铁律)
-->
<template>
  <MobileActionSheet
    v-model:show="modelValue"
    title="文件操作"
    :actions="actions"
  />
</template>

<script setup>
/**
 * MobileLongPressUpgradeAction.vue — 长按文件 ActionSheet (含升级空间)
 *
 * 派工依据:
 * - W72 第 2 批 C-3 Mobile UX v3.4 商业化暗色
 * - 复用 MobileActionSheet 老组件
 * - 在标准 6 操作 (预览/下载/重命名/可见性/加入知识库/删除) 基础上插入 "升级空间"
 * - 高亮样式 (💎 icon) 引导用户升级
 *
 * 用法 (替换 MobileFileList.vue 老 MobileActionSheet):
 *   <MobileLongPressUpgradeAction
 *     v-model:show="showActionSheet"
 *     :file="selectedFile"
 *     :on-preview="() => preview(file)"
 *     :on-download="() => download(file)"
 *     ...
 *   />
 */

import { computed } from 'vue'
import { useRouter } from 'vue-router'
import MobileActionSheet from './MobileActionSheet.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  file: { type: Object, default: () => null },
  onPreview: { type: Function, default: null },
  onDownload: { type: Function, default: null },
  onRename: { type: Function, default: null },
  onVisibility: { type: Function, default: null },
  onAddToKb: { type: Function, default: null },
  onDelete: { type: Function, default: null },
})

const emit = defineEmits(['update:modelValue'])

const router = useRouter()

const actions = computed(() => {
  if (!props.file) return []
  const list = []
  if (props.onPreview) list.push({ name: '预览', icon: '👁', callback: props.onPreview })
  if (props.onDownload) list.push({ name: '下载', icon: '⬇️', callback: props.onDownload })
  if (props.onRename) list.push({ name: '重命名', icon: '✏️', callback: props.onRename })
  if (props.onVisibility) list.push({ name: '可见性', icon: '🔓', callback: props.onVisibility })
  if (props.onAddToKb) list.push({ name: '加入知识库', icon: '📚', callback: props.onAddToKb })
  // W72 第 2 批 C-3: 升级空间选项 (高亮)
  list.push({
    name: '升级空间',
    icon: '💎',
    highlight: true,
    description: '100 GB + 高级 RAG',
    callback: goSubscription,
  })
  if (props.onDelete) list.push({ name: '删除', icon: '🗑', danger: true, callback: props.onDelete })
  return list
})

function goSubscription() {
  emit('update:modelValue', false)
  // CLAUDE.md 2026-06-27 教训: 长按/点击触发式操作必含 navigator.vibrate(10)
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    try { navigator.vibrate(10) } catch (_) { /* noop */ }
  }
  router.push('/mobile/subscription')
}
</script>

<!--
  W72 第 2 批 C-3 dark mode 高亮 action 样式
  CLAUDE.md v60-v67 教训: dark mode 跨组件必须非 scoped
-->
<style>
[data-theme="dark"] .action-item.highlight {
  background: rgba(255, 122, 92, 0.15);
  border-left: 3px solid var(--color-primary);
}
[data-theme="dark"] .action-item.highlight .action-label {
  color: rgb(255, 179, 71);
  font-weight: 700;
}
</style>