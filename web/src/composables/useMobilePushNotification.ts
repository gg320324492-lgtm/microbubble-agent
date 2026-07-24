/**
 * useMobilePushNotification.ts — 移动端 PWA 推送通知（iOS Safari 16.4+ + Android Chrome）
 *
 * W68 路线 5 第 3 批: Mobile UX v3.2 PWA 推送
 *
 * 设计目标:
 * 1. Web Push API 完整探测链 — Notification.permission + navigator.serviceWorker.pushManager
 * 2. iOS Safari 16.4+ PWA standalone (添加到主屏) 才能用 push, 普通 Safari tab 无 push
 * 3. Android Chrome PWA standalone 即支持 (无版本限制)
 * 4. 申请权限 → 订阅服务端 → 7 天内不再弹窗 (拒绝后冷却)
 * 5. 触发本地通知: new Notification(title, options) — 调试 / 通知 banner 用
 * 6. 服务端订阅端点: POST /api/v1/notifications/push-subscribe (本项目已规划)
 *    注: 本项目目前无 VAPID 后端, 订阅逻辑**预留** — 服务器未就绪时降级到本地通知
 *
 * ⚠️ iOS Safari 铁律 (CLAUDE.md 2026-06-13 webhint PWA 教训):
 *  - 必须 viewport-fit=cover + manifest.webmanifest + standalone display
 *  - 必须用户主动添加到主屏才能 push (URL bar Safari tab 无 push)
 *  - 16.4 之前完全无 push, 16.4+ 必须 standalone mode
 *  - Notification.requestPermission() 必须在用户手势内触发 (click/tap 事件)
 *
 * ⚠️ Android Chrome 铁律:
 *  - 站点必须 HTTPS (localhost 除外)
 *  - 订阅端点需要 VAPID 公钥 (本项目**未来**集成)
 *
 * 用法:
 *   const push = useMobilePushNotification()
 *   await push.requestPermission()       // 申请权限 (用户手势内)
 *   await push.subscribe()               // 创建 PushManager 订阅 + 上报服务端
 *   push.showLocal({ title, body })     // 触发本地通知 (调试用)
 *   push.unsubscribe()                   // 取消订阅 + 服务端撤销
 */

import { ref, computed, readonly } from 'vue'

// localStorage key (W68 纪律: 拒绝后 7 天冷却)
const LS_KEY_DISMISSED_AT = 'mobile_push_dismissed_at'
const LS_KEY_SUBSCRIBED_AT = 'mobile_push_subscribed_at'
const LS_KEY_ENDPOINT = 'mobile_push_endpoint'

// 7 天冷却 (CLAUDE.md 2026-06-27 教训 — 频率与节奏)
const DISMISS_TTL_DAYS = 7
const DISMISS_TTL_MS = DISMISS_TTL_DAYS * 24 * 60 * 60 * 1000

// 服务端订阅端点 (本项目目前尚未实装 VAPID, 优雅降级)
const API_PUSH_SUBSCRIBE = '/api/v1/notifications/push-subscribe'
const API_PUSH_UNSUBSCRIBE = '/api/v1/notifications/push-unsubscribe'

/**
 * 探测浏览器 push 支持能力 (按需复用)
 */
function detectSupport() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return {
      hasNotification: false,
      hasServiceWorker: false,
      hasPushManager: false,
      isIOS: false,
      isStandalone: false,
      canPush: false,
    }
  }
  const hasNotification = 'Notification' in window
  const hasServiceWorker = 'serviceWorker' in navigator
  const hasPushManager = hasServiceWorker && 'PushManager' in window
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !/CriOS|FxiOS|EdgiOS/.test(navigator.userAgent)
  // standalone: PWA 添加到主屏
  const isStandalone = (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator.standalone === true ||
    document.referrer.includes('android-app://')
  )
  return {
    hasNotification,
    hasServiceWorker,
    hasPushManager,
    isIOS,
    isStandalone,
    // iOS Safari 16.4+: standalone PWA 才能 push; Android: 任意 HTTPS PWA
    canPush: hasPushManager && (isStandalone || !isIOS),
  }
}

/**
 * 读取 dismissed_at (Unix ms), 无 / 过期 → null
 */
