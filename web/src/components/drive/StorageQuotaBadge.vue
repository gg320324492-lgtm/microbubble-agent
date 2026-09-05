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
  <!-- 批次⑧ 对齐视觉稿 .qbox: 「全组已用 + 粗体值」单行 + 5px 渐变进度条 (图标/百分比大字退役, 百分比进 tooltip) -->
  <div class="storage-quota-badge" :class="badgeClass" v-if="quotaInfo">
    <el-tooltip :content="tooltipText" placement="bottom" effect="light">
      <div class="quota-row">
        <span class="quota-label">全组已用</span>
        <b class="quota-val">{{ sizeDisplay }}</b>
      </div>
    </el-tooltip>
    <div class="quota-track" aria-hidden="true">
      <i :style="{ width: Math.min(100, Math.round((quotaInfo.percent || 0) * 100)) + '%' }"></i>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

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
    `已用: ${formatBytes(used_bytes)} (${percentDisplay.value})`,
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
/* 批次⑧ 对齐视觉稿 .qbox: 暖纸底圆角卡 + 单行 label/值 + 5px 渐变条 */
.storage-quota-badge {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 11px 12px;
  border-radius: var(--radius-lg, 12px);
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  transition: border-color 0.2s;
  cursor: pointer;
  user-select: none;
}
.storage-quota-badge:hover { border-color: var(--color-primary-border, var(--color-primary)); }

.quota-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.quota-val {
  font-family: var(--font-mono, Consolas, monospace);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.quota-track { height: 5px; border-radius: 3px; background: var(--color-border); overflow: hidden; }
.quota-track i { display: block; height: 100%; border-radius: 3px; background: var(--gradient-cta-button, var(--color-primary)); transition: width 0.4s var(--ease-out, ease); }

/* 阈值染色只作用在进度条填充上 (<80% 恒为视觉稿深青渐变) */
.storage-quota-badge.is-warning .quota-track i { background: var(--color-warning, #e6a23c); }
.storage-quota-badge.is-danger .quota-track i,
.storage-quota-badge.is-over .quota-track i { background: var(--color-danger, #f56c6c); }
.storage-quota-badge.is-over .quota-val { color: var(--color-danger, #f56c6c); }
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR5 初次提交, dark 适配留到 PR8 统一审计
-->