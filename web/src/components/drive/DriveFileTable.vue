<!--
  DriveFileTable.vue — 三栏工作台中间密集行表 (批次③ B 版式, 2026-09-05)

  设计 (对齐视觉稿 docs/design-proposals/drive-2026-09/style-b.html):
  - 文件夹行恒排最前, 单击进入; 文件行单击 = 选中 + 通知父层刷新右栏 (不跳页)
  - 列: checkbox | 名称(类型点+搜索态所属夹) | 大小 | 上传者 | 上传时间 | 收藏★
  - 列头 名称/大小/时间 可点排序 (sort-change 事件, 方向切换由父层做)
  - 行高固定 (comfortable 40 / compact 32) → 接 components/common/VirtualList (>60 行虚拟化)
  - 键盘: 容器可 focus, ↑↓ 移动活动行, Space 预览, Enter 打开详情, Del 删除, ⌘/Ctrl+A 全选, Shift+单击连选
  - 拖源: 行 draggable, dragstart 写 DRIVE_MOVE_MIME ids (多选拖整批)
  - 右键: emit contextmenu(file|folder, event) 由父层弹全套菜单
  - 配色全部走 variables.css token (暗色/6 主题自动跟随), 不引 drive-view.css 新全局规则
-->
<template>
  <div
    class="dft"
    :class="[`dft--${density}`, { 'dft--dragging': draggingIds }]"
    tabindex="0"
    role="grid"
    :aria-rowcount="rows.length"
    @keydown="onKeydown"
  >
    <!-- 列头 -->
    <div class="dft-head" role="row">
      <span class="dft-c dft-c--check">
        <input
          type="checkbox"
          :checked="allChecked"
          :indeterminate.prop="someChecked"
          aria-label="全选本页文件"
          @change="$emit('select-all', $event.target.checked)"
        />
      </span>
      <span
        class="dft-c dft-c--name sortable"
        role="columnheader"
        @click="$emit('sort-change', 'file_name')"
      >名称<span v-if="sortKeyOf === 'file_name'" class="dft-arr">{{ arrow }}</span></span>
      <span
        class="dft-c dft-c--size sortable"
        role="columnheader"
        @click="$emit('sort-change', 'file_size')"
      >大小<span v-if="sortKeyOf === 'file_size'" class="dft-arr">{{ arrow }}</span></span>
      <span class="dft-c dft-c--owner">上传者</span>
      <span
        class="dft-c dft-c--time sortable"
        role="columnheader"
        @click="$emit('sort-change', 'created_at')"
      >上传时间<span v-if="sortKeyOf === 'created_at'" class="dft-arr">{{ arrow }}</span></span>
      <span class="dft-c dft-c--star" title="收藏 (仅自己可见)">藏</span>
    </div>

    <!-- 表体 -->
    <div class="dft-body">
      <div v-if="loading" class="dft-states">
        <div v-for="i in 8" :key="'sk' + i" class="dft-skel" :style="{ animationDelay: i * 60 + 'ms' }">
          <span class="dft-skel-dot"></span>
          <span class="dft-skel-line" :style="{ width: 30 + ((i * 37) % 45) + '%' }"></span>
        </div>
      </div>
      <div v-else-if="loadError" class="dft-states dft-states--err">
        <p>{{ loadError }}</p>
        <button type="button" class="dft-retry" @click="$emit('retry')">重试</button>
      </div>
      <div v-else-if="!rows.length" class="dft-states dft-states--empty">
        <p class="dft-empty-ico">🗂</p>
        <p>{{ showPath ? `没有找到相关文件 — 换个更短的关键词试试` : '这个位置还没有文件 — 拖进来或点右上「上传文件」' }}</p>
      </div>
      <VirtualList
        v-else
        :items="rows"
        :item-height="rowH"
        :threshold="60"
        :container-style="{ height: '100%' }"
      >
        <template #default="{ item, index }">
          <div
            class="dft-row"
            :class="{
              'is-active': item.key === activeKey,
              'is-sel': item.kind === 'file' && selectedIdSet.has(item.data.id),
              'is-folder': item.kind === 'folder',
              'is-drop-into': dropFolderKey === item.key,
              'is-drag-src': draggingIds && draggingIds.includes(item.data?.id),
            }"
            :style="{ height: rowH + 'px' }"
            :data-row-key="item.key"
            role="row"
            :aria-selected="item.kind === 'file' && selectedIdSet.has(item.data.id)"
            :draggable="true"
            @click="onRowClick(item, index, $event)"
            @dblclick="onRowDblclick(item)"
            @contextmenu.prevent="$emit('row-contextmenu', item, $event)"
            @dragstart="onRowDragstart(item, $event)"
            @dragend="onRowDragend"
            @dragover="onRowFolderDragover(item, $event)"
            @dragleave="onRowDragleave(item)"
            @drop="onRowFolderDrop(item, $event)"
          >
            <span class="dft-c dft-c--check" @click.stop>
              <template v-if="item.kind === 'file'">
                <input
                  type="checkbox"
                  :checked="selectedIdSet.has(item.data.id)"
                  :aria-label="'选择 ' + item.label"
                  @change="$emit('select-toggle', item.data.id)"
                />
              </template>
            </span>
            <span class="dft-c dft-c--name">
              <span
                class="dft-dot"
                :style="{ background: item.kind === 'folder' ? 'var(--color-primary)' : item.color }"
                :title="item.abbr"
              ></span>
              <span class="dft-name">{{ item.label }}</span>
              <span v-if="item.kind === 'file' && showPath && item.data.folder_name" class="dft-path">
                📂 {{ item.data.folder_name }}
              </span>
              <span v-if="item.kind === 'file' && item.data.is_latest === false" class="dft-old" title="非最新版本">旧版</span>
            </span>
            <span class="dft-c dft-c--size num">{{ item.kind === 'file' ? fmtSize(item.data.file_size) : '—' }}</span>
            <span class="dft-c dft-c--owner">
              <template v-if="item.kind === 'file' && (item.data.owner_name || item.data.owner_username)">
                <span class="dft-av">{{ (item.data.owner_name || item.data.owner_username).slice(0, 1) }}</span>
                {{ item.data.owner_name || item.data.owner_username }}
              </template>
              <template v-else-if="item.kind === 'file'">—</template>
            </span>
            <span class="dft-c dft-c--time num">{{ fmtTime(item.kind === 'file' ? item.data.created_at : item.data.updated_at) }}</span>
            <span class="dft-c dft-c--star" @click.stop>
              <button
                v-if="item.kind === 'file'"
                type="button"
                class="dft-star"
                :class="{ 'on': item.data.is_starred }"
                :aria-label="item.data.is_starred ? '取消收藏' : '收藏 (仅自己可见)'"
                :aria-pressed="!!item.data.is_starred"
                @click="$emit('toggle-star', item.data)"
              >★</button>
            </span>
          </div>
        </template>
      </VirtualList>
    </div>

    <!-- 底部分页 + 计数 (表格自带, B 稿右下角 "共 23 条 · 1-8 · 3 页") -->
    <div class="dft-foot">
      <span class="dft-foot-stat num">{{ footStat }}</span>
      <span class="dft-foot-sp"></span>
      <el-pagination
        v-if="total > pageSize"
        size="small"
        layout="prev, pager, next, sizes"
        :page-sizes="[20, 50, 100, 200]"
        :total="total"
        :current-page="currentPage"
        :page-size="pageSize"
        @current-change="(p) => $emit('page-change', p)"
        @size-change="(s) => $emit('size-change', s)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, nextTick } from 'vue'
