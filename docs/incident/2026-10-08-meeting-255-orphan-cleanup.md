# 会议 255 孤儿清理误杀事故 — 根因 + 修复方案

> **事故日期**：2026-10-08（北京时间 18:45 开会，19:23 被孤儿清理误杀）
> **受害对象**：会议 255 / user_id=58 / iPhone (iOS 18.7, Safari 26.6, IP 202.113.185.204)
> **上一同类事故**：会议 250 / 2026-09-14 / 修复链 `ee55b3f81`
> **本文性质**：调查 + 修复方案（Phase 1）。**未实施任何代码改动。**
> **目录约定更正**：任务书要求落到 `docs/incidents/`（复数），但仓库实际约定是
> **`docs/incident/`（单数）**——见 `docs/incident/README.md:1` 与 `CLAUDE.md` 顶部
> "想知道某次事故的完整过程 → `docs/incident/`"。本文遵循仓库既有约定。

---

## 事故时间线（全部来自生产库实查，非推测）

`audit_log` 表实际留存区间 `2026-07-01 18:24` → `2026-10-08 13:50`，共 192,975 行，
**事故窗口数据完整未被清理**，可直接作为证据。

| UTC 时间 | 北京时间 | 事件 | 证据 |
|---|---|---|---|
| 10:45:03.110 | 18:45:03 | user 58 `POST /api/v1/auth/login` → 200 | `audit_log` id=193358 |
| **10:45:17.480** | **18:45:17** | **会议 255 创建**，`status='recording'`，`recording_started_at` 落库 | `meetings.id=255` |
| 10:45:17.536 | 18:45:17 | user 58 `POST /api/v1/meetings/start-recording` → 200 | `audit_log` id=193370 |
| 10:45:33 → 10:52:12 | 18:45–18:52 | user 58 每 30s 轮询 `GET /api/v1/notifications/unread-count` → 200，**共 12 次，页面存活 ~7 分钟** | `audit_log` id=193371–193383 |
| **10:45–11:35 全窗口** | — | **`recording-heartbeat` POST：0 条** | `path LIKE '%recording-heartbeat%'` 零命中 |
| **10:45–11:35 全窗口** | — | **`audio-chunk` PUT：0 条**（iOS 预期行为，见根因 B） | `path LIKE '%audio-chunk%'` 零命中 |
| 10:52:12 → 11:09:13 | 18:52–19:09 | **17 分钟无任何请求**（页面被切后台 / 锁屏 / 被系统回收） | `audit_log` 空档 |
| 11:09:13 | 19:09:13 | unread-count 轮询恢复 | `audit_log` id=193384 |
| **11:09:27–11:09:28** | **19:09:27** | **user 58 `GET /api/v1/meetings/255` + `GET /api/v1/meetings/255/upload-status` ×2** → 200 | `audit_log` id=193388–193395 |
| **11:23:04** | **19:23:04** | `orphan_meeting_cleanup` 标记 `status='error'` | `meetings.id=255.error_reason` |
| — | — | 错误原文：`录音超过 30min 未 stop (last_chunk_index=-1, total_chunks=None), 已自动清理 [UA: Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X)...]` | `meetings.id=255` |
| — | — | 标题被改写为 `听会记录（已清理 10-08 10:45）` | `orphan_meeting_cleanup.py:111-112` |
| — | — | `meeting_chunks` 表 meeting_id=255：**0 行** | `SELECT count(*) ... WHERE meeting_id=255` |
| — | — | Redis `meeting:recording:heartbeat:*`：**空**（事后） | `redis-cli --scan` |

**决定性指纹**：11:09:27 的 `GET /meetings/255` + `GET /meetings/255/upload-status`
这对请求，**正是恢复路径 `web/src/views/MeetingRoomView.vue:257-260` 的代码**：

```js
const [meetingRes, uploadRes] = await Promise.all([
  axios.get(`/api/v1/meetings/${id}`),
  axios.get(`/api/v1/meetings/${id}/upload-status`).catch(() => null),
])
```

这是"页面被重新加载 / 重新进入录音室"的铁证，而非普通浏览。

---

## 根因

### 根因 A（主因）：心跳生命周期绑死在组件实例，且恢复路径**从不启动**心跳

这是本次事故的**真正根因**，也是 09-15 修复链的一个未被发现的致命缺口。

**A-1 心跳是组件局部状态，不是录音会话状态**

```js
// web/src/components/AudioRecorder.vue:129
let heartbeatTimer = null
```

`heartbeatTimer` 是 `<script setup>` 的局部变量，生命周期 = AudioRecorder 组件实例。

**A-2 `startHeartbeat()` 只在"用户点按钮"这一条路径上被调用**

```js
// web/src/components/AudioRecorder.vue:137-141
function startHeartbeat() {
  stopHeartbeat()
  beatHeartbeat()
  heartbeatTimer = setInterval(beatHeartbeat, 60000)
}
```

全仓 grep 确认，`startHeartbeat()` 的**唯一**调用点是：

