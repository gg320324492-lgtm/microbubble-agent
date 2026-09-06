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
      <!-- 批次⑩.39/40 (K1+折叠): 全量直出 + 按类型分组, 组头类型色淡底可点击折叠 (默认展开, 换夹重置) -->
      <template v-else>
        <template v-for="g in rfGroups" :key="'rfg-' + g.key">
          <div
            class="rf-k1" :style="{ background: `color-mix(in srgb, ${g.color} 9%, transparent)`, color: g.color }"
            role="button" tabindex="0" :aria-expanded="!rfFolded.has(g.key)"
            :title="rfFolded.has(g.key) ? '展开' : '折叠'"
            @click="toggleRfGroup(g.key)" @keydown.enter="toggleRfGroup(g.key)"
          >
            <span class="rf-k1-chev" :class="{ fold: rfFolded.has(g.key) }"><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6" /></svg></span>
            <span>{{ g.label }}</span>
            <span class="rf-k1-n mono">{{ g.items.length }}</span>
            <span class="rf-k1-sub mono">{{ rfSubtotal(g.items) }}</span>
          </div>
          <template v-if="!rfFolded.has(g.key)">
            <div
              v-for="f in g.items" :key="'rff-' + f.id"
              class="rf-item" role="button" tabindex="0"
              :title="f.file_name"
              @click="$emit('preview', f)" @keydown.enter="$emit('preview', f)"
            >
              <span class="rf-dot" :style="{ background: dotColor(f.file_name) }"></span>
              <span class="rf-nm">{{ f.file_name }}</span>
              <span class="rf-n mono">{{ fmtSize(f.file_size) }}</span>
            </div>
          </template>
        </template>
        <div v-if="!rfFiles.length" class="rf-note">该文件夹还没有文件</div>
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
        <div ref="rfStageRef" class="rf-stage" :class="'rf-k-' + previewKind" :style="{ height: stageHeight + 'px' }">
          <!-- 加载中 (媒体/PDF blob) -->
          <div v-if="stageLoading" class="rf-load"><span class="rf-spin"></span></div>
          <!-- 缩略图/图片真图 (缩略图管线就位后 office 自动升级) -->
          <template v-else-if="coverUrl">
            <img :src="coverUrl" :alt="name" class="rf-img" />
            <span v-if="previewKind === 'office'" class="rf-auto">首页缩略图 · 自动</span>
          </template>
          <!-- 图片真图 -->
          <img v-else-if="previewKind === 'image'" :src="stageUrl" :alt="name" class="rf-img" />
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
          <!-- 批次⑩.25 (用户拍板): PPT 逐页 PNG 图片浏览 (LibreOffice 管线), 弃自研 HTML 渲染 -->
          <div v-else-if="previewKind === 'ppt'" class="rf-ppt" ref="pptStageRef">
            <div v-if="pptImgStatus === 'loading' || pptImgStatus === 'converting'" class="rf-skel">
              <div class="rf-conv-t">正在把 PPT 转换为图片…</div>
              <div class="rf-conv-s">首次约 10-30 秒 · 之后打开秒出</div>
              <div class="rf-skel-ttl" style="margin-top:18px"></div>
              <div class="rf-skel-ln" style="width:78%"></div>
              <div class="rf-skel-ln" style="width:62%"></div>
            </div>
            <div v-else-if="pptImgStatus === 'error'" class="rf-conv-t" style="color:var(--color-danger)">转换失败：{{ pptImgError }}</div>
            <template v-else-if="pptImgStatus === 'ready'">
              <div class="rf-slide-wrap">
                <Transition name="rfpg" mode="out-in">
                  <img
                    :key="pptPageClamped"
                    :src="pptBlobCurrent || undefined"
                    class="rf-ppt-img"
                    @load="onImgLoad"
                  />
                </Transition>
              </div>
              <div class="rf-pill">
                <button type="button" class="rf-pill-btn" :disabled="pptPageClamped <= 1" @click="prevPptPage">‹</button>
                <span class="rf-pill-pg mono">{{ pptPageClamped }} / {{ pptImgTotalSafe }}</span>
                <button type="button" class="rf-pill-btn" :disabled="pptPageClamped >= pptImgTotalSafe" @click="nextPptPage">›</button>
                <span class="rf-pill-sep"></span>
                <button type="button" class="rf-fs-btn" :title="pptFull ? '退出放映' : '全屏放映'" @click="togglePptFull">
                  <svg viewBox="0 0 24 24"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg>
                  {{ pptFull ? '退出放映' : '全屏' }}
                </button>
              </div>
            </template>
          </div>
          <!-- 批次⑩.53 (选型 C 改): DOCX 预览 — 常态首页竖版自适应, 全屏才出缩略图侧栏 -->
          <div v-else-if="previewKind === 'docx'" class="rf-ppt" ref="docxStageRef">
            <div v-if="docxImgStatus === 'loading' || docxImgStatus === 'converting'" class="rf-skel">
              <div class="rf-conv-t">正在把 DOCX 转换为可预览格式…</div>
              <div class="rf-conv-s">首次约 10-30 秒 · 之后打开秒出</div>
              <div class="rf-skel-ttl" style="margin-top:18px"></div>
              <div class="rf-skel-ln" style="width:78%"></div>
              <div class="rf-skel-ln" style="width:62%"></div>
            </div>
            <div v-else-if="docxImgStatus === 'error'" class="rf-conv-t" style="color:var(--color-danger)">转换失败：{{ docxImgError }}</div>
            <template v-else-if="docxImgStatus === 'ready'">
              <div class="docx-fs-wrap" :class="{ fs: pptFull }">
                <div v-if="pptFull" class="docx-thumbs">
                  <img
                    v-for="t in docxThumbItems" :key="'dt' + t.i"
                    :src="t.url"
                    class="docx-thumb"
                    :class="{ on: t.i === docxPageClamped }"
                    @click="docxPage = t.i"
                  />
                </div>
                <div class="docx-main">
                  <div class="rf-slide-wrap">
                    <Transition name="rfpg" mode="out-in">
                      <img
                        :key="docxPageClamped"
                        :src="docxBlobCurrent || undefined"
                        class="rf-ppt-img"
                        @load="onDocxImgLoad"
                      />
                    </Transition>
                  </div>
                  <div class="rf-pill rf-pill-docx">
                    <button type="button" class="rf-pill-btn" :disabled="docxPageClamped <= 1" @click="prevDocxPage">‹</button>
                    <span class="rf-pill-pg mono">{{ docxPageClamped }} / {{ docxImgTotalSafe }}</span>
                    <button type="button" class="rf-pill-btn" :disabled="docxPageClamped >= docxImgTotalSafe" @click="nextDocxPage">›</button>
                    <span class="rf-pill-sep"></span>
                    <button type="button" class="rf-fs-btn" :title="pptFull ? '退出放映' : '全屏阅读'" @click="toggleDocxFull">
                      <svg viewBox="0 0 24 24"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg>
                      {{ pptFull ? '退出放映' : '全屏阅读' }}
                    </button>
                  </div>
                </div>
              </div>
            </template>
          </div>
          <!-- 兜底占位 -->
          <div v-else class="rail-cover-ph" :style="{ borderColor: typeColor }">
            <span class="rail-cover-abbr">{{ typeAbbr }}</span>
            <span class="rail-cover-hint">{{ thumbnailHint }}</span>
          </div>
        </div>
        <h3 class="rail-name" :title="name">{{ name }}<span v-if="(previewKind === 'ppt' || previewKind === 'docx') && (pptImgStatus === 'ready' || docxImgStatus === 'ready')" class="rf-page-cnt">{{ (previewKind === 'ppt' ? pptPageClamped : docxPageClamped) }} / {{ (previewKind === 'ppt' ? pptImgTotalSafe : docxImgTotalSafe) }} 页</span></h3>
        <!-- 批次⑩.37 (用户选型 B): ppt 时首排三键 上一页·全屏放映·下一页, 悬浮胶囊退役 (仅全屏态保留) -->
        <div class="rail-actions" :class="{ 'rail-actions--pager': previewKind === 'ppt' || previewKind === 'docx' }">
          <template v-if="previewKind === 'ppt' || previewKind === 'docx'">
            <button type="button" class="rail-act pg pv" :disabled="prevDisabled" title="上一页 (←)" @click="prevAnyPage">
              <span class="pg-arr"><svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6" /></svg></span><span class="pg-lbl">上一页</span>
            </button>
            <button type="button" class="rail-act pri" :title="pptFull ? '退出放映' : '全屏放映'" @click="togglePptFull">
              <span class="rf-act-fs-ico"><svg viewBox="0 0 24 24"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg></span>{{ pptFull ? '退出放映' : '全屏放映' }}
            </button>
            <button type="button" class="rail-act pg nx" :disabled="nextDisabled" title="下一页 (→)" @click="nextAnyPage">
              <span class="pg-lbl">下一页</span><span class="pg-arr"><svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6" /></svg></span>
            </button>
          </template>
          <template v-else>
            <button type="button" class="rail-act pri" :title="pptFull ? '退出放映' : '全屏放映'" @click="togglePptFull">
              <span class="rf-act-fs-ico"><svg viewBox="0 0 24 24"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg></span>{{ pptFull ? '退出放映' : '全屏放映' }}
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
          </template>
        </div>
        <!-- 批次⑩.38 (选型 A): ppt 二排 3 列, 空位消失 -->
        <div v-if="previewKind === 'ppt' || previewKind === 'docx'" class="rail-actions rail-actions--second rail-actions--pager">
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
        <div class="rail-actions rail-actions--second" :class="{ 'rail-actions--pager': previewKind === 'ppt' }">
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
import { ref, computed, reactive, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
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
  'goto-folder', 'open-versions-dialog', 'refresh',
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
/* 批次⑩.40: 组折叠态 — 声明必须在下方 watch 之前 (刷新恢复场景 watch 同步执行, 后置声明会 TDZ) */
const rfFolded = ref(new Set())
function toggleRfGroup(key) {
  const s = new Set(rfFolded.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  rfFolded.value = s
}
watch(() => props.folder?.id, async (fid) => {
  rfFiles.value = []
  rfTotal.value = 0
  rfFolded.value = new Set()
  if (fid == null) return
  const seq = ++rfSeq
  rfLoading.value = true
  try {
    const resp = await axios.get('/api/v1/drive/files', {
      params: { folder_id: fid, view: 'team', page: 1, page_size: 100, sort_by: 'created_at', sort_order: 'desc' },
    })
    if (seq !== rfSeq) return  // 已切到别的文件夹, 丢弃过期响应
    rfFiles.value = resp.data.items || []
    rfTotal.value = resp.data.total || 0
  } catch { /* 预览拉取失败静默, 空态兜底 */ }
  finally { if (seq === rfSeq) rfLoading.value = false }
}, { immediate: true })

const RF_DOT = { pdf: 'var(--color-file-pdf)', doc: 'var(--color-file-doc)', docx: 'var(--color-file-doc)', ppt: 'var(--color-warning)', pptx: 'var(--color-warning)', xls: 'var(--color-file-excel)', xlsx: 'var(--color-file-excel)', csv: 'var(--color-file-excel)', png: 'var(--color-file-image)', jpg: 'var(--color-file-image)', jpeg: 'var(--color-file-image)', mp4: 'var(--color-file-video)', mov: 'var(--color-file-video)', m4a: 'var(--color-warning)', mp3: 'var(--color-warning)' }

/* 批次⑩.39 (K1): 文件夹文件按类型分组 (组序固定, 组内保持服务端时间倒序) */
const RF_TYPE_GROUPS = [
  { key: 'ppt', label: 'PPT 演示文稿', color: 'var(--color-warning)', exts: ['ppt', 'pptx', 'pps', 'ppsx'] },
  { key: 'doc', label: 'Word 文档', color: 'var(--color-file-doc)', exts: ['doc', 'docx'] },
  { key: 'xls', label: 'Excel 表格', color: 'var(--color-file-excel)', exts: ['xls', 'xlsx', 'csv'] },
  { key: 'pdf', label: 'PDF 文档', color: 'var(--color-file-pdf)', exts: ['pdf'] },
  { key: 'img', label: '图片', color: 'var(--color-file-image)', exts: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'heic'] },
  { key: 'video', label: '视频', color: 'var(--color-file-video)', exts: ['mp4', 'mov', 'avi', 'mkv', 'webm'] },
  { key: 'audio', label: '音频', color: 'var(--color-warning)', exts: ['mp3', 'm4a', 'wav', 'flac', 'aac', 'ogg'] },
]
const rfGroups = computed(() => {
  const buckets = new Map()
  const other = []
  for (const f of rfFiles.value) {
    const ext = (f.file_name || '').split('.').pop().toLowerCase()
    const g = RF_TYPE_GROUPS.find(t => t.exts.includes(ext))
    if (g) {
      if (!buckets.has(g.key)) buckets.set(g.key, { ...g, items: [] })
      buckets.get(g.key).items.push(f)
    } else {
      other.push(f)
    }
  }
  const list = RF_TYPE_GROUPS.filter(t => buckets.has(t.key)).map(t => buckets.get(t.key))
  if (other.length) list.push({ key: 'other', label: '其他文件', color: 'var(--color-text-placeholder)', items: other })
  return list
})
function rfSubtotal(items) {
  return fmtSize(items.reduce((s, f) => s + (f.file_size || 0), 0))
}
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
  if (['doc', 'docx'].includes(e)) return 'docx'   // 批次⑩.53: LibreOffice 管线预览
  if (['ppt', 'pptx', 'xls', 'xlsx'].includes(e)) return 'office'
  return 'none'
})
// 舞台高度: 文档 470 (A4) / 视频 189 (16:9) / 音频 130 / 图片 220 / 文本 300 / Office 220
const stageHeight = computed(() => {
  // 批次⑩.27: PPT 舞台高度跟随页图比例 (304 宽 × 16:9 ≈ 171px) — 横向长方形正好贴合
  if (previewKind.value === 'ppt') {
    const nat = pptImgNat.value
    return nat ? Math.round(304 * nat.h / nat.w) : Math.round(304 * 9 / 16)
  }
  if (previewKind.value === 'docx') {
    const nat = docxImgNat.value
    // 批次⑩.53: 竖版 A4 贴合 — 首页图自然比例未知前用 A4 竖比 (210:297)
    return nat ? Math.round(304 * nat.h / nat.w) : Math.round(304 * 297 / 210)
  }
  return { image: 220, video: 189, audio: 130, pdf: 470, text: 300, office: 220 }[previewKind.value] || 168
})

