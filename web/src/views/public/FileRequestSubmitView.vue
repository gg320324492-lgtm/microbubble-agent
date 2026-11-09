<!--
  FileRequestSubmitView.vue — v2 PR7 文件请求公开提交页 (无需登录)

  路由: /r/:token
  设计: 极简独立页, 不走 Element Plus 侧栏, 纯 CSS (纯净网盘 / OneDrive 文件请求 UX)

  2026-11-09: 大文件分片上传。两条通路按大小分流, **小文件通路原样保留**:
    · <  200 MB → POST /file-requests/{token}/submit (一次 multipart, 服务端整份读进内存)
    · >= 200 MB → /uploads 分片会话 (服务端 MinIO 拼接, 支持断点续传, 逐片 SHA256)
  阈值与分片细节都在 composables/usePublicChunkedUpload.js, 本页只管状态与文案。
  失败文案一律过 utils/fileRequestFailure.js —— 不在本页另写一份 (两处各写必漂移)。
-->
<template>
  <div class="file-request-submit-public">
    <div class="submit-card">
      <h1 class="submit-title">📂 {{ requestInfo?.title || '文件请求' }}</h1>

      <div v-if="loading" class="submit-state">
        加载中...
      </div>

      <div v-else-if="!requestInfo" class="submit-state error">
        <h2>文件请求不存在</h2>
        <p>该链接可能已失效，请联系发起人重新生成。</p>
      </div>

      <!-- ── 成功: 小文件通路 ─────────────────────────────────────────── -->
      <div v-else-if="submitted" class="submit-success">
        <h2>✅ 提交成功</h2>
        <p>感谢您提交文件「{{ submittedFileName }}」</p>
        <button @click="onSubmitAnother" class="submit-btn">再提交一份</button>
      </div>

      <!-- ── 成功: 分片通路 (带无损凭证) ───────────────────────────────
           ⚠️ 必须排在"链接已关闭"之前: auto_close_on_limit 会让**成功后的那一次刷新**
              把 active 变成 false, 若先判 active 就把对方刚拿到的校验凭证吞掉了 -->
      <div v-else-if="chunkDone" class="submit-success">
        <h2>✅ 上传成功</h2>
        <p>文件「{{ doneFilename }}」已收到。</p>
        <!-- 服务端合并后**实算**的 sha256 —— 对方留存前 12 位即可自证文件无损。
             整文件哈希由服务端算, 前端不算 (浏览器没有流式 SHA256, 读 10GB 会爆内存)。
             ⚠️ 重复 complete 时后端只回 {success, already_completed, file_id, sha256},
                没有 filename/size ⇒ 一律留 uploader 里的本地值兜底 -->
        <dl class="proof">
          <div class="proof-row">
            <dt>文件大小</dt>
            <dd>{{ formatSize(chunkResult.size || uploader.fileSize.value) }}</dd>
          </div>
          <div v-if="chunkResult.sha256" class="proof-row">
            <dt>校验值 (SHA256 前 12 位)</dt>
            <dd><code>{{ chunkResult.sha256.slice(0, 12) }}</code></dd>
          </div>
        </dl>
        <p v-if="chunkResult.request_closed" class="proof-note">
          这个收件链接已经<strong>收满并自动关闭</strong>了，后续不能再提交 —— 这不是出错，
          您的文件是最后一个收到的。如还需提交请联系发起人重新生成链接。
        </p>
        <p v-else-if="chunkResult.content_type_matched === false" class="proof-note warn">
          提示：文件的类型标签与扩展名不太一致，收件人已能看到文件，但预览可能受限。
          文件本身已完整收到，无需重传。
        </p>
        <button @click="onSubmitAnother" class="submit-btn">再提交一份</button>
      </div>

      <div v-else-if="!requestInfo.active" class="submit-state error">
        <h2>文件请求已关闭</h2>
        <p v-if="requestInfo.expired">链接已于 {{ formatTime(requestInfo.expires_at) }} 过期。</p>
        <p v-else>发起人已关闭此文件请求，无法再提交文件。</p>
      </div>

      <!-- ── 上传中 / 失败 / 可续传 ──────────────────────────────────── -->
      <div v-else class="submit-form">
        <div v-if="requestInfo.description" class="submit-desc">
          <p>{{ requestInfo.description }}</p>
        </div>

        <div class="submit-meta">
          <span v-if="requestInfo.allowed_extensions && requestInfo.allowed_extensions.length">
            仅限类型: {{ requestInfo.allowed_extensions.map(ext => '.' + ext).join(', ') }}
          </span>
          <span v-if="effectiveLimitMb">单文件 ≤ {{ formatMb(effectiveLimitMb) }}</span>
          <span v-if="remainTotalMb !== null">
            本链接还能收 {{ formatMb(remainTotalMb) }}（已用 {{ formatMb(requestInfo.used_mb || 0) }}）
          </span>
          <span v-if="requestInfo.expires_at">截止: {{ formatTime(requestInfo.expires_at) }}</span>
        </div>

        <!-- 分片进度卡片: 已传字节 / 片号 / 速度 / 剩余时间 -->
        <div v-if="uploadActive" class="upload-progress" role="status" aria-live="polite">
          <div class="progress-head">
            <span class="progress-title">
              {{ uploader.status.value === 'merging' ? '服务器正在合并并校验…'
                : uploader.status.value === 'preparing' ? '正在建立上传会话…'
                : '正在分片上传' }}
            </span>
            <span class="progress-pct">{{ uploader.percent.value }}%</span>
          </div>

          <div class="progress-track">
            <div class="progress-bar" :style="{ width: uploader.percent.value + '%' }" />
          </div>

          <div class="progress-grid">
            <div><b>{{ formatSize(uploader.uploadedBytes.value) }}</b> / {{ formatSize(uploader.fileSize.value) }}</div>
            <div>第 {{ uploader.currentChunk.value + 1 }} / {{ uploader.totalChunks.value }} 片</div>
            <div v-if="uploader.speedBps.value > 0">
              {{ formatSize(uploader.speedBps.value) }}/s
              <span v-if="uploader.etaSec.value > 0"> · 约剩 {{ formatDuration(uploader.etaSec.value) }}</span>
            </div>
            <div v-else>速度统计中…</div>
          </div>

          <!-- ⚠️ 逐片校验不可用时必须明说, 不能让对方以为有校验在保护 (类 20.220) -->
          <p v-if="!hashOn" class="progress-note warn">
            {{ hashOffText }}
          </p>
          <p v-else-if="hashSkipped > 0" class="progress-note warn">
            ⚠ 有 {{ hashSkipped }} 片的校验值没算出来，那几片未带逐片校验（其余不受影响）。
          </p>

          <!-- 断点有效期: 服务端会话 24h 后被清理, 必须讲清楚 —— 否则对方以为
               "随时回来接着传", 结果第二天回来只剩"会话已过期" -->
          <p v-if="sessionDeadline" class="progress-note">
            已传的部分会保留到 <b>{{ sessionDeadline }}</b>，在那之前回来都能接着传。
          </p>
          <div class="progress-actions">
            <button
              v-if="uploader.status.value === 'uploading'"
              class="btn-ghost"
              @click="uploader.pause()"
            >
              暂停
            </button>
            <button class="btn-ghost danger" @click="onAbort">放弃并删除已传部分</button>
          </div>
        </div>

        <!-- 失败卡片: 标题 / 能做什么 / 技术详情折叠 / 补救按钮 -->
        <div v-else-if="failure" class="failure-card" role="alert">
          <h3 class="failure-title">{{ failure.title }}</h3>
          <p class="failure-detail">{{ failure.detail }}</p>
          <!-- 技术详情折起来: 给发起人/我们排查用, 不占对方的注意力 -->
          <details v-if="failure.technical || rawDetail" class="failure-tech">
            <summary>技术详情（反馈给发起人时请附上）</summary>
            <p>{{ [failure.technical, rawDetail].filter(Boolean).join(' · ') }}</p>
          </details>
          <div class="failure-actions">
            <button v-if="canResumeHere" class="submit-btn" @click="onResume">继续上传</button>
            <button v-else class="submit-btn" :disabled="busy" @click="onSubmit">
              {{ uploader.status.value === 'merging' ? '合并中…' : '重试上传' }}
            </button>
            <button class="btn-ghost danger" @click="onAbort">放弃</button>
          </div>
        </div>

        <!-- 检测到断点 -->
        <div v-else-if="resumableFound" class="resume-card">
          <p>
            检测到这台设备上次也在传<b>同一个文件</b>（共
            {{ resumeChunksTotal }} 片），已经传上去的部分服务器还留着。
            点「继续上传」会先核对一遍再只补缺的片，不必从头再来。
          </p>
          <div class="failure-actions">
            <button class="submit-btn" :disabled="busy" @click="onResume">继续上传</button>
            <button class="btn-ghost" :disabled="busy" @click="onStartFresh">重新开始</button>
          </div>
        </div>

        <form @submit.prevent="onSubmit" enctype="multipart/form-data">
          <div v-if="requestInfo.require_uploader_name" class="form-row">
            <label>你的姓名 <span class="required">*</span></label>
            <input
              v-model="uploaderName"
              type="text"
              required
              maxlength="100"
              placeholder="如: 张三"
              :disabled="busy"
            />
          </div>

          <div class="form-row">
            <label>选择文件 <span class="required">*</span></label>
            <input
              ref="fileInput"
              type="file"
              required
              :accept="acceptTypes"
              :disabled="busy"
              @change="onFileChange"
            />
            <small v-if="file" class="file-info">
              {{ file.name }} · {{ formatSize(file.size) }}
              <span v-if="isBigFile" class="file-tag">将分 {{ estimateChunks }} 片上传（每片 {{ formatSize(serverChunkHint) }}）</span>
              <span v-else class="file-tag">小文件，一次传完</span>
            </small>
          </div>

          <div v-if="errorMessage" class="submit-error">{{ errorMessage }}</div>

          <button type="submit" :disabled="submitting || busy || !canSubmit" class="submit-btn">
            {{ submitLabel }}
          </button>
          <p v-if="isBigFile" class="form-hint">
            大文件会切成多片依次上传，中途断网或刷新页面后可以接着传。
            上传期间请不要关闭本页面。
          </p>
          <!-- 选完文件就讲, 不要等传到一半才发现少了道保护 —— 传 10GB 的人
               没有第二次机会重看这行字 (类 20.229: 提示要出现在决策点之前) -->
          <p v-if="isBigFile && !hashOn" class="progress-note warn">{{ hashOffText }}</p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useFileRequests } from '@/composables/useFileRequests'
