<!--
  DriveDetailRail.vue — 三栏工作台右栏常驻详情 (批次③ B 版式, 2026-09-05)

  点中栏行即换档: 封面预览 + 元数据 + 全动作按钮 + 评论/版本 tab。
  动作全部 emit 给父视图 (DesktopDriveView 统一接既有 handler/dialog),
  本组件只做展示与 评论(CommentThread 复用)/版本(listVersions + 恢复 + 开 VersionHistoryDialog 对比)。
  配色全 token, 不依赖 drive-view.css 新规则。
-->
<template>
  <aside class="rail" :aria-label="'文件详情'">
    <!-- 批次⑩.14 (用户选型 RAIL A 清单式): 文件夹预览态 — 点文件夹行显示下一级内容 -->
    <template v-if="!file && folder">
      <div class="rf-head">
        <span class="rf-ic">
          <svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
        </span>
        <div class="rf-title">
          <h3 class="rf-name" :title="folder.name">{{ folder.name }}</h3>
          <div class="rf-stats mono">
            {{ fmtSize(folder.size_bytes) }} · {{ rfTotal + (folderChildren?.length || 0) }} 项 · 最新 {{ fmtMonth(folder.latest_file_at) }}
          </div>
        </div>
      </div>
      <div class="rf-acts">
        <button type="button" @click="$emit('open-folder', folder)">打开</button>
        <button type="button" @click="$emit('share-folder', folder)">分享</button>
        <button
          type="button"
          :class="{ 'is-starred': folder.is_starred }"
          @click="$emit('toggle-star-folder', folder)"
        >{{ folder.is_starred ? '已收藏' : '收藏' }}</button>
      </div>

      <template v-if="folderChildren?.length">
        <div class="rf-grp"><span>子文件夹</span><span class="rf-n mono">{{ folderChildren.length }}</span></div>
        <div
          v-for="c in folderChildren" :key="'rfc-' + c.id"
          class="rf-item" role="button" tabindex="0"
          @click="$emit('open-folder', c)" @keydown.enter="$emit('open-folder', c)"
        >
          <svg class="rf-fic" viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
          <span class="rf-nm">{{ c.name }}</span>
          <span v-if="c.children?.length" class="rf-n mono">{{ c.children.length }}</span>
        </div>
      </template>

      <div class="rf-grp"><span>文件</span><span class="rf-n mono">{{ rfLoading ? '…' : rfTotal }}</span></div>
      <div v-if="rfLoading" class="rf-note">正在加载下一级文件…</div>
      <template v-else>
        <div
          v-for="f in rfFiles" :key="'rff-' + f.id"
          class="rf-item" role="button" tabindex="0"
          :title="f.file_name"
          @click="$emit('preview', f)" @keydown.enter="$emit('preview', f)"
        >
          <span class="rf-dot" :style="{ background: dotColor(f.file_name) }"></span>
          <span class="rf-nm">{{ f.file_name }}</span>
          <span class="rf-n mono">{{ fmtSize(f.file_size) }}</span>
        </div>
        <div v-if="!rfFiles.length" class="rf-note">该文件夹还没有文件</div>
        <button v-if="rfTotal > rfFiles.length" type="button" class="rf-more" @click="$emit('open-folder', folder)">
          显示全部 {{ rfTotal }} 个文件 ↓
        </button>
      </template>
    </template>

    <div v-else-if="!file" class="rail-empty">
      <template v-if="recent.length">
        <p class="rail-recent-cap">最近上传</p>
        <button
          v-for="f in recent.slice(0, 6)" :key="'rc-' + f.id"
          type="button" class="rail-recent-item"
          @click="$emit('pick-file', f)"
        >
          <span
            class="rail-recent-glyph"
            :style="{ color: TYPE_COLOR[extOfName(f)] || 'var(--color-text-placeholder)', background: `color-mix(in srgb, ${TYPE_COLOR[extOfName(f)] || 'var(--color-text-placeholder)'} 12%, transparent)` }"
          >{{ (extOfName(f) || 'FILE').toUpperCase().slice(0, 4) }}</span>
          <span class="rail-recent-name" :title="f.file_name || f.title">{{ f.file_name || f.title }}</span>
          <span class="rail-recent-day">{{ String(f.created_at || '').slice(5, 10) }}</span>
        </button>
        <p class="rail-empty-sub">点中栏行或上方条目，这里显示预览、评论与版本</p>
      </template>
      <template v-else>
        <p class="rail-empty-ico">▤</p>
        <p>选中一个文件，这里显示预览、信息、评论与版本。</p>
        <p class="rail-empty-sub">空格预览 · Enter 打开详情页 · Del 进回收站</p>
      </template>
    </div>
    <template v-else>
      <!-- 封面预览块 → 批次⑩.16 (用户选型 FIT 1 自适应舞台): 舞台高度随类型动画 -->
      <div class="rail-hero">
        <div class="rf-stage" :class="'rf-k-' + previewKind" :style="{ height: stageHeight + 'px' }">
          <!-- 加载中 (媒体/PDF blob) -->
          <div v-if="stageLoading" class="rf-load"><span class="rf-spin"></span></div>
          <!-- 缩略图/图片真图 (缩略图管线就位后 office 自动升级) -->
          <template v-else-if="coverUrl">
            <img :src="coverUrl" :alt="name" class="rf-img" />
            <span v-if="previewKind === 'office'" class="rf-auto">首页缩略图 · 自动</span>
          </template>
          <!-- 图片真图 -->
          <img v-else-if="previewKind === 'image'" :src="inlineUrl" :alt="name" class="rf-img" />
          <!-- 视频播放器 (blob 流) -->
          <video v-else-if="previewKind === 'video' && stageUrl" :src="stageUrl" controls playsinline class="rf-media"></video>
          <!-- 音频紧凑播放条 -->
          <div v-else-if="previewKind === 'audio'" class="rf-audio">
            <span class="rf-disc">♫</span>
            <div class="rf-audio-body">
              <div class="rf-audio-nm" :title="name">{{ name }}</div>
              <audio v-if="stageUrl" :src="stageUrl" controls class="rf-audio-ctl"></audio>
              <div v-else class="rf-audio-nm" style="opacity:.6">加载中…</div>
            </div>
          </div>
          <!-- PDF 原生查看器 (blob iframe, A4 大舞台) -->
          <iframe v-else-if="previewKind === 'pdf' && stageUrl" :src="stageUrl" class="rf-pdf" :title="name"></iframe>
          <!-- 批次⑩.17: 自研 PPT 结构化渲染 (python-pptx JSON → HTML) -->
          <div v-else-if="previewKind === 'ppt'" class="rf-ppt">
            <div v-if="pptLoading" class="rf-load"><span class="rf-spin"></span></div>
            <template v-else-if="pptData">
              <div class="rf-slide-wrap">
                <div class="rf-slide" :style="{ width: '304px', height: pptSlideH + 'px', background: currentSlideBg }" v-html="pptSlideHtml"></div>
              </div>
              <div class="rf-pgr">
                <button type="button" :disabled="pptPage <= 1" @click="pptPage--">‹</button>
                <span class="rf-pgn mono">{{ pptPage }} / {{ pptData.total }} 页</span>
                <button type="button" :disabled="pptPage >= pptData.total" @click="pptPage++">›</button>
                <span class="rf-ppttag">自研渲染</span>
              </div>
            </template>
            <div v-else class="rf-note" style="color:#cbd5d0">解析失败或文件损坏</div>
          </div>
          <!-- 文本/MD/CSV 内容渲染 (后端 /preview 1KB 截取) -->
          <pre v-else-if="previewKind === 'text'" class="rf-text">{{ textPreview || '加载中…' }}</pre>
          <!-- Office 信息卡 (无转换时) -->
          <div v-else-if="previewKind === 'office'" class="rf-office">
            <span class="rf-ext">{{ typeAbbr }}</span>
            <span class="rf-osz mono">{{ fmtSize(file.file_size) }}</span>
            <button type="button" class="rf-open" @click="$emit('preview', file)">打开大预览</button>
            <span class="rf-tip">转换管线就位后自动升级为首页图</span>
          </div>
          <!-- 兜底占位 -->
          <div v-else class="rail-cover-ph" :style="{ borderColor: typeColor }">
            <span class="rail-cover-abbr">{{ typeAbbr }}</span>
            <span class="rail-cover-hint">{{ thumbnailHint }}</span>
          </div>
        </div>
        <h3 class="rail-name" :title="name">{{ name }}</h3>
        <div class="rail-actions">
          <button type="button" class="rail-act pri" @click="$emit('preview', file)">
            <span>▣</span>预览
          </button>
          <button type="button" class="rail-act" @click="$emit('download', file)">
            <span>⬇</span>下载
          </button>
          <button type="button" class="rail-act" @click="$emit('share', file)">
            <span>◈</span>分享
          </button>
          <button
            type="button"
            class="rail-act"
            :class="{ starred: file.is_starred }"
            :aria-pressed="!!file.is_starred"
            @click="$emit('toggle-star', file)"
          >
            <span>★</span>{{ file.is_starred ? '已收藏' : '收藏' }}
          </button>
        </div>
        <div class="rail-actions rail-actions--second">
          <!-- 2026-09-05: "加入知识库"按钮移除 — 网盘文件上传后已默认自动入库 RAG -->
          <button type="button" class="rail-act wide" @click="$emit('rename', file)">✎ 重命名</button>
          <button type="button" class="rail-act wide" @click="$emit('move', file)">📂 移动</button>
          <button type="button" class="rail-act wide danger" @click="$emit('delete', file)">🗑 删除</button>
        </div>
      </div>

      <!-- 元数据 -->
      <dl class="rail-meta">
        <dt>位置</dt>
        <dd>
          <button v-if="file.folder_id" type="button" class="rail-link" @click="$emit('goto-folder', file.folder_id)">
            📂 {{ file.folder_name || ('文件夹 #' + file.folder_id) }}
          </button>
          <span v-else>团队共享盘 · 根目录</span>
        </dd>
        <dt>大小</dt><dd class="mono">{{ fmtSize(file.file_size) }}</dd>
        <dt>类型</dt><dd>{{ (file.file_type || typeAbbr) }}<template v-if="versionNumber > 1"> · v{{ versionNumber }}</template></dd>
        <dt>上传者</dt><dd>{{ file.owner_name || file.owner_username || '—' }}</dd>
        <dt>上传于</dt><dd class="mono">{{ fmtDT(file.created_at) }}</dd>
        <dt>修改于</dt><dd class="mono">{{ fmtDT(file.updated_at) }}</dd>
        <dt>下载数</dt><dd class="mono">{{ file.download_count || 0 }}</dd>
        <dt>分享</dt>
        <dd>
          <span v-if="!file.share_token">未开启</span>
          <span v-else>已开启<template v-if="file.share_expires_at"> · 至 {{ fmtDT(file.share_expires_at) }}</template></span>
        </dd>
        <dt>更多</dt>
        <dd><button type="button" class="rail-link" @click="$emit('open-detail', file)">打开完整详情页 →</button></dd>
      </dl>

      <!-- tabs: 评论 / 版本 -->
      <div class="rail-tabs" role="tablist">
        <button
          type="button" role="tab" class="rail-tab" :class="{ on: tab === 'comments' }"
          :aria-selected="tab === 'comments'" @click="tab = 'comments'"
        >评论</button>
        <button
          type="button" role="tab" class="rail-tab" :class="{ on: tab === 'versions' }"
          :aria-selected="tab === 'versions'" @click="switchVersions"
        >版本<span v-if="versions.length" class="rail-tab-n mono">{{ versions.length }}</span></button>
      </div>

      <div class="rail-pane">
        <template v-if="tab === 'comments'">
          <CommentThread
            :key="'cmt-' + file.id"
            :file-id="file.id"
            :current-user-id="currentUserId"
            :is-file-owner="isFileOwner"
          />
        </template>
        <template v-else>
          <div v-if="versionsLoading" class="rail-note">加载版本…</div>
          <div v-else-if="!versions.length" class="rail-note">
            暂无历史版本 — 重新上传同名文件会自动生成 v2。
          </div>
          <template v-else>
            <button type="button" class="rail-diff-btn" @click="$emit('open-versions-dialog', file)">
              版本管理 · 对比任意两版…
            </button>
            <ul class="rail-vers">
              <li v-for="v in versions" :key="v.id" class="rail-ver">
                <span class="rail-ver-no mono" :class="{ cur: v.version_number === (file.version_number || 1) }">v{{ v.version_number }}</span>
                <span class="rail-ver-body">
                  {{ fmtDT(v.created_at) }} · {{ v.uploaded_by_name || '—' }}
                  <small v-if="v.change_note">{{ v.change_note }}</small>
                </span>
                <button
                  v-if="v.version_number !== (file.version_number || 1)"
                  type="button" class="rail-ver-act restore"
                  @click="restoreVersion(v)"
                >恢复此版</button>
              </li>
            </ul>
          </template>
        </template>
      </div>
    </template>
  </aside>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import CommentThread from '@/components/drive/CommentThread.vue'
