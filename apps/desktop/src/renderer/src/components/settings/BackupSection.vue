<script setup lang="ts">
// 设置页「备份与恢复」区块（M5-1 + M5-2）— 本地/云端快照合并列表、OSS 配置、退出自动备份。
// OSS Secret 永不回显（主侧 safeStorage 加密存储）；开关状态走 settings 通道持久化。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// ---------- 本地备份（M5-1） ----------
const backupPassword = ref('')
const backupPasswordConfirm = ref('')
const backupTargetDir = ref('')
const backupResult = ref<{ fileName: string; size: number } | null>(null)
const creating = ref(false)
const restoring = ref(false)
const restorePassword = ref('')

// ---------- OSS 配置（M5-2） ----------
const ossForm = ref({ bucket: '', endpoint: '', prefix: 'desktop-backup/', accessKeyId: '', accessKeySecret: '' })
const ossConfigured = ref(false)
const ossTesting = ref(false)
const ossTestResult = ref<{ ok: boolean; text: string } | null>(null)
const cloudError = ref('')

// ---------- 开关（M5-2，默认关） ----------
const autoOnExit = ref(false)
const uploadAfterCreate = ref(false)

// ---------- 快照合并列表（本地 + 云端） ----------
interface LocalSnap { fileName: string; size: number; createdAt: number; path: string }
interface CloudSnap { key: string; size: number; lastModified: string }
interface MergedSnap {
  fileName: string
  size: number
  time: number
  hasLocal: boolean
  hasCloud: boolean
  localPath?: string
  remoteKey?: string
}
const localSnaps = ref<LocalSnap[]>([])
const cloudSnaps = ref<CloudSnap[]>([])

const mergedSnaps = computed<MergedSnap[]>(() => {
  const map = new Map<string, MergedSnap>()
  for (const s of localSnaps.value) {
    map.set(s.fileName, { fileName: s.fileName, size: s.size, time: s.createdAt, hasLocal: true, hasCloud: false, localPath: s.path })
  }
  for (const c of cloudSnaps.value) {
    const fileName = c.key.split('/').pop() ?? c.key
    const exist = map.get(fileName)
    if (exist) { exist.hasCloud = true; exist.remoteKey = c.key }
    else map.set(fileName, { fileName, size: c.size, time: new Date(c.lastModified).getTime() || 0, hasLocal: false, hasCloud: true, remoteKey: c.key })
  }
  return [...map.values()].sort((a, b) => b.time - a.time)
})

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

// ---------- OSS 配置加载 / 保存 / 测试 ----------
async function loadOssForm(): Promise<void> {
  try {
    const [bucket, endpoint, prefix, akId, secretEnc] = await Promise.all([
      window.api.settings.get('backup.oss.bucket'),
      window.api.settings.get('backup.oss.endpoint'),
      window.api.settings.get('backup.oss.prefix'),
      window.api.settings.get('backup.oss.accessKeyId'),
      window.api.settings.get('backup.oss.accessKeySecretEnc')
    ])
    ossForm.value.bucket = typeof bucket === 'string' ? bucket : ''
    ossForm.value.endpoint = typeof endpoint === 'string' ? endpoint : ''
    ossForm.value.prefix = typeof prefix === 'string' && prefix ? prefix : 'desktop-backup/'
    ossForm.value.accessKeyId = typeof akId === 'string' ? akId : ''
    ossConfigured.value = Boolean(ossForm.value.bucket && secretEnc)
  } catch {
    ossConfigured.value = false
  }
}

async function onSaveOssConfig(): Promise<void> {
  if (!ossForm.value.bucket || !ossForm.value.accessKeyId) {
    ElMessage.warning('Bucket 与 AK ID 为必填项')
    return
  }
  if (!ossForm.value.accessKeySecret && !ossConfigured.value) {
    ElMessage.warning('请填写 AccessKeySecret')
    return
  }
  try {
    // Secret 为空 = 保留已存密文（主侧逻辑），避免重复输入
    await window.api.backup.oss.saveConfig({ ...ossForm.value })
    ossConfigured.value = true
    ossForm.value.accessKeySecret = ''
    ElMessage.success('OSS 配置已保存（Secret 经 safeStorage 加密存储）')
    await refreshCloud()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  }
}