/* 媒体/PDF blob 流 (带鉴权 axios → objectURL; 换文件/卸载即 revoke) */
const stageUrl = ref(null)
const stageLoading = ref(false)
let stageSeq = 0
async function loadStageBlob() {
  const seq = ++stageSeq
  if (stageUrl.value) { URL.revokeObjectURL(stageUrl.value); stageUrl.value = null }
  const kind = previewKind.value
  if (!props.file || !['video', 'audio', 'pdf', 'image'].includes(kind)) { stageLoading.value = false; return }
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

/* ---- 批次⑩.25 (用户拍板): PPT 逐页 PNG 图片浏览 (后端 LibreOffice 管线) ---- */
const pptImgStatus = ref('idle')   // idle | loading | converting | ready | error
const pptImgError = ref('')
const pptImgUrls = ref([])
const pptImgTotal = ref(0)
const pptPage = ref(1)
const pptImgNat = ref(null)        // 首页图片原始尺寸 {w,h}
let pptPollTimer = null
let pptPollSeq = 0
const pptImgTotalSafe = computed(() => Math.max(1, pptImgTotal.value))
const pptPageClamped = computed(() => Math.min(Math.max(pptPage.value, 1), Math.max(1, pptImgTotal.value)))
function nextPptPage() { if (pptPage.value < pptImgTotal.value) pptPage.value++ }
function prevPptPage() { if (pptPage.value > 1) pptPage.value-- }
function onImgLoad(ev) {
  const img = ev.target
  if (img?.naturalWidth) pptImgNat.value = { w: img.naturalWidth, h: img.naturalHeight }
}

/* 页图带 Bearer 头经 axios 取 blob → objectURL; 预取当前±1 页 */
const pptBlobMap = reactive({})
const pptBlobCurrent = ref(null)
let blobSeq = 0
async function ensurePageBlob(fid, pageIdx) {
  if (fid == null || pptBlobMap[pageIdx]) return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${fid}/pptx-pages/img-${pageIdx}`, { responseType: 'blob' })
    pptBlobMap[pageIdx] = URL.createObjectURL(resp.data)
  } catch { /* 加载失败静默 */ }
}
async function refreshPptBlobs() {
  const fid = props.file?.id
  // 批次⑩.56 守卫: 非 ppt 或转换未就绪时绝不预取页图 (避免 404 刷屏)
  if (fid == null || previewKind.value !== 'ppt' || pptImgStatus.value !== 'ready') { pptBlobCurrent.value = null; return }
  const seq = ++blobSeq
  const p = pptPageClamped.value
  await ensurePageBlob(fid, p)
  if (p < pptImgTotalSafe.value) await ensurePageBlob(fid, p + 1)  // 预取下一页 (有边界)
  if (seq !== blobSeq) return
  pptBlobCurrent.value = pptBlobMap[p] || null
}
watch([() => props.file?.id, previewKind], ([fid]) => {
  if (fid != null) revokePptBlobs()  // 换文件清旧 blob
})
watch([() => props.file?.id, previewKind, pptPageClamped, pptImgStatus], refreshPptBlobs, { immediate: true })

function stopPptPoll() { if (pptPollTimer) { clearTimeout(pptPollTimer); pptPollTimer = null } }
function startPptPoll(fid) {
  stopPptPoll()
  const seq = ++pptPollSeq
  const tick = async () => {
    if (seq !== pptPollSeq) return
    try {
      const resp = await axios.get(`/api/v1/drive/files/${fid}/pptx-pages`)
      const st = resp.data?.status
      window.__pptPoll = { status: st, total: resp.data?.total, n: (resp.data?.pages || []).length, t: Date.now() }
      if (st === 'ready') {
        pptImgStatus.value = 'ready'
        pptImgUrls.value = resp.data.pages || []
        pptImgTotal.value = resp.data.total || (resp.data.pages || []).length
        return
      }
      if (st === 'error') {
        pptImgStatus.value = 'error'
        pptImgError.value = resp.data?.message || '转换失败'
        return
      }
      pptPollTimer = setTimeout(tick, 2000)
    } catch {
      pptPollTimer = setTimeout(tick, 2500)
    }
  }
  tick()
}
watch([() => props.file?.id, previewKind], ([fid, kind]) => {
  stopPptPoll()
  pptPage.value = 1
  pptImgUrls.value = []
  pptImgNat.value = null
  if (kind === 'ppt' && fid != null) {
    pptImgStatus.value = 'loading'
    startPptPoll(fid)
  } else {
    pptImgStatus.value = 'idle'
  }
}, { immediate: true })
function revokePptBlobs() {
  for (const k of Object.keys(pptBlobMap)) { try { URL.revokeObjectURL(pptBlobMap[k]) } catch {} delete pptBlobMap[k] }
  pptBlobCurrent.value = null
}
onBeforeUnmount(() => { stopPptPoll(); pptPollSeq++; revokePptBlobs() })

/* ---- 批次⑩.53: DOCX 预览 (LibreOffice 管线复用, 常态首页竖版 / 全屏缩略图) ---- */
const docxImgStatus = ref('idle')
const docxImgError = ref('')
const docxImgUrls = ref([])
const docxImgTotal = ref(0)
const docxPage = ref(1)
const docxImgNat = ref(null)
let docxPollTimer = null
let docxPollSeq = 0
const docxImgTotalSafe = computed(() => Math.max(1, docxImgTotal.value))
const docxPageClamped = computed(() => Math.min(Math.max(docxPage.value, 1), Math.max(1, docxImgTotal.value)))
function nextDocxPage() { if (docxPage.value < docxImgTotal.value) docxPage.value++ }
function prevDocxPage() { if (docxPage.value > 1) docxPage.value-- }
function onDocxImgLoad(ev) {
  const img = ev.target
  if (img?.naturalWidth) docxImgNat.value = { w: img.naturalWidth, h: img.naturalHeight }
}
const docxBlobMap = reactive({})
const docxBlobCurrent = ref(null)
let docxBlobSeq = 0
function docxThumbUrl(i) {
  return docxBlobMap[i] || ''
}
async function ensureDocxBlob(fid, pageIdx) {
  if (fid == null || docxBlobMap[pageIdx]) return
  try {
    const resp = await axios.get('/api/v1/drive/files/' + fid + '/docx-pages/img-' + pageIdx, { responseType: 'blob' })
    docxBlobMap[pageIdx] = URL.createObjectURL(resp.data)
  } catch { /* 静默 */ }
}
async function refreshDocxBlobs() {
  const fid = props.file?.id
  // 批次⑩.56 守卫: 非 docx 或转换未就绪时绝不预取页图
  if (fid == null || previewKind.value !== 'docx' || docxImgStatus.value !== 'ready') { docxBlobCurrent.value = null; return }
  const seq = ++docxBlobSeq
  const pg = docxPageClamped.value
  await ensureDocxBlob(fid, pg)
  if (pg < docxImgTotalSafe.value) await ensureDocxBlob(fid, pg + 1)
  if (seq !== docxBlobSeq) return
  docxBlobCurrent.value = docxBlobMap[pg] || null
}
watch([() => props.file?.id, previewKind, docxPageClamped, docxImgStatus], refreshDocxBlobs, { immediate: true })

let docxAllSeq = 0
async function ensureAllDocxBlobs(fid) {
  if (fid == null) return
  const seq = ++docxAllSeq
  for (let i = 1; i <= docxImgTotalSafe.value; i++) {
    if (seq !== docxAllSeq) return
    await ensureDocxBlob(fid, i)
    await new Promise(r => setTimeout(r, 0))
  }
}
function stopDocxPoll() { if (docxPollTimer) { clearTimeout(docxPollTimer); docxPollTimer = null } }
function startDocxPoll(fid) {
  stopDocxPoll()
  const seq = ++docxPollSeq
  const tick = async () => {
    if (seq !== docxPollSeq) return
    try {
      const resp = await axios.get('/api/v1/drive/files/' + fid + '/docx-pages')
      const st = resp.data?.status
      if (st === 'ready') {
        docxImgStatus.value = 'ready'
        docxImgUrls.value = resp.data.pages || []
        docxImgTotal.value = resp.data.total || (resp.data.pages || []).length
        ensureAllDocxBlobs(fid)
      }
      if (st === 'error') {
        docxImgStatus.value = 'error'
        docxImgError.value = resp.data?.message || '转换失败'
        return
      }
      docxPollTimer = setTimeout(tick, 2000)
    } catch {
      docxPollTimer = setTimeout(tick, 2500)
    }
  }
  tick()
}
watch([() => props.file?.id, previewKind], ([fid, kind]) => {
  stopDocxPoll()
  docxPage.value = 1
  docxImgUrls.value = []
  docxImgNat.value = null
  if (kind === 'docx' && fid != null) {
    docxImgStatus.value = 'loading'
    startDocxPoll(fid)
  } else {
    docxImgStatus.value = 'idle'
  }
}, { immediate: true })
function revokeDocxBlobs() {
  for (const k of Object.keys(docxBlobMap)) { try { URL.revokeObjectURL(docxBlobMap[k]) } catch {} delete docxBlobMap[k] }
  docxBlobCurrent.value = null
}
onBeforeUnmount(() => { stopDocxPoll(); docxPollSeq++; revokeDocxBlobs() })

const prevDisabled = computed(() => previewKind.value === 'docx' ? docxPageClamped.value <= 1 : pptPageClamped.value <= 1)
const nextDisabled = computed(() => previewKind.value === 'docx' ? docxPageClamped.value >= docxImgTotalSafe.value : pptPageClamped.value >= pptImgTotalSafe.value)
function prevAnyPage() { if (previewKind.value === 'docx') prevDocxPage(); else prevPptPage() }
function nextAnyPage() { if (previewKind.value === 'docx') nextDocxPage(); else nextPptPage() }

const docxThumbItems = computed(() => {
  const arr = []
  for (let i = 1; i <= docxImgTotalSafe.value; i++) {
    const url = docxBlobMap[i]
    if (url) arr.push({ i, url })
  }
  return arr
})

const docxStageRef = ref(null)
function toggleDocxFull() {
  const el = rfStageRef.value || docxStageRef.value
  if (!el) return
  if (document.fullscreenElement) document.exitFullscreen?.()
  else el.requestFullscreen?.()
}

// 批次⑩.19: 舞台宽随全屏自适应 (rail 态 304 / 全屏按视口等比适配, 比例取页图自然尺寸)
const pptStageRef = ref(null)
const rfStageRef = ref(null)
const pptFull = ref(false)
function onFsChange() {
  pptFull.value = !!document.fullscreenElement
}
let wheelLock = 0
function onFsWheel(ev) {
  if (!pptFull.value || !document.fullscreenElement) return
  ev.preventDefault()
  const now = Date.now()
  if (now - wheelLock < 450) return
  // 批次⑩.53: docx 分支 — 同一套滚轮翻页逻辑
  const isDocx = previewKind.value === 'docx'
  const page = isDocx ? docxPage : pptPage
  const total = isDocx ? docxImgTotalSafe.value : pptImgTotalSafe.value
  if (ev.deltaY > 0 && page.value < total) { wheelLock = now; page.value++ }
  else if (ev.deltaY < 0 && page.value > 1) { wheelLock = now; page.value-- }
}
function onFsKeydown(ev) {
  if (!pptFull.value) return
  const isDocx = previewKind.value === 'docx'
  const page = isDocx ? docxPage : pptPage
  const total = isDocx ? docxImgTotalSafe.value : pptImgTotalSafe.value
  if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(ev.key)) { ev.preventDefault(); if (page.value < total) page.value++ }
  else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(ev.key)) { ev.preventDefault(); if (page.value > 1) page.value-- }
}
onMounted(() => {
  document.addEventListener('fullscreenchange', onFsChange)
  document.addEventListener('keydown', onFsKeydown)
  document.addEventListener('wheel', onFsWheel, { passive: false })
})
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFsChange)
  document.removeEventListener('keydown', onFsKeydown)
  document.removeEventListener('wheel', onFsWheel)
  if (document.fullscreenElement) document.exitFullscreen?.()
})
function togglePptFull() {
  const el = rfStageRef.value || pptStageRef.value
  if (!el) return
  if (document.fullscreenElement) document.exitFullscreen?.()
  else {
    el.requestFullscreen?.()
  }
}
const pptSlideH = computed(() => {
  if (!pptFull.value) return null
  const nat = pptImgNat.value
  if (!nat) return null
  return Math.round(stageW.value / (nat.w / nat.h))
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
.rf-slide { position: relative; box-shadow: 0 8px 26px rgba(0, 0, 0, .38); overflow: hidden; flex: none; color: #1F2A26; }
/* 玻璃胶囊翻页器 (悬浮舞台底部) */
.rf-pill {
  position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 9px;
  background: rgba(20, 40, 35, .62); border: 1px solid rgba(255, 255, 255, .14);
  border-radius: 9999px; padding: 4px 8px; backdrop-filter: blur(8px);
  /* 批次⑩.37 (选型 B): 常态退役 — 翻页/全屏已下沉为下方矩阵按钮; 胶囊仅在全屏放映态浮现 */
  display: none;
}
/* 批次⑩.53: docx 胶囊常态隐藏 (翻页走下方矩阵), 全屏放映态显示 */
.rf-pill-docx { display: none; }
:is(.rf-stage, .rf-ppt):fullscreen .rf-pill-docx { display: flex; }
/* docx 全屏: 缩略图侧栏 + 主视图 */
.docx-fs-wrap { display: flex; width: 100%; height: 100%; background: #0D1210; }
.docx-thumbs {
  width: 92px; flex: none; background: #12161A;
  overflow-y: auto; padding: 8px 6px;
  display: flex; flex-direction: column; gap: 6px;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}
.docx-thumb {
  width: 100%; display: block; cursor: pointer;
  border-radius: 2px; opacity: 0.55;
  border: 2px solid transparent; box-sizing: border-box;
}
.docx-thumb:hover { opacity: 0.85; }
.docx-thumb.on { opacity: 1; border-color: #12968B; }
.docx-main { flex: 1; min-width: 0; position: relative; display: flex; }
.docx-main .rf-slide-wrap { flex: 1; }
.rf-pill-btn {
  font: inherit; font-size: 12px; border: none; background: none;
  color: #fff; width: 22px; height: 22px; border-radius: 50%; cursor: pointer;
  display: grid; place-items: center; transition: background var(--duration-fast);
}
.rf-pill-btn:hover:not(:disabled) { background: rgba(255, 255, 255, .18); }
.rf-pill-btn:disabled { opacity: .35; cursor: default; }
.rf-pill-pg { font-family: var(--font-mono, monospace); font-size: 10px; color: rgba(255, 255, 255, .92); letter-spacing: .05em; }
.rf-badge {
  position: absolute; top: 9px; right: 9px; z-index: 3;
  font-family: var(--font-mono, monospace); font-size: 8.5px;
  color: rgba(255, 255, 255, .85); background: rgba(20, 40, 35, .5);
  padding: 2px 8px; border-radius: 9999px; backdrop-filter: blur(6px);
}
/* 画布精修 */
.rf-slide { border-radius: 3px; }
/* 翻页过渡 */
.rfpg-enter-active { transition: opacity .22s ease, transform .22s ease; }
.rfpg-leave-active { transition: opacity .16s ease, transform .16s ease; }
.rfpg-enter-from { opacity: 0; transform: translateX(12px); }
.rfpg-leave-to { opacity: 0; transform: translateX(-12px); }
/* 加载骨架屏 */
.rf-skel { height: 100%; box-sizing: border-box; padding: 26px 28px; background: var(--color-bg-card); }
.rf-skel-ttl { height: 14px; width: 55%; border-radius: 4px; background: var(--color-border); margin-bottom: 16px; animation: rf-shimmer 1.1s ease infinite alternate; }
.rf-skel-ln { height: 7px; border-radius: 4px; background: var(--color-border); margin-bottom: 11px; animation: rf-shimmer 1.1s ease infinite alternate; }
@keyframes rf-shimmer { from { opacity: .45 } to { opacity: 1 } }
/* 表格美化 */
.rf-slide table td {
  border: 1px solid #C9CFCC; padding: 2px 5px; color: var(--color-text-regular);
}
.rf-slide table tr:first-child td { font-weight: 600; background: #EDF2F0; color: var(--color-text-primary); }
/* 全屏放映态 (FIT2 沉浸基因): 舞台铺满视口, 幻灯片居中, 胶囊放大 */
.rf-ppt-img { display: block; width: 100%; height: auto; border-radius: 4px 4px 0 0; }
/* 全屏放映: 全屏根是 .rf-stage (rfStageRef, 带内联高度) 而非 .rf-ppt — 选择器必须用 :is(.rf-stage,.rf-ppt):fullscreen 才能命中 */
:is(.rf-stage, .rf-ppt):fullscreen { background: #0D1210; border: none; }
:is(.rf-stage, .rf-ppt):fullscreen .rf-slide-wrap { padding: 0; }
/* contain 适配: 元素盒撑满视口 + object-fit:contain → 等比最大化居中, 任意屏幕比例不裁切不留边 */
:is(.rf-stage, .rf-ppt):fullscreen .rf-ppt-img { width: 100%; height: 100%; object-fit: contain; border-radius: 0; }
:is(.rf-stage, .rf-ppt):fullscreen .rf-pill { display: flex; bottom: 26px; padding: 6px 12px; }
:is(.rf-stage, .rf-ppt):fullscreen .rf-pill-btn { width: 30px; height: 30px; font-size: 14px; }
:is(.rf-stage, .rf-ppt):fullscreen .rf-pill-pg { font-size: 12px; }
:is(.rf-stage, .rf-ppt):fullscreen .rf-badge { top: 18px; right: 20px; font-size: 10px; }
.rf-pill-sep { width: 1px; height: 14px; background: rgba(255, 255, 255, .25); margin: 0 2px; }
.rf-fs-btn {
  display: inline-flex; align-items: center; gap: 5px;
  border: none; background: none; color: #fff; cursor: pointer;
  font: inherit; font-size: 11px; padding: 4px 11px; border-radius: 9999px;
  white-space: nowrap;
  transition: background var(--duration-fast);
}
.rf-fs-btn svg { width: 12px; height: 12px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; flex: none; }
.rf-fs-btn:hover { background: rgba(14, 118, 110, .85); }
@media (prefers-reduced-motion: reduce) {
  .rf-stage { transition: none; }
  .rfpg-enter-active, .rfpg-leave-active { transition: none; }
  .rf-skel-ttl, .rf-skel-ln { animation: none; }
}
.rail-cover-img { width: 100%; height: 100%; object-fit: cover; }
.rail-cover-ph { display: flex; flex-direction: column; align-items: center; gap: 6px; border: 2px dashed; border-radius: var(--radius-md); padding: 22px 30px; background: transparent; }
.rail-cover-abbr { font-family: var(--font-family-mono, monospace); font-size: 22px; font-weight: 700; }
.rail-cover-hint { font-size: 11px; color: var(--color-text-secondary); }

.rail-name { margin: 12px 0 12px; font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); line-height: 1.45; word-break: break-all; }
/* 批次⑩.37 (选型 B): 页码芯片挂文件名旁 */
.rf-page-cnt {
  display: inline-flex; align-items: center; vertical-align: 2px;
  margin-left: 8px; padding: 2px 9px;
  font-family: var(--font-family-mono, monospace); font-size: 10.5px; font-weight: 500;
  color: var(--color-text-secondary); background: var(--color-bg-page, rgba(0, 0, 0, .04));
  border: 1px solid var(--color-border); border-radius: 9999px; white-space: nowrap;
}
.rail-actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.rail-actions--second { margin-top: 8px; grid-template-columns: repeat(4, 1fr); }
/* 批次⑩.37/38 (选型 B→A): ppt 三排全 3 列等宽, 横排图文; --pager 须定义在 --second 之后以覆盖列数 */
.rail-actions--pager { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.rail-actions--pager .rail-act { flex-direction: row; justify-content: center; gap: 6px; font-size: 12px; height: 46px; padding: 0 8px; }
.rail-actions--pager .rf-act-fs-ico { margin-right: 0; }
/* 对称翻页键: 3 列内网格 — 箭头钉死外缘, 文字绝对居中 (两键镜像, 与中间 pri 重心对齐); gap 归零防文字列被挤压换行 */
.rail-act.pg { display: grid; grid-template-columns: 14px 1fr 14px; align-items: center; justify-items: center; padding: 0 10px; gap: 0; }
.rail-act.pg .pg-lbl { grid-column: 2; grid-row: 1; white-space: nowrap; }
.rail-act.pg .pg-arr { display: inline-flex; grid-row: 1; color: var(--color-text-secondary); }
.rail-act.pg.pv .pg-arr { grid-column: 1; }
.rail-act.pg.nx .pg-arr { grid-column: 3; }
.rail-act.pg .pg-arr svg { width: 13px; height: 13px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.rail-act:disabled { opacity: .38; cursor: default; pointer-events: none; }
.rail-act {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  font-size: 11.5px; color: var(--color-text-regular);
  padding: 8px 4px 7px; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  background: var(--color-bg-card); transition: all var(--duration-fast) var(--ease-out, ease);
}
.rail-act span { font-size: 13px; line-height: 1; }
.rf-act-fs-ico { display: inline-flex; margin-right: 4px; }
.rf-act-fs-ico svg { width: 13px; height: 13px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
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
/* 批次⑩.39 (K1): 类型组头横条 — 类型色 9% 淡底 + 类型色文字, 数量胶囊 + 右侧小计 */
.rf-k1 {
  display: flex; align-items: center; gap: 8px;
  margin: 12px 8px 2px; padding: 8px 12px;
  border-radius: 9px; font-size: 12px; font-weight: 650;
  cursor: pointer; user-select: none;
  transition: filter var(--duration-fast);
}
.rf-k1:hover { filter: brightness(.965); }
.rf-k1:focus-visible { outline: 2px solid currentColor; outline-offset: 1px; }
/* 批次⑩.40: 折叠箭头 (folded 转 -90°) */
.rf-k1-chev { display: inline-flex; transition: transform var(--duration-fast) var(--ease-out, ease); }
.rf-k1-chev.fold { transform: rotate(-90deg); }
.rf-k1-chev svg { width: 11px; height: 11px; stroke: currentColor; fill: none; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
.rf-item:first-of-type { margin-top: 0; }
.rf-k1 .rf-k1-n {
  font-size: 10px; font-weight: 500; color: var(--color-text-secondary);
  background: var(--color-bg-card); border-radius: 9999px; padding: 1px 8px;
}
.rf-k1 .rf-k1-sub { margin-left: auto; font-size: 10px; font-weight: 500; opacity: .75; }
</style>