import { useDriveFiles } from '@/composables/useDriveFiles'
import { useUserStore } from '@/stores/user'

const props = defineProps({
  file: { type: Object, default: null },
  /** 未选中文件时右栏兜底展示的本目录最近条目 (父层传当前列表前几名) */
  recent: { type: Array, default: () => [] },
  // 批次⑩.14 (RAIL A): 文件夹预览态 — 点中栏文件夹行时显示下一级内容
  folder: { type: Object, default: null },
  /** 该文件夹的子文件夹 (父层从 folderTree 取, 已含 children 计数) */
  folderChildren: { type: Array, default: () => [] },
})
const emit = defineEmits([
  'preview', 'download', 'share', 'toggle-star', 'rename', 'move', 'delete',
  'open-detail', 'goto-folder', 'open-versions-dialog', 'refresh',
  'pick-file',
  'open-folder', 'share-folder', 'toggle-star-folder',
])

const { listVersions, restoreVersion: restoreApi } = useDriveFiles()
const userStore = useUserStore()
const currentUserId = computed(() => userStore.userInfo?.id ?? null)
const isFileOwner = computed(() => !!(props.file && currentUserId.value && props.file.created_by === currentUserId.value))

const name = computed(() => props.file?.file_name || props.file?.title || `文件 ${props.file?.id}`)
const versionNumber = computed(() => props.file?.version_number || 1)

