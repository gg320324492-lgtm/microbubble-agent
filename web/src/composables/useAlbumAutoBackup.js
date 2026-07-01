// useAlbumAutoBackup.js — v2 PR8.5 Android Chrome 相册自动备份
// 2026-07-02
//
// 触发场景:
// - 用户授权后, 监听 <input type=file accept="image/*" capture="environment"> 的 change
// - 每次拍照/选图, 自动上传到 /drive (visibility=private, folder=AutoBackup)
// - 完整实现见 PR8 plan: "Android Chrome getUserMedia album 自动备份"
//
// 平台差异:
// - Android Chrome 4.4+: 支持 capture="environment" 调后置摄像头
// - iOS Safari 14+: 部分支持 (用户必须手动授权)
// - Desktop: 不支持 capture, 仅作 fallback
//
// 状态:
// - enabled: localStorage 持久化 (PR8.5 默认关)
// - lastBackupAt: ISO string
// - pendingCount: 上传中数量
//
// 复用:
// - 上传走 DriveService 上传管线 (上传到 'uploads/album_backup' prefix)
// - 不入库 knowledge_index (source_type='drive' 已隔离)
//
// 简化:
// - 本 composable 只暴露接口 + UI 触发按钮逻辑
// - 真实拍照循环 (Camera API / getUserMedia) 留 MobileAlbumBackupSettings.vue 配置页

import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const STORAGE_KEY = 'mnb:drive:album-auto-backup:enabled'
const STORAGE_KEY_LAST = 'mnb:drive:album-auto-backup:last-at'

export function useAlbumAutoBackup() {
  const enabled = ref(false)
  const lastBackupAt = ref(null)
  const pendingCount = ref(0)
  const isAndroidChrome = computed(() => {
    if (typeof navigator === 'undefined') return false
    return /Android.*Chrome/i.test(navigator.userAgent)
  })
  const isIOSSafari = computed(() => {
    if (typeof navigator === 'undefined') return false
    return /iPhone|iPad|iPod/i.test(navigator.userAgent) && /Safari/i.test(navigator.userAgent) && !/Chrome|CriOS|FxiOS/i.test(navigator.userAgent)
  })

  function loadSettings() {
    try {
      enabled.value = localStorage.getItem(STORAGE_KEY) === 'true'
      lastBackupAt.value = localStorage.getItem(STORAGE_KEY_LAST)
    } catch (e) {
      // localStorage 不可用 (隐私模式), silent fallback
      enabled.value = false
    }
  }

  function setEnabled(val) {
    enabled.value = val
    try {
      localStorage.setItem(STORAGE_KEY, val ? 'true' : 'false')
    } catch (e) {
      // silent
    }
  }

  // 上传单个文件到 drive (visibility=private)
  async function uploadPhoto(file) {
    pendingCount.value++
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('visibility', 'private')
      formData.append('storage_mode', 'drive')
      // folder_id: NULL (顶级), PR5 会加 AutoBackup folder
      const resp = await axios.post('/api/v1/drive/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      lastBackupAt.value = new Date().toISOString()
      try {
        localStorage.setItem(STORAGE_KEY_LAST, lastBackupAt.value)
      } catch (e) { /* silent */ }
      return resp.data
    } finally {
      pendingCount.value--
    }
  }

  // 批量上传 (input change 触发, 可能一次多张)
  async function uploadPhotos(files) {
    if (!files || files.length === 0) return []
    const results = []
    for (const f of Array.from(files)) {
      try {
        const r = await uploadPhoto(f)
        results.push({ ok: true, id: r.id, name: f.name })
      } catch (e) {
        results.push({ ok: false, name: f.name, error: e.message })
      }
    }
    return results
  }

  // 检测相册输入 (Android Chrome 调摄像头, iOS 调相册选择器)
  function createPhotoInput() {
    if (typeof document === 'undefined') return null
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    // Android Chrome 用 capture=environment 调后置摄像头
    // iOS Safari 14+ 调相册选择器 (capture 属性被忽略)
    // Desktop fallback: 仅文件选择
    if (isAndroidChrome.value) {
      input.capture = 'environment'
    }
    input.multiple = true
    return input
  }

  // 触发拍照/选图 + 上传
  async function triggerBackup() {
    const input = createPhotoInput()
    if (!input) return []
    return new Promise((resolve) => {
      input.addEventListener('change', async (e) => {
        const files = e.target.files
        if (!files || files.length === 0) {
          resolve([])
          return
        }
        const results = await uploadPhotos(files)
        resolve(results)
      })
      input.click()
    })
  }

  onMounted(loadSettings)

  return {
    enabled,
    lastBackupAt,
    pendingCount,
    isAndroidChrome,
    isIOSSafari,
    setEnabled,
    loadSettings,
    uploadPhoto,
    uploadPhotos,
    triggerBackup,
  }
}