```js
// web/src/components/AudioRecorder.vue:169-173
async function handleStart() {
  try {
    await start()
    startHeartbeat()      // ← 唯一调用点，在 handleStart 里
    emit('recording-start')
```

`handleStart()` 只绑定在按钮上（`AudioRecorder.vue:6` `@click="handleStart"`）。
即：**只有"用户亲手点开始听会"才可能有心跳。**

**A-3 全站没有 keep-alive → 任何路由切换立即卸载组件并停心跳**

```html
<!-- web/src/App.vue:3-17 -->
<router-view v-slot="{ Component, route }">
  <Suspense><component :is="Component" :key="route.fullPath" ... /></Suspense>
</router-view>

<!-- web/src/layouts/MainLayout.vue:134 -->
<router-view />
```

两处 `router-view` 均**无 `<keep-alive>`**。而：

```js
// web/src/components/AudioRecorder.vue:155
onUnmounted(stopHeartbeat)
```

产品明确支持"导航到其他页面录音继续"（`MeetingRoomView.vue:64` 帮助文案、
`MeetingRoom.vue`/胶囊交互、`useGlobalRecorder.js:1-5` "录音在后台持续进行，
不受组件销毁/挂载影响"）。**录音是全局单例继续跑的，心跳却随组件一起死了。**

**A-4 恢复路径直接调 composable，完全绕过 `handleStart()`**

```js
// web/src/views/MeetingRoomView.vue:274-281（移动端 MobileMeetingRoom.vue:254-260 完全同款）
try {
  await startGlobalRecorder()      // ← useGlobalRecorder().start()，不是 handleStart
  console.warn('[MeetingRoomView] 自动启动 MediaRecorder 成功, meetingId =', id)
```

父组件直接调用 `useGlobalRecorder().start()`，**`AudioRecorder.handleStart()` 从未执行，
`startHeartbeat()` 从未被调用**。

**A-5 唯一的兜底 `watch` 在恢复路径上恰好不触发**

```js
// web/src/components/AudioRecorder.vue:151-153
watch(meetingIdRef, (mid) => {
  if (mid && isActive()) beatHeartbeat()
})
```

恢复路径的执行顺序是：

| 步骤 | 代码位置 | 动作 | 此时 `isActive()` |
|---|---|---|---|
| 1 | `MeetingRoomView.vue:248` | `meetingId.value = id` | **false**（MediaRecorder 还没启动） |
| 2 | props 传导 → `AudioRecorder.vue:89-91` | `meetingIdRef.value = 255` | **false** |
| 3 | `watch(meetingIdRef)` 触发 | `if (mid && isActive())` → **条件不成立，跳过** | false |
| 4 | `MeetingRoomView.vue:276` | `await startGlobalRecorder()` | true（太晚了，watch 不会重跑） |

→ **恢复路径连那一次兜底心跳都发不出去。全程 0 心跳。**

**A-6 `onMounted` 也没有补心跳**

```js
// web/src/components/AudioRecorder.vue:159-165
onMounted(() => {
  if (state.value === 'stopped' || (state.value !== 'idle' && !sessionStorage.getItem('recording_meeting_id'))) {
    reset()
  }
})
```

只在"状态陈旧"时 reset，**从不调用 `startHeartbeat()`**。

**结论**：09-15 的心跳守卫只在"用户点按钮 → 全程不刷新、不切页"的窄路径上有效。
**任何一次页面刷新或路由离开再回来，心跳守卫永久失效**——而这恰恰是 iOS Safari
用户最常见的行为。会议 255 的 11:09 指纹（根因见时间线）精确命中此路径。

**附带发现**：心跳的**新建路径首次心跳也是废的**。
`handleStart()` 里 `startHeartbeat()` 先调 `beatHeartbeat()`，此刻 `meetingIdRef.value`
仍是 `null`（meetingId 要等 `emit('recording-start')` 后的 POST 返回才到位），
`beatHeartbeat()` 第一行 `if (!mid) return` 直接返回。之后靠 60s interval 兜底。
这解释了为什么会议 255 在页面存活的前 7 分钟（10:45–10:52，12 次轮询可证）
仍然一条心跳都没有——**要么 interval 被 iOS 挂起，要么这 7 分钟里发生过一次组件重建**。

### 根因 B：iOS Safari 不遵守 `MediaRecorder.start(timeslice)` → 全程 0 分片

```js
// web/src/composables/useGlobalRecorder.js:126
mediaRecorder.start(1000)
```

iOS Safari 忽略 timeslice 参数，`ondataavailable` 只在 `stop()` 时触发一次。
这是 09-15 修复链已经明确记录在案的既有事实
（`web/src/composables/useMeetingAudioUpload.js:7-9`、`recording_heartbeat.py` docstring）。
会议 255 `meeting_chunks` 0 行 + `last_chunk_index=-1` 完全吻合。

**这不是 bug，是 iOS 平台限制**——但它让"边录边传"这条唯一的持久化路径彻底失效（见根因 C）。

### 根因 C：录音内容只存在于内存，`page reload` 必然全丢；IndexedDB 救不了 iOS