const tab = ref('comments')
watch(() => props.file?.id, () => { tab.value = 'comments' })



/* ---- 批次⑩.14 (RAIL A): 文件夹下一级文件预览 (懒拉 8 条, 换夹即刷新) ---- */
const rfFiles = ref([])
const rfTotal = ref(0)
const rfLoading = ref(false)
let rfSeq = 0
watch(() => props.folder?.id, async (fid) => {
  rfFiles.value = []
  rfTotal.value = 0
  if (fid == null) return
  const seq = ++rfSeq
  rfLoading.value = true
  try {
    const resp = await axios.get('/api/v1/drive/files', {
      params: { folder_id: fid, view: 'team', page: 1, page_size: 8, sort_by: 'created_at', sort_order: 'desc' },
    })
    if (seq !== rfSeq) return  // 已切到别的文件夹, 丢弃过期响应
    rfFiles.value = resp.data.items || []
    rfTotal.value = resp.data.total || 0
  } catch { /* 预览拉取失败静默, 空态兜底 */ }
  finally { if (seq === rfSeq) rfLoading.value = false }
}, { immediate: true })

const RF_DOT = { pdf: 'var(--color-file-pdf)', doc: 'var(--color-file-doc)', docx: 'var(--color-file-doc)', ppt: 'var(--color-warning)', pptx: 'var(--color-warning)', xls: 'var(--color-file-excel)', xlsx: 'var(--color-file-excel)', csv: 'var(--color-file-excel)', png: 'var(--color-file-image)', jpg: 'var(--color-file-image)', jpeg: 'var(--color-file-image)', mp4: 'var(--color-file-video)', mov: 'var(--color-file-video)', m4a: 'var(--color-warning)', mp3: 'var(--color-warning)' }
function dotColor(name) {
  const ext = (name || '').split('.').pop().toLowerCase()
  return RF_DOT[ext] || 'var(--color-text-placeholder)'
}
function fmtMonth(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.getFullYear() === new Date().getFullYear()
    ? `${d.getMonth() + 1} 月`
    : `${d.getFullYear()} 年 ${d.getMonth() + 1} 月`
}