async function onTestOss(): Promise<void> {
  ossTesting.value = true
  ossTestResult.value = null
  try {
    const r = await window.api.backup.oss.test()
    ossTestResult.value = r.ok
      ? { ok: true, text: '✓ 连接成功 — bucket 可访问' }
      : { ok: false, text: `✗ 连接失败：${r.error ?? '未知原因'}` }
  } catch (e) {
    ossTestResult.value = { ok: false, text: `✗ 连接失败：${e instanceof Error ? e.message : '未知错误'}` }
  } finally {
    ossTesting.value = false
  }
}

// ---------- 开关持久化 ----------
async function onAutoExitChange(): Promise<void> {
  if (autoOnExit.value) {
    let pwd: string
    try {
      const { value } = await ElMessageBox.prompt(
        '退出时将用此密码自动创建加密备份（请牢记，恢复时需要）：',
        '开启退出自动备份',
        {
          inputType: 'password',
          confirmButtonText: '开启',
          cancelButtonText: '取消',
          inputValidator: (v: string) => (v && v.trim() ? true : '密码不能为空')
        }
      )
      pwd = value
    } catch {
      autoOnExit.value = false
      return
    }
    try {
      await window.api.settings.set('backup.exitPassword', pwd)
      await window.api.settings.set('backup.autoOnExit', true)
      ElMessage.success(`已开启：退出时自动备份到本地${ossConfigured.value ? '（已配置 OSS，将同时上传云端）' : ''}`)
    } catch (e) {
      autoOnExit.value = false
      ElMessage.error(e instanceof Error ? e.message : '保存失败')
    }
  } else {
    try { await window.api.settings.set('backup.autoOnExit', false) } catch { /* 忽略 */ }
    ElMessage.info('已关闭退出自动备份')
  }
}

async function onUploadSwitchChange(): Promise<void> {
  try { await window.api.settings.set('backup.uploadAfterCreate', uploadAfterCreate.value) } catch { /* 忽略 */ }
}

// ---------- 快照刷新 / 备份 / 上传 ----------
async function refreshLocal(): Promise<void> {
  try {
    localSnaps.value = (await window.api.backup.list(backupTargetDir.value || '')) as LocalSnap[]
  } catch {
    localSnaps.value = []
  }
}

async function refreshCloud(): Promise<void> {
  cloudError.value = ''
  if (!ossConfigured.value) {
    cloudSnaps.value = []
    return
  }
  try {
    cloudSnaps.value = await window.api.backup.oss.listRemote()
  } catch (e) {
    cloudSnaps.value = []
    cloudError.value = e instanceof Error ? e.message : '云端列表获取失败'
  }
}

async function refreshSnapshots(): Promise<void> {
  await Promise.all([refreshLocal(), refreshCloud()])
}

async function uploadSnapshotFile(fileName: string): Promise<void> {
  const local = localSnaps.value.find((s) => s.fileName === fileName)
  if (!local) return
  try {
    const r = await window.api.backup.oss.upload(local.path)
    ElMessage.success(`已上传云端：${r.key}`)
    await refreshCloud()
  } catch (e) {
    ElMessage.warning(`云端上传失败：${e instanceof Error ? e.message : '未知错误'}`)
  }
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
    const res = await window.api.backup.create(backupPassword.value, backupTargetDir.value || (undefined as never))
    backupResult.value = res
    ElMessage.success(`备份完成：${res.fileName}`)
    backupPassword.value = ''
    backupPasswordConfirm.value = ''
    await refreshLocal()
    if (uploadAfterCreate.value) await uploadSnapshotFile(res.fileName)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '备份失败')
  } finally {
    creating.value = false
  }
}

// ---------- 恢复（云端自动先下载） / 删除 ----------
async function onRestore(row: MergedSnap): Promise<void> {
  if (!restorePassword.value) {
    ElMessage.warning('请先在下方输入恢复密码')
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
    let backupFile: string
    if (row.hasLocal && row.localPath) {
      backupFile = row.localPath
    } else if (row.remoteKey) {
      ElMessage.info('云端快照下载中…')
      const dl = await window.api.backup.oss.download(row.remoteKey)
      backupFile = dl.localPath
      await refreshLocal()
    } else {
      ElMessage.error('快照来源异常')
      return
    }
    await window.api.backup.restore(restorePassword.value, backupFile)
    ElMessage.success('恢复完成，正在重启应用…')
    setTimeout(() => window.location.reload(), 1500)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '恢复失败')
  } finally {
    restoring.value = false
  }
}