import {
  usePublicChunkedUpload,
  shouldUseChunked,
  makeLocalFailure,
} from '@/composables/usePublicChunkedUpload'
import {
  FR_FAILURE_ACTION,
  FR_FAILURE_CODE,
  describeFileRequestFailure,
} from '@/utils/fileRequestFailure'
// formatSize: 共享 util (会显示到 GB, 10GB 级必须用它); parseDbDate: 后端给的是
// naive UTC 串, 直接 new Date() 会按本地时区解读差 8 小时 (类 20.221)
import { formatSize as formatBytes, parseDbDate } from '@/utils/format'

const route = useRoute()
const token = route.params.token

const { fetchPublicInfo, submitPublic } = useFileRequests()
const uploader = usePublicChunkedUpload(token)

const requestInfo = ref(null)
const loading = ref(true)
const uploaderName = ref('')
const file = ref(null)
const fileInput = ref(null)
const submitting = ref(false)
const errorMessage = ref('')
const submitted = ref(false)
const submittedFileName = ref('')
/** 结构化失败 (describeFileRequestFailure 的形状); 与 errorMessage 互斥使用 */
const failure = ref(null)

const acceptTypes = computed(() => {
  if (!requestInfo.value?.allowed_extensions?.length) return '*/*'
  return requestInfo.value.allowed_extensions.map(ext => '.' + ext).join(',')
})