```js
// web/src/composables/useGlobalRecorder.js:67
let audioChunks = []          // 模块级数组，非持久化

// useGlobalRecorder.js:165 / :308
const blob = new Blob(audioChunks, { type: 'audio/webm' })
function getAudioBlob() { ... return new Blob(audioChunks, ...) }
```

页面 reload → 模块重新初始化 → `audioChunks = []` → **录音彻底消失**。

**关于任务书的问题"IndexedDB 能否在 reload 后恢复已录音频"——答案是：iOS 路径下不能。**

`web/src/utils/idbStore.js` 实现了完整的 IndexedDB chunk 持久化
（`putChunk` / `getPendingChunks` / `getAllChunks`，307 行），但**唯一写入入口**是：

```js
// web/src/composables/useChunkedRecorder.js:92-167
function handleChunk({ index, blob, size }) {
  ...
  idbStore.putChunk(mid, index, blob, { uploaded: false })
```

`handleChunk` 由 `useGlobalRecorder` 的 `ondataavailable` 驱动（`useChunkedRecorder.js:200`）。
**iOS 上 `ondataavailable` 整个录音期间一次都不触发 → IndexedDB 全程为空。**

`useChunkedRecorder` 的 `resumePending()`（`:74-89`）恢复能力再强也无源可恢。
9 月的 `docs/CLAUDE-history.md:412` 记录的那套"5 阶段录音断网防御"对桌面 Chrome 有效，
**对 iOS Safari 是空转**。

### 根因 D：阈值与 TTL 数值本身不是问题——问题是心跳根本没在发

实测值（生产库 + 源码双向确认）：

| 参数 | 实测值 | 位置 |
|---|---|---|
| `ORPHAN_MEETING_TIMEOUT_MINUTES` | **30**（无任何 env/compose 覆盖） | `app/config.py:222` |
| Celery beat `cleanup-orphan-meetings` | **600.0s（10 分钟）** | `app/core/celery.py:108-112` |
| `HEARTBEAT_TTL_SECONDS` | **300s（5 分钟）** | `app/services/recording_heartbeat.py:48` |
| 前端心跳间隔 | 60s | `AudioRecorder.vue:140` |

数值本身是自洽的：只要心跳每 60s 发一次，TTL 永不过期，清理任务永远跳过。

**但心跳一旦停止**，Redis key 在最后一次心跳后 300s 消失，而清理任务每 600s 扫一次
→ **误杀窗口 = 心跳停止后 300~900 秒**。会议 255：心跳最后可能停在 10:52（页面挂起），
key 于 10:57 过期，11:23 的 tick 正好落在窗口内 → 判死。

**讨论：阈值该不该调大？** 建议 **不动**（见修复方案 P2 理由）。
调大只是把误杀窗口从"30min"推到"45/90min"，不解决"心跳断了"这个根因，
同时让真孤儿（用户真的走了）多占 45~90 分钟会议槽位，副作用大于收益。

### 根因 E：录音链路完全没有可见性 / 卸载感知

全仓 grep `visibilitychange|pagehide|beforeunload` 在**录音链路零命中**。
唯一使用这些事件的是 WebSocket：

```js
// web/src/utils/wsClient.js:50-52
window.addEventListener('freeze', this._onBfcacheFreeze)
window.addEventListener('pagehide', (e) => { if (e.persisted) this._onBfcacheFreeze() })
window.addEventListener('resume', this._onBfcacheResume)
```

即：**WS 连接有 bfcache 感知能力，录音心跳完全没有。** 具体缺失：

1. 切后台 → 不降频、不停发、不上报（iOS 下发了也发不出去，但至少应记录）
2. 切回前台 → **不立即补心跳**（恢复后最长要等 60s 才补，而这 60s 正是最危险的窗口）
3. 页面卸载 → **不通知后端**。用户关页面后，后端仍以为是活跃录音，直到超时误杀
4. `recording_heartbeat.py:32-34` 的设计文档只考虑了
   "stop-recording / cancel-recording / merge 后清 key"，**完全没考虑"页面消失"这个最常见路径**

### 根因 F：服务端兜底过于激进——0 分片也直接判死并删数据

```python
# app/services/orphan_meeting_cleanup.py:101-119
m.status = "error"
m.error_reason = f"录音超过 {settings.ORPHAN_MEETING_TIMEOUT_MINUTES}min 未 stop ..."
...
deleted = await chunked_upload_service.delete_chunks(m.id)   # ← 无条件删
```

09-15 在**查询判定**上加了保守兜底（心跳查失败时返回 True 保守判活，
`recording_heartbeat.py:88-91`"宁可漏清一个孤儿，也不误杀"），
但**在数据销毁上没有同等保守策略**：

- 会议 255 实际删了 0 个 chunk（本来就没有）——侥幸
- 但若是桌面 Chrome 录到一半刷新（已有部分分片），**已上传的音频会被直接删除，用户连补救机会都没有**

这是设计上的第二个洞：只保护了"判定"，没保护"数据"。

