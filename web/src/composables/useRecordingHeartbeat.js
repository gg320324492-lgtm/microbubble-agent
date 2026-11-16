/**
 * useRecordingHeartbeat.js — 录音心跳模块级单例 (2026-10-08 P0-1~P0-3)
 *
 * 事故背景（2026-10-08 会议 255 / user_id=58 / iPhone Safari）
 * ------------------------------------------------------------------
 * 上一版心跳守卫 (2026-09-15 P0) 写在 `web/src/components/AudioRecorder.vue:129-155`，
 * `heartbeatTimer` 是组件局部变量，绑组件实例生命周期。
 * 全站 `<router-view>` 无 `<keep-alive>`，任意路由切换立即 `onUnmounted(stopHeartbeat)`。
 * 而恢复路径（用户从其他页面跳回 /meetings/room）直接调 `useGlobalRecorder().start()`，
 * **完全绕过** `AudioRecorder.handleStart()` → 心跳从未启动 → 会议 255 录音 38min 全程
 * 0 心跳 → orphan_meeting_cleanup 在 30min+TTL 后误判 error。
 *
 * 本模块的职责
 * ------------------------------------------------------------------
 * 心跳的"会话状态"是**录音会话**（useGlobalRecorder 级别），不是**录音 UI 组件**。
 * - 模块级单例，跨组件挂载/卸载持久
 * - 与 useGlobalRecorder 同生命周期：start() → ensureHeartbeat(id) → stop()/reset() → stopHeartbeat
 * - 注册 visibilitychange/pageshow/focus → 切回前台立即补一次（iOS Safari 后台挂起后最危险的 60s）
 * - 注册 pagehide + sendBeacon → 通知后端"页面离开"（presence 信号）
 *
 * 设计纪律
 * ------------------------------------------------------------------
 * - 心跳失败不抛错（与 useMeetingAudioUpload.sendRecordingHeartbeat 同款 best-effort）
 * - pagehide 上报用 `fetch(keepalive: true)` 而非 `navigator.sendBeacon` ——
 *   sendBeacon 无法带 Authorization header，而后端 get_current_user 只认 Bearer，
 *   用 sendBeacon 会 100% 被拒（详见 pageHideHandler 处注释）
 * - localStorage 写 elapsed+meetingId 仅供前端对齐，不参与守卫判定
 *
 * 调用点（web/src/composables, web/src/components, web/src/views）:
 *   - AudioRecorder.vue: handleStart / onMounted / watch meetingIdRef / doStop
 *   - MeetingRoomView.vue: onMounted 后 await startGlobalRecorder() 成功后
 *   - MobileMeetingRoom.vue: 同上
 *   - useGlobalRecorder.js: start() 内兜底 ensureHeartbeat(meetingId optional)
 *
 * 与 useGlobalRecorder 的解耦
 * ------------------------------------------------------------------
 * useGlobalRecorder 不感知 meetingId（meetingId 由父组件 props 传入），
 * 因此 useRecordingHeartbeat 也**不在 start() 内自动启动**（会拿不到 id）。
 * 兜底设计：调用方必须显式 ensureHeartbeat(meetingId)。useGlobalRecorder 仅暴露
 * 一个 setCurrentMeetingId hook 让兜底调用能在模块外触达。
 */

import { sendRecordingHeartbeat } from './useMeetingAudioUpload'

// ===== 模块级状态（跨组件持久，与 useGlobalRecorder 同寿命） =====

let timer = null
let currentMeetingId = null
let currentSessionId = null
let currentPhase = 'recording'
let listenersRegistered = false
let lastBeatAt = 0
let isPausedForVisibility = false  // 仅诊断用：visibilitychange → hidden 时打 log

/** 合法心跳阶段：录音中 / 收尾上传中 / 恢复上传中（后两阶段仍要防止孤儿清理误杀，与后端对齐） */
const HEARTBEAT_PHASES = new Set(['recording', 'finalizing', 'uploading'])

function normalizePhase(phase) {
  return HEARTBEAT_PHASES.has(phase) ? phase : 'recording'
}

/** 当前是否有活跃心跳（用于 UI 状态查询 / 测试断言） */
export function isHeartbeatActive() {
  return timer !== null && currentMeetingId !== null
}

/** 取当前心跳 meetingId（测试断言用） */
export function getCurrentMeetingId() {
  return currentMeetingId
}

/** 取上一次心跳时间戳（测试断言用，0 表示从未发） */
export function getLastBeatAt() {
  return lastBeatAt
}

