<!--
  MobileDriveFAB.vue — Drive 专属浮动操作按钮 (v3.0 PR8 R4 W68 Agent 4)
  2026-07-24

  在通用 MobileFab 之上叠加 2 个 Drive 专属增强:
    1. 最近上传照片 (来自 album-auto-backup) — 当 latestBackup prop 传入时,
       FAB 顶部显示 1 张最新上传的照片缩略图, 点击直达预览
    2. 长按 QR 扫描按钮 → "扫描二维码" 入口 — 在 FAB 旁边显示一个小 QR 按钮,
       短按直接打开扫描对话框; 长按 800ms 显示"已就绪"提示气泡确认手势

  设计原则:
    - 完全复用 MobileFab 的展开/收起 + 触觉反馈 + dark mode 适配
    - 最近上传走 prop fallback (latestBackup 为 null 时不显示, 不报错)
    - QR 扫描用 input[type=file accept=image/*] + BarcodeDetector API 兜底
    - 0 production code 改动铁律: 不动后端, 不动 API, 只前端 FAB 增强
-->
<template>
  <div class="mobile-drive-fab-root" ref="rootRef">
    <!-- 最近上传照片缩略图 (来自 album-auto-backup) -->
    <button
      v-if="latestBackup"
      type="button"
      class="mobile-drive-fab-recent"
      :aria-label="`最近上传: ${latestBackup.file_name || '照片'}, 点击预览`"
      @click="onRecentClick"
    >
      <img :src="latestBackup.thumb_url || latestBackup.url" :alt="latestBackup.file_name || ''" />
      <span class="mobile-drive-fab-recent-badge" aria-hidden="true">新</span>
    </button>

    <!-- QR 扫描入口按钮 (FAB 旁边的子按钮, 短按打开扫描; 长按 800ms 显示手势提示) -->
    <button
      type="button"
      class="mobile-drive-fab-qr"
      :class="{ 'is-pressed': isQrPressed }"
      aria-label="扫描二维码"
      @click.stop="openQrScan"
      @pointerdown="onQrPressedDown"
      @pointerup="onQrPressedUp"
      @pointercancel="onQrPressedUp"
      @pointerleave="onQrPressedUp"
    >
      <span aria-hidden="true">⊞</span>
      <span v-if="showQrScanHint" class="mobile-drive-fab-qr-hint" aria-hidden="true">长按</span>
    </button>

    <!-- 通用 FAB (复用 MobileFab 行为 + 触觉反馈) -->
    <MobileFab :actions="driveFabActions" />

    <!-- QR 扫描对话框 (长按 FAB 触发) -->
    <Teleport to="body">
      <Transition name="qr-scan">
        <div v-if="showQrScan" class="qr-scan-overlay" @click.self="closeQrScan">
          <div class="qr-scan-panel">
            <div class="qr-scan-handle" />
            <div class="qr-scan-header">
              <h3 class="qr-scan-title">扫描二维码</h3>
              <button type="button" class="qr-scan-close" aria-label="关闭" @click="closeQrScan">✕</button>
            </div>
            <div class="qr-scan-body">
              <p class="qr-scan-hint">支持扫描文件分享二维码或任何文本二维码</p>
              <div class="qr-scan-actions">
                <label class="qr-scan-btn qr-scan-btn-primary">
                  <input
                    ref="qrFileInputRef"
                    type="file"
                    accept="image/*"
                    class="qr-scan-file"
                    @change="onQrFileSelected"
                  />
                  📷 从相册选择
                </label>
                <button
                  v-if="cameraSupported"
                  type="button"
                  class="qr-scan-btn"
                  @click="onQrCameraScan"
                >🎥 调用摄像头</button>
              </div>
              <div v-if="qrResult" class="qr-scan-result">
                <p class="qr-scan-result-label">识别结果:</p>
                <pre class="qr-scan-result-text">{{ qrResult }}</pre>
                <button type="button" class="qr-scan-btn qr-scan-btn-primary" @click="onQrCopy">复制链接</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import MobileFab from '@/components/mobile/MobileFab.vue'

const props = defineProps({
  /** FAB 默认 actions (与 MobileFab 一致), Drive 场景下由父组件传 upload/folder/share/search */
  actions: { type: Array, default: () => [] },
  /** 最近上传照片 (来自 album-auto-backup 配置), 缺省时不显示缩略图 */
  latestBackup: { type: Object, default: null },
})

const emit = defineEmits(['recent-click', 'qr-scan-result'])