### 根因 G：心跳与音频分片共用 `write` 限流桶（30/min），且 429 不写审计

```python
# app/core/rate_limit.py:266-276
# 2026-07-02: 听会边录边传 (chunked audio upload) 端点精确路径匹配
# PUT /api/v1/meetings/{meeting_id}/audio-chunk?chunk_index=N
# - MediaRecorder.start(1000) 每 1s 触发 ondataavailable → 1秒1片
# - 走 write tier 30/min → 30秒录音就 429 触顶, 用户看到"网络断开"
# - 必须独立 tier (60/min = 1分钟录音)
_CHUNKED_UPLOAD_PATH_RE = re.compile(r"^/api/v1/meetings/\d+/audio-chunk$")
```

项目已经知道"边录边传会打爆 write 桶"并给 `audio-chunk` 开了独立 tier，
**但 09-15 新增的 `recording-heartbeat` 没有被加进这个白名单**，仍走默认 `write` 30/min。

桌面 Chrome 场景：分片 1/s（60/min，独立 tier 不冲突）+ 心跳 1/min（write 桶）
看似够用，但 write 桶是**全站共享**的——用户同时在聊天/建任务/传文件时，
心跳随时可能被挤掉。

**更麻烦的是 429 不可观测**：

```python
# app/core/rate_limit.py:477-484
try:
    await limiter.check(client_key)
except HTTPException as e:
    return JSONResponse(status_code=e.status_code, ...)   # ← 提前 return，跳过审计
```

429 分支**在审计集成之前就 return 了**——被限流的心跳不会留任何 audit_log 痕迹。
这直接削弱了"audit_log 没有心跳 = 前端没发心跳"这一推断的强度（见下方歧义点）。

### 根因 H：审计口径陷阱（方法论问题，非事故根因）

`_extract_resource()`（`audit_middleware.py:99-118`）会把
`/api/v1/meetings/255/recording-heartbeat` 的 `resource_id` 解析成 `'255'`。
排查时按 `path LIKE '%255%'` 过滤会把心跳 / 分片 / stop / GET 详情全混在一起。
**必须按完整 path 过滤**。本次调查已按完整 path 复核。

---

## 与 09-14 会议 250 事故对比

| 维度 | 会议 250（2026-09-14） | 会议 255（2026-10-08） | 修复差距 |
|---|---|---|---|
| 设备 | iPhone（杜同贺） | iPhone（user 58, iOS 18.7 / Safari 26.6） | 同 |
| 录音时长 | 1h40m | ~38min（10:45→11:23） | 255 更短，**更不该被杀** |
| 分片数 | 0（iOS timeslice 不遵守） | **0**（同） | 无改进 |
| nginx 413 | **有**（162MB 单请求超 50m） | **无**（从未上传） | ✅ 已修（50m→1024m） |
| 收尾上传三路降级 | ✅ 已实现（`useMeetingAudioUpload.js`） | ⛔ **根本没走到 stop，无从触发** | 代码在，但用户没能走到那一步 |
| `merge_chunks_raw` 字节拼接 | ✅ 已实现 | ⛔ 同上，未触发 | 同上 |
| 心跳守卫代码 | ✅ 已实现且**已部署**（容器/仓库 `diff` 一致，dist 含 `recording-heartbeat`） | ✅ 已部署 | **无部署差距——是逻辑差距** |
| 心跳实际发送 | 09-14 事故时该功能尚不存在 | **0 条** | ❌ **修复存在但从未生效** |
| 录音内容可恢复性 | 内存 blob，reload 即丢 | 内存 blob，reload 即丢 | ❌ **无改进** |
| 可见性/卸载感知 | 无 | 无 | ❌ **无改进** |
| 结局 | 用户用手机自带录音器补录 137MB m4a，最终 `status='completed'`（库实查） | 用户主动清理，**整场录音丢失** | 255 更严重 |

### 关键结论：09-15 修复链"看起来完整"，实际存在三段断裂

`ee55b3f81`（2026-09-15）落地了四段修复，**但没有一处在 `docs/incident/` 留下复盘**，
也没有提炼成 `CLAUDE.md` 的"永久铁律"条目。经本次彻查：

| # | 断裂点 | 何时暴露 |
|---|---|---|
| 1 | 心跳只在按钮路径启动，恢复路径不发（根因 A） | **2026-10-08 会议 255**（本次） |
| 2 | `merge_chunks` ffmpeg concat 静默丢分片（307 片只剩首片有 EBML 头） | 2026-09-18 **会议 253**（音频只剩 0.96s），commit `35e410761` 才补 `assert_merged_integrity` |
| 3 | `useMeetingAudioUpload.js` 248 行三路降级逻辑**无任何单元测试** | 至今 |

**会议 253/254 的真相（任务书前提需更正）**：

- **会议 253（2026-09-18）不是成功，是失败事故**。见
  `docs/incident/2026-08-04--2026-09-18-status-snapshots.md:14-52`：
  merge 静默丢 306/307 片 + sensevoice CUDA 500 → 只剩 0.96s。