function readDismissedAt() {
  if (typeof localStorage === 'undefined') return null
  const v = localStorage.getItem(LS_KEY_DISMISSED_AT)
  if (!v) return null
  const ts = Number(v)
  if (!Number.isFinite(ts)) return null
  if (Date.now() - ts > DISMISS_TTL_MS) {
    localStorage.removeItem(LS_KEY_DISMISSED_AT)
    return null
  }
  return ts
}

export function useMobilePushNotification() {
  const support = detectSupport()

  // 权限状态: 'default' (未申请) | 'granted' | 'denied' | 'unsupported'
  const permission = ref(support.hasNotification ? Notification.permission : 'unsupported')

  // 订阅状态
  const isSubscribed = ref(false)
  const subscription = ref(null)
  const subscriptionEndpoint = ref(null)

  // 7 天冷却: 已拒绝/关闭弹窗的 ts, 在 TTL 内不再弹
  const dismissedAt = ref(readDismissedAt())
  const isDismissed = computed(() => dismissedAt.value !== null)

  // 错误
  const lastError = ref(null)

  // 是否处于 loading (申请/订阅中)
  const loading = ref(false)

  /**
   * 是否应该自动弹窗 (用户未拒绝 + 未授权)
   */
  const shouldPrompt = computed(() => {
    if (!support.canPush) return false
    if (permission.value === 'granted' || permission.value === 'denied') return false
    if (isDismissed.value) return false
    return true
  })

  /**
   * 申请权限 (必须在用户手势内调用: click/tap 事件)
   * @returns {Promise<NotificationPermission>} 'granted' | 'denied' | 'default'
   */
  async function requestPermission() {
    if (!support.hasNotification) {
      lastError.value = '当前浏览器不支持 Notification API'
      return 'unsupported'
    }
    loading.value = true
    try {
      const result = await Notification.requestPermission()
      permission.value = result
      if (result === 'denied') {
        // 标记 dismissed (7 天内不再弹)
        markDismissed()
      } else if (result === 'granted') {
        // 清除 dismissed 标记 (允许了就不再冷却)
        clearDismissed()
      }
      return result
    } catch (e) {
      lastError.value = e?.message || String(e)
      console.error('[useMobilePushNotification] requestPermission failed:', e)
      return permission.value
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建 PushManager 订阅 (VAPID 未来集成)
   * 当前**降级**到 Notification.permission 状态同步 (无 VAPID 后端)
   * @returns {Promise<boolean>} 是否订阅成功 (含降级到本地通知场景)
   */
  async function subscribe() {
    if (!support.canPush) {
      lastError.value = '当前浏览器不支持 Web Push (iOS Safari 必须 standalone PWA)'
      return false
    }
    if (permission.value !== 'granted') {
      // 自动请求权限
      const result = await requestPermission()
      if (result !== 'granted') return false
    }

    loading.value = true
    try {
      // 1. 等待 SW ready
      const reg = await navigator.serviceWorker.ready

      // 2. 检查现有订阅 (避免重复)
      let existing = await reg.pushManager.getSubscription()
      if (!existing) {
        // ⚠️ 当前项目尚未实装 VAPID 公钥 — 此处降级
        // 未来集成:
        //   const vapidKey = await fetchVapidPublicKey()
        //   existing = await reg.pushManager.subscribe({
        //     userVisibleOnly: true,
        //     applicationServerKey: vapidKey,
        //   })
        // 当前: 跳过真实 subscribe (没 VAPID 会抛 InvalidArgumentError)
        // 仅记录"用户已授权"状态到 localStorage, 触发本地通知时用
        const placeholderEndpoint = `local://granted/${Date.now()}`
        subscriptionEndpoint.value = placeholderEndpoint
        isSubscribed.value = true
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem(LS_KEY_SUBSCRIBED_AT, String(Date.now()))
          localStorage.setItem(LS_KEY_ENDPOINT, placeholderEndpoint)
        }
        // 上报服务端 (best-effort, 端点不存在静默失败)
        reportToServer(API_PUSH_SUBSCRIBE, {
          endpoint: placeholderEndpoint,
          subscription_type: 'local_only',
          user_agent: navigator.userAgent,
          subscribed_at: new Date().toISOString(),
        }).catch(() => {})
        return true
      }

      // 已有订阅 (可能是其他页面创建的)
      subscription.value = existing
      subscriptionEndpoint.value = existing.endpoint
      isSubscribed.value = true
      return true
    } catch (e) {
      lastError.value = e?.message || String(e)
      console.error('[useMobilePushNotification] subscribe failed:', e)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 取消订阅
   */
  async function unsubscribe() {
    loading.value = true
    try {
      if (support.hasServiceWorker && support.hasPushManager) {
        try {
          const reg = await navigator.serviceWorker.ready
          const existing = await reg.pushManager.getSubscription()
          if (existing) {
            await existing.unsubscribe()
          }
        } catch (e) {
          // 静默 (没真订阅就忽略)
          console.debug('[useMobilePushNotification] unsubscribe sw:', e)
        }
      }
      subscription.value = null
      subscriptionEndpoint.value = null
      isSubscribed.value = false
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(LS_KEY_SUBSCRIBED_AT)
        localStorage.removeItem(LS_KEY_ENDPOINT)
      }
      // 上报服务端 (best-effort)
      reportToServer(API_PUSH_UNSUBSCRIBE, {}).catch(() => {})
      return true
    } catch (e) {
      lastError.value = e?.message || String(e)
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * 触发本地通知 (debug / banner 用)
   * 必须 permission === 'granted', 否则会被浏览器静默丢弃
   * @param {{ title: string, body?: string, icon?: string, tag?: string, data?: any }} opts
   */
  function showLocal(opts) {
    if (!support.hasNotification) return null
    if (permission.value !== 'granted') {
      console.warn('[useMobilePushNotification] showLocal ignored: permission not granted')
      return null
    }
    try {
      const n = new Notification(opts.title, {
        body: opts.body || '',
        icon: opts.icon || '/pwa-192.png',
        badge: opts.badge || '/pwa-192.png',
        tag: opts.tag,
        data: opts.data,
        // iOS Safari 16.4+ 必须 silent=false (默认) 才显示横幅
      })
      // 自动关闭 (5s)
      setTimeout(() => {
        try { n.close() } catch {}
      }, 5000)
      return n
    } catch (e) {
      lastError.value = e?.message || String(e)
      console.error('[useMobilePushNotification] showLocal failed:', e)
      return null
    }
  }

  /**
   * 标记 dismissed (拒绝/关闭后 7 天不再弹)
   */
  function markDismissed() {
    const now = Date.now()
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(LS_KEY_DISMISSED_AT, String(now))
    }
    dismissedAt.value = now
  }

  function clearDismissed() {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(LS_KEY_DISMISSED_AT)
    }
    dismissedAt.value = null
  }

  /**
   * 重置 dismissed 标记 (供用户手动重置, 比如"重新询问我")
   */
  function resetDismissed() {
    clearDismissed()
    permission.value = support.hasNotification ? Notification.permission : 'unsupported'
  }

  /**
   * 上报订阅状态给服务端 (best-effort, 静默失败)
   */
  async function reportToServer(url, payload) {
    try {
      const token = localStorage.getItem('access_token')
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
        credentials: 'same-origin',
      })
      if (!resp.ok) {
        // 端点可能未实装 (本项目目前无 VAPID), 静默
        console.debug(`[useMobilePushNotification] report ${url} → ${resp.status}`)
      }
    } catch (e) {
      console.debug('[useMobilePushNotification] report network fail:', e)
    }
  }

  /**
   * 从 localStorage 还原订阅状态 (页面刷新 / 重启)
   */
  function restore() {
    if (typeof localStorage === 'undefined') return
    const endpoint = localStorage.getItem(LS_KEY_ENDPOINT)
    if (endpoint) {
      subscriptionEndpoint.value = endpoint
      isSubscribed.value = true
    }
    dismissedAt.value = readDismissedAt()
  }

  // 初始化: 还原状态
  restore()

  return {
    // 探测
    support: readonly(ref(support)),
    canPush: computed(() => support.canPush),
    isIOS: computed(() => support.isIOS),
    isStandalone: computed(() => support.isStandalone),
    // 状态
    permission: readonly(permission),
    isSubscribed: readonly(isSubscribed),
    subscriptionEndpoint: readonly(subscriptionEndpoint),
    isDismissed: readonly(isDismissed),
    dismissedAt: readonly(dismissedAt),
    shouldPrompt: readonly(shouldPrompt),
    loading: readonly(loading),
    lastError: readonly(lastError),
    // 操作
    requestPermission,
    subscribe,
    unsubscribe,
    showLocal,
    markDismissed,
    clearDismissed,
    resetDismissed,
    restore,
  }
}

export default useMobilePushNotification