// ── 门禁口径: 一律用服务端给的 max_single_file_mb ─────────────────────────────
// 它是「网盘天花板 / 收件天花板 / 本请求声明的上限」**三重取最小**的结果
// (app/services/file_request_gates.py)。前端只挑其中一个来判就会与后端不一致 ——
// 现象是"前端让选、后端 413 拒" (类 20.250 ①: 同一个闸两条路各判一遍必漂移)。
// max_file_size_mb 只在老后端没给新字段时兜底。
const effectiveLimitMb = computed(() => {
  const info = requestInfo.value || {}
  if (info.max_single_file_mb) return Number(info.max_single_file_mb)
  if (info.max_file_size_mb) return Number(info.max_file_size_mb)
  return 0
})
const remainTotalMb = computed(() => {
  const info = requestInfo.value || {}
  if (!info.max_total_mb) return null
  return Math.max(0, Number(info.max_total_mb) - Number(info.used_mb || 0))
})

const isBigFile = computed(() => !!file.value && shouldUseChunked(file.value.size))
/** 后端还没 init 时不知道真实 chunk_size; 用服务端的 max_chunk_mb 做预告, 并注明是"约" */
const serverChunkHint = computed(() => {
  const mb = Number(requestInfo.value?.max_chunk_mb) || 32
  return mb * 1024 * 1024
})
const estimateChunks = computed(() =>
  file.value ? Math.ceil(file.value.size / serverChunkHint.value) : 0
)