import VirtualList from '@/components/common/VirtualList.vue'
import { DRIVE_MOVE_MIME, isDriveMoveDragging, readDriveMovePayload } from '@/composables/useDriveDragMove'

const props = defineProps({
  files: { type: Array, default: () => [] },
  folders: { type: Array, default: () => [] },
  loading: Boolean,
  loadError: { type: String, default: null },
  selectedIds: { type: Array, default: () => [] },
  /** 右栏/键盘活动行 id (file.id 或 'f-'+folder.id) */
  activeKey: { type: [Number, String], default: null },
  sortBy: { type: String, default: 'created_at' },
  sortOrder: { type: String, default: 'desc' },
  /** 搜索态: 名称列内联"所属文件夹" */
  showPath: Boolean,
  density: { type: String, default: 'comfortable' }, // comfortable | compact
  total: { type: Number, default: 0 },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
})

const emit = defineEmits([
  'row-activate',      // (row|null, {shift}) → 父层更新 activeKey (+ shift 时 select-range)
  'row-open',          // 双击 folder / Enter: 进入文件夹
  'row-open-detail',   // Enter file → 详情页路由
  'row-delete',        // Del → 父层 confirm + deleteFile
  'row-preview',       // Space/双击 file → FilePreviewDialog
  'row-contextmenu',   // (row, event)
  'sort-change',       // (prop)
  'select-toggle',     // (id)
  'select-all',        // (bool)
  'select-range',      // (ids) shift 连选增量
  'toggle-star',       // (file)
  'retry',
  'page-change',
  'size-change',
  'drag-change',       // (bool) 父层据此给树挂高亮提示
  'drop-into-folder',  // ({folderId, ids}) 拖到表内文件夹行
])

