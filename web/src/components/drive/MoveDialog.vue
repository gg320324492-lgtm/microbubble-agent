<!--
  MoveDialog.vue — 课题组网盘 移动到对话框 (批次⑩.15 MOVE A 墨线树选式重绘, 2026-09-06)

  用户选型 MOVE A (与 CreateFolderDialog DLG A 同血统):
  - 白卡墨线 + mono 副标, 待移文件卡置顶 (单选=文件行, 批量=前3张+合计条)
  - 搜索框按名过滤 (过滤态平铺匹配项); 树 = 团队共享盘全量 (修「还没有文件夹」误报:
    旧实现走 FolderTree 个人盘过滤, 单一团队空间下 regularFolders 恒空)
  - 选中位置条: 「移动到 + 团队共享盘 / 组会PPT / 杨慈」路径
  - 可见性文案/徽章全部移除 (公开属性由分享驱动, 批次⑩.8)
  - 顶级语义修正: 「团队共享盘 · 顶层」(旧「顶级目录 (我的网盘)」个人盘时代退役)

  契约不变: emit('move', { fileId, targetFolderId }) — fileId 为 number 或 array
  (父层 onMoveFile 按类型路由 moveFile/batchMove)
-->
<template>
  <el-dialog
    v-model="visible"
    class="mvd-arch"
    width="480px"
    :close-on-click-modal="false"
    @open="onOpen"
  >
    <template #header>
      <div class="mvd-head">
        <div class="mvd-title">移动到</div>
        <div class="mvd-sub">MOVE · MICROBUBBLE LAB DRIVE</div>
      </div>
    </template>

    <div class="mvd-body">
      <!-- 待移档案卡 (单选=1张, 批量=前3张+合计) -->
      <div class="mvd-files">
        <div v-for="f in movedFiles.slice(0, 3)" :key="f.id" class="mvd-fcard">
          <span class="mvd-dot" :style="{ background: dotColor(f.file_name || f.title) }"></span>
          <span class="mvd-fnm" :title="f.file_name || f.title">{{ f.file_name || f.title }}</span>
          <span class="mvd-fsz">{{ fmtSize(f.file_size) }}</span>
        </div>
        <div v-if="movedFiles.length > 3" class="mvd-fmore">
          共 {{ movedFiles.length }} 项 · 合计 {{ fmtSize(totalBytes) }}
        </div>
      </div>

      <!-- 搜索过滤 -->
      <div class="mvd-srch">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="M16.5 16.5 21 21" /></svg>
        <input v-model="search" placeholder="搜索文件夹名…" />
      </div>

      <!-- 团队共享盘树 (搜索态=平铺匹配, 常态=层级树) -->
      <div class="mvd-tree">
        <div class="mvd-troot">
          <svg viewBox="0 0 24 24"><path d="M12 5.5l2 4 4.4.6-3.2 3.1.8 4.4-4-2.1-4 2.1.8-4.4-3.2-3.1 4.4-.6z" /></svg>
          团队共享盘
        </div>

        <template v-if="search.trim()">
          <div
            v-for="n in searchHits" :key="'s' + n.id"
            class="mvd-tn" :class="{ 'is-on': selectedFolderId === n.id }"
            @click="selectedFolderId = n.id"
          >
            <span class="mvd-tw"></span>
            <svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
            <span class="mvd-n">{{ n.name }}</span>
          </div>
          <div v-if="!searchHits.length" class="mvd-note">没有匹配「{{ search.trim() }}」的文件夹</div>
        </template>

        <template v-else>
          <div
            v-for="row in visibleRows" :key="row.node.id"
            class="mvd-tn" :class="{ 'is-on': selectedFolderId === row.node.id }"
            :style="{ paddingLeft: 9 + row.depth * 17 + 'px' }"
            @click="selectFolder(row.node)"
          >
            <span class="mvd-tw" @click.stop="toggleExpand(row.node.id)">{{ row.hasKids ? (isExpanded(row.node.id) ? '▾' : '▸') : '' }}</span>
            <svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
            <span class="mvd-n">{{ row.node.name }}</span>
            <span v-if="row.hasKids" class="mvd-c">{{ row.node.children.length }}</span>
          </div>
        </template>
      </div>

      <!-- 已选位置条 -->
      <div class="mvd-selbar">
        <span class="mvd-k">移动到</span>
        <svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>
        <span class="mvd-v" :title="targetPath">{{ targetPath }}</span>
      </div>
    </div>

    <template #footer>
      <div class="mvd-foot">
        <button type="button" class="mvd-btn ghost" @click="visible = false">取消</button>
        <button type="button" class="mvd-btn pri" :disabled="submitting" @click="onSubmit">
          {{ submitting ? '移动中…' : '移动到此' }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useFolderTree } from '@/composables/useFolderTree'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  currentFolderId: { type: [Number, null], default: null },
  fileId: { type: [Number, Array, null], default: null },  // number | id 数组 (批量)
  /** 批次⑩.15: 待移档案对象 (父层从当前列表取, 供文件卡展示) */
  files: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'move'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