async function onDelete(row: MergedSnap): Promise<void> {
  const scope = [row.hasLocal ? '本地' : null, row.hasCloud ? '云端' : null].filter(Boolean).join(' + ')
  try {
    await ElMessageBox.confirm(
      `确定删除快照 ${row.fileName}（${scope}）？删除后不可恢复。`,
      '删除快照',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  const errs: string[] = []
  if (row.hasLocal) {
    try { await window.api.backup.deleteLocal(row.fileName) } catch (e) { errs.push(`本地：${e instanceof Error ? e.message : '失败'}`) }
  }
  if (row.hasCloud && row.remoteKey) {
    try { await window.api.backup.oss.deleteRemote(row.remoteKey) } catch (e) { errs.push(`云端：${e instanceof Error ? e.message : '失败'}`) }
  }
  if (errs.length) {
    ElMessage.error(`删除失败：${errs.join('；')}`)
  } else {
    ElMessage.success('快照已删除')
    await refreshSnapshots()
  }
}

onMounted(async () => {
  await loadOssForm()
  try {
    autoOnExit.value = (await window.api.settings.get('backup.autoOnExit')) === true
    uploadAfterCreate.value = (await window.api.settings.get('backup.uploadAfterCreate')) === true
  } catch { /* 默认关 */ }
  await refreshSnapshots()
})
</script>

<template>
  <section class="card block">
    <h2>备份与恢复</h2>
    <p class="hint">全部工作数据（数据库 + 附件）打包为 AES-256-GCM 加密容器。支持本地备份与云端备份（阿里云 OSS）。</p>

    <div class="backup-form">
      <div class="form-row"><label>备份密码</label><input v-model="backupPassword" type="password" placeholder="设置备份密码" /></div>
      <div class="form-row"><label>确认密码</label><input v-model="backupPasswordConfirm" type="password" placeholder="再输入一次" /></div>
      <button class="primary-btn" data-testid="btn-backup" :disabled="creating" @click="onCreateBackup">立即备份</button>
      <p v-if="backupResult" class="ok-text">✓ {{ backupResult.fileName }}（{{ fmtSize(backupResult.size) }}）</p>
    </div>

    <div class="switch-row">
      <label><input type="checkbox" v-model="uploadAfterCreate" data-testid="upload-switch" @change="onUploadSwitchChange" /> 备份后上传云端</label>
      <label><input type="checkbox" v-model="autoOnExit" data-testid="auto-exit-switch" @change="onAutoExitChange" /> 退出时自动备份</label>
    </div>

    <!-- OSS 配置（M5-2） -->
    <div class="oss-section">
      <h3>云端备份（阿里云 OSS）</h3>
      <div class="form-row"><label>Bucket</label><input v-model="ossForm.bucket" placeholder="bucket 名称" /></div>
      <div class="form-row"><label>Endpoint</label><input v-model="ossForm.endpoint" placeholder="https://oss-cn-hangzhou.aliyuncs.com" /></div>
      <div class="form-row"><label>前缀</label><input v-model="ossForm.prefix" placeholder="desktop-backup/" /></div>
      <div class="form-row"><label>AK ID</label><input v-model="ossForm.accessKeyId" placeholder="AccessKeyId" /></div>
      <div class="form-row"><label>Secret</label><input v-model="ossForm.accessKeySecret" type="password" :placeholder="ossConfigured ? '已加密保存 — 留空则不修改' : 'AccessKeySecret'" /></div>
      <div class="form-actions">
        <button class="mini-btn" data-testid="oss-save" @click="onSaveOssConfig">保存配置</button>
        <button class="mini-btn" data-testid="oss-test" :disabled="ossTesting" @click="onTestOss">测试连接</button>
      </div>
      <p v-if="ossTestResult" :class="ossTestResult.ok ? 'ok-text' : 'err-text'" data-testid="oss-test-result">{{ ossTestResult.text }}</p>
    </div>

    <!-- 快照合并列表（本地 + 云端，来源标注） -->
    <div class="snapshot-section">
      <h3>快照列表<span class="hint-inline">（本地 + 云端）</span></h3>
      <div class="form-row restore-pwd-row"><label>恢复密码</label><input v-model="restorePassword" type="password" placeholder="恢复云端/本地快照所需的备份密码" /></div>
      <p v-if="cloudError" class="err-text">云端列表获取失败：{{ cloudError }}</p>
      <p v-else-if="!ossConfigured" class="hint-inline">未配置 OSS — 仅显示本地快照</p>
      <div v-if="mergedSnaps.length === 0" class="empty-snap">暂无快照</div>
      <div v-for="s in mergedSnaps" :key="s.fileName" class="snapshot-row">
        <span class="snap-name">{{ s.fileName }}</span>
        <span class="snap-tags">
          <span v-if="s.hasLocal" class="tag tag-local">本地</span>
          <span v-if="s.hasCloud" class="tag tag-cloud">云端</span>
        </span>
        <span class="snap-size">{{ fmtSize(s.size) }}</span>
        <button class="mini-btn" :disabled="restoring" @click="onRestore(s)">恢复</button>
        <button class="mini-btn danger" data-testid="snap-delete" @click="onDelete(s)">删除</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.block { padding: var(--space-6); }
.block h2 { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); margin-bottom: var(--space-4); }
.hint { margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--color-text-secondary); line-height: 1.7; }
.hint-inline { font-size: var(--font-size-xs); color: var(--color-text-placeholder); font-weight: normal; }
.backup-form { display: flex; flex-direction: column; gap: var(--space-2); margin-top: var(--space-3); }
.form-row { display: grid; grid-template-columns: 80px 1fr; gap: var(--space-2); align-items: center; }
.form-row label { font-size: var(--font-size-sm); color: var(--color-text-regular); }
.form-row input { height: 32px; padding: 0 var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--font-size-xs); }
.primary-btn { padding: 6px 18px; border: none; border-radius: var(--radius-md); background: var(--color-primary); color: #fff; cursor: pointer; font-size: var(--font-size-sm); }
.primary-btn:disabled { opacity: 0.6; cursor: default; }
.primary-btn { align-self: flex-start; }
.ok-text { color: var(--color-success, #22a06b); font-size: var(--font-size-xs); }
.err-text { color: var(--color-danger, #d64545); font-size: var(--font-size-xs); }
.switch-row { display: flex; gap: var(--space-5); margin-top: var(--space-3); }
.switch-row label { display: flex; align-items: center; gap: 6px; font-size: var(--font-size-sm); color: var(--color-text-regular); cursor: pointer; }
.oss-section { margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--color-border-light); display: flex; flex-direction: column; gap: var(--space-2); }
.oss-section h3 { font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); }
.form-actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.snapshot-section { margin-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); }
.snapshot-section h3 { font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); }
.restore-pwd-row { margin-bottom: var(--space-1); }
.empty-snap { font-size: var(--font-size-xs); color: var(--color-text-placeholder); }
.snapshot-row { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-1) 0; border-bottom: 1px dashed var(--color-border-light); font-size: var(--font-size-xs); }
.snap-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.snap-tags { display: flex; gap: 4px; flex-shrink: 0; }
.tag { padding: 1px 6px; border-radius: var(--radius-sm); font-size: 10px; line-height: 1.4; }
.tag-local { background: var(--color-bg-hover, #f0f2f5); color: var(--color-text-secondary); }
.tag-cloud { background: rgba(34, 160, 107, 0.12); color: var(--color-success, #22a06b); }
.snap-size { flex-shrink: 0; color: var(--color-text-placeholder); }
.mini-btn { padding: 3px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg-card); cursor: pointer; font-size: var(--font-size-xs); }
.mini-btn:disabled { opacity: 0.5; cursor: default; }
.mini-btn.danger:hover { border-color: var(--color-danger, #d64545); color: var(--color-danger, #d64545); }
</style>