const rowH = computed(() => (props.density === 'compact' ? 32 : 40))

const TYPE_META = {
  pdf:   { abbr: 'PDF',  color: 'var(--color-file-pdf, #DC3545)' },
  doc:   { abbr: 'DOC',  color: 'var(--color-file-doc, #0D6EFD)' },
  docx:  { abbr: 'DOCX', color: 'var(--color-file-doc, #0D6EFD)' },
  ppt:   { abbr: 'PPT',  color: 'var(--color-warning, #E6A23C)' },
  pptx:  { abbr: 'PPTX', color: 'var(--color-warning, #E6A23C)' },
  xls:   { abbr: 'XLS',  color: 'var(--color-file-excel, #198754)' },
  xlsx:  { abbr: 'XLSX', color: 'var(--color-file-excel, #198754)' },
  csv:   { abbr: 'CSV',  color: 'var(--color-file-excel, #198754)' },
  png:   { abbr: 'PNG',  color: 'var(--color-file-image, #9C27B0)' },
  jpg:   { abbr: 'JPG',  color: 'var(--color-file-image, #9C27B0)' },
  jpeg:  { abbr: 'JPG',  color: 'var(--color-file-image, #9C27B0)' },
  tiff:  { abbr: 'TIFF', color: 'var(--color-file-image, #9C27B0)' },
  gif:   { abbr: 'GIF',  color: 'var(--color-file-image, #9C27B0)' },
  mp4:   { abbr: 'MP4',  color: 'var(--color-danger, #F56C6C)' },
  mov:   { abbr: 'MOV',  color: 'var(--color-danger, #F56C6C)' },
  m4a:   { abbr: 'M4A',  color: 'var(--color-accent, #FFB347)' },
  mp3:   { abbr: 'MP3',  color: 'var(--color-accent, #FFB347)' },
  wav:   { abbr: 'WAV',  color: 'var(--color-accent, #FFB347)' },
  md:    { abbr: 'MD',   color: 'var(--color-info, #909399)' },
  txt:   { abbr: 'TXT',  color: 'var(--color-info, #909399)' },
  json:  { abbr: 'JSON', color: 'var(--color-info, #909399)' },
}

function metaOf(file) {
  const n = (file.file_name || file.title || '').toLowerCase()
  const ext = n.slice(n.lastIndexOf('.') + 1)
  const meta = TYPE_META[ext]
  if (meta) return meta
  return { abbr: (ext || 'FILE').toUpperCase().slice(0, 4), color: 'var(--color-text-placeholder, #C0C4CC)' }
}

// 统一行模型 (folder 行恒在前 — 与系统文件管理器一致)
const rows = computed(() => {
  const fs = (props.folders || []).map((f) => ({
    kind: 'folder',
    key: 'f-' + f.id,
    data: f,
    label: f.name,
    abbr: 'FOLDER',
    color: 'var(--color-primary)',
  }))
  const ff = (props.files || []).map((x) => {
    const m = metaOf(x)
    return { kind: 'file', key: x.id, data: x, label: x.file_name || x.title || `文件${x.id}`, abbr: m.abbr, color: m.color }
  })
  return [...fs, ...ff]
})

const selectedIdSet = computed(() => new Set(props.selectedIds))
const fileRows = computed(() => rows.value.filter((r) => r.kind === 'file'))
const allChecked = computed(() => fileRows.value.length > 0 && fileRows.value.every((r) => selectedIdSet.value.has(r.data.id)))
const someChecked = computed(() => !allChecked.value && fileRows.value.some((r) => selectedIdSet.value.has(r.data.id)))

const sortKeyOf = computed(() => props.sortBy)
const arrow = computed(() => (props.sortOrder === 'asc' ? '▲' : '▼'))

let lastClickIdx = -1

function onRowClick(row, index, ev) {
  if (row.kind === 'file' && (ev.ctrlKey || ev.metaKey)) {
    // Ctrl/⌘+单击 = 多选切换 (与 checkbox 同效)
    emit('select-toggle', row.data.id)
    return
  }
  if (row.kind === 'file' && ev.shiftKey && lastClickIdx >= 0) {
    // Shift 连选: 取上次点击行到当前行之间的全部 file ids (增量交给父层并入选择集)
    const [a, b] = [Math.min(lastClickIdx, index), Math.max(lastClickIdx, index)]
    const ids = rows.value.slice(a, b + 1).filter((r) => r.kind === 'file').map((r) => r.data.id)
    emit('select-range', ids)
    return
  }
  if (row.kind === 'file') lastClickIdx = index
  if (row.kind === 'folder') {
    emit('row-activate', row, { shift: false })
    return
  }
  emit('row-activate', row, { shift: false })
}

