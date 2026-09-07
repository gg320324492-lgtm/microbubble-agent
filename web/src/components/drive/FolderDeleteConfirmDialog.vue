<!--
  FolderDeleteConfirmDialog.vue — 批次⑩.81 (2026-09-08 选型 A 轻确认卡片)
  替换文件夹删除的通用 ElMessageBox (docs/superpowers/mockups/2026-09-08-folder-delete-confirm-4ui.html 方案 A):
  文件夹主角卡 (图标 + 名称 + 子项计数) + 「移入回收站 · 30 天内可恢复」说明,
  主按钮深青 (可恢复操作不用红色恐吓)。他人文件夹 (admin 越权) 保留红字警告分支。
  保留期与后端 DRIVE_RETENTION_DAYS=30 对齐 (app/config.py)。
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
      <span class="fdc-title">删除文件夹</span>
    </template>
    <div class="fdc-body">
      <div class="fdc-hero">
        <span class="fdc-ficon">
          <svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
        </span>
        <div class="fdc-info">
          <div class="nm" :title="folderName">{{ folderName }}</div>
          <div class="meta">
            {{ hasChildren ? `${folderCount} 个子文件夹 · ${fileCount} 个文件` : '空文件夹' }}
          </div>
        </div>
      </div>
      <div v-if="adminWarning" class="fdc-admin-warn">
        ⚠️ 该文件夹由其他成员拥有，删除后将影响其使用者，建议先与对方确认。
      </div>
      <div class="fdc-recycle">
        <svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-6.4 2.6L3 8"/><path d="M3 3v5h5"/></svg>
        <span v-if="hasChildren">以上内容将<b>全部移入回收站</b>，30 天内可整体恢复</span>
        <span v-else>文件夹将移入回收站，<b>30 天内可随时恢复</b>，不会立即丢失</span>
      </div>
    </div>
    <template #footer>
      <button class="fdc-btn" :disabled="loading" @click="emit('update:modelValue', false)">取消</button>
      <button class="fdc-btn fdc-primary" :disabled="loading" @click="emit('confirm')">
        {{ loading ? '删除中…' : '移入回收站' }}
      </button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  folderName: { type: String, default: '' },
  folderCount: { type: Number, default: 0 },
  fileCount: { type: Number, default: 0 },
  adminWarning: { type: Boolean, default: false },  // 删除他人文件夹 (admin 越权) 红字警告
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'confirm'])

const hasChildren = computed(() => props.folderCount > 0 || props.fileCount > 0)
</script>

<style scoped>
.fdc-title { font-size: 15px; font-weight: 600; color: var(--color-text-primary); }
.fdc-body { font-size: 13px; color: var(--color-text-regular); }
.fdc-hero {
  display: flex; align-items: center; gap: 12px; padding: 12px 14px; margin: 2px 0 0;
  background: #fafbfa; border: 1px solid var(--color-border); border-radius: 8px;
}
.fdc-ficon {
  flex: none; width: 40px; height: 40px; border-radius: 10px; background: #f0f9f7;
  border: 1px solid #cbe4dc; display: flex; align-items: center; justify-content: center;
}
.fdc-ficon svg { width: 22px; height: 22px; fill: none; stroke: #0e766e; stroke-width: 1.7; }
.fdc-info { min-width: 0; }
.fdc-info .nm { font-size: 14px; font-weight: 600; color: var(--color-text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fdc-info .meta { font-size: 11.5px; color: var(--color-text-secondary); margin-top: 2px; }
.fdc-admin-warn {
  margin-top: 10px; padding: 8px 11px; border-radius: 7px; font-size: 12px; line-height: 1.55;
  background: #fef0f0; border: 1px solid #fbc4c4; color: #c45656;
}
.fdc-recycle {
  display: flex; align-items: center; gap: 7px; margin-top: 10px;
  background: #f0f9f7; border: 1px solid #cbe4dc; border-radius: 7px;
  padding: 7px 11px; font-size: 12px; color: #0b5c43;
}
.fdc-recycle svg { width: 14px; height: 14px; flex: none; stroke: #0b5c43; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.fdc-btn {
  font: inherit; font-size: 13px; border-radius: 6px; padding: 8px 18px; cursor: pointer;
  border: 1px solid var(--color-border); background: var(--color-bg-card);
  color: var(--color-text-regular); transition: all 0.15s;
}
.fdc-btn:disabled { opacity: 0.55; cursor: default; }
.fdc-btn:hover:not(:disabled) { border-color: #b8e0db; color: var(--teal, #0e766e); }
.fdc-primary {
  background: linear-gradient(135deg, #0e766e, #12897c); border: none; color: #fff;
  font-weight: 600; box-shadow: 0 2px 8px rgba(14, 118, 110, 0.3);
}
.fdc-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(14, 118, 110, 0.32); color: #fff; }
</style>