- **会议 254（2026-09-24）成功了，但全仓无任何文档记录**。库实查：
  `title='2026-09-24 例行组会'`, `status='completed'`,
  `meeting_chunks` **25 行**（chunk_index 0–24）。
  **25 个分片 = 桌面 Chrome 正常触发 timeslice**。
  这正是"iOS 0 分片 vs 桌面 25 分片"的对照样本——
  **它成功不是因为修复更好，而是因为它没用 iOS。**
- 会议 250 最终 `status='completed'`（库实查），但那是用户**事后用手机自带录音器补录**
  重新上传的结果，不是原录音救回来了。

---

## 修复方案（按优先级）

### P0-1 前端 — 心跳从组件局部提升为全局单例（**最高优先级，直接堵死根因 A**）

**问题**：`heartbeatTimer` 绑组件，组件一卸载心跳就死。
**改法**：在 `web/src/composables/useGlobalRecorder.js`（已是模块级单例）
或新建 `web/src/composables/useRecordingHeartbeat.js` 中实现模块级心跳管理器，
与 `useGlobalRecorder` 同生命周期。

```js
// 新增 web/src/composables/useRecordingHeartbeat.js（模块级单例）
let timer = null
let currentMeetingId = null

export function ensureHeartbeat(meetingId) {
  if (!meetingId) return
  currentMeetingId = meetingId
  beat()
  if (!timer) timer = setInterval(beat, 60000)
}
export function stopHeartbeat() { clearInterval(timer); timer = null; currentMeetingId = null }
function beat() {
  if (!currentMeetingId) return
  sendRecordingHeartbeat(currentMeetingId)   // 复用 useMeetingAudioUpload.js:83
}
```

**改动点**：
- `web/src/components/AudioRecorder.vue:129-155` — 删除组件局部 heartbeat 全套，
  改为调用单例的 `ensureHeartbeat(mid)` / `stopHeartbeat()`
- `web/src/components/AudioRecorder.vue:172` — `startHeartbeat()` → `ensureHeartbeat(meetingIdRef.value)`
- **`web/src/components/AudioRecorder.vue:159-165` `onMounted` — 新增**：
  若 `isActive()` 且 `meetingIdRef.value` 存在，立即 `ensureHeartbeat()`（补 A-6 缺口）
- **`web/src/views/MeetingRoomView.vue:276`** — `await startGlobalRecorder()` 之后
  `ensureHeartbeat(id)`（补 A-4 缺口）
- **`web/src/views/mobile/meeting/MobileMeetingRoom.vue:256`** — 同上
- `web/src/composables/useGlobalRecorder.js:82-133` `start()` 内也可兜底调一次
  （组件无关，任何调用 `start()` 的地方都自动带上心跳）

**验收**：`vitest` 用例——挂载/卸载 AudioRecorder、切换路由、`startGlobalRecorder()`
三条路径各自断言心跳仍在发；卸载组件后 fake timer 推进 60s，心跳仍被调用。

### P0-2 前端 — `visibilitychange` / `pageshow` 切回前台立即补心跳

```js
// web/src/composables/useRecordingHeartbeat.js 内注册（模块加载即注册）
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') beat()   // 切回前台立即补
})
window.addEventListener('pageshow', (e) => { if (e.persisted) beat() })  // bfcache 恢复
window.addEventListener('focus', beat)
```

**为什么必要**：iOS Safari 后台挂起后 interval 会被冻结，恢复时最长 60s 才补一次，
**而这 60s 正是最危险窗口**。切回前台的第一件事必须是补心跳。

### P0-3 前端 — `pagehide` / `visibilitychange(hidden)` 标记"用户离开"（防孤儿）

iOS 不可靠地支持 `beforeunload`（不弹确认框、且后台切换时可能不触发）。
可落地的组合：

1. `visibilitychange → hidden` 时，把最后已录时长 + `document.hidden` 状态写 `localStorage`
   （供用户回来时对齐 elapsed）
2. `pagehide` 时用 `navigator.sendBeacon()`（iOS Safari 支持）POST
   `/api/v1/meetings/{id}/recording-presence` 标记"页面已卸载"，
   **注意：不要标记 stop**，只是让后端知道"可能只是切走了"，
   让 orphan cleanup 把这类会议**降级为"待确认"而非立即判死**。

**保守原则**：iOS 上 `pagehide` 同样可能被挂起，所以这只能是"减少误杀"，
不能替代 P0-1/P0-2（那两条是主动保活，更可靠）。

### P0-4 后端 — orphan cleanup 判死前，若有分片则保留数据（堵死根因 F）

```python
# app/services/orphan_meeting_cleanup.py:114-119 之前插入
has_chunks = m.last_chunk_index is not None and m.last_chunk_index >= 0
if has_chunks:
    # 有音频数据 → 只标 error，但**保留 MinIO 分片**，供人工/前端重传补救
    logger.warning(f"会议 {m.id} 有 {m.last_chunk_index+1} 个分片, 保留 MinIO 供补救")
else:
    await chunked_upload_service.delete_chunks(m.id)
```