function onRowDblclick(row) {
  if (row.kind === 'folder') { emit('row-open', row); return }
  emit('row-preview', row.data)
}

/* ---- 键盘导航 (容器 focus 后 ↑↓ 移活动行 / Space 预览 / Enter 打开 / Del 删 / ⌘A 全选) ---- */
function onKeydown(ev) {
  const idx = rows.value.findIndex((r) => r.key === props.activeKey)
  if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
    ev.preventDefault()
    const next = ev.key === 'ArrowDown'
      ? Math.min(rows.value.length - 1, idx < 0 ? 0 : idx + 1)
      : Math.max(0, idx < 0 ? 0 : idx - 1)
    emit('row-activate', rows.value[next], { shift: !!ev.shiftKey, keyboard: true })
    scrollTo(next)
  } else if (ev.key === ' ' && idx >= 0) {
    ev.preventDefault()
    const r = rows.value[idx]
    r.kind === 'file' ? emit('row-preview', r.data) : emit('row-open', r)
  } else if (ev.key === 'Enter' && idx >= 0) {
    ev.preventDefault()
    const r = rows.value[idx]
    r.kind === 'file' ? emit('row-open-detail', r.data) : emit('row-open', r)
  } else if ((ev.key === 'Delete' || ev.key === 'Backspace') && idx >= 0 && rows.value[idx].kind === 'file') {
    ev.preventDefault()
    emit('row-delete', rows.value[idx].data)
  } else if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'a') {
    ev.preventDefault()
    emit('select-all', true)
  } else if (ev.key === 'Escape') {
    emit('select-all', false)
  }
}

function scrollTo(i) {
  nextTick(() => {
    const el = document.querySelector(`.dft [data-row-key="${CSS.escape(String(rows.value[i]?.key ?? ''))}"]`)
    el?.scrollIntoView?.({ block: 'nearest' })
  })
}

/* ---- 拖源 ---- */
const draggingIds = ref(null)
function onRowDragstart(row, ev) {
  if (row.kind !== 'file') { ev.preventDefault(); return }
  const ids = props.selectedIds.includes(row.data.id) ? [...props.selectedIds] : [row.data.id]
  draggingIds.value = ids
  ev.dataTransfer.setData(DRIVE_MOVE_MIME, JSON.stringify(ids))
  ev.dataTransfer.setData('text/plain', row.label)  // 拖到系统外的降级文案
  ev.dataTransfer.effectAllowed = 'move'
  emit('drag-change', true)
}
function onRowDragend() {
  draggingIds.value = null
  dropFolderKey.value = null
  emit('drag-change', false)
}

/* ---- 表格内文件夹行也是移动落点 (拖文件 → 夹行 → 移动进去) ---- */
const dropFolderKey = ref(null)
function onRowFolderDragover(row, ev) {
  if (row.kind !== 'folder' || !isDriveMoveDragging(ev)) return
  ev.preventDefault()
  ev.dataTransfer.dropEffect = 'move'
  dropFolderKey.value = row.key
}
function onRowDragleave(row) {
  if (dropFolderKey.value === row.key) dropFolderKey.value = null
}
function onRowFolderDrop(row, ev) {
  if (row.kind !== 'folder') return
  const ids = readDriveMovePayload(ev.dataTransfer)
  dropFolderKey.value = null
  if (!ids) return
  ev.preventDefault()
  ev.stopPropagation()
  emit('drop-into-folder', { folderId: row.data.id, ids })
}

/* ---- 格式化 ---- */
function fmtSize(bytes) {
  if (bytes == null) return '—'
  const n = Number(bytes) || 0
  if (n < 1024) return n + ' B'
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = n / 1024, u = 0
  while (v >= 1024 && u < units.length - 1) { v /= 1024; u++ }
  return v >= 100 ? Math.round(v) + ' ' + units[u] : v.toFixed(1) + ' ' + units[u]
}
function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return String(iso).slice(0, 10)
  const now = new Date()
  const p = (x) => String(x).padStart(2, '0')
  const sameYear = d.getFullYear() === now.getFullYear()
  return sameYear
    ? `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
    : `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const footStat = computed(() => {
  const n = props.total
  const start = (props.currentPage - 1) * props.pageSize + 1
  const end = Math.min(n, props.currentPage * props.pageSize)
  if (!n) return '共 0 项'
  return `共 ${n} 项 · 显示 ${start}–${end} · 第 ${props.currentPage} / ${Math.max(1, Math.ceil(n / props.pageSize))} 页`
})