/* ---- 类型色块 ---- */
const TYPE_COLOR = {
  pdf: 'var(--color-file-pdf)', doc: 'var(--color-file-doc)', docx: 'var(--color-file-doc)',
  ppt: 'var(--color-warning)', pptx: 'var(--color-warning)',
  xls: 'var(--color-file-excel)', xlsx: 'var(--color-file-excel)', csv: 'var(--color-file-excel)',
  png: 'var(--color-file-image)', jpg: 'var(--color-file-image)', jpeg: 'var(--color-file-image)',
  gif: 'var(--color-file-image)', tiff: 'var(--color-file-image)',
  mp4: 'var(--color-danger)', mov: 'var(--color-danger)',
  m4a: 'var(--color-accent)', mp3: 'var(--color-accent)', wav: 'var(--color-accent)',
}
/** 最近条目按扩展名着色 (与 typeColor 同源映射, 纯函数供模板使用) */
function extOfName(f) {
  const n = (f.file_name || f.title || '').toLowerCase()
  const i = n.lastIndexOf('.')
  return i > 0 ? n.slice(i + 1) : ''
}
const extOf = computed(() => {
  const n = name.value.toLowerCase()
  return n.slice(n.lastIndexOf('.') + 1)
})
const typeAbbr = computed(() => (extOf.value || 'FILE').toUpperCase().slice(0, 4))
const typeColor = computed(() => TYPE_COLOR[extOf.value] || 'var(--color-text-placeholder)')
const thumbnailHint = computed(() =>
  props.file?.thumbnail_status === 'processing' ? '缩略图生成中…' : '无预览图')

/* ---- 封面 (复用 /thumbnail 签名 URL, 与 FileCard 同源; 图片类直接 inline download) ---- */
const coverUrl = ref(null)
watch(() => [props.file?.id, props.file?.thumbnail_status], async () => {
  coverUrl.value = null
  const f = props.file
  if (!f) return
  if (['png', 'jpg', 'jpeg', 'gif'].includes(extOf.value)) {
    coverUrl.value = `/api/v1/drive/files/${f.id}/download?disposition=inline`
    return
  }
  if (f.thumbnail_status === 'ready') {
    try {
      const resp = await axios.get(`/api/v1/drive/files/${f.id}/thumbnail`)
      if (resp.data?.thumbnail_url) coverUrl.value = resp.data.thumbnail_url
    } catch { /* 无缩略图走类型块 */ }
  }
}, { immediate: true })

/* ---- 批次⑩.16 (用户选型 FIT 1 自适应舞台): 类型分层真预览 ---- */
const previewKind = computed(() => {
  const e = extOf.value
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(e)) return 'image'
  if (['mp4', 'mov', 'webm'].includes(e)) return 'video'
  if (['mp3', 'm4a', 'wav'].includes(e)) return 'audio'
  if (e === 'pdf') return 'pdf'
  if (e === 'pptx') return 'ppt'   // 批次⑩.17: 自研结构化渲染 (python-pptx JSON)
  if (['md', 'txt', 'csv', 'json', 'log'].includes(e)) return 'text'
  if (['ppt', 'pptx', 'doc', 'docx', 'xls', 'xlsx'].includes(e)) return 'office'
  return 'none'
})
// 舞台高度: 文档 470 (A4) / 视频 189 (16:9) / 音频 130 / 图片 220 / 文本 300 / Office 220
const stageHeight = computed(() => ({
  image: 220, video: 189, audio: 130, pdf: 470, ppt: 400, text: 300, office: 220,
}[previewKind.value] || 168))