配套：`error_reason` 里加 `chunks_preserved=N`，前端会议详情页识别该标记时
显示"检测到未完成的录音，可尝试恢复"。

### P0-5 后端 — 心跳走独立限流 tier（堵死根因 G）

```python
# app/core/rate_limit.py 新增
_RECORDING_HEARTBEAT_PATH_RE = re.compile(
    r"^/api/v1/meetings/\d+/recording-heartbeat$"
)
# _rate_limiters 新增
"recording_heartbeat": AsyncRedisRateLimiter(max_attempts=10, window_seconds=60),
# _get_rate_limit_type 中优先判定（与 _CHUNKED_UPLOAD_PATH_RE 同级）
```

10/min 足够（前端 1/min），且**独立于全站 write 桶**，杜绝被聊天/上传挤掉。

### P1-1 前端 — iOS 强制提示"请同时开手机自带录音"（诚实降级）

在 iOS Safari 上检测到不支持 timeslice 时（启动后 5s 内 `totalChunks === 0`），
弹出明确告知：

> ⚠️ 检测到您使用的是 iOS Safari，网页录音在切换到后台时会被系统挂起，
> 可能导致录音中断或丢失。**强烈建议同时开启手机自带「语音备忘录」录音**，
> 结束后可在会议详情页上传补充。

**定位**：这是产品现实，不是技术缺陷。iOS 的限制无法绕过，只能诚实告知。
09-14 事故中用户正是自己用手机录音器补录的——说明这个需求真实存在。

### P1-2 前端 — iOS 路径的周期性 blob 快照（缓解根因 C）

既然 `ondataavailable` 不触发，可在 `useGlobalRecorder` 里加一条 iOS 专用补偿：
每 120s（避开 iOS 后台挂起频率）从 `AudioContext` 的实时采样缓冲导出一次快照，
写入 IndexedDB 的独立 store（**不能复用 chunks store**——分片合并逻辑依赖
"只有首片有容器头"的假设）。

**风险**：导出的快照不保证容器可解析（与 09-18 会议 253 的 merge 丢片同类问题）。
**建议先做可行性验证再实施，不要直接上生产。**

### P2-1 后端 — `ORPHAN_MEETING_TIMEOUT_MINUTES` **建议维持 30，不调大**

理由：见根因 D。调大不解决心跳断裂，只推迟误杀并延长真孤儿占位。
**若 P0-1/P0-2 上线后仍有个别误判**，再考虑提到 45，且必须同时把
P0-1/P0-2 作为前置条件。

### P2-2 后端 — `HEARTBEAT_TTL_SECONDS` **建议维持 300，不调大**

理由同上。当前 300s / 前端 60s 的比例（5 倍冗余）是健康的。

### P2-3 后端 — 清理任务增加"二次确认"机制

把当前的单次判死改成两段式：
- 第一次扫描命中 → 标 `error_pending`（或写 `orphan_suspect_at` 字段）+ 再等 1 个 beat 周期
- 第二个扫描仍无心跳且无新分片 → 才真判死

代价：真孤儿多存活 10 分钟。收益：消除"心跳恰好断在两个 tick 之间"的边界误杀。

### P3-1 全局 — 验证现有 P0 修复在 iOS 后台是否真的有效

**这是本次事故暴露的最大流程问题：09-15 的 P0 修复从未在 iOS 真机上验证过。**

验证方案：
1. iPhone 真机，Safari，记录开始后锁屏 10 分钟，解锁后立即查
   `redis-cli EXISTS meeting:recording:heartbeat:{id}` 应为 1
2. iPhone 真机，Safari，记录中切到微信再切回，同上
3. iPhone 真机，Safari，记录中**刷新页面**，确认心跳恢复（这是根因 A 的直接复现）
4. iPhone 真机，Safari，记录中切换到桌面端导航栏其他页面再回来
5. 桌面 Chrome，记录中刷新页面，确认 `meeting_chunks` 索引连续无空洞
6. 桌面 Chrome，长录音 >30min，确认 `skipped_alive` 生效
   （查 celery 日志：`会议 {id} 录音超时但心跳仍在`）

**建议把 3、4 两条写进 Playwright 视觉回归或新增 e2e**，作为长期回归。

### P3-2 全局 — 补齐 09-15 修复链缺失的档案

- 本文档之外，建议在 `CLAUDE.md` `## 永久铁律` 新增一条：
  > **类 20.218**：录音心跳必须绑**录音会话**（全局单例），不能绑 UI 组件——
  > 无 keep-alive 的 `<router-view>` 下，组件卸载即心跳死亡，恢复路径若不显式
  > 重启心跳则守卫永久失效。恢复/续传路径必须与新建路径一样启动心跳。
- 在 `memory/` 建 `meeting-255-ios-recording-2026-10-08.md` 归档本文要点
- 为 `useMeetingAudioUpload.js` 的三路降级补单元测试（09-15 起至今 0 覆盖）