defineExpose({ focus: () => nextTick(() => document.querySelector('.dft')?.focus?.()) })
</script>

<style scoped>
.dft {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  outline: none;
}
.dft:focus-visible { box-shadow: 0 0 0 2px rgba(var(--color-primary-rgb), .25); }

.dft-head, .dft-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 86px 108px 118px 34px;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
}
.dft-head {
  flex: none;
  height: 34px;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  user-select: none;
  position: sticky; top: 0; z-index: 3;
  background: var(--color-bg-card);
}
.dft-head .sortable { cursor: pointer; }
.dft-head .sortable:hover { color: var(--color-primary-dark); }
.dft-arr { font-size: 9px; margin-left: 3px; color: var(--color-primary); }

.dft-body { flex: 1; min-height: 0; }

.dft-row {
  border-bottom: 1px solid var(--color-border-light, var(--color-border));
  cursor: default;
  transition: background var(--duration-fast);
}
.dft-row:hover { background: var(--color-bg-hover, rgba(var(--color-primary-rgb), .05)); }
.dft-row.is-sel { background: var(--color-primary-bg); }
.dft-row.is-active { box-shadow: inset 0 0 0 1.5px var(--color-primary); }
.dft-row.is-active.is-sel { box-shadow: inset 0 0 0 1.5px var(--color-primary-dark); }
.dft-row.is-drag-src { opacity: .45; }
.dft-row.is-drop-into { background: var(--color-primary-bg); box-shadow: inset 0 0 0 1.5px var(--color-primary); border-radius: var(--radius-sm); }
.dft-row.is-folder .dft-name { font-weight: var(--font-weight-medium); }
.dft--compact .dft-row { font-size: var(--font-size-xs); }

.dft-c { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--font-size-sm); color: var(--color-text-regular); }
.dft-c--name { display: flex; align-items: center; gap: 8px; min-width: 0; color: var(--color-text-primary); }
.dft-c--check, .dft-c--star { display: flex; justify-content: center; }
.dft-c--owner { display: flex; align-items: center; gap: 6px; }
.num { text-align: right; font-family: var(--font-family-mono, monospace); font-size: var(--font-size-xs); }
.dft-head .num { text-align: right; }

.dft-dot { flex: none; width: 7px; height: 7px; border-radius: 50%; }
.dft-name { overflow: hidden; text-overflow: ellipsis; }
.dft-path { flex: none; font-size: 11px; color: var(--color-text-secondary); max-width: 150px; overflow: hidden; text-overflow: ellipsis; }
.dft-old { flex: none; font-size: 10px; color: var(--color-warning); border: 1px solid var(--color-warning); border-radius: var(--radius-sm); padding: 0 4px; }
.dft-av {
  flex: none; width: 18px; height: 18px; border-radius: 50%;
  background: var(--gradient-welcome-hero, linear-gradient(135deg, #FF7A5C, #FFB347));
  color: #fff; font-size: 10px; display: inline-grid; place-items: center;
}
.dft-star { border: none; background: none; font-size: 14px; line-height: 1; color: var(--color-border); padding: 2px; transition: color var(--duration-fast), transform var(--duration-fast); }
.dft-star:hover { color: var(--color-accent); transform: scale(1.15); }
.dft-star.on { color: var(--color-accent); }

/* 空/载/错 */
.dft-states { padding: 14px 16px; color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.dft-states--err { text-align: center; }
.dft-states--empty { text-align: center; padding: 48px 16px; }
.dft-empty-ico { font-size: 34px; margin-bottom: 8px; }
.dft-retry { margin-top: 10px; padding: 6px 16px; border-radius: var(--radius-md); border: 1px solid var(--color-primary-border); background: var(--color-primary-bg); color: var(--color-primary-dark); font-size: var(--font-size-sm); }
.dft-skel { display: flex; align-items: center; gap: 10px; height: 40px; border-bottom: 1px solid var(--color-border-light, var(--color-border)); animation: dft-fade .8s ease infinite alternate; }
.dft-skel-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--color-border); flex: none; }
.dft-skel-line { height: 10px; border-radius: 5px; background: var(--color-border-light, var(--color-border)); }
@keyframes dft-fade { from { opacity: .5; } to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .dft-skel { animation: none; } }

.dft-foot {
  flex: none;
  display: flex; align-items: center; gap: 10px;
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  border-top: none;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  background: var(--color-bg-card);
}
.dft-foot-stat { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.dft-foot-sp { flex: 1; }
.dft.drag-hint { }
</style>