/* 媒体/PDF blob 流 (带鉴权 axios → objectURL; 换文件/卸载即 revoke) */
const stageUrl = ref(null)
const stageLoading = ref(false)
let stageSeq = 0
async function loadStageBlob() {
  const seq = ++stageSeq
  if (stageUrl.value) { URL.revokeObjectURL(stageUrl.value); stageUrl.value = null }
  const kind = previewKind.value
  if (!props.file || !['video', 'audio', 'pdf'].includes(kind)) { stageLoading.value = false; return }
  stageLoading.value = true
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/download?disposition=inline`, { responseType: 'blob' })
    if (seq !== stageSeq) return
    stageUrl.value = URL.createObjectURL(resp.data)
  } catch { /* 加载失败回落占位 */ }
  finally { if (seq === stageSeq) stageLoading.value = false }
}

/* 文本类 1KB 截取渲染 (后端 /preview) */
const textPreview = ref('')
async function loadTextPreview() {
  textPreview.value = ''
  if (previewKind.value !== 'text' || !props.file) return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/preview`)
    textPreview.value = resp.data?.text_preview || '(空文件或无法预览)'
  } catch { textPreview.value = '(预览加载失败)' }
}

/* ---- 批次⑩.17: 自研 PPT 结构化渲染 (python-pptx JSON → HTML) ---- */
const pptData = ref(null)
const pptPage = ref(1)
const pptLoading = ref(false)
let pptSeq = 0
watch([() => props.file?.id, previewKind], async () => {
  if (previewKind.value !== 'ppt' || !props.file) { pptData.value = null; return }
  const seq = ++pptSeq
  pptLoading.value = true
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/pptx-structure`)
    if (seq !== pptSeq) return
    pptData.value = resp.data
    pptPage.value = 1
  } catch { if (seq === pptSeq) pptData.value = null }
  finally { if (seq === pptSeq) pptLoading.value = false }
}, { immediate: true })

const escHtml = (t) => String(t ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const STAGE_W = 304  // 右栏内容区宽 (336 - 边距)

const pptSlideH = computed(() => {
  const d = pptData.value
  if (!d?.slide_w_emu) return 171
  return Math.round(STAGE_W * (d.slide_h_emu / d.slide_w_emu))
})
const currentSlideBg = computed(() => {
  const sl = pptData.value?.slides?.[pptPage.value - 1]
  return sl?.bg ? '#' + sl.bg : '#ffffff'
})
const pptSlideHtml = computed(() => {
  const d = pptData.value
  const slide = d?.slides?.[pptPage.value - 1]
  if (!slide) return ''
  const scale = STAGE_W / (d.slide_w_emu || 9144000)
  const posStyle = (sp) => `left:${(sp.x * 100).toFixed(2)}%;top:${(sp.y * 100).toFixed(2)}%;width:${(sp.w * 100).toFixed(2)}%;height:${(sp.h * 100).toFixed(2)}%;`
  let html = ''
  for (const sp of slide.shapes || []) {
    try {
      if (sp.kind === 'text') {
        const paras = (sp.paras || []).map((p) => {
          const runs = (p.runs || []).map((r) => {
            const px = Math.max(7, Math.round((r.sz || 18) * 12700 * scale))
            const st = `font-size:${px}px;` + (r.b ? 'font-weight:700;' : '') + (r.c ? `color:#${r.c};` : '')
            return `<span style="${st}">${escHtml(r.t)}</span>`
          }).join('')
          const al = p.align === 'center' ? 'center' : p.align === 'right' ? 'right' : ''
          return `<div style="margin-bottom:2px;${al ? 'text-align:' + al : ''}">${runs || '&nbsp;'}</div>`
        }).join('')
        html += `<div style="position:absolute;${posStyle(sp)}overflow:hidden;">${paras}</div>`
      } else if (sp.kind === 'image' && sp.src) {
        html += `<img src="${sp.src}" style="position:absolute;${posStyle(sp)}object-fit:contain;" />`
      } else if (sp.kind === 'table' && sp.rows) {
        const trs = sp.rows.map((r) => `<tr>${r.map((c) => `<td>${escHtml(c)}</td>`).join('')}</tr>`).join('')
        html += `<div style="position:absolute;${posStyle(sp)}overflow:hidden;background:#fff;"><table style="border-collapse:collapse;width:100%;height:100%;font-size:8px;">${trs}</table></div>`
      } else if (sp.kind === 'chart') {
        html += `<div style="position:absolute;${posStyle(sp)}display:grid;place-items:center;background:rgba(14,118,110,.06);color:var(--color-text-3,#8B968F);font-size:9px;">图表 (二期 ECharts 重绘)</div>`
      } else if (sp.kind === 'shape' && sp.color) {
        html += `<div style="position:absolute;${posStyle(sp)}background:#${sp.color};"></div>`
      }
    } catch { /* 单形状失败跳过 */ }
  }
  return html
})

const inlineUrl = computed(() =>
  props.file ? `/api/v1/drive/files/${props.file.id}/download?disposition=inline` : '')

watch([() => props.file?.id, previewKind], async () => {
  loadStageBlob()
  loadTextPreview()
}, { immediate: true })
onBeforeUnmount(() => { if (stageUrl.value) URL.revokeObjectURL(stageUrl.value) })

