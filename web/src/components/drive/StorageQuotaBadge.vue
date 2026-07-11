<!--
  StorageQuotaBadge.vue — v2 网盘 PR5 配额徽章
  2026-07-01

  显示位置: DesktopDriveView Toolbar 右侧 / DriveUploadDialog 顶部
  颜色阈值:
  - < 80%: success (绿)
  - 80% ~ 95%: warning (黄)
  - >= 95%: danger (红)
  - >= 100%: over (深红 + 禁用上传)

  交互:
  - 鼠标 hover → 弹出 tooltip 详情 (used/total/file count/updated_at)
  - 点 → 打开 useStorageQuota 详情面板 (本期不展开)
-->
<template>
  <div class="storage-quota-badge" :class="badgeClass" v-if="quotaInfo">
    <el-tooltip :content="tooltipText" placement="bottom" effect="light">
      <div class="quota-content">
        <el-icon class="quota-icon"><DataLine /></el-icon>
        <div class="quota-text">
          <div class="quota-percent">{{ percentDisplay }}</div>
          <div class="quota-detail">{{ sizeDisplay }}</div>
        </div>
      </div>
    </el-tooltip>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { DataLine } from '@element-plus/icons-vue'

const props = defineProps({
  quotaInfo: {
    type: Object,
    default: null,
    // { user_id, used_bytes, quota_bytes, percent, file_count, is_over_quota, updated_at }
  },
})

const percentDisplay = computed(() => {
  if (!props.quotaInfo) return '0%'
  return `${Math.round((props.quotaInfo.percent || 0) * 100)}%`
})

const sizeDisplay = computed(() => {
  if (!props.quotaInfo) return '0 / 0 B'
  const used = props.quotaInfo.used_bytes || 0
  const total = props.quotaInfo.quota_bytes || 0
  return `${formatBytes(used)} / ${formatBytes(total)}`
})

const badgeClass = computed(() => {
  if (!props.quotaInfo) return ''
  const p = props.quotaInfo.percent || 0
  if (p >= 1.0) return 'is-over'
  if (p >= 0.95) return 'is-danger'
  if (p >= 0.8) return 'is-warning'
  return 'is-success'
})

const tooltipText = computed(() => {
  if (!props.quotaInfo) return '配额数据加载中...'
  const { used_bytes, quota_bytes, file_count, updated_at, is_over_quota } = props.quotaInfo
  const lines = [
    `已用: ${formatBytes(used_bytes)}`,
    `总配额: ${formatBytes(quota_bytes)}`,
    `文件数: ${file_count || 0}`,
    is_over_quota ? '⚠️ 已超额' : '',
    updated_at ? `更新: ${new Date(updated_at).toLocaleString('zh-CN')}` : '',
  ].filter(Boolean)
  return lines.join('\n')
})

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`
}
</script>

<style scoped>
.storage-quota-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 16px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border-light);
  transition: all 0.2s;
  cursor: pointer;
  user-select: none;
}

.storage-quota-badge:hover {
  background: var(--color-bg-hover, #ecf5ff);
  border-color: var(--color-primary, #409eff);
}

.quota-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quota-icon {
  font-size: 18px;
  color: var(--color-text-secondary, #909399);
}

.quota-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.2;
}

.quota-percent {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
}

.quota-detail {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
}

/* 颜色阈值 */
.storage-quota-badge.is-success .quota-icon { color: var(--color-success, #67c23a); }
.storage-quota-badge.is-success .quota-percent { color: var(--color-success, #67c23a); }

.storage-quota-badge.is-warning {
  background: var(--color-warning-light-9, #fdf6ec);
  border-color: var(--color-warning-light-5, #e6a23c);
}
.storage-quota-badge.is-warning .quota-icon { color: var(--color-warning, #e6a23c); }
.storage-quota-badge.is-warning .quota-percent { color: var(--color-warning, #e6a23c); }

.storage-quota-badge.is-danger {
  background: var(--color-danger-light-9, #fef0f0);
  border-color: var(--color-danger-light-5, #f56c6c);
}
.storage-quota-badge.is-danger .quota-icon { color: var(--color-danger, #f56c6c); }
.storage-quota-badge.is-danger .quota-percent { color: var(--color-danger, #f56c6c); }

.storage-quota-badge.is-over {
  background: var(--color-danger, #f56c6c);
  border-color: var(--color-danger, #f56c6c);
}
.storage-quota-badge.is-over .quota-icon,
.storage-quota-badge.is-over .quota-percent,
.storage-quota-badge.is-over .quota-detail {
  color: white;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR5 初次提交, dark 适配留到 PR8 统一审计
-->