const uploadActive = computed(() =>
  ['preparing', 'uploading', 'merging'].includes(uploader.status.value)
)
const busy = computed(() => uploadActive.value)
const chunkDone = computed(() => uploader.status.value === 'done')
const chunkResult = computed(() => uploader.result.value || {})
const hashOn = computed(() => uploader.hashAvailable.value)
const hashSkipped = computed(() => uploader.hashSkippedChunks.value)
/**
 * 降级说明 —— 两处要用**同一句话** (选完文件时 + 进度卡片里), 所以抽成常量化的
 * computed 而不是各写一遍字面量。措辞要点: 说清"为什么不能算"、"还能不能传"、
 * "还有什么在保护", 否则对方会以为上传坏了。
 */
const hashOffText = computed(() =>
  '⚠ 本环境无法逐片校验（浏览器只在 https 或 localhost 下允许计算校验值）。' +
  '上传照常进行，服务器合并时仍会实算整份校验值，只是发现坏片会晚到最后一步。'
)
const resumableFound = computed(() =>
  !!uploader.resumableSession.value && !uploadActive.value && !failure.value
)
const rawDetail = computed(() => uploader.rawErrorDetail.value)

/** 失败卡片上该不该出现「继续上传」: 有 upload_id 说明服务端会话还在 */
const canResumeHere = computed(() =>
  !!uploader.uploadId.value &&
  failure.value?.action === FR_FAILURE_ACTION.RETRY &&
  !uploadActive.value
)

/**
 * 「检测到断点」卡片上的片数。
 * ⚠️ 这里**只显示总片数, 不显示"已传几片"** —— 本地记录里没有已传片数
 *    (那是服务端的账, 只有 GET status 才知道), 显示一个算不出来的数就是在骗人 (类 20.250 ②:
 *    "算不出来"不许渲染成 0 或 100%)。点「继续上传」时才会去问服务端还缺哪些片。
 */
const resumeChunksTotal = computed(() =>
  Number(uploader.resumableSession.value?.totalChunks || 0)
)

/**
 * 断点有效期。后端 `expires_at` 是 **naive UTC** 串 (无 Z 后缀),
 * 直接 new Date() 会按本地时区读 ⇒ 差 8 小时 (类 20.221)。
 * 一律走 parseDbDate (它给无标记的串补 Z), 再按本地时区显示。
 */
const sessionDeadline = computed(() => {
  const iso = uploader.serverExpiresAt.value || uploader.resumableSession.value?.expiresAt
  if (!iso) return ''
  const d = parseDbDate(iso)
  return d ? d.toLocaleString('zh-CN', { hour12: false }) : ''
})

/** complete 响应在"重复提交"分支里没有 filename/size, 一律回落本地记录的值 */
const doneFilename = computed(() =>
  chunkResult.value.filename || uploader.filename.value || file.value?.name || '(未命名文件)'
)

const canSubmit = computed(() => {
  if (!requestInfo.value) return false
  if (requestInfo.value.require_uploader_name && !uploaderName.value.trim()) return false
  if (!file.value) return false
  return true
})

const submitLabel = computed(() => {
  if (uploader.status.value === 'merging') return '服务器合并中…'
  if (uploadActive.value) return '上传中…'
  if (submitting.value) return '上传中…'
  return isBigFile.value ? '上传大文件' : '提交文件'
})

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = parseDbDate(iso)
    return d ? d.toLocaleString('zh-CN', { hour12: false }) : iso
  } catch { return iso }
}