/** 取当前录音会话 ID（模块级，跨组件挂载/卸载持久） */
export function getCurrentSessionId() {
  return currentSessionId
}

/** 取当前心跳阶段（recording / finalizing） */
export function getHeartbeatPhase() {
  return currentPhase
}

// ===== 核心方法 =====

/**
 * 启动心跳（若已启动则替换 meetingId 并立即补一次 beat）
 * - 幂等：重复调不会创建第二个 timer
 * - 立即发一次 beat（不等 60s）—— 上层刚拿到 meetingId 时不要等一整周期
 * @param {number|null|undefined} meetingId
 * @param {{sessionId?: string|null, phase?: string}} [options]
 *   旧调用只传 meetingId 时保持完全兼容；sessionId 只在首次建立会话时采纳，
 *   防止组件重挂载用旧 id 覆盖 useGlobalRecorder.start() 新建的会话。
 */
export function ensureHeartbeat(meetingId, options = {}) {
  if (!meetingId) {
    console.warn('[useRecordingHeartbeat] ensureHeartbeat called without meetingId')
    return
  }
  if (currentMeetingId !== meetingId) {
    // 换会议但心跳还在（组件重建先于 stop）→ 先清掉旧会话的 timer，避免旧会议被打字
    if (currentMeetingId && timer) {
      clearInterval(timer)
      timer = null
    }
    currentMeetingId = meetingId
    // 换会议时只在调用方【显式】给出 sessionId 时才覆盖；组件 watch 早于
    // useGlobalRecorder.start() 触发时必须保住 start 建立的 currentSessionId，
    // 否则心跳丢掉 session_id，后端无法把心跳关联到正确录音会话（2026-11-16 审核）。
    // 没有 sessionId 时保留当前 phase（不回退成 recording：可能正处 finalizing/uploading）。
    if (options.sessionId) currentSessionId = options.sessionId
    if (options.phase !== undefined) currentPhase = normalizePhase(options.phase)
  } else {
    // 同会议收到显式 sessionId = 一次新的录音会话，允许覆盖旧 id
    if (options.sessionId) currentSessionId = options.sessionId
    if (options.phase !== undefined) currentPhase = normalizePhase(options.phase)
  }
  registerListenersOnce()
  // 立即补一次（不等下一个 60s 周期 —— 这正是恢复路径最容易死的窗口）
  beat()
  if (!timer) {
    timer = setInterval(beat, 60000)
  }
}

/**
 * 切换心跳阶段（e.g. 停止录音进入 finalize 时切到 finalizing）。
 * 阶段变化会立即发一次 beat，让后端马上看到"还在收尾"而不是等下一个 60s 周期。
 * @param {string} phase 'recording' | 'finalizing'
 */
export function setHeartbeatPhase(phase) {
  const next = normalizePhase(phase)
  if (!currentMeetingId || next === currentPhase) return
  currentPhase = next
  beat()
}

/**
 * 停心跳（录音真正结束时调：stop-recording / cancel-recording / merge 完成）
 *
 * **不**在组件 unmount 时调用 —— 见任务书"重要陷阱 1"。组件卸载不该杀心跳，
 * 否则恢复路径就成了"心跳已死但录音在跑"的永久失效状态。
 */
export function stopHeartbeat() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  currentMeetingId = null
  currentSessionId = null
  currentPhase = 'recording'
  lastBeatAt = 0
  isPausedForVisibility = false
}

/**
 * 只在 heartbeat 服务于指定会议时停表 —— finalize 成功/失败的 finally 调用。
 * 防止 stop-recording 后立刻又开始另一场录音时被旧收尾误杀。
 */
export function stopHeartbeatForMeeting(meetingId) {
  if (!meetingId || currentMeetingId !== meetingId) return false
  stopHeartbeat()
  return true
}

/**
 * 主动发一次心跳（外部触发：visibilitychange → visible / pageshow persisted / focus）
 * 没有 currentMeetingId 时直接返回（录音未开）
 */
export function beat(phase) {
  if (!currentMeetingId) return
  if (phase !== undefined) currentPhase = normalizePhase(phase)
  lastBeatAt = Date.now()
  // sendRecordingHeartbeat 内部 try/catch + console.warn，best-effort
  sendRecordingHeartbeat(currentMeetingId, {
    sessionId: currentSessionId,
    phase: currentPhase,
  })
  return true
}

// ===== 可见性 / 焦点 监听 =====

let visibilityHandler = null
let pageShowHandler = null
let focusHandler = null
let pageHideHandler = null