// FAB 默认 actions, 父组件未传时使用兜底
const driveFabActions = computed(() => props.actions.length ? props.actions : [
  { name: 'upload', label: '上传文件', icon: '📁' },
  { name: 'folder', label: '新建文件夹', icon: '📂' },
  { name: 'share', label: '分享网盘', icon: '🔗' },
  { name: 'search', label: '搜索文件', icon: '🔍' },
])

function onRecentClick() {
  if (!props.latestBackup) return
  if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') navigator.vibrate(10)
  emit('recent-click', props.latestBackup)
}

// ---- QR 扫描 ----
const showQrScan = ref(false)
const showQrScanHint = ref(false)
const isQrPressed = ref(false)
const qrResult = ref('')
const qrFileInputRef = ref(null)
const cameraSupported = ref(false)
const rootRef = ref(null)
let qrPressedTimer = null

function onQrPressedDown() {
  isQrPressed.value = true
  qrPressedTimer = setTimeout(() => {
    // 长按 800ms 显示手势提示气泡
    showQrScanHint.value = true
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') navigator.vibrate(10)
    setTimeout(() => { showQrScanHint.value = false }, 1500)
  }, 800)
}

function onQrPressedUp() {
  isQrPressed.value = false
  if (qrPressedTimer) { clearTimeout(qrPressedTimer); qrPressedTimer = null }
}

function openQrScan() {
  if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') navigator.vibrate(10)
  showQrScan.value = true
  qrResult.value = ''
}

function closeQrScan() {
  showQrScan.value = false
  qrResult.value = ''
  if (qrFileInputRef.value) qrFileInputRef.value.value = ''
}

onMounted(() => {
  cameraSupported.value = typeof window !== 'undefined'
    && 'BarcodeDetector' in window
    && !!navigator.mediaDevices
})

async function onQrFileSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    const text = await detectBarcodeFromImageFile(file)
    if (text) {
      qrResult.value = text
      emit('qr-scan-result', text)
    } else {
      ElMessage.warning('未识别到二维码内容, 试试更清晰的图片')
    }
  } catch (err) {
    console.warn('[MobileDriveFAB] QR 识别失败:', err)
    ElMessage.error('识别失败: ' + (err?.message || '未知错误'))
  }
}

async function detectBarcodeFromImageFile(file) {
  if (typeof window === 'undefined' || !('BarcodeDetector' in window)) {
    throw new Error('当前浏览器不支持 BarcodeDetector API, 请使用 Chrome/Edge 或调用摄像头')
  }
  const img = await loadImageBitmap(file)
  // eslint-disable-next-line no-undef
  const detector = new BarcodeDetector({ formats: ['qr_code'] })
  const barcodes = await detector.detect(img)
  return barcodes?.[0]?.rawValue || ''
}

function loadImageBitmap(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = async () => {
      try {
        const blob = await fetch(reader.result).then((r) => r.blob())
        const bitmap = await createImageBitmap(blob)
        resolve(bitmap)
      } catch (err) {
        reject(err)
      }
    }
    reader.onerror = () => reject(new Error('读取图片失败'))
    reader.readAsDataURL(file)
  })
}

async function onQrCameraScan() {
  ElMessage.info('摄像头扫描入口: 调用 navigator.mediaDevices.getUserMedia (后续 PR 集成)')
}

