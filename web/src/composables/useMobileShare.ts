/**
 * useMobileShare.ts — 移动端分享能力 (Web Share API + 内置分享面板 fallback)
 *
 * W68 第 8 批 B-3: Mobile UX v3.2 iOS 分享集成
 *
 * 设计要点:
 * 1. 探测链优先:
 *    navigator.canShare (API 可用 + 数据合规) → navigator.share (系统分享面板)
 *    ↓ 不满足
 *    复制链接 + 自定义 MobileShareSheet (微信/QQ/微博/复制/保存/系统分享)
 * 2. 3 类型:
 *    - shareLink({ url, title, text }) — 分享网页/链接
 *    - shareText({ text }) — 分享纯文本
 *    - shareFile({ file, title, text }) — 分享文件 (Android Chrome 可, iOS Safari 仅图片/PDF)
 * 3. iOS Safari 铁律:
 *    - navigator.share 必须**用户手势内**触发 (click/touchend event handler)
 *    - iOS 12.1+ 才有 navigator.share; 12.0 及以前无
 *    - iOS Safari share file 仅支持 images / videos / pdfs / .docx 等; 不支持 .doc/.xls 等老格式
 * 4. Android Chrome 铁律:
 *    - 必须 HTTPS (localhost 除外)
 *    - share file MIME 受限 (image/* / video/* / text/* 优先)
 * 5. 优雅降级:
 *    - canShare 返回 false → fallback 复制 + 自定义 sheet
 *    - 用户拒绝 → 静默返回 (无错误弹窗, 仅 console.warn)
 *    - 复制成功 → ElMessage.success 提示
 *
 * 用法:
 *   const { shareLink, shareText, shareFile, copyLink, canNativeShare } = useMobileShare()
 *   await shareLink({ url: 'https://xxx', title: '分享', text: '...' })
 *   await shareText({ text: '...' })
 *   await shareFile({ file: someBlob, filename: 'photo.png' })
 *   await copyLink('https://xxx')
 */

import { ref, readonly } from 'vue'
import { ElMessage } from 'element-plus'

// 平台探测
function detectPlatform() {
  if (typeof navigator === 'undefined') {
    return { isIOS: false, isAndroid: false, isMobile: false, userAgent: '' }
  }
  const ua = navigator.userAgent || ''
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (ua.includes('Mac') && 'ontouchend' in document)
  const isAndroid = /Android/.test(ua)
  return {
    isIOS,
    isAndroid,
    isMobile: isIOS || isAndroid || /Mobile/.test(ua),
    userAgent: ua,
  }
}

// Web Share API + canShare 探测 (在用户手势外可调, 仅判断能力)
function detectNativeShare() {
  if (typeof navigator === 'undefined') {
    return { hasShare: false, hasCanShare: false, canShareFiles: false }
  }
  const hasShare = typeof navigator.share === 'function'
  const hasCanShare = typeof navigator.canShare === 'function'
  // canShare 需要一个测试数据; 我们用空对象测 (仅 API 是否存在)
  const canShareFiles = hasCanShare // 实际能 share file, 在具体数据上再验证
  return { hasShare, hasCanShare, canShareFiles }
}

// 8 字符 SHA256 hash (与 manifest hash 模式一致, 2026-06-13 webhint PWA 教训)
function shortHash(input: string): string {
  if (typeof crypto === 'undefined' || !crypto.subtle) {
    // fallback: 简单 djb2 哈希
    let hash = 5381
    for (let i = 0; i < input.length; i++) {
      hash = (hash * 33) ^ input.charCodeAt(i)
    }
    return (hash >>> 0).toString(16).padStart(8, '0')
  }
  // 同步 fallback (subtle 是异步, 分享场景用同步即可)
  let hash = 0
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) - hash + input.charCodeAt(i)) | 0
  }
  return Math.abs(hash).toString(16).padStart(8, '0')
}

export type ShareResultStatus = 'shared' | 'dismissed' | 'fallback' | 'failed'

export interface ShareResult {
  status: ShareResultStatus
  /** native share 路径成功才返回 true, fallback 路径返回 false */
  native: boolean
  /** 错误信息 (status='failed' 时) */
  error?: string
  /** 调用了哪种分享方式 (供分析/埋点) */
  method?: string
}

export interface ShareLinkOptions {
  url: string
  title?: string
  text?: string
}

export interface ShareTextOptions {
  text: string
  title?: string
}

export interface ShareFileOptions {
  file: Blob | File
  filename?: string
  title?: string
  text?: string
}

/**
 * useMobileShare — 单例 composable (Pinia 风格的工具集合)
 */