// 批次⑩.15 根因修复: useFolderTree() 返回 Pinia store 实例, 解构出的 folderTree
// 是已解包数组而非 ref — 旧代码 folderTree.value 恒 undefined → 树恒空 → 误显
// 「还没有文件夹」。改走 storeToRefs 拿响应式引用。
const folderTreeStore = useFolderTree()
const { fetchTree } = folderTreeStore
const folderTree = computed(() => folderTreeStore.folderTree || [])

const selectedFolderId = ref(null)
const submitting = ref(false)
const search = ref('')
const expandedIds = ref(new Set())

const movedFiles = computed(() => props.files || [])
const totalBytes = computed(() => movedFiles.value.reduce((s, f) => s + (f.file_size || 0), 0))

// 展示树 = 全量顶层 (团队根 + 个人夹, 单一团队空间下都挂团队共享盘)
const displayTree = computed(() => folderTree.value || [])

// 搜索态: 平铺全部匹配
const allFolders = computed(() => {
  const out = []
  const walk = (nodes) => { for (const n of nodes || []) { out.push(n); walk(n.children) } }
  walk(folderTree.value || [])
  return out
})
const searchHits = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return []
  return allFolders.value.filter((n) => (n.name || '').toLowerCase().includes(q))
})

function isExpanded(id) { return expandedIds.value.has(id) }
function toggleExpand(id) {
  const next = new Set(expandedIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expandedIds.value = next
}
function selectFolder(n) { selectedFolderId.value = n.id }

// 选中路径 (团队共享盘 / 组会PPT / 杨慈)
const targetPath = computed(() => {
  if (selectedFolderId.value === null) return '团队共享盘 · 顶层'
  const chain = []
  const walk = (nodes, acc) => {
    for (const n of nodes || []) {
      if (n.id === selectedFolderId.value) { chain.push(...acc, n.name); return true }
      if (n.children?.length && walk(n.children, [...acc, n.name])) return true
    }
    return false
  }
  walk(folderTree.value || [], [])
  return chain.length ? `团队共享盘 / ${chain.join(' / ')}` : '团队共享盘 · 顶层'
})

// 打开时: 拉树 + 重置 (默认展开第一层)
watch(visible, async (v) => {
  if (v) {
    submitting.value = false
    search.value = ''
    selectedFolderId.value = null
    await fetchTree()
    const first = new Set()
    for (const n of folderTree.value || []) if (n.children?.length) first.add(n.id)
    expandedIds.value = first
  } else {
    submitting.value = false
  }
})

function fmtSize(bytes) {
  if (bytes == null) return '—'
  const n = Number(bytes) || 0
  if (n < 1024) return n + ' B'
  const u = ['KB', 'MB', 'GB', 'TB']; let v = n / 1024, i = 0
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
  return (v >= 100 ? Math.round(v) : v.toFixed(1)) + ' ' + u[i]
}
function dotColor(name) {
  const ext = (name || '').split('.').pop().toLowerCase()
  const map = { pdf: '#B3392F', doc: '#2F5D8A', docx: '#2F5D8A', ppt: '#B07C24', pptx: '#B07C24', xls: '#3E7A52', xlsx: '#3E7A52', csv: '#3E7A52', png: '#7C4E96', jpg: '#7C4E96', jpeg: '#7C4E96', mp4: '#A84B6F', mov: '#A84B6F' }
  return map[ext] || '#8F877B'
}

// 批次⑩.15: 扁平可见行 (按 expandedIds 裁剪, 免递归组件)
const visibleRows = computed(() => {
  const rows = []
  const walk = (nodes, depth) => {
    for (const n of nodes || []) {
      const hasKids = !!n.children?.length
      rows.push({ node: n, depth, hasKids })
      if (hasKids && isExpanded(n.id)) walk(n.children, depth + 1)
    }
  }
  walk(displayTree.value, 0)
  return rows
})

function onSubmit() {
  submitting.value = true
  emit('move', {
    fileId: props.fileId,
    targetFolderId: selectedFolderId.value
  })
}

</script>

<script>
// 递归组件注册 (template 字符串组件需要显式名) + teleport 壳样式走非 scoped 块
export default { name: 'MoveDialog' }
</script>

<style>
/* teleport 到 body — 壳样式必须非 scoped (v60-v67 教训) */
.mvd-arch {
  border-radius: 12px;
  border: 1px solid var(--color-border, #E5E1D8);
  box-shadow: 0 24px 64px rgba(10, 20, 16, .35);
  background: var(--color-bg-card, #fff);
  overflow: hidden;
}
.mvd-arch .el-dialog__header { padding: 18px 22px 0; margin-right: 0; }
.mvd-arch .el-dialog__headerbtn { top: 16px; right: 16px; width: 28px; height: 28px; border-radius: 7px; }
.mvd-arch .el-dialog__headerbtn:hover { background: var(--color-bg-page, #F2F0EB); }
.mvd-arch .el-dialog__body { padding: 14px 22px 0; }
.mvd-arch .el-dialog__footer {
  padding: 0;
  border-top: 1px solid var(--color-border, #E5E1D8);
  background: var(--color-bg-page, #F2F0EB);
}
/* 主按钮统一深青 (teleport 逃出 workbench 主色重映射, 批次⑩.9 同款) */
.mvd-arch .el-button--primary {
  background: linear-gradient(135deg, #0E766E, #12897C) !important;
  border: none !important; color: #fff !important;
}
</style>

<style scoped>
.mvd-head { display: flex; flex-direction: column; gap: 3px; }
.mvd-title { font-size: 15.5px; font-weight: 700; color: var(--color-text-primary); }
.mvd-sub { font-family: var(--font-mono, Consolas, monospace); font-size: 10px; letter-spacing: .14em; color: var(--color-text-placeholder); }

.mvd-files { margin-bottom: 12px; }
.mvd-fcard {
  display: flex; align-items: center; gap: 10px;
  background: var(--color-bg-page); border: 1px solid var(--color-border);
  border-radius: 8px; padding: 9px 12px;
}
.mvd-fcard + .mvd-fcard { margin-top: 6px; }
.mvd-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.mvd-fnm { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: var(--font-weight-medium); }
.mvd-fsz { font-family: var(--font-mono, Consolas, monospace); font-size: 10.5px; color: var(--color-text-secondary); }
.mvd-fmore { margin-top: 6px; font-size: 11.5px; color: var(--color-text-secondary); }

.mvd-srch {
  display: flex; align-items: center; gap: 8px;
  border: 1px solid var(--color-border); border-radius: 8px;
  padding: 8px 12px; margin-bottom: 10px;
  transition: border-color var(--duration-fast), box-shadow var(--duration-fast);
}
.mvd-srch:focus-within { border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), .1); }
.mvd-srch svg { width: 13px; height: 13px; stroke: var(--color-text-secondary); fill: none; stroke-width: 1.8; flex: none; }
.mvd-srch input { flex: 1; border: none; outline: none; background: none; font: inherit; font-size: 12.5px; color: var(--color-text-primary); }
.mvd-srch input::placeholder { color: var(--color-text-placeholder); }

.mvd-tree {
  border: 1px solid var(--color-border); border-radius: 8px;
  padding: 6px; max-height: 250px; overflow-y: auto; background: var(--color-bg-card);
}
.mvd-troot {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; letter-spacing: .1em; color: var(--color-text-secondary);
  padding: 4px 9px 6px;
}
.mvd-troot svg { width: 12px; height: 12px; stroke: var(--color-primary); fill: none; stroke-width: 1.8; }
.mvd-tn {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 9px; border-radius: 7px; cursor: pointer;
  font-size: 13px; color: var(--color-text-regular);
  transition: background var(--duration-fast);
}
.mvd-tn:hover { background: var(--color-bg-page); }
.mvd-tn.is-on { background: var(--color-primary-bg); color: var(--color-primary-dark); font-weight: var(--font-weight-semibold); }
.mvd-tn svg { width: 15px; height: 15px; stroke: var(--color-primary); fill: none; stroke-width: 1.7; flex: none; }
.mvd-tn.is-on svg { stroke: var(--color-primary-dark); }
.mvd-tw { width: 12px; text-align: center; color: var(--color-text-placeholder); font-size: 9px; flex: none; cursor: pointer; }
.mvd-n { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mvd-c { font-family: var(--font-mono, Consolas, monospace); font-size: 10.5px; color: var(--color-text-placeholder); }
.mvd-nest { margin-left: 17px; border-left: 1px dashed var(--color-border); padding-left: 6px; }
.mvd-note { padding: 10px; font-size: var(--font-size-xs); color: var(--color-text-secondary); }

.mvd-selbar {
  display: flex; align-items: center; gap: 8px;
  background: var(--color-bg-page); border: 1px solid var(--color-border);
  border-radius: 8px; padding: 9px 12px; margin-top: 10px; font-size: 12.5px;
}
.mvd-k { color: var(--color-text-secondary); flex: none; }
.mvd-selbar svg { width: 14px; height: 14px; stroke: var(--color-primary); fill: none; stroke-width: 1.7; flex: none; }
.mvd-v { font-weight: var(--font-weight-semibold); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.mvd-foot { display: flex; justify-content: flex-end; gap: 10px; padding: 13px 22px; }
.mvd-btn { font: inherit; font-size: 13px; padding: 8px 18px; border-radius: 8px; cursor: pointer; transition: all .15s; }
.mvd-btn.ghost { border: 1px solid var(--color-border); background: var(--color-bg-card); color: var(--color-text-regular); }
.mvd-btn.ghost:hover { border-color: var(--color-primary-border); color: var(--color-primary-dark); }
.mvd-btn.pri {
  border: none; background: var(--gradient-cta-button, linear-gradient(135deg, #0E766E, #12897C));
  color: #fff; font-weight: var(--font-weight-semibold);
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), .3);
}
.mvd-btn.pri:hover { transform: translateY(-1px); }
.mvd-btn.pri:disabled { opacity: .6; transform: none; cursor: default; }
</style>