/* ---- 版本 ---- */
const versions = ref([])
const versionsLoading = ref(false)
async function switchVersions() {
  tab.value = 'versions'
  if (!props.file || versions.value.length || versionsLoading.value) return
  versionsLoading.value = true
  try {
    versions.value = await listVersions(props.file.id)
  } catch (e) {
    ElMessage.error(e.message || '版本列表加载失败')
  } finally {
    versionsLoading.value = false
  }
}
async function restoreVersion(v) {
  try {
    await ElMessageBox.confirm(
      `将文件恢复到 v${v.version_number} (${fmtDT(v.created_at)})？当前 v${versionNumber.value} 会保留为历史版本。`,
      '恢复版本', { type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消' },
    )
    await restoreApi(props.file.id, v.id)
    ElMessage.success(`已恢复到 v${v.version_number}`)
    versions.value = []          // 强制重拉
    emit('refresh')
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(e.message || '恢复失败')
  }
}
/* 旧版本无独立下载端点 (restore-only 设计), 版本行仅提供「恢复此版」+ 顶部对比 dialog */

/* ---- 格式化 ---- */
function fmtSize(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return n + ' B'
  const u = ['KB', 'MB', 'GB', 'TB']; let v = n / 1024, i = 0
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
  return (v >= 100 ? Math.round(v) : v.toFixed(1)) + ' ' + u[i]
}
function fmtDT(x) {
  if (!x) return '—'
  const d = new Date(x)
  if (isNaN(d)) return String(x).slice(0, 16)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
</script>

<style scoped>
.rail {
  display: flex; flex-direction: column;
  width: 100%; height: 100%; min-height: 0;
  background: var(--color-bg-card);
  border-left: 1px solid var(--color-border);
  overflow-y: auto;
}
.rail-empty { margin: auto; text-align: center; color: var(--color-text-secondary); font-size: var(--font-size-sm); padding: 30px; }
.rail-empty-ico { font-size: 30px; opacity: .4; margin-bottom: 10px; }
.rail-empty-sub { margin-top: 8px; font-size: var(--font-size-xs); opacity: .8; }
/* 未选中兜底: 最近上传 (复刻视觉稿右栏常驻感, 不留白) */
.rail-empty:has(.rail-recent-cap) { margin: 0 auto; text-align: left; width: 100%; padding: 18px 16px; }
.rail-recent-cap { font-size: 10.5px; letter-spacing: .14em; color: var(--color-text-secondary); margin-bottom: 10px; }
.rail-recent-item {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 7px 8px; margin-bottom: 4px; border-radius: var(--radius-md);
  border: 1px solid transparent; background: none; cursor: pointer; text-align: left;
  color: var(--color-text-primary); font: inherit; font-size: var(--font-size-sm);
  transition: background var(--duration-fast), border-color var(--duration-fast);
}
.rail-recent-item:hover { background: var(--color-primary-bg); border-color: var(--color-primary-border); }
.rail-recent-glyph {
  flex: none; width: 26px; height: 26px; border-radius: 6px;
  display: grid; place-items: center;
  font-family: var(--font-mono, Consolas, monospace); font-size: 8px; font-weight: 700;
}
.rail-recent-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rail-recent-day { flex: none; font-size: var(--font-size-xs); color: var(--color-text-secondary); }

.rail-hero { padding: 16px 16px 12px; border-bottom: 1px solid var(--color-border); }
/* 批次⑧ 对齐视觉稿 .d-cover: 暖纸→蜜桃渐变底 (无缩略图占位也吃同一渐变) */
.rail-cover { height: 188px; border-radius: var(--radius-lg); overflow: hidden; border: 1px solid var(--color-border); background: linear-gradient(165deg, #ffffff 0%, #FFF6EF 55%, #FFEBE2 100%); display: grid; place-items: center; }

/* ── 批次⑩.16 (FIT 1 自适应舞台): 高度随类型动画 ── */
.rf-stage {
  border-radius: var(--radius-lg); overflow: hidden;
  border: 1px solid var(--color-border); background: var(--color-bg-card);
  position: relative;
  transition: height .35s cubic-bezier(.4, 0, .2, 1);
}
.rf-k-pdf { background: #525659; }
.rf-k-video { background: #101613; }
.rf-k-audio { background: linear-gradient(165deg, #ffffff, #F1EDE4); }
.rf-k-office { background: linear-gradient(165deg, #FFF9F2 0%, #FFEDDD 100%); }
.rf-img, .rf-media, .rf-pdf { width: 100%; height: 100%; object-fit: cover; display: block; border: none; }
.rf-media { object-fit: contain; }
.rf-pdf { background: #525659; }
.rf-load { position: absolute; inset: 0; display: grid; place-items: center; }
.rf-spin {
  width: 22px; height: 22px; border-radius: 50%;
  border: 3px solid var(--color-border); border-top-color: var(--color-primary);
  animation: rf-rotate .8s linear infinite;
}
@keyframes rf-rotate { to { transform: rotate(360deg) } }
.rf-auto {
  position: absolute; right: 8px; bottom: 8px;
  font-family: var(--font-mono, monospace); font-size: 9px; color: var(--color-text-3, #8B968F);
  background: rgba(255,255,255,.78); padding: 2px 7px; border-radius: 9999px;
}
.rf-audio { padding: 12px 16px; display: flex; align-items: center; gap: 12px; height: 100%; box-sizing: border-box; }
.rf-disc {
  width: 40px; height: 40px; border-radius: 50%; flex: none;
  background: var(--gradient-cta-button); display: grid; place-items: center;
  color: #fff; font-size: 16px; box-shadow: 0 4px 12px rgba(14,118,110,.3);
}
.rf-audio-body { flex: 1; min-width: 0; }
.rf-audio-nm { font-size: 11.5px; font-weight: var(--font-weight-medium); margin-bottom: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rf-audio-ctl { width: 100%; height: 30px; }
.rf-text {
  margin: 0; width: 100%; height: 100%; box-sizing: border-box;
  padding: 12px 14px; overflow: hidden; white-space: pre-wrap; word-break: break-all;
  font-family: var(--font-mono, monospace); font-size: 10.5px; line-height: 1.65;
  color: var(--color-text-regular); background: var(--color-bg-card);
  -webkit-mask-image: linear-gradient(#000 72%, transparent); mask-image: linear-gradient(#000 72%, transparent);
}
.rf-office { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; }
.rf-ext { font-family: var(--font-mono, monospace); font-size: 20px; font-weight: 700; letter-spacing: .08em; color: var(--color-warning); }
.rf-osz { font-size: 10.5px; color: var(--color-text-secondary); }
.rf-open {
  margin-top: 3px; font: inherit; font-size: 11.5px; color: #fff;
  background: var(--gradient-cta-button); border: none; border-radius: 9999px;
  padding: 6px 16px; cursor: pointer; box-shadow: 0 2px 8px rgba(14,118,110,.3);
  transition: transform var(--duration-fast), box-shadow var(--duration-fast);
}
.rf-open:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(14,118,110,.32); }
.rf-tip { font-size: 9.5px; color: var(--color-text-placeholder); }
.rf-k-ppt { background: #525659; }
.rf-ppt { height: 100%; display: flex; flex-direction: column; box-sizing: border-box; }
.rf-slide-wrap { flex: 1; min-height: 0; display: grid; place-items: center; overflow: hidden; }
.rf-slide { position: relative; box-shadow: 0 8px 26px rgba(0, 0, 0, .38); overflow: hidden; flex: none; }
.rf-pgr {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  padding: 7px; background: var(--color-bg-card); border-top: 1px solid var(--color-border);
}
.rf-pgr button {
  font: inherit; font-size: 11px; border: 1px solid var(--color-border);
  background: var(--color-bg-card); color: var(--color-text-regular);
  border-radius: 6px; padding: 3px 10px; cursor: pointer;
}
.rf-pgr button:disabled { opacity: .45; cursor: default; }
.rf-pgn { font-size: 10px; color: var(--color-text-secondary); }
.rf-ppttag {
  font-family: var(--font-mono, monospace); font-size: 8.5px; color: var(--color-text-placeholder);
  border: 1px dashed var(--color-border); border-radius: 4px; padding: 1px 6px;
}
@media (prefers-reduced-motion: reduce) { .rf-stage { transition: none; } }
.rail-cover-img { width: 100%; height: 100%; object-fit: cover; }
.rail-cover-ph { display: flex; flex-direction: column; align-items: center; gap: 6px; border: 2px dashed; border-radius: var(--radius-md); padding: 22px 30px; background: transparent; }
.rail-cover-abbr { font-family: var(--font-family-mono, monospace); font-size: 22px; font-weight: 700; }
.rail-cover-hint { font-size: 11px; color: var(--color-text-secondary); }

.rail-name { margin: 12px 0 12px; font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); line-height: 1.45; word-break: break-all; }
.rail-actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.rail-actions--second { margin-top: 8px; grid-template-columns: repeat(4, 1fr); }
.rail-act {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  font-size: 11.5px; color: var(--color-text-regular);
  padding: 8px 4px 7px; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  background: var(--color-bg-card); transition: all var(--duration-fast) var(--ease-out, ease);
}
.rail-act span { font-size: 13px; line-height: 1; }
.rail-act:hover { border-color: var(--color-primary-border); color: var(--color-primary-dark); background: var(--color-primary-bg); }
.rail-act:active { transform: scale(.95); }
.rail-act.pri { background: var(--gradient-cta-button, var(--color-primary)); border-color: transparent; color: #fff; font-weight: var(--font-weight-semibold); }
.rail-act.pri:hover { transform: translateY(-1px); box-shadow: var(--shadow-primary); color: #fff; }
.rail-act.starred { color: var(--color-accent); border-color: var(--color-accent); background: var(--color-accent-bg, transparent); }
.rail-act.wide { flex-direction: row; gap: 6px; font-size: 12px; }
.rail-act.danger:hover { color: var(--color-danger); border-color: var(--color-danger); background: var(--color-danger-bg, #fef0f0); }

.rail-meta { display: grid; grid-template-columns: 58px 1fr; gap: 7px 10px; padding: 14px 16px; margin: 0; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-xs); }
.rail-meta dt { color: var(--color-text-secondary); }
.rail-meta dd { color: var(--color-text-regular); margin: 0; word-break: break-all; }
.rail-meta .mono { font-family: var(--font-family-mono, monospace); font-size: 11px; }
.rail-link { border: none; background: none; color: var(--color-primary-dark); font-size: inherit; padding: 0; cursor: pointer; }
.rail-link:hover { text-decoration: underline; }

.rail-tabs { display: flex; gap: 2px; padding: 10px 12px 0; }
.rail-tab { border: none; background: none; font-size: var(--font-size-sm); color: var(--color-text-secondary); padding: 8px 13px; border-radius: var(--radius-md) var(--radius-md) 0 0; border-bottom: 2px solid transparent; }
.rail-tab.on { color: var(--color-primary-dark); font-weight: var(--font-weight-semibold); background: var(--color-primary-bg); border-bottom-color: var(--color-primary); }
.rail-tab-n { margin-left: 5px; font-size: 10px; color: var(--color-text-secondary); }

.rail-pane { padding: 10px 14px 24px; flex: 1; }
.rail-note { color: var(--color-text-secondary); font-size: var(--font-size-sm); padding: 14px 4px; }
.rail-diff-btn { width: 100%; margin-bottom: 10px; padding: 8px; border: 1px solid var(--color-primary-border); border-radius: var(--radius-md); background: var(--color-primary-bg); color: var(--color-primary-dark); font-size: var(--font-size-sm); }
.rail-diff-btn:hover { box-shadow: var(--shadow-glow, none); }
.rail-vers { list-style: none; margin: 0; padding: 0; }
.rail-ver { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px dashed var(--color-border); font-size: var(--font-size-xs); }
.rail-ver-no { flex: none; font-size: 10.5px; border: 1px solid var(--color-border); border-radius: var(--radius-full, 9999px); padding: 1px 8px; color: var(--color-text-secondary); }
.rail-ver-no.cur { color: var(--color-primary-dark); border-color: var(--color-primary); font-weight: var(--font-weight-semibold); }
.rail-ver-body { flex: 1; min-width: 0; color: var(--color-text-regular); }
.rail-ver-body small { display: block; color: var(--color-text-secondary); }
.rail-ver-act { flex: none; border: 1px solid var(--color-border); background: var(--color-bg-card); border-radius: var(--radius-sm); font-size: 11px; padding: 3px 8px; color: var(--color-text-regular); }
.rail-ver-act:hover { color: var(--color-primary-dark); border-color: var(--color-primary-border); }
.rail-ver-act.restore:hover { color: var(--color-warning); border-color: var(--color-warning); }

/* ── 批次⑩.14 (RAIL A 清单式): 文件夹预览态 ── */
.rf-head { display: flex; align-items: center; gap: 12px; padding: 16px 16px 12px; border-bottom: 1px solid var(--color-border); }
.rf-ic {
  width: 38px; height: 38px; border-radius: 9px; flex: none;
  background: var(--gradient-cta-button); display: grid; place-items: center;
}
.rf-ic svg { width: 18px; height: 18px; stroke: #fff; fill: none; stroke-width: 1.7; }
.rf-title { min-width: 0; }
.rf-name { font-size: 14.5px; font-weight: var(--font-weight-semibold); word-break: break-all; }
.rf-stats { font-size: 10.5px; color: var(--color-text-secondary); margin-top: 2px; }
.rf-acts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; padding: 12px 16px; border-bottom: 1px solid var(--color-border); }
.rf-acts button {
  font: inherit; font-size: 11.5px; padding: 6px 0; border-radius: 7px;
  border: 1px solid var(--color-border); background: none; color: var(--color-text-regular);
  cursor: pointer; transition: all var(--duration-fast) var(--ease-out, ease);
}
.rf-acts button:hover { border-color: var(--color-primary-border); color: var(--color-primary-dark); background: var(--color-primary-bg); }
.rf-acts button.is-starred { color: var(--color-accent); border-color: var(--color-accent); background: var(--color-accent-bg, transparent); }
.rf-grp { display: flex; align-items: center; justify-content: space-between; padding: 11px 16px 4px; font-size: 10.5px; letter-spacing: .12em; color: var(--color-text-secondary); }
.rf-n { font-size: 10.5px; color: var(--color-text-placeholder); letter-spacing: 0; }
.rf-item {
  display: flex; align-items: center; gap: 9px; padding: 8px 16px;
  cursor: pointer; transition: background var(--duration-fast);
}
.rf-item:hover { background: var(--color-primary-bg); }
.rf-item:hover .rf-nm { color: var(--color-primary-dark); }
.rf-item .rf-nm { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: var(--font-weight-medium); transition: color var(--duration-fast); }
.rf-fic { width: 15px; height: 15px; stroke: var(--color-primary); fill: none; stroke-width: 1.7; flex: none; }
.rf-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.rf-note { padding: 10px 16px; font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.rf-more {
  display: block; width: 100%; padding: 10px; border: none; background: none;
  font: inherit; font-size: 12px; color: var(--color-primary-dark); cursor: pointer;
  transition: background var(--duration-fast);
}
.rf-more:hover { background: var(--color-primary-bg); }
</style>