export function useMobileShare() {
  // 全局探测结果 (一次性, 避免每次调用重复探测)
  const platform = detectPlatform()
  const support = detectNativeShare()

  // 是否启用过 fallback (供 UI 决定是否弹自定义 sheet)
  const lastUsedFallback = ref(false)
  const lastShareAt = ref<number>(0)

  // 内部: 检查 canShare 是否真的接受当前数据
  function _canShare(data: ShareData): boolean {
    if (!support.hasShare) return false
    if (typeof navigator === 'undefined' || typeof navigator.canShare !== 'function') {
      // 没 canShare — 保守判断: 有 share 即可
      return true
    }
    try {
      return navigator.canShare(data)
    } catch {
      return false
    }
  }

  /**
   * 分享链接
   */
  async function shareLink(opts: ShareLinkOptions): Promise<ShareResult> {
    if (!opts.url) {
      return { status: 'failed', native: false, error: 'url 不能为空' }
    }
    const data: ShareData = {
      title: opts.title,
      text: opts.text,
      url: opts.url,
    }

    if (_canShare(data)) {
      try {
        await navigator.share(data)
        lastShareAt.value = Date.now()
        return { status: 'shared', native: true, method: 'navigator.share' }
      } catch (err: any) {
        // 用户取消 (AbortError) — 静默返回, 不抛错
        if (err?.name === 'AbortError') {
          return { status: 'dismissed', native: true }
        }
        console.warn('[useMobileShare] navigator.share failed:', err)
        // 降级到 fallback
        lastUsedFallback.value = true
        await copyLink(opts.url)
        return { status: 'fallback', native: false, method: 'clipboard', error: err?.message }
      }
    }

    // 不支持 native share — fallback 复制 + 自定义 sheet
    lastUsedFallback.value = true
    await copyLink(opts.url)
    return { status: 'fallback', native: false, method: 'clipboard' }
  }

  /**
   * 分享纯文本
   */
  async function shareText(opts: ShareTextOptions): Promise<ShareResult> {
    if (!opts.text) {
      return { status: 'failed', native: false, error: 'text 不能为空' }
    }
    const data: ShareData = {
      title: opts.title,
      text: opts.text,
    }

    if (_canShare(data)) {
      try {
        await navigator.share(data)
        lastShareAt.value = Date.now()
        return { status: 'shared', native: true, method: 'navigator.share' }
      } catch (err: any) {
        if (err?.name === 'AbortError') {
          return { status: 'dismissed', native: true }
        }
        console.warn('[useMobileShare] navigator.share text failed:', err)
        lastUsedFallback.value = true
        return { status: 'fallback', native: false, method: 'text-only', error: err?.message }
      }
    }

    lastUsedFallback.value = true
    return { status: 'fallback', native: false, method: 'text-only' }
  }

  /**
   * 分享文件 (图片/PDF/视频等)
   * - iOS Safari: 仅支持 image/* / video/* / application/pdf 等
   * - Android Chrome: 支持更宽, 但 MIME 必须有效
   */
  async function shareFile(opts: ShareFileOptions): Promise<ShareResult> {
    if (!opts.file) {
      return { status: 'failed', native: false, error: 'file 不能为空' }
    }

    // File 对象必须 (navigator.share 要求 File, 不是 Blob; safari 部分版本接受 Blob)
    let fileToShare: File
    if (opts.file instanceof File) {
      fileToShare = opts.file
    } else {
      // Blob → File (保留 MIME)
      const filename = opts.filename || `share-${shortHash(opts.file.type + Date.now())}.bin`
      fileToShare = new File([opts.file], filename, {
        type: opts.file.type || 'application/octet-stream',
      })
    }

    const data: ShareData = {
      title: opts.title,
      text: opts.text,
      files: [fileToShare],
    }

    if (_canShare(data)) {
      try {
        await navigator.share(data)
        lastShareAt.value = Date.now()
        return { status: 'shared', native: true, method: 'navigator.share-files' }
      } catch (err: any) {
        if (err?.name === 'AbortError') {
          return { status: 'dismissed', native: true }
        }
        console.warn('[useMobileShare] navigator.share file failed:', err)
        lastUsedFallback.value = true
        return { status: 'fallback', native: false, method: 'file-failed', error: err?.message }
      }
    }

    // 文件不支持 native share → fallback 到复制链接
    lastUsedFallback.value = true
    return { status: 'fallback', native: false, method: 'file-unsupported' }
  }

  /**
   * 复制链接到剪贴板 (fallback 路径 或 单独使用)
   */
  async function copyLink(url: string): Promise<boolean> {
    if (!url) return false
    try {
      // 优先 Clipboard API (需要 HTTPS + 用户手势, modern browsers)
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url)
        ElMessage?.success?.('链接已复制')
        return true
      }
      // Fallback: textarea + execCommand('copy') (老 Safari / WebView)
      const ta = document.createElement('textarea')
      ta.value = url
      ta.style.position = 'fixed'
      ta.style.top = '0'
      ta.style.left = '0'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.focus()
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      if (ok) {
        ElMessage?.success?.('链接已复制')
        return true
      }
      ElMessage?.warning?.('复制失败, 请手动复制')
      return false
    } catch (err) {
      console.warn('[useMobileShare] copy failed:', err)
      ElMessage?.warning?.('复制失败, 请手动复制')
      return false
    }
  }

  /**
   * 复制图片到剪贴板 (分享图片但不支持 navigator.share 时用)
   */
  async function copyImage(blob: Blob): Promise<boolean> {
    if (!blob) return false
    try {
      if (typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
        await navigator.clipboard.write([new ClipboardItem({ [blob.type || 'image/png']: blob })])
        ElMessage?.success?.('图片已复制')
        return true
      }
      return false
    } catch (err) {
      console.warn('[useMobileShare] copy image failed:', err)
      return false
    }
  }

  /**
   * 下载文件 (通过 a[download] 触发, 用于"保存图片"等场景)
   */
  function downloadFile(blob: Blob, filename: string): boolean {
    try {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      // 不立即 revoke, 让浏览器有 1s 时间开始下载
      setTimeout(() => {
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }, 1000)
      return true
    } catch (err) {
      console.warn('[useMobileShare] download failed:', err)
      return false
    }
  }

  return {
    // 平台/能力信息
    isIOS: platform.isIOS,
    isAndroid: platform.isAndroid,
    isMobile: platform.isMobile,
    canNativeShare: support.hasShare,
    canShareFiles: support.canShareFiles,

    // 分享 API (用户必须从 click/touchend 内调用)
    shareLink,
    shareText,
    shareFile,

    // 工具 API
    copyLink,
    copyImage,
    downloadFile,

    // 状态 (只读)
    lastUsedFallback: readonly(lastUsedFallback),
    lastShareAt: readonly(lastShareAt),
  }
}

export default useMobileShare