async function onQrCopy() {
  if (!qrResult.value) return
  try {
    await navigator.clipboard.writeText(qrResult.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败, 请手动选中')
  }
}

// 长按 FAB 全局委托: 监听 FAB 触发按钮的 pointerdown (Vue 3 自定义)
// 由于 MobileFab 已经实现了 longpress 触发 expand, 我们通过给 MobileFab 注入额外的 longpress 监听器不可行
// 改用全局 touch 长按检测: 当用户在 FAB 触发区域按 600ms 且无 expand 触发, 我们截获
// 简化方案: 单独渲染一个透明的 QR 触发按钮 (藏在 FAB 后面), 用户长按这个透明按钮进入 QR 扫描
// 但这会和 MobileFab 的 click/toggle 冲突 — 妥协方案: 暴露 openQrScan 给父组件手动调用
defineExpose({ openQrScan, closeQrScan })
</script>

<style scoped>
.mobile-drive-fab-root { position: relative; }

.mobile-drive-fab-recent {
  position: fixed;
  right: 20px;
  bottom: calc(80px + 60px + env(safe-area-inset-bottom, 0px) + 10px);
  z-index: 2001;
  width: 48px;
  height: 48px;
  padding: 0;
  border: 2px solid var(--el-color-white, #fff);
  border-radius: 50%;
  background: var(--color-bg-card);
  box-shadow: var(--shadow-md);
  cursor: pointer;
  overflow: hidden;
  -webkit-tap-highlight-color: transparent;
  animation: recent-fade-in 220ms ease-out;
}
.mobile-drive-fab-recent:active { transform: scale(.94); }
.mobile-drive-fab-recent img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.mobile-drive-fab-recent-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  padding: 2px 6px;
  background: var(--color-danger, #f56c6c);
  color: var(--el-color-white, #fff);
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
}

/* QR 扫描子按钮 (FAB 旁边) */
.mobile-drive-fab-qr {
  position: fixed;
  right: 20px;
  bottom: calc(80px + 56px + 12px + env(safe-area-inset-bottom, 0px));
  z-index: 2001;
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(28, 25, 23, .1));
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  transition: transform var(--duration-fast, 150ms);
  -webkit-tap-highlight-color: transparent;
}
.mobile-drive-fab-qr:active,
.mobile-drive-fab-qr.is-pressed { transform: scale(.92); }
.mobile-drive-fab-qr-hint {
  position: absolute;
  right: calc(100% + 6px);
  top: 50%;
  transform: translateY(-50%);
  padding: 4px 8px;
  background: var(--color-text-primary);
  color: var(--color-bg-card);
  border-radius: var(--radius-sm, 4px);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  animation: qr-hint-fade 220ms ease-out;
}
@keyframes qr-hint-fade {
  from { opacity: 0; transform: translate(-4px, -50%); }
  to   { opacity: 1; transform: translate(0, -50%); }
}

@keyframes recent-fade-in {
  from { opacity: 0; transform: translateY(10px) scale(.85); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* ---- QR 扫描 Sheet ---- */
.qr-scan-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.qr-scan-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 16px 16px;
  max-height: 70vh;
  overflow-y: auto;
}
[data-theme="dark"] .qr-scan-panel { background: var(--color-bg-card); }
.qr-scan-handle {
  width: 36px;
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
}
.qr-scan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.qr-scan-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.qr-scan-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.qr-scan-close:active { background: var(--color-bg-hover); }
.qr-scan-body { padding: 8px 0; }
.qr-scan-hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--color-text-secondary);
  text-align: center;
}
.qr-scan-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.qr-scan-btn {
  flex: 1;
  padding: 12px;
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--color-border);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  text-align: center;
  -webkit-tap-highlight-color: transparent;
}
.qr-scan-btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: var(--el-color-white, #fff);
  border-color: transparent;
}
.qr-scan-btn:active { opacity: 0.7; }
.qr-scan-file { display: none; }
.qr-scan-result {
  padding: 12px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
}
.qr-scan-result-label {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.qr-scan-result-text {
  margin: 0 0 12px;
  padding: 8px;
  background: var(--color-bg-card);
  border-radius: var(--radius-sm, 4px);
  font-family: ui-monospace, monospace;
  font-size: 12px;
  color: var(--color-text-primary);
  word-break: break-all;
  white-space: pre-wrap;
  max-height: 120px;
  overflow-y: auto;
}

/* 进出动画 */
.qr-scan-enter-active, .qr-scan-leave-active { transition: opacity 0.25s ease; }
.qr-scan-enter-active .qr-scan-panel,
.qr-scan-leave-active .qr-scan-panel { transition: transform 0.3s ease; }
.qr-scan-enter-from, .qr-scan-leave-to { opacity: 0; }
.qr-scan-enter-from .qr-scan-panel,
.qr-scan-leave-to .qr-scan-panel { transform: translateY(100%); }
@media (prefers-reduced-motion: reduce) {
  .mobile-drive-fab-recent, .qr-scan-panel { animation: none; transition: none; }
}
</style>

<!-- v77 P2.6-B dark 覆盖 (v60-v67 教训: 非 scoped) -->
<style>
[data-theme="dark"] .mobile-drive-fab-recent { background: var(--color-bg-card); border-color: var(--color-bg-page); }
[data-theme="dark"] .mobile-drive-fab-qr { background: var(--color-bg-card); border-color: var(--color-border); color: var(--color-text-primary); }
[data-theme="dark"] .mobile-drive-fab-qr-hint { background: var(--color-text-primary); color: var(--color-bg-card); }
[data-theme="dark"] .qr-scan-result { background: var(--color-bg-page); }
[data-theme="dark"] .qr-scan-result-text { background: var(--color-bg-card); }
</style>