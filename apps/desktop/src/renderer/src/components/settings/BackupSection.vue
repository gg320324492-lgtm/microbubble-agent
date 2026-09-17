<script setup lang="ts">
// 设置页「备份与恢复」区块（M5-1）— 立即备份/本地快照列表/恢复（危险确认）
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const backupPassword = ref('')
const backupPasswordConfirm = ref('')
const backupTargetDir = ref('')
const backupResult = ref<{ fileName: string; size: number } | null>(null)
const creating = ref(false)

const snapshots = ref<{ fileName: string; size: number; createdAt: number; path: string }[]>([])
const restoring = ref(false)
const restorePassword = ref('')

function fmtSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`
}

async function onCreateBackup(): Promise<void> {
  if (!backupPassword.value) {
    ElMessage.warning('请输入备份密码')
    return
  }
  if (backupPassword.value !== backupPasswordConfirm.value) {
    ElMessage.warning('两次密码输入不一致')
    return
  }
  creating.value = true
  try {
    const res = await window.api.backup.create(backupPassword.value, backupTargetDir.value || undefined as never)
    backupResult.value = res
    ElMessage.success(`备份完成：${res.fileName}`)
    backupPassword.value = ''
    backupPasswordConfirm.value = ''
    await refreshSnapshots()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '备份失败')
  } finally {
    creating.value = false
  }
}

async function refreshSnapshots(): Promise<void> {
  try {
    snapshots.value = await window.api.backup.list(backupTargetDir.value || '')
  } catch {
    snapshots.value = []
  }
}

async function onRestore(fileName: string): Promise<void> {
  if (!restorePassword.value) {
    ElMessage.warning('请输入备份密码')
    return
  }
  try {
    await ElMessageBox.confirm(
      '恢复将覆盖当前全部数据，已自动保留恢复前快照。确定恢复？',
      '危险操作 — 恢复备份',
      { type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  restoring.value = true
  try {
    await window.api.backup.restore(restorePassword.value, fileName)
    ElMessage.success('恢复完成，正在重启应用…')
    setTimeout(() => window.location.reload(), 1500)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '恢复失败')
  } finally {
    restoring.value = false
  }
}

onMounted(async () => {
  await refreshSnapshots()
})
</script>

<template>
  <section class="card block">
    <h2>备份与恢复</h2>
    <p class="hint">全部工作数据（数据库 + 附件）打包为 AES-256-GCM 加密容器。云端备份将于下个版本提供。</p>

    <div class="backup-form">
      <div class="form-row"><label>备份密码</label><input v-model="backupPassword" type="password" placeholder="设置备份密码" /></div>
      <div class="form-row"><label>确认密码</label><input v-model="backupPasswordConfirm" type="password" placeholder="再输入一次" /></div>
      <button class="primary-btn" data-testid="btn-backup" @click="onCreateBackup">立即备份</button>
      <p v-if="backupResult" class="ok-text">✓ {{ backupResult.fileName }}（{{ fmtSize(backupResult.size) }}）</p>
    </div>

    <div class="snapshot-section">
      <h3>本地快照</h3>
      <div v-if="snapshots.length === 0" class="empty-snap">暂无本地快照</div>
      <div v-for="s in snapshots" :key="s.fileName" class="snapshot-row">
        <span class="snap-name">{{ s.fileName }}</span>
        <span class="snap-size">{{ fmtSize(s.size) }}</span>
        <button class="mini-btn danger" @click="onRestore(s.fileName)">恢复</button>
      </div>
    </div>

    <div class="oss-placeholder">
      <p class="hint">☁ 云端备份将于下个版本提供（需配置阿里云 OSS）。</p>
    </div>
  </section>
</template>

<style scoped>
.block { padding: var(--space-6); }
.block h2 { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); margin-bottom: var(--space-4); }
.hint { margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--color-text-secondary); line-height: 1.7; }
.backup-form { display: flex; flex-direction: column; gap: var(--space-2); margin-top: var(--space-3); }
.form-row { display: grid; grid-template-columns: 80px 1fr; gap: var(--space-2); align-items: center; }
.form-row label { font-size: var(--font-size-sm); color: var(--color-text-regular); }
.form-row input { height: 32px; padding: 0 var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--font-size-xs); }
.primary-btn { padding: 6px 18px; border: none; border-radius: var(--radius-md); background: var(--color-primary); color: #fff; cursor: pointer; font-size: var(--font-size-sm); }
.ok-text { color: var(--color-success, #22a06b); font-size: var(--font-size-xs); }
.snapshot-section { margin-top: var(--space-4); }
.snapshot-section h3 { font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); }
.empty-snap { font-size: var(--font-size-xs); color: var(--color-text-placeholder); }
.snapshot-row { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-1) 0; border-bottom: 1px dashed var(--color-border-light); font-size: var(--font-size-xs); }
.snap-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.snap-size { flex-shrink: 0; color: var(--color-text-placeholder); }
.mini-btn { padding: 3px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg-card); cursor: pointer; font-size: var(--font-size-xs); }
.mini-btn.danger:hover { border-color: var(--color-danger, #d64545); color: var(--color-danger, #d64545); }
.oss-placeholder { margin-top: var(--space-3); }
</style>