---

## 验收清单

### 代码改动定位（Phase 2 执行时逐条对照）

- [ ] **P0-1** 新建 `web/src/composables/useRecordingHeartbeat.js`
- [ ] **P0-1** `web/src/components/AudioRecorder.vue:129-155`（删组件局部心跳）
- [ ] **P0-1** `web/src/components/AudioRecorder.vue:159-165`（`onMounted` 补 `ensureHeartbeat`）
- [ ] **P0-1** `web/src/components/AudioRecorder.vue:172`（`startHeartbeat` → `ensureHeartbeat`）
- [ ] **P0-1** `web/src/views/MeetingRoomView.vue:276` 之后补 `ensureHeartbeat(id)`
- [ ] **P0-1** `web/src/views/mobile/meeting/MobileMeetingRoom.vue:256` 之后补 `ensureHeartbeat(id)`
- [ ] **P0-1** `web/src/composables/useGlobalRecorder.js:82-133`（`start()` 内兜底）
- [ ] **P0-2** `useRecordingHeartbeat.js` 内注册 `visibilitychange` / `pageshow` / `focus`
- [ ] **P0-3** `useRecordingHeartbeat.js` 内注册 `pagehide` + `sendBeacon`
- [ ] **P0-4** `app/services/orphan_meeting_cleanup.py:114-119`（有分片则保留）
- [ ] **P0-5** `app/core/rate_limit.py`（新增 `recording_heartbeat` tier + 路径正则）
- [ ] **P1-1** `web/src/components/AudioRecorder.vue`（iOS 5s 无分片提示）
- [ ] **P3-1** iOS 真机 6 项验证，其中第 3、4 项必须进 e2e

### 纪律约束（Phase 2 必须遵守）

- [ ] **R-5 入库纪律**：`web/src/**` 源码改动 → **先 commit 源码** → 再
      `cd web && npm run build` → **再 commit dist**。
      **严禁 src+dist 原子同 commit**（会导致 timestamp 滞后一个源提交，
      该提交上重建不恒等）。详见 `CLAUDE.md` 「W100 构建确定性永久纪律」。
- [ ] 构建后 `git diff --cached -- web/dist/` 确认只有产物变化；
      禁止任何 `process.env` / `Date.now()` / `Math.random()` 进入构建产物。
- [ ] **派工 v11 锚点范式**：本次新增铁律编号建议 **类 20.218**（接 20.217），
      派工时若与其他并行 agent 撞号，按 `CLAUDE.md` 类 20.172 的 buffer 规则避让。
- [ ] **0 production code 改动铁律**：`CLAUDE.md` W68 §3 明确列了例外清单，
      本次涉及 `web/src/**`（前端末端）+ `app/services/orphan_meeting_cleanup.py`
      + `app/core/rate_limit.py`（后端基础设施）。
      **`app/core/rate_limit.py` 属于「老安全/限流基础设施」，在 W68 §3 明确禁止修改之列**
      → P0-5 必须由主指挥**显式批准为例外**，不得由执行 agent 自行拍板。
- [ ] 后端改动若涉及 schema（如 P2-3 的 `orphan_suspect_at`），
      必须串 alembic 单链，merge 后 verify 恰为 1 个 head（类 20.171 / 2026-07-24 纪律）。
- [ ] 改 `app/` 后必须 `docker compose up -d --force-recreate`（不是 `restart`）
      + 重建后 `nginx -s reload`（memory #29 / #30 实战教训）。

### Phase 3 重跑 m4a 的具体触发路径

会议 255 的音频已随内存 blob 彻底丢失（根因 C），**必须由用户用手机自带录音器补录**。
补录文件上传后的触发路径：

1. 用户在**会议 255 的详情页**（不是新建会议）找到上传入口
2. `PUT /api/v1/meetings/255/audio-chunk` 分片上传
   —— **注意：会议 255 当前 `status='error'`**，需先确认
   `audio-chunk` 端点是否接受非 `recording` 状态的会议。
   若拒绝（`useChunkedRecorder.js:127-147` 有"会议已不在录音状态→主动停录"的守卫，
   说明后端对非录音态确有校验），则 P0-4 的"保留分片 + 允许重传"必须扩展为
   **允许向 `error` 会议补传**，否则用户补录仍传不上去。
   → **这是 Phase 2 必须一并解决的阻塞点，调查阶段未验证。**
3. `POST /api/v1/meetings/255/merge-chunks?mode=auto|raw`
4. 手工把 `meetings.status` 从 `error` 改回 `processing`，
   或补一个 `POST /meetings/{id}/reprocess` 端点（`app/api/v1/admin_meetings.py`
   已有 `meeting_reprocess` 审计动作可参考）
5. Celery 后处理链自动接管：ASR → 声纹 → 摘要 → 任务提取

**Phase 3 执行前必须先验证第 2 步的状态校验行为**，否则补录会再次失败。

---

## 附：调查方法与证据可信度