/** formatSize(0) 在共享 util 里返回 '—', 进度行里要的是 0 B */
function formatSize(bytes) {
  const n = Number(bytes) || 0
  return n > 0 ? formatBytes(n) : '0 B'
}

function formatMb(mb) {
  const n = Number(mb) || 0
  return n >= 1024 ? `${(n / 1024).toFixed(1)} GB` : `${n} MB`
}

function formatDuration(sec) {
  const s = Math.max(0, Math.round(Number(sec) || 0))
  if (s < 60) return `${s} 秒`
  if (s < 3600) return `${Math.floor(s / 60)} 分 ${s % 60} 秒`
  return `${Math.floor(s / 3600)} 小时 ${Math.floor((s % 3600) / 60)} 分`
}

/**
 * 把客户端预检的拒绝也走**同一份**文案表 (伪造成对应的 HTTP 状态码),
 * 这样"文件太大"这句话在前端预检和后端 413 两个来源下说法一致。
 */
function clientFailure(status, detailText) {
  return describeFileRequestFailure({ response: { status, data: { detail: detailText } } })
}

function onFileChange(e) {
  const f = e.target.files[0]
  failure.value = null
  errorMessage.value = ''
  if (!f) return
  // 客户端检查扩展名 (服务端也查, 双重防御)
  if (requestInfo.value?.allowed_extensions?.length) {
    const ext = (f.name.split('.').pop() || '').toLowerCase()
    if (!requestInfo.value.allowed_extensions.includes(ext)) {
      failure.value = clientFailure(415, `不允许的文件类型 .${ext}`)
      clearFile()
      return
    }
  }
  // 客户端检查大小 —— 用后端同一个数 (effectiveLimitMb)
  if (effectiveLimitMb.value) {
    const maxBytes = effectiveLimitMb.value * 1024 * 1024
    if (f.size > maxBytes) {
      failure.value = clientFailure(
        413,
        `文件 ${formatSize(f.size)} 超过单文件上限 ${formatMb(effectiveLimitMb.value)}`,
      )
      clearFile()
      return
    }
  }
  // 累计总量闸: 文案里必须带"累计总量"四个字 —— utils/fileRequestFailure.js 的规则表
  // 靠它把 413 分到"链接总容量满了"而不是"你这个文件太大" (两种处置方式不同)
  if (remainTotalMb.value !== null && f.size > remainTotalMb.value * 1024 * 1024) {
    failure.value = clientFailure(
      413,
      `本链接累计总量剩余 ${formatMb(remainTotalMb.value)}，装不下 ${formatSize(f.size)}`,
    )
    clearFile()
    return
  }
  // 后端按部署配置才决定支不支持分片 (settings.FILE_REQUEST_MAX_CHUNK_MB=0 之类的
  // 异常配置会让它 false)。不支持时大文件只能走单请求通路并大概率 413 ——
  // 与其让对方白传一半再失败, 不如在选文件这一步就讲清楚。
  if (shouldUseChunked(f.size) && requestInfo.value?.chunked_supported === false) {
    failure.value = makeLocalFailure(
      FR_FAILURE_CODE.UNKNOWN, '这个链接收不了这么大的文件',
      `服务端当前没开启大文件分片通道，而这个文件有 ${formatSize(f.size)}，` +
        '一次传不完。请联系发起人开启后重试，或先把文件拆小/压缩后再传。',
      FR_FAILURE_ACTION.CONTACT,
      `chunked_supported=false 而文件大小 ${f.size} ≥ 分片阈值`,
    )
    clearFile()
    return
  }
  // 换文件 = 换一场。先把上一场的内存态清掉, 否则失败卡片上的「继续上传」会拿着
  // **上一个文件的 upload_id** 去续传新选的文件。断点本身在 localStorage 里,
  // 清内存态不会丢 (key 带 token+文件名+大小+mtime 指纹, 按新文件重新探测)。
  uploader.reset()
  file.value = f
  if (shouldUseChunked(f.size)) uploader.findResumable(f)
  else uploader.clearResumable(f)
}

