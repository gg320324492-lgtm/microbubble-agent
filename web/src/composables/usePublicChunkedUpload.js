/**
 * usePublicChunkedUpload.js — 匿名收件页的大文件分片上传 (2026-11-09)
 *
 * 为什么需要它: 原有的 `POST /file-requests/{token}/submit` 会把请求体**整份
 * read() 进 Python 内存**, app 容器 mem_limit=8g ⇒ 外部人员传 GB 级视频必然 OOM。
 * 后端新增了 5 个匿名分片端点 (MinIO 服务端拼接, 全程不进内存), 本 composable 是它的前端驱动。
 *
 * ⚠️ 这是**匿名**通路: 没有 JWT, 不进 Pinia, 不做登录态假设。
 *    与登录态的 useDriveChunkedUpload 是两套 (那边的 URL/鉴权/配额都不同),
 *    故此处**不复用那个组件**, 只借鉴它的分片循环写法。
 *
 * 五条与后端契约强绑定的实现要点:
 *  1. **chunk_size 必须用服务端返回值**。非末片长度要求逐字节相等 (后端 400),
 *     自己算的只要差一个字节整场上传就废 —— 所以 init 之后一切偏移都按返回的 chunk_size 推。
 *  2. **限流档是 120/min/IP** (chunked_upload tier, 见 app/core/rate_limit.py 的
 *     _CHUNKED_UPLOAD_PATH_RE) ⇒ 并发上限 2 + 客户端滚动窗口限速 (100/min) + 指数退避。
 *     并发数本身不构成限速: 上行够快时 2 个 worker 也能冲到 240/min。
 *     另外「发起/查询/合并/放弃」四个端点**不在**那条白名单里, 落 write 档 (30/min)
 *     ⇒ 一场上传各只调一次 (对账每轮一次 GET 走 read 档 200/min, 不受影响)。
 *  3. **逐片 SHA256 只在 secure context 可算** (http:// 非 localhost 时
 *     crypto.subtle 是 undefined) ⇒ 算不了就**降级成不带校验头**, 绝不让上传整体不可用。
 *  4. **missing_chunks 服务端只回前 200 个** (防响应体爆炸) ⇒ 不能把它当完整集合用,
 *     截断时按 planPending() 的规则保守补全 (宁可重传, 不可漏传)。
 *  5. **断点必须能跨页面刷新恢复** ⇒ upload_id 存 localStorage,
 *     key 里带 token + 文件名 + 大小 (本仓踩过 basename 碰撞静默复用错数据的坑, 类 20.242)。
 */
import { computed, getCurrentScope, onScopeDispose, ref } from 'vue'
import { useFileRequests } from './useFileRequests'
import {
  FR_FAILURE_CODE,
  FR_FAILURE_ACTION,
  describeFileRequestFailure,
  detailOf,
  statusOf,
} from '@/utils/fileRequestFailure'

// ── 可调常量 (导出给单测与 UI 文案共用, 不要在别处再写一遍字面量) ──────────────

/**
 * 小文件通路 vs 分片通路的分流阈值。
 * 200 MB = 与现有单请求 submit 的用户体验一致的边界 (再大就该看到进度条而不是转圈),
 * 同时远离后端 8g 内存天花板。
 */
export const CHUNKED_THRESHOLD_BYTES = 200 * 1024 * 1024

/** 并发 ≤2: 限流 120/min 下留足重试余量, 也避免把上行打满导致全部超时 */
export const MAX_CHUNK_CONCURRENCY = 2

/** 单片最多重试次数 (429 与网络错误共用这个额度) */
export const MAX_CHUNK_RETRIES = 5

/**
 * 一分钟内最多发起多少个分片 PUT。
 * 后端 chunked_upload 档是 **120/min/IP** (app/core/rate_limit.py)。
 * 并发 2 本身不构成限速: 上行够快时 (500 Mbps 约 0.5s 传完一片 32 MiB)
 * 两个 worker 也能冲到 240/min 被 429 掐。取 100 = 120 减 20 留给重试与抖动。
 * ⚠️ 用**滚动窗口**而不是固定间隔 —— 慢网下永远不触发 (一分钟发不满 100 片),
 *    不牺牲任何真实吞吐; 快网下才在客户端排队, 而不是让服务端回 429。
 *    (固定间隔那版会把整场上传拖慢, 且测不了: 真等 520ms×N。)
 */
export const MAX_PUTS_PER_MINUTE = 100

/** 限流窗口长度, 与后端 AsyncRedisRateLimiter(window_seconds=60) 同口径 */
export const RATE_WINDOW_MS = 60000

/** 退避: 1s → 2s → 4s → 8s → 16s, 封顶 30s */
export const BACKOFF_BASE_MS = 1000
export const BACKOFF_CAP_MS = 30000

/** 服务端 _missing() 的截断长度 —— 契约的一部分, 改动要跟后端同步 */
export const MISSING_CHUNKS_CAP = 200

/** localStorage 键前缀 (带版本号: 结构变了旧记录要能被识别并丢弃) */
export const STORAGE_PREFIX = 'mnb:file-request-upload:v1:'

/** 可中断等待的检查粒度 */
const CANCEL_TICK_MS = 100

/** 收尾对账最多再跑几轮 (防 missing 一直不空导致死循环) */
const MAX_SETTLE_ROUNDS = 5