| 结论 | 证据强度 |
|---|---|
| 心跳绑组件、恢复路径不启动（根因 A） | **确证**——源码逐行 + 11:09 请求指纹交叉验证 |
| 会议 255 = 0 分片（根因 B） | **确证**——`meeting_chunks` 实查 0 行 |
| IndexedDB 在 iOS 路径下无法恢复（根因 C） | **确证**——唯一写入入口 `handleChunk` 由 `ondataavailable` 驱动 |
| 无可见性/卸载感知（根因 E） | **确证**——全仓 grep 零命中 |
| 心跳走 write 桶 + 429 不审计（根因 G） | **确证**——`rate_limit.py:477-484` 提前 return |
| 修复已正确部署（非部署问题） | **确证**——容器/仓库 `diff` 一致，dist 含 `recording-heartbeat` |
| 会议 254 成功因桌面 Chrome 25 分片 | **确证**——`meeting_chunks` 实查 25 行 |
| 会议 253 是失败非成功 | **确证**——`docs/incident/2026-08-04--2026-09-18-status-snapshots.md:14-52` |
| 页面存活前 7 分钟为何仍无心跳 | **未完全解释**，见下方歧义点 |

**本调查全程只读**：未修改任何 production code、未重启服务、未删除会议 255 数据。
唯一写入是本文件。

---

## 永久铁律沉淀（Phase 2 实施后追加）

### 类 20.218：录音心跳必须绑录音会话（全局单例），不能绑 UI 组件

> **2026-10-08 会议 255 事故沉淀**。无 keep-alive 的 `<router-view>` 下，
> 组件卸载即心跳死亡，恢复/续传路径若不显式重启心跳则守卫永久失效。
> 恢复/续传路径必须与新建路径一样启动心跳。

**具体形态**（四个必须同时满足，缺一即复现事故）：

1. **心跳状态是模块级变量**，与 `useGlobalRecorder` 同寿命，**不**在
   `onUnmounted` 里停（组件卸载 ≠ 录音结束）。只有 stop-recording /
   cancel-recording / merge 完成才停心跳。
2. **meetingId 到位即刻补心跳**，且**不**用 `if (isActive())` 做前置守卫 ——
   恢复路径的时序是「先设 meetingId（此时 MediaRecorder 还没启动）→ 后 start()」，
   带守卫的 watch 必然一次都不触发（会议 255 全程 0 心跳的直接原因）。
3. **恢复路径显式调 `ensureHeartbeat(id)`**，不能依赖 `handleStart()` 兜底 ——
   父组件直接调 `useGlobalRecorder().start()` 时 `handleStart` 从未执行。
4. **切回前台立即补心跳**：`visibilitychange → visible` / `pageshow(persisted)` /
   `focus` 三个事件都要挂。iOS Safari 后台挂起后 interval 会被冻结，恢复后
   最长要等一个整周期，而这一个整周期正是误杀窗口。

**同源纪律（一并适用）**：

- **服务端兜底要保护"数据"而不只保护"判定"**：判死孤儿时若有已上传分片，
  必须保留（`error_reason` 追加 `chunks_preserved=N` 供前端识别补救），
  不能无条件 `delete_chunks` 把用户唯一的补救路径销毁掉。
- **长轮询类保活端点必须有独立限流 tier**：心跳与分片共用 `write` 桶时，
  用户顺手聊天/建任务就能把心跳挤掉；且 **429 分支必须也写审计**，
  否则"audit 无心跳 = 前端没发"这个推断会在限流场景下被彻底骗过。
- **`navigator.sendBeacon` 无法携带 Authorization header**。凡是需要 JWT 鉴权的
  端点，页面卸载通知必须用 `fetch(..., { keepalive: true })` + 显式 header，
  否则该端点在真实浏览器里 100% 401（signal 永远写不进去，且无任何错误日志）。

### 本次修复的落地对照

| 铁律条目 | 落地文件 |
|---|---|
| 心跳全局单例 + 组件卸载不停 | `web/src/composables/useRecordingHeartbeat.js`（新建） |
| meetingId 到位无条件 ensureHeartbeat | `web/src/components/AudioRecorder.vue`（watch 去 `isActive()` 守卫） |
| 恢复路径显式 ensureHeartbeat | `web/src/views/MeetingRoomView.vue`、`web/src/views/mobile/meeting/MobileMeetingRoom.vue` |
| 切前台立即补心跳 | 同 `useRecordingHeartbeat.js` 内 3 个事件监听 |
| 页面卸载通知（fetch keepalive + Bearer） | 同上 `pageHideHandler` |
| 数据保护（有分片保留 + `chunks_preserved=N`） | `app/services/orphan_meeting_cleanup.py` |
| presence 弱信号强制保留分片 | 同上（`presence_recent` 判据） |
| 心跳独立限流 tier + 429 也审计 | `app/core/rate_limit.py` |
| error 态会议可补传（chunk/reset/merge/reprocess） | `app/api/v1/meeting_recording.py` |
| presence 落库字段 | `alembic/versions/142_recording_presence_at.py` + `app/models/meeting.py` |