function clearFile() {
  file.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function onSubmit() {
  if (!canSubmit.value || busy.value) return
  failure.value = null
  errorMessage.value = ''

  // ── 小文件: 原有单请求通路, 原样保留 ──
  if (!shouldUseChunked(file.value.size)) {
    submitting.value = true
    try {
      const formData = new FormData()
      if (requestInfo.value.require_uploader_name) {
        formData.append('uploader_name', uploaderName.value.trim())
      }
      formData.append('file', file.value)
      await submitPublic(token, formData)
      submittedFileName.value = file.value.name
      submitted.value = true
      clearFile()
    } catch (e) {
      // 走同一张文案表: 404/409/410/413/415/422 各有说法, 不再甩裸状态码
      failure.value = describeFileRequestFailure(e)
    } finally {
      submitting.value = false
    }
    return
  }

  // ── 大文件: 分片通路 ──
  const res = await uploader.upload(
    file.value,
    requestInfo.value.require_uploader_name ? uploaderName.value.trim() : undefined,
  )
  if (res.ok) {
    // 成功后重置输入, 让"再提交一份"从干净状态开始
    clearFile()
    // 刷新一次 info: 可能因为 auto_close_on_limit 已经关闭/收满
    refreshInfo()
  } else {
    failure.value = res.error || describeFileRequestFailure(null)
  }
}

async function onResume() {
  if (!file.value) {
    errorMessage.value = '请先重新选择同一个文件，再点「继续上传」。'
    return
  }
  failure.value = null
  const res = await uploader.resume(file.value)
  if (res.ok) { clearFile(); refreshInfo() }
  else failure.value = res.error || describeFileRequestFailure(null)
}

/** 「重新开始」= 放弃服务端会话 + 清断点, 然后当作一次全新上传 */
async function onStartFresh() {
  await uploader.abort(file.value)
  failure.value = null
  const res = await uploader.upload(
    file.value,
    requestInfo.value.require_uploader_name ? uploaderName.value.trim() : undefined,
  )
  if (res.ok) { clearFile(); refreshInfo() }
  else failure.value = res.error || describeFileRequestFailure(null)
}

async function onAbort() {
  // 先记下文件名: abort() 内部要用它算 localStorage 的 key
  const f = file.value
  await uploader.abort(f)
  uploader.reset()
  failure.value = null
  errorMessage.value = ''
}

function onSubmitAnother() {
  submitted.value = false
  uploader.reset()
  failure.value = null
  uploaderName.value = ''
}

async function refreshInfo() {
  try { requestInfo.value = await fetchPublicInfo(token) } catch { /* 保持旧值 */ }
}

// 上传期间关页面 = 白传, 拦一道 (浏览器原生确认框, 文案由浏览器定)
function onBeforeUnload(e) {
  if (!uploadActive.value) return undefined
  e.preventDefault()
  e.returnValue = ''
  return ''
}

onMounted(async () => {
  window.addEventListener('beforeunload', onBeforeUnload)
  try {
    requestInfo.value = await fetchPublicInfo(token)
  } catch (e) {
    requestInfo.value = null
    // 链接本身就读不出来时, 用同一张文案表说话 (404/410 的措辞不一样, 别混)
    if (e?.response?.status) failure.value = describeFileRequestFailure(e)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})
</script>

<style scoped>
.file-request-submit-public {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf3 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
}

.submit-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  padding: 40px;
  max-width: 540px;
  width: 100%;
}

.submit-title {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  margin: 0 0 24px 0;
  color: var(--color-text-primary);
}

.submit-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--color-text-secondary);
}
.submit-state.error h2 {
  color: var(--color-danger);
  font-size: var(--font-size-lg);
  margin-bottom: 8px;
}

.submit-desc {
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin-bottom: 16px;
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  line-height: 1.5;
}

.submit-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  margin-bottom: 20px;
}
.submit-meta span {
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  padding: 3px 8px;
}

