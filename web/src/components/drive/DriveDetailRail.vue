<!--
  DriveDetailRail.vue — 三栏工作台右栏常驻详情 (批次③ B 版式, 2026-09-05)

  点中栏行即换档: 封面预览 + 元数据 + 全动作按钮 + 评论/版本 tab。
  动作全部 emit 给父视图 (DesktopDriveView 统一接既有 handler/dialog),
  本组件只做展示与 评论(CommentThread 复用)/版本(listVersions + 恢复 + 开 VersionHistoryDialog 对比)。
  配色全 token, 不依赖 drive-view.css 新规则。
-->
<template>
  <aside class="rail" :aria-label="'文件详情'">
    <div v-if="!file" class="rail-empty">
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
      <!-- 封面预览块 -->
      <div class="rail-hero">
        <div class="rail-cover">
          <img v-if="coverUrl" :src="coverUrl" :alt="name" class="rail-cover-img" />
          <div v-else class="rail-cover-ph" :style="{ borderColor: typeColor }">
            <span class="rail-cover-abbr" :style="{ color: typeColor }">{{ typeAbbr }}</span>
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
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import CommentThread from '@/components/drive/CommentThread.vue'
import { useDriveFiles } from '@/composables/useDriveFiles'
import { useUserStore } from '@/stores/user'

const props = defineProps({
  file: { type: Object, default: null },
  /** 未选中文件时右栏兜底展示的本目录最近条目 (父层传当前列表前几名) */
  recent: { type: Array, default: () => [] },
})
const emit = defineEmits([
  'preview', 'download', 'share', 'toggle-star', 'rename', 'move', 'delete',
  'open-detail', 'goto-folder', 'open-versions-dialog', 'refresh',
  'pick-file',
])

const { listVersions, restoreVersion: restoreApi } = useDriveFiles()
const userStore = useUserStore()
const currentUserId = computed(() => userStore.userInfo?.id ?? null)
const isFileOwner = computed(() => !!(props.file && currentUserId.value && props.file.created_by === currentUserId.value))

const name = computed(() => props.file?.file_name || props.file?.title || `文件 ${props.file?.id}`)
const versionNumber = computed(() => props.file?.version_number || 1)

const tab = ref('comments')
watch(() => props.file?.id, () => { tab.value = 'comments' })

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
</style>