function registerListenersOnce() {
  if (listenersRegistered) return
  listenersRegistered = true

  // P0-2: 切回前台立即补心跳 —— iOS Safari 后台挂起后 interval 可能被冻结，
  // 恢复时最长要等 60s 才补一次，而这 60s 正是误杀窗口。
  if (typeof document !== 'undefined') {
    visibilityHandler = () => {
      if (document.visibilityState === 'visible') {
        if (isHeartbeatActive()) beat()
      } else {
        // P0-3: hidden 时记录当前 elapsed + meetingId 到 localStorage 供前端对齐
        // —— 后端判定仍以 Redis key 为准，localStorage 只辅助前端 UX
        try {
          if (currentMeetingId) {
            localStorage.setItem('recording:presence', JSON.stringify({
              meetingId: currentMeetingId,
              sessionId: currentSessionId,
              phase: currentPhase,
              hiddenAt: Date.now(),
            }))
          }
        } catch {
          // localStorage 不可用（隐私模式 / quota）—— best-effort
        }
        isPausedForVisibility = true
      }
    }
    document.addEventListener('visibilitychange', visibilityHandler)
  }

  // P0-2: bfcache 恢复（Safari 后退按钮 / 前进按钮）
  if (typeof window !== 'undefined') {
    pageShowHandler = (e) => {
      if (e.persisted && isHeartbeatActive()) beat()
    }
    focusHandler = () => {
      if (isHeartbeatActive()) beat()
    }
    window.addEventListener('pageshow', pageShowHandler)
    window.addEventListener('focus', focusHandler)

    // P0-3: pagehide（页面卸载 / 切走）→ 通知后端"页面离开"
    //
    // ⚠️ 为什么不用 navigator.sendBeacon (2026-10-08 主指挥复验发现):
    //   sendBeacon **无法携带 Authorization header** —— 它只能发 cookie 和 body。
    //   而 `app/core/security.py:102-104` 的 get_current_user 只认
    //   HTTPAuthorizationCredentials(Bearer)，所以 sendBeacon 打过来的
    //   /recording-presence 端点在真实浏览器里 **100% 401**，presence 永远写不进去。
    //
    //   改用 fetch + keepalive:true (Safari 12+ 支持):
    //   - 可以自由设置 Authorization header (从 localStorage.access_token 取，
    //     与 web/src/utils/request.js 的 axios 拦截器同款取值)
    //   - keepalive 让请求在页面卸载后继续完成（sendBeacon 的等价能力）
    //   - 64KB body 上限对这个 ~100B 载荷绰绰有余
    //   - catch 里静默失败即可 —— pagehide 本来就是弱信号（best-effort）
    pageHideHandler = () => {
      if (!currentMeetingId) return
      try {
        const token = localStorage.getItem('access_token')
        if (!token) {
          console.warn('[useRecordingHeartbeat] pagehide: 无 access_token, 跳过 presence 上报')
          return
        }
        const url = `/api/v1/meetings/${currentMeetingId}/recording-presence`
        fetch(url, {
          method: 'POST',
          keepalive: true,               // 页面卸载后仍完成该请求 (Safari 12+)
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            hiddenAt: Date.now(),
            presence: 'pagehide',
            sessionId: currentSessionId,
            phase: currentPhase,
          }),
        }).catch((err) => {
          // pagehide 是弱信号, 失败静默 —— 后端会依赖 Redis TTL 判死
          console.warn('[useRecordingHeartbeat] pagehide presence 上报失败:', err?.message)
        })
      } catch (err) {
        console.warn('[useRecordingHeartbeat] pagehide handler error:', err?.message)
      }
    }
    window.addEventListener('pagehide', pageHideHandler)
  }
}

function unregisterListeners() {
  if (typeof document !== 'undefined' && visibilityHandler) {
    document.removeEventListener('visibilitychange', visibilityHandler)
  }
  if (typeof window !== 'undefined') {
    if (pageShowHandler) window.removeEventListener('pageshow', pageShowHandler)
    if (focusHandler) window.removeEventListener('focus', focusHandler)
    if (pageHideHandler) window.removeEventListener('pagehide', pageHideHandler)
  }
  visibilityHandler = null
  pageShowHandler = null
  focusHandler = null
  pageHideHandler = null
}

// 仅供诊断 / 测试用
export function _isPausedForVisibility() {
  return isPausedForVisibility
}

// 仅供测试用 —— 重置模块级单例避免状态污染
export function _resetForTests() {
  stopHeartbeat()
  unregisterListeners()
  listenersRegistered = false
}