.form-row {
  margin-bottom: 20px;
}
.form-row label {
  display: block;
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 6px;
}
.required {
  color: var(--color-danger);
}
.form-row input[type="text"] {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  box-sizing: border-box;
  font-family: inherit;
}
.form-row input[type="text"]:focus {
  outline: none;
  border-color: var(--color-primary);
}
.form-row input[type="file"] {
  font-size: var(--font-size-base);
  font-family: inherit;
  width: 100%;
}
.form-row input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.file-info {
  display: block;
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.file-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
}
.form-hint {
  margin: 10px 0 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.submit-btn {
  display: block;
  width: 100%;
  padding: 12px;
  background: var(--color-primary);
  color: var(--el-color-white);   /* 沿用本页原有写法; stylelint 禁硬编码 #fff */
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
  font-family: inherit;
}
.submit-btn:hover:not(:disabled) {
  background: var(--color-primary-dark);
}
.submit-btn:disabled {
  background: var(--color-border);
  cursor: not-allowed;
}

.btn-ghost {
  padding: 10px 14px;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  color: var(--color-text-regular);
  cursor: pointer;
  font-family: inherit;
}
.btn-ghost:hover {
  border-color: var(--color-primary);
  color: var(--color-primary-dark);
}
.btn-ghost.danger:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.submit-error {
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--color-danger-bg);
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-md);
  color: var(--color-danger);
  font-size: var(--font-size-sm);
}

.submit-success {
  text-align: center;
  padding: 20px;
}
.submit-success h2 {
  color: var(--color-success);
  font-size: var(--font-size-xl);
  margin-bottom: 12px;
}
.submit-success p {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  margin-bottom: 16px;
}
.submit-success .submit-btn {
  margin-top: 16px;
}

/* 无损凭证: 大小 + 服务端实算 sha256 前 12 位 */
.proof {
  margin: 0 0 16px 0;
  padding: 12px 16px;
  background: var(--color-success-bg);
  border-radius: var(--radius-md);
  text-align: left;
}
.proof-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: var(--font-size-sm);
  padding: 3px 0;
}
.proof-row dt {
  color: var(--color-text-secondary);
  margin: 0;
}
.proof-row dd {
  margin: 0;
  color: var(--color-text-primary);
}
.proof-row code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.06em;
  background: var(--color-bg-card);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}
.proof-note {
  font-size: var(--font-size-sm);
  line-height: 1.6;
  color: var(--color-text-regular);
  background: var(--color-accent-bg);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  text-align: left;
}
.proof-note.warn {
  background: var(--color-warning-bg);
}

/* 分片进度 */
.upload-progress {
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 20px;
  background: var(--color-bg-warm);
}
.progress-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
}
.progress-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
}
.progress-pct {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-primary-dark);
}
.progress-track {
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--color-border-light);
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
  transition: width 0.3s ease;
}
.progress-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 10px;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.progress-grid b {
  color: var(--color-text-primary);
  font-weight: 600;
}
.progress-note {
  margin: 10px 0 0 0;
  font-size: var(--font-size-xs);
  line-height: 1.5;
  color: var(--color-text-regular);
  background: var(--color-warning-bg);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
}
.progress-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.progress-actions .btn-ghost {
  flex: 1;
}

/* 失败卡片 (文案来自 utils/fileRequestFailure.js) */
.failure-card {
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 20px;
  background: var(--color-danger-bg);
}
.failure-title {
  margin: 0 0 8px 0;
  font-size: var(--font-size-md);
  color: var(--color-danger);
}
.failure-detail {
  margin: 0 0 10px 0;
  font-size: var(--font-size-sm);
  line-height: 1.6;
  color: var(--color-text-primary);
}
.failure-tech {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-bottom: 12px;
}
.failure-tech summary {
  cursor: pointer;
  user-select: none;
}
.failure-tech p {
  margin: 6px 0 0 0;
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.failure-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.failure-actions .submit-btn {
  width: auto;
  flex: 1;
  padding: 10px 16px;
}

.resume-card {
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  margin-bottom: 20px;
  background: var(--color-primary-bg);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  color: var(--color-text-primary);
}

@media (max-width: 640px) {
  .file-request-submit-public {
    padding: 12px;
  }
  .submit-card {
    padding: 24px 18px;
    border-radius: var(--radius-lg);
  }
  .submit-title {
    font-size: var(--font-size-xl);
  }
  .failure-actions,
  .progress-actions {
    flex-direction: column;
  }
  .failure-actions .submit-btn,
  .progress-actions .btn-ghost {
    width: 100%;
  }
}
</style>