/** 速度统计的滑动窗口 (ms) —— 窗口太短会抖得没法看, 太长对断网反应慢 */
const SPEED_WINDOW_MS = 12000

// ── 纯函数 (导出给单测, 不依赖 Vue / DOM) ────────────────────────────────────

/** 分流判据: 文件够不够大要走分片 */
export function shouldUseChunked(fileSize) {
  const n = Number(fileSize)
  return Number.isFinite(n) && n >= CHUNKED_THRESHOLD_BYTES
}

/** 第 index 片的字节区间 [start, end) 与长度 */
export function chunkRange(fileSize, chunkSize, index) {
  const start = index * chunkSize
  const end = Math.min(fileSize, start + chunkSize)
  return { start, end, len: Math.max(0, end - start) }
}

/**
 * 由服务端给的 missing_chunks 推出「必须上传的下标集合」。
 *
 * 服务端 `missing = [i for i in range(total) if i not in done][:200]` —— **升序 + 截断**。
 * 于是:
 *   · 列表没满 200 ⇒ 它就是完整集合, 直接用;
 *   · 列表正好 200  ⇒ 第 200 个之后的下标**无法判定**是否已传,
 *     而未列出的较小下标可以证明已传。
 *     ⇒ 保守做法: 列出的这些 + 比最大者大的全部下标。宁可重传 (幂等覆盖同一个对象键),
 *       也绝不能漏传 (漏传会在 complete 时 409, 但那时已经浪费了一整轮等待)。
 */
export function planPending(totalChunks, missingChunks, cap = MISSING_CHUNKS_CAP) {
  const total = Number(totalChunks) || 0
  const raw = Array.isArray(missingChunks) ? missingChunks : []
  const seen = new Set()
  for (const i of raw) {
    // ⚠️ 必须先挡 null/undefined/'': Number(null)===0 会把它们变成**合法的 0 号片**
    //    (与 utils/meetingFailure.js 里 Number(null)===0 那个坑同源)。传 0 号片无害但没道理。
    if (i === null || i === undefined || i === '') continue
    const idx = Number(i)
    if (Number.isInteger(idx) && idx >= 0 && idx < total) seen.add(idx)
  }
  const sorted = [...seen].sort((a, b) => a - b)
  const truncated = sorted.length >= cap
  const out = sorted
  if (truncated) {
    const maxListed = sorted[sorted.length - 1]
    for (let i = maxListed + 1; i < total; i++) {
      if (!seen.has(i)) out.push(i)
    }
  }
  return out
}

/**
 * 这次失败该不该重试这一片。
 * 可重试: 429 (限流) / 422 (这一片传输损坏, 重传即可, 后端只拒这一片) /
 *         5xx (服务端抖动) / 0 (网络错误, 拿不到响应)
 * 不可重试: 404/409/410/413/415 —— 链接或会话本身的问题, 重传多少片都没用
 */
export function isRetryableStatus(status) {
  const st = Number(status) || 0
  if (st === 0 || st === 408 || st === 422 || st === 429) return true
  return st >= 500
}

/** 退避时长: 优先听服务端的 Retry-After, 否则指数退避; 返回 ms */
export function resolveRetryDelayMs(err, attempt) {
  const raw = err?.response?.headers?.['retry-after'] ?? err?.response?.headers?.['Retry-After']
  if (raw !== undefined && raw !== null && raw !== '') {
    const secs = Number(raw)
    if (Number.isFinite(secs) && secs >= 0) return Math.min(secs * 1000, BACKOFF_CAP_MS)
    const date = Date.parse(String(raw))
    if (Number.isFinite(date)) {
      return Math.min(Math.max(0, date - Date.now()), BACKOFF_CAP_MS)
    }
  }
  const exp = BACKOFF_BASE_MS * Math.pow(2, Math.max(0, attempt))
  // ±20% 抖动: 并发 2 若同步退避会形成周期性齐射, 反而更容易再撞 429
  const jitter = exp * 0.2 * (Math.random() * 2 - 1)
  return Math.min(BACKOFF_CAP_MS, Math.max(200, Math.round(exp + jitter)))
}

/**
 * `crypto.subtle` 到底能不能用。
 * 判据是「**subtle 存在且 isSecureContext 没被显式判否**」两者都成立:
 * 浏览器在非 secure context 下本来就把 crypto.subtle 置为 undefined, 但显式检查
 * isSecureContext 能让我们给出「请改用 https」这句话, 而不是笼统的「环境不支持」。
 * ⚠️ 返回 false **不等于**上传失败 —— 只是不带 X-Chunk-SHA256, 后端仍会做合并后实算校验。
 */
export function canComputeChunkHash(g = globalThis) {
  try {
    if (g?.window && g.window.isSecureContext === false) return false
    if (typeof g?.crypto?.subtle?.digest !== 'function') return false
    return true
  } catch {
    return false
  }
}

/** ArrayBuffer → 小写 hex (后端要求 64 位十六进制, 否则 400) */
export function bufToHex(buf) {
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('')
}

/**
 * 会话指纹: 只取文件名 + 大小 + mtime 三者拼起来做一个非加密散列。
 * 目的不是防伪 (后端有 token), 而是让 localStorage 的 key **短且无非法字符**,
 * 同时保证「同名不同文件」落到不同 key 上 (类 20.242 的教训)。
 */
export function fileFingerprint(file) {
  const raw = `${file?.name || ''}|${file?.size ?? 0}|${file?.lastModified ?? 0}`
  let h = 0x811c9dc5
  for (let i = 0; i < raw.length; i++) {
    h ^= raw.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

/** 断点记录的 localStorage 键 —— 必带 token + 文件名 + 大小 */
export function storageKey(token, file) {
  const name = encodeURIComponent(String(file?.name || '').slice(0, 40))
  return `${STORAGE_PREFIX}${encodeURIComponent(String(token || ''))}:${name}:${file?.size ?? 0}:${fileFingerprint(file)}`
}

/**
 * 存下来的记录与当前这个 File 是不是同一份。
 * ⚠️ 必须逐字段比, **不能只比 key** —— key 里含散列, 但把整条记录读回来再核一次
 *    才能在「散列撞了」或「用户换了个同名同大小的文件」时兜住。
 */
export function isSessionCompatible(session, file) {
  if (!session || !file) return false
  return (
    session.filename === file.name &&
    Number(session.fileSize) === Number(file.size) &&
    Number(session.lastModified || 0) === Number(file.lastModified || 0) &&
    Number(session.totalChunks) > 0 &&
    Number(session.chunkSize) > 0
  )
}

/**
 * 造一个与 describeFileRequestFailure 同形状的前端侧失败对象。
 * 用于「不是 HTTP 报错」的失败 (对账不上、参数缺失) —— 这些走不了状态码规则表,
 * 但 UI 只认一种形状, 否则就得在组件里 if/else 两套渲染分支 (类 20.220: 两处各写一遍必漂移)。
 */
export function makeLocalFailure(code, title, detail, action, technical = '') {
  return { code, title, detail, action, technical, status: 0 }
}

/** 前端主动"暂停"不是失败, 但复用同一个形状让 UI 只有一条渲染路径 */
export function makePausedFailure(uploaded, total) {
  return makeLocalFailure(
    FR_FAILURE_CODE.UNKNOWN,
    '上传已暂停',
    `已停下 ${uploaded}/${total} 片。已传的部分服务器都记着，` +
      '点「继续上传」会从断点接着传，不会从头再来。',
    FR_FAILURE_ACTION.RETRY,
    '客户端暂停',
  )
}

// ── localStorage 存取 (整块包 try/catch: 隐私模式/Safari 满盘都会抛) ──────────

function readAllSessions() {
  const out = []
  try {
    for (let i = 0; i < (globalThis.localStorage?.length || 0); i++) {
      const k = globalThis.localStorage.key(i)
      if (!k || !k.startsWith(STORAGE_PREFIX)) continue
      try {
        out.push({ key: k, value: JSON.parse(globalThis.localStorage.getItem(k) || 'null') })
      } catch {
        out.push({ key: k, value: null })
      }
    }
  } catch {
    /* 遍历不了就算了, 当作没有记录 —— 最坏是退化成"重新上传" */
  }
  return out
}

/** 清掉已经过期/损坏的记录, 顺手把数量压到 20 条以内 */
function pruneSessions() {
  const now = Date.now()
  const sessions = readAllSessions()
  for (const s of sessions) {
    const v = s.value
    const stale =
      !v ||
      !v.uploadId ||
      (v.expiresAt && Date.parse(v.expiresAt) < now) ||
      (v.savedAt && now - v.savedAt > 7 * 86400000)
    if (stale) {
      try { globalThis.localStorage.removeItem(s.key) } catch { /* 忽略 */ }
    }
  }
  const alive = readAllSessions().sort((a, b) => (b.value?.savedAt || 0) - (a.value?.savedAt || 0))
  for (const s of alive.slice(20)) {
    try { globalThis.localStorage.removeItem(s.key) } catch { /* 忽略 */ }
  }
}

function saveSession(key, session) {
  try {
    globalThis.localStorage.setItem(key, JSON.stringify({ ...session, savedAt: Date.now() }))
    pruneSessions()
  } catch (e) {
    // 存不下不影响本次上传, 只影响"刷新后续传" —— 记一行, 不打断
    console.warn('[FR-upload] 断点记录写入失败 (刷新后将无法续传):', e?.message || e)
  }
}

function loadSession(key) {
  try {
    const raw = globalThis.localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function removeSession(key) {
  try { globalThis.localStorage.removeItem(key) } catch { /* 忽略 */ }
}

/**
 * 纯函数版滚动窗口限流: 给定"现在"与"窗口内已发起的时刻列表",
 * 算出**这次要等多久**以及**该记下的新时刻列表**。
 * 抽成纯函数是因为直接测并发循环要么真等一分钟, 要么上假定时器
 * (假定时器又跟真实时钟不同步 —— 上一版固定间隔就把 12 个视图用例拖挂了);
 * 而限流算错的方向是"被服务端 429 掐死", 必须有测试兜住。
 */
export function paceWindow(
  nowMs, recent, limit = MAX_PUTS_PER_MINUTE, windowMs = RATE_WINDOW_MS,
) {
  const now = Number(nowMs) || 0
  const keep = (Array.isArray(recent) ? recent : []).filter((t) => now - t < windowMs)
  const waitMs = keep.length >= limit
    ? Math.max(0, windowMs - (now - Math.min(...keep)))
    : 0
  const at = now + waitMs
  // 等过这段时间之后, 最老的那些时刻已经出窗, 不能继续占额度
  return { waitMs, stamps: [...keep.filter((t) => at - t < windowMs), at] }
}

// ── composable ───────────────────────────────────────────────────────────────

/**
 * @param {string} token 收件链接 token (URL 里的 /r/:token)
 * @param {object} [opts]
 * @param {number} [opts.maxPutsPerMinute] 滚动窗口额度, 默认 MAX_PUTS_PER_MINUTE。
 *   调低它是给**测试**用的 (设成 2 就能在毫秒级观察到限流真的发生);
 *   生产不要传大值 —— 那只会更快撞上服务端的 429。
 * @param {number} [opts.rateWindowMs] 限流窗口, 默认 RATE_WINDOW_MS (同上, 只为测试)
 */
export function usePublicChunkedUpload(token, opts = {}) {
  const api = useFileRequests()
  const putsPerMinute = Number.isFinite(opts.maxPutsPerMinute)
    ? Number(opts.maxPutsPerMinute)
    : MAX_PUTS_PER_MINUTE
  const rateWindowMs = Number.isFinite(opts.rateWindowMs)
    ? Number(opts.rateWindowMs)
    : RATE_WINDOW_MS

  /** idle | preparing | uploading | merging | done | error | aborted */
  const status = ref('idle')
  const uploadId = ref(null)
  const chunkSize = ref(0)
  const totalChunks = ref(0)
  const uploadedCount = ref(0)
  const uploadedBytes = ref(0)
  const fileSize = ref(0)
  const filename = ref('')
  const lastCompleted = ref(-1)      // 本轮最后一个传成功的片下标
  const lastError = ref(null)        // describeFileRequestFailure() 的结果
  const rawErrorDetail = ref('')
  const result = ref(null)           // complete 的响应
  const resumableSession = ref(null) // 探测到的可续传记录
  const serverExpiresAt = ref(null)

  // 逐片校验用不了的情况要**明说**, 不能悄悄降级 (类 20.220: 用户以为有校验其实没有)
  const hashAvailable = ref(canComputeChunkHash())
  const hashSkippedChunks = ref(0)

  /** 速度 (B/s) 与剩余时间 (s) —— 用滑动窗口, 断流时会自然归零 */
  const speedBps = ref(0)
  const etaSec = ref(0)
  const samples = []

  let pendingQueue = []
  const doneSet = new Set()
  const inFlight = new Set()
  // 已传片数 = **服务端基线** + 本轮 doneSet 增量。
  // 只用 doneSet.size 会在每次对账后清零 ⇒ 暂停提示一度显示"已停下 3/250 片"
  // 而实际早已传了 200 片 (类 20.220: 数字在骗人)。
  let uploadedBase = 0
  let cancelFlag = false
  let tickTimer = null
  let abortController = null
  // 本次上传/续传所依据的那份 File。断点记录的 key 含 lastModified, 所以
  // **删除记录时必须用同一份 File 去算 key** —— 自己拼一个 {name,size} 会算出别的 key。
  let recentStamps = []        // 最近 RATE_WINDOW_MS 内发起过的 PUT 时刻 (滚动限流)
  let currentFile = null
  function fileForKey() {
    return currentFile || { name: filename.value, size: fileSize.value, lastModified: 0 }
  }

  const percent = computed(() => {
    if (!fileSize.value) return 0
    return Math.min(100, Math.round((uploadedBytes.value / fileSize.value) * 100))
  })
  /** 「当前片号」优先取**正在传**的那一片 (并发 2 时是最小下标), 否则取最后完成的 */
  const currentChunk = computed(() =>
    inFlight.size ? Math.min(...inFlight) + 1 : lastCompleted.value + 1
  )
  const busy = computed(() =>
    status.value === 'preparing' || status.value === 'uploading' || status.value === 'merging'
  )

  function setStatus(s) { status.value = s }

  /**
   * 传完但对账不齐 —— 这**不是网络错误**, 不能套用状态码规则表 (表里没有 HTTP 码可用)。
   * 说清楚"还差几片 + 已经停在这里 + 接着点就行", 别让人以为整场白传了。
   */
  function settleFailure(remaining) {
    const described = makeLocalFailure(
      FR_FAILURE_CODE.CHUNKS_INCOMPLETE,
      `还差 ${remaining} 片没被服务器确认`,
      '这一轮已经把能确认的分片都传完了，但服务器说还差几片。' +
        '已传的部分都安全地留在服务器上，点「继续上传」会再对一次账并补传缺的。',
      FR_FAILURE_ACTION.RETRY,
      `客户端对账 ${MAX_SETTLE_ROUNDS} 轮后仍有 ${remaining} 片未确认`,
    )
    lastError.value = described
    setStatus('error')
    stopTick()
    return described
  }

  function fail(err, context = '') {
    const described = describeFileRequestFailure(err)
    lastError.value = described
    rawErrorDetail.value = [context, detailOf(err)].filter(Boolean).join(' · ')
    // ⚠️ 必须同时叫停**另一个 worker**: 判定不可重试(如 410 链接已关)时,
    //    并发 2 的另一个协程还在队列里继续 PUT, 会把剩下的片全数撞墙一遍,
    //    既白等又刷 429。cancelFlag 让两个 worker 都在下一次取片前退出。
    cancelFlag = true
    // 404/410 这类"链接或会话没了"必须把断点记录删掉, 否则下次刷新还会提示可续传
    // ⚠️ key 里含 lastModified, 所以必须用**当时那份 File**(currentFile)去算,
    //    临时拼一个 {name,size} 会算出另一个 key、删不掉 (本函数原先就是这个错)
    if ([404, 410].includes(described.status) && token && (currentFile || filename.value)) {
      removeSession(storageKey(token, fileForKey()))
      resumableSession.value = null
    }
    setStatus('error')
    stopTick()
    return described
  }

  /** 刷新速度/ETA。bytes 是"当前累计已传字节" */
  function sampleSpeed(bytes) {
    const now = Date.now()
    samples.push({ t: now, b: bytes })
    while (samples.length > 2 && now - samples[0].t > SPEED_WINDOW_MS) samples.shift()
    const first = samples[0]
    const last = samples[samples.length - 1]
    const dt = (last.t - first.t) / 1000
    if (dt > 0.3) {
      const bps = Math.max(0, (last.b - first.b) / dt)
      // 平滑一下, 否则并发 2 的完成节奏会让数字一跳一跳
      speedBps.value = speedBps.value ? speedBps.value * 0.6 + bps * 0.4 : bps
      const remain = Math.max(0, fileSize.value - uploadedBytes.value)
      etaSec.value = speedBps.value > 1024 ? Math.round(remain / speedBps.value) : 0
    }
  }

  function startTick() {
    stopTick()
    tickTimer = setInterval(() => sampleSpeed(uploadedBytes.value), 1000)
  }
  function stopTick() {
    if (tickTimer) { clearInterval(tickTimer); tickTimer = null }
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  /**
   * **可中断**的等待 —— 用于退避与客户端限速。
   * 裸 sleep(60000) 的话, 用户按「暂停」最长要等一整个限流窗口才停得下来
   * (限速的等待上限就是窗口长度)。这里每 CANCEL_TICK_MS 检查一次 cancelFlag,
   * 暂停的响应时间就压到一个 tick。
   * @returns {Promise<boolean>} true=睡满了, false=中途被取消
   */
  async function sleepCancellable(ms) {
    const target = Date.now() + Math.max(0, Number(ms) || 0)
    while (true) {
      if (cancelFlag) return false
      const left = target - Date.now()
      if (left <= 0) return true
      await sleep(Math.min(left, CANCEL_TICK_MS))
    }
  }

  /** 算本片 sha256; 算不了/算失败 ⇒ 返回 null (调用方就不带校验头) */
  async function hashSlice(blob) {
    if (!hashAvailable.value) return null
    try {
      const buf = typeof blob?.arrayBuffer === 'function'
        ? await blob.arrayBuffer()
        : await blobToBufferFallback(blob)
      const digest = await globalThis.crypto.subtle.digest('SHA-256', buf)
      return bufToHex(digest)
    } catch (e) {
      // 单片失败 ⇒ 跳过校验继续传; 连续失败到一定量再整体降级
      console.warn('[FR-upload] 逐片校验计算失败, 本片不带校验头:', e?.message || e)
      return null
    }
  }

  /** 老浏览器没有 Blob.arrayBuffer —— 用 FileReader 兜底 */
  function blobToBufferFallback(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = () => reject(reader.error || new Error('读取分片失败'))
      reader.readAsArrayBuffer(blob)
    })
  }

  /**
   * 开一场的统一清场。upload() 与 resume() **必须都走这里** ——
   * 两处各列一遍字段, 下次加一个状态就只会补一处 (类 20.250 ①: 
   * "修好了"只对被改的那条路径成立)。
   */
  function beginRun(file) {
    cancelFlag = false
    currentFile = file
    // 每次开场换一个新的 AbortController: 暂停时 abort() 过的那个会永久保持
    // aborted 状态, 复用它会让续传的第一片就"被取消"。
    abortController = typeof AbortController !== 'undefined' ? new AbortController() : null
    lastError.value = null
    result.value = null
    rawErrorDetail.value = ''
    serverExpiresAt.value = null
    uploadId.value = null
    chunkSize.value = 0
    totalChunks.value = 0
    doneSet.clear()
    inFlight.clear()
    pendingQueue = []
    uploadedBase = 0
    lastCompleted.value = -1
    uploadedCount.value = 0
    uploadedBytes.value = 0
    samples.length = 0
    speedBps.value = 0
    etaSec.value = 0
    hashSkippedChunks.value = 0
    recentStamps = []                               // 开场不背上一场的额度
    hashAvailable.value = canComputeChunkHash()   // 每次重新探, 用户可能中途换了 https
    fileSize.value = file.size
    filename.value = file.name
  }

  /** 传一片, 内含退避重试。返回 true=成功, false=已判定为不可重试或已取消 */
  async function uploadOneChunk(file, index) {
    let attempt = 0
    while (attempt < MAX_CHUNK_RETRIES) {
      if (cancelFlag) return false
      const { start, len } = chunkRange(fileSize.value, chunkSize.value, index)
      const blob = file.slice(start, start + len)
      const sha = await hashSlice(blob)
      if (sha === null && hashAvailable.value) hashSkippedChunks.value += 1

      // 客户端起跑限速: 见 MAX_PUTS_PER_MINUTE 的注释。
      // 先记账再 await —— 单线程下两个 worker 不会同时读到同一份旧窗口
      const pace = paceWindow(Date.now(), recentStamps, putsPerMinute, rateWindowMs)
      recentStamps = pace.stamps
      if (pace.waitMs > 0 && !(await sleepCancellable(pace.waitMs))) return false
      if (cancelFlag) return false

      inFlight.add(index)
      try {
        try {
          await api.putPublicChunk(token, uploadId.value, index, blob, sha, abortController?.signal)
        } finally {
          inFlight.delete(index)
        }
        if (!doneSet.has(index)) {
          doneSet.add(index)
          uploadedBytes.value += len
        }
        uploadedCount.value = Math.min(totalChunks.value, uploadedBase + doneSet.size)
        lastCompleted.value = index
        sampleSpeed(uploadedBytes.value)
        return true
      } catch (e) {
        if (cancelFlag || e?.code === 'ERR_CANCELED') return false
        const st = statusOf(e)
        if (!isRetryableStatus(st)) {
          fail(e, `第 ${index + 1}/${totalChunks.value} 片`)
          return false
        }
        attempt += 1
        if (attempt >= MAX_CHUNK_RETRIES) {
          fail(e, `第 ${index + 1}/${totalChunks.value} 片重试 ${MAX_CHUNK_RETRIES} 次仍失败`)
          return false
        }
        if (!(await sleepCancellable(resolveRetryDelayMs(e, attempt)))) return false
      }
    }
    return false
  }

  /** 并发 2 的 worker 池。返回 false 表示中途出了不可重试的错或被取消 */
  async function drainQueue(file) {
    async function worker() {
      while (pendingQueue.length) {
        // ⚠️ cancelFlag 必须是**失败**, 不能算"队列跑完了"。
        //    原先写成 while (!cancelFlag && pendingQueue.length) { ... } return true,
        //    暂停时正好卡在 await 上 → 循环正常退出 → 返回 true →
        //    settleUntilDone 以为都传完了, 又白跑 5 轮对账, 最后报"还差 50 片"
        //    而不是"已暂停" (类 20.220: 控制流把中止当成了成功)。
        if (cancelFlag) return false
        const idx = pendingQueue.shift()
        const ok = await uploadOneChunk(file, idx)
        if (!ok) return false
      }
      return !cancelFlag
    }
    const workers = []
    for (let i = 0; i < Math.min(MAX_CHUNK_CONCURRENCY, pendingQueue.length || 1); i++) {
      workers.push(worker())
    }
    const results = await Promise.all(workers)
    return results.every(Boolean)
  }

  /**
   * 服务端对账: 用 GET 回来的 uploaded/missing 修正本地计数, 并把还没传的排进队列。
   * 返回 { allDone, ok, remaining } —— `remaining` 必须在这里就定下来:
   * 调用方随后会 drainQueue() 把 pendingQueue 清空, 那时再读它就永远是 0 了
   * (本函数原先就是这个错, 报成"还差 0 片")。
   */
  async function syncFromServer(file) {
    try {
      const st = await api.getPublicUploadStatus(token, uploadId.value)
      // ⚠️ 续传的**第一道自检**: 服务端记的文件大小必须与本地这份一致。
      //    本仓踩过 basename 碰撞 ⇒ 同名不同内容会静默复用错数据 (类 20.242)。
      //    localStorage 的 key 已经带了名字+大小+指纹, 这里是第二道, 且是唯一
      //    能发现"记录是旧的/被手改过"的一道 —— 不一致就拒绝续传, 绝不硬拼。
      const serverSize = Number(st.file_size)
      if (Number.isFinite(serverSize) && serverSize > 0 && serverSize !== Number(fileSize.value)) {
        removeSession(storageKey(token, file))
        resumableSession.value = null
        lastError.value = makeLocalFailure(
          FR_FAILURE_CODE.UNKNOWN, '断点记录与当前文件对不上',
          `服务器上的这份记录是 ${serverSize} 字节，而你选的这份是 ${fileSize.value} 字节，` +
            '不是同一个文件。请直接点「上传大文件」重新传，不要续传这条记录。',
          FR_FAILURE_ACTION.RESELECT,
          `size 不一致: server=${serverSize} local=${fileSize.value} upload=${uploadId.value}`,
        )
        setStatus('error')
        stopTick()
        return { allDone: false, ok: false, remaining: 0 }
      }
      // 对账回来的字段一律"有才覆盖" —— 缺字段时**保留已知的值**, 不要拿 undefined
      // 把界面上已经显示的东西抹掉 (chunk_size 那行的 `|| 旧值` 就是同一个道理)
      chunkSize.value = Number(st.chunk_size) || chunkSize.value
      totalChunks.value = Number(st.total_chunks) || totalChunks.value
      if (st.expires_at) serverExpiresAt.value = st.expires_at
      if (st.filename) filename.value = st.filename
      const list = planPending(totalChunks.value, st.missing_chunks)
      doneSet.clear()
      pendingQueue = list
      uploadedBytes.value = Math.max(
        0,
        fileSize.value - list.reduce((acc, i) => acc + chunkRange(fileSize.value, chunkSize.value, i).len, 0)
      )
      uploadedBase = Math.max(0, totalChunks.value - list.length)
      uploadedCount.value = Math.min(totalChunks.value, uploadedBase)
      // 顺手把断点记录刷成服务端校正后的值 —— 对账每跑一次记录就新一次,
      // 这样"刷新页面再续传"拿到的一定是服务端口径的 chunk_size/total_chunks
      persist()
      return { allDone: list.length === 0, ok: true, remaining: list.length }
    } catch (e) {
      fail(e, '查询断点进度')
      return { allDone: false, ok: false, remaining: 0 }
    }
  }

  /**
   * 「传到服务端认账为止」: 对账 → 补缺口 → 再对账, 最多 MAX_SETTLE_ROUNDS 轮。
   * 为什么必须循环: 后端的 missing_chunks **只回前 200 个**, 一轮补完只会露出下一批。
   * 返回 true 表示服务端已确认全齐 (false 时 lastError 已就位)。
   */
  async function settleUntilDone(file) {
    for (let round = 0; round <= MAX_SETTLE_ROUNDS; round++) {
      const sync = await syncFromServer(file)
      if (!sync.ok) return false
      if (sync.allDone) return true
      const drained = await drainQueue(file)
      if (!drained) return false
    }
    const last = await syncFromServer(file)
    if (!last.ok) return false
    if (last.allDone) return true
    settleFailure(last.remaining)
    return false
  }

  /** 把 upload_id 记进 localStorage (key 带 token+文件名+大小, 值里再存一份用于回读校验) */
  function persist() {
    if (!token || !uploadId.value) return
    const f = fileForKey()
    saveSession(storageKey(token, f), {
      uploadId: uploadId.value,
      filename: f.name,
      fileSize: f.size,
      lastModified: f.lastModified ?? 0,
      chunkSize: chunkSize.value,
      totalChunks: totalChunks.value,
      expiresAt: serverExpiresAt.value,
    })
  }

  /** 探测: 这个文件有没有可续传的历史记录 (页面选完文件后调) */
  function findResumable(file) {
    resumableSession.value = null
    if (!token || !file) return null
    const rec = loadSession(storageKey(token, file))
    if (!isSessionCompatible(rec, file)) {
      if (rec) removeSession(storageKey(token, file))
      return null
    }
    if (rec.expiresAt && Date.parse(rec.expiresAt) < Date.now()) {
      removeSession(storageKey(token, file))
      return null
    }
    resumableSession.value = rec
    return rec
  }

  function clearResumable(file) {
    if (file) removeSession(storageKey(token, file))
    resumableSession.value = null
  }

  function reset() {
    cancelFlag = true
    stopTick()
    status.value = 'idle'
    uploadId.value = null
    chunkSize.value = 0
    totalChunks.value = 0
    uploadedCount.value = 0
    uploadedBytes.value = 0
    fileSize.value = 0
    filename.value = ''
    lastCompleted.value = -1
    inFlight.clear()
    uploadedBase = 0
    lastError.value = null
    rawErrorDetail.value = ''
    result.value = null
    pendingQueue = []
    doneSet.clear()
    samples.length = 0
    speedBps.value = 0
    etaSec.value = 0
    hashSkippedChunks.value = 0
    hashAvailable.value = canComputeChunkHash()
  }

  /**
   * 走完整流程: init → 传齐 → complete。
   * @param {File} file
   * @param {string} [uploaderName]
   * @returns {Promise<{ok: boolean, data?: object, error?: object}>}
   */
  async function upload(file, uploaderName) {
    if (!file) {
      return {
        ok: false,
        error: makeLocalFailure(
          FR_FAILURE_CODE.UNKNOWN, '还没有选择文件',
          '请先点「选择文件」挑一个要上传的文件，再点上传。',
          FR_FAILURE_ACTION.NONE, 'upload() 未收到 file',
        ),
      }
    }
    beginRun(file)

    setStatus('preparing')
    let init
    try {
      init = await api.initPublicUpload(token, {
        filename: file.name,
        fileSize: file.size,
        uploaderName,
      })
    } catch (e) {
      const described = fail(e, '发起分片上传')
      return { ok: false, error: described }
    }

    uploadId.value = init.upload_id
    // ⚠️ 用服务端的 chunk_size —— 自己算的那个数不作数 (后端会按它逐字节核长度)
    chunkSize.value = Number(init.chunk_size) || 0
    totalChunks.value = Number(init.total_chunks) || 0
    serverExpiresAt.value = init.expires_at || null
    if (!chunkSize.value || !totalChunks.value) {
      // 契约破了 (后端没给 chunk_size) —— 绝不能自己编一个数往下传:
      // 非末片长度必须与服务端的值逐字节相等, 编错了整场会卡在 400/409
      lastError.value = makeLocalFailure(
        FR_FAILURE_CODE.UNKNOWN,
        '服务器没有返回分片参数',
        '这个链接的大文件通道没有正常初始化（服务器没告诉前端该按多大切分）。' +
          '请重试，或先用「普通上传」传一个小的文件；持续如此请联系发起人。',
        FR_FAILURE_ACTION.RETRY,
        `init 响应缺少 chunk_size/total_chunks: ${JSON.stringify({ c: init?.chunk_size, t: init?.total_chunks })}`,
      )
      setStatus('error')
      stopTick()
      return { ok: false, error: lastError.value }
    }
    setStatus('uploading')
    startTick()
    persist()

    pendingQueue = planPending(totalChunks.value, init.missing_chunks)
    uploadedBytes.value = fileSize.value -
      pendingQueue.reduce((acc, i) => acc + chunkRange(fileSize.value, chunkSize.value, i).len, 0)
    uploadedBase = Math.max(0, totalChunks.value - pendingQueue.length)
    uploadedCount.value = uploadedBase

    let ok = await drainQueue(file)
    if (!ok) return { ok: false, error: lastError.value }

    // 对账: 本地 doneSet 只是"我以为传完了", 服务端的 missing 才是真值
    ok = await settleUntilDone(file)
    if (!ok) return { ok: false, error: lastError.value }

    setStatus('merging')
    try {
      const done = await api.completePublicUpload(token, uploadId.value)
      result.value = done
      // 成功了就把断点记录清掉, 否则下次进来还会提示"有未完成的上传"
      clearResumable(file)
      removeSession(storageKey(token, file))
      setStatus('done')
      stopTick()
      return { ok: true, data: done }
    } catch (e) {
      const described = fail(e, '服务端合并')
      return { ok: false, error: described }
    }
  }

  /**
   * 从断点续传: 用 localStorage 里的 upload_id 问服务端还缺哪些片。
   * 服务端会话已过期/不存在 ⇒ 记录作废, 返回 error 让 UI 提示重新上传。
   */
  async function resume(file) {
    const stored = file ? loadSession(storageKey(token, file)) : null
    const rec = stored && isSessionCompatible(stored, file) ? stored : resumableSession.value
    if (!file || !rec?.uploadId) {
      return {
        ok: false,
        error: makeLocalFailure(
          FR_FAILURE_CODE.UNKNOWN, '没有可用的断点记录',
          '这台设备上没找到这份文件的未完成上传记录，需要重新选文件从头上传。',
          FR_FAILURE_ACTION.RESELECT, 'resume() 未找到匹配的本会话记录',
        ),
      }
    }
    beginRun(file)
    uploadId.value = rec.uploadId
    // 本地记录里的 chunk_size/total_chunks 只当占位用 —— 
    // 紧接着的对账会用服务端口径覆盖一次, 以免在等待响应期间界面显示 0 片
    chunkSize.value = Number(rec.chunkSize) || 0
    totalChunks.value = Number(rec.totalChunks) || 0

    setStatus('uploading')
    startTick()

    // 对账 + 补传 + 合并前确认全齐, 全在 settleUntilDone 里 (它第一步就是对账,
    // 并把服务端校正后的 chunk_size/total_chunks 顺手写回断点记录)。
    // ⚠️ 这里**不要再自己 sync 一次**: 两轮对账之间服务端可能已被 beat 清理,
    //    多问一次只是浪费 read 额度, 且原先那次还导致 record 被写两遍。
    const settled = await settleUntilDone(file)
    if (!settled) return { ok: false, error: lastError.value }

    setStatus('merging')
    try {
      const done = await api.completePublicUpload(token, uploadId.value)
      result.value = done
      removeSession(storageKey(token, file))
      resumableSession.value = null
      setStatus('done')
      stopTick()
      return { ok: true, data: done }
    } catch (e) {
      return { ok: false, error: fail(e, '服务端合并') }
    }
  }

  /** 暂停 (保留服务端会话与断点记录, 之后可续传) */
  function pause() {
    cancelFlag = true
    if (abortController) { try { abortController.abort() } catch { /* 忽略 */ } }
    stopTick()
    // 暂停期间可能正好有一片在飞, abort 会让它抛 ERR_CANCELED —— uploadOneChunk
    // 已按 cancelFlag 返回 false, 不会误报成失败
    lastError.value = makePausedFailure(uploadedCount.value, totalChunks.value)
    inFlight.clear()
    setStatus('error')
  }

  /** 放弃: 通知服务端删掉临时分片, 并清掉本地断点 */
  async function abort(file) {
    cancelFlag = true
    if (abortController) { try { abortController.abort() } catch { /* 忽略 */ } }
    stopTick()
    const f = file || fileForKey()
    if (token && uploadId.value) {
      try { await api.abortPublicUpload(token, uploadId.value) } catch (e) {
        // 服务端删不掉有 beat 清理兜底, 这里不拦用户
        console.warn('[FR-upload] abort 失败 (服务端会按 24h TTL 自动清理):', detailOf(e))
      }
    }
    removeSession(storageKey(token, f))
    resumableSession.value = null
    setStatus('aborted')
  }

  if (getCurrentScope()) {
    onScopeDispose(() => { stopTick() })
  }

  return {
    // 常量
    CHUNKED_THRESHOLD_BYTES,
    MAX_CHUNK_CONCURRENCY,
    // state
    status, uploadId, chunkSize, totalChunks, uploadedCount, uploadedBytes,
    fileSize, filename, currentChunk, lastError, rawErrorDetail, result,
    resumableSession, serverExpiresAt, hashAvailable, hashSkippedChunks,
    speedBps, etaSec,
    // computed
    percent, busy,
    // api
    upload, resume, pause, abort, reset, findResumable, clearResumable,
  }
}
