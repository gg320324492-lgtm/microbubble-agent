<!--
  FolderTree.vue — 课题组网盘 PR3.2 + v2 PR2 文件夹树组件
  2026-07-01 (v2 PR2: 加 3 个特殊固定项)

  结构:
  - 顶级固定节点 "📁 我的网盘" (selectedFolderId=null)
  - "⭐ 我的收藏" (specialView='starred', emit 'update:specialView')
  - "🗑️ 回收站" (specialView='trash')
  - 递归渲染文件夹树 (el-tree 自定义节点)
  - hover 节点显示快捷操作 (新建子文件夹 / 删除)

  数据:
  - props.folderTree: 从 useFolderTree composable
  - props.selectedFolderId / emits.update:selectedFolderId
  - props.expandedFolderIds / emits.update:expandedFolderIds
  - props.specialView: 'starred' | 'trash' | null
-->
<template>
  <!-- v2.0 (2026-07-09) Drive 美化: .drive-folder-tree 走共享 CSS (玻璃态侧栏 + 多色 special) -->
  <!-- v2.8 (2026-07-10) 右键菜单: 5 个根项 + 3 个 sub (FolderTreeNode 内) 全部用 FolderContextMenu 包裹 -->
  <div class="folder-tree drive-folder-tree" tabindex="0" aria-label="文件夹树">
    <!-- v2.28 (2026-07-12) 三态玻璃态: 复用 .drive-grid-* 设计语言 (hero 渐变 + glass CTA)
         sidebar 紧凑 adapter (48px mini hero + 二级 helper + 紧凑圆形 CTA)
         loading 旋转 + 进度文案, error 红字 + 重试, empty 大号 icon + 二级文案 + 快捷按钮 -->
    <div v-if="loading" class="folder-tree-loading drive-folder-tree-loading">
      <el-icon><Loading /></el-icon>
      <span class="drive-folder-tree-loading-text">正在加载文件夹…</span>
    </div>
    <div v-else-if="loadError" class="folder-tree-error drive-folder-tree-error">
      <el-icon><Warning /></el-icon>
      <p class="drive-folder-tree-error-text">{{ loadError }}</p>
      <el-button size="small" @click="$emit('retry')">重试</el-button>
    </div>
    <div v-else-if="folderTree.length === 0" class="folder-tree-empty drive-folder-tree-empty">
      <div class="drive-folder-tree-empty-hero">
        <el-icon><FolderAdd /></el-icon>
      </div>
      <p class="drive-folder-tree-empty-title">还没有文件夹</p>
      <p class="drive-folder-tree-empty-hint">
        右键点击空白处新建 ·<br>或将文件拖拽到此处
      </p>
      <el-button
        size="small"
        class="drive-folder-tree-empty-cta"
        @click="$emit('request-new-folder')"
      >
        <el-icon style="margin-right: 4px"><Plus /></el-icon>
        新建文件夹
      </el-button>
    </div>
    <template v-else>
      <FolderTreeNode
        v-for="folder in regularFolders"
        :key="folder.id"
        :folder="folder"
        :selected-folder-id="selectedFolderId"
        :expanded-folder-ids="expandedFolderIds"
        @select="handleFolderSelect"
        @toggle="$emit('toggle-expanded', $event)"
        @context-command="onSubContext"
        @drop-files="$emit('drop-files', $event)"
      />
    </template>

    <div class="folder-tree-divider drive-folder-tree-divider" />

    <!-- v2 PR7: 团队共享盘 (绿) + 文件请求 (橙) -->
    <FolderContextMenu :items="teamMenuItems" placement="right-start" @command="(cmd) => onTeamContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item is-team"
        :class="{ 'is-active': specialView === 'team' }"
        @click="$emit('update:specialView', 'team')"
      >
        <el-icon><Share /></el-icon>
        <span>团队共享盘</span>
        <span v-if="teamCount != null" class="folder-tree-special-count">{{ teamCount }}</span>
      </div>
    </FolderContextMenu>

    <!-- v2.27 (2026-07-12) BUG G 修复: team root folder (is_team_default=true)
         嵌套显示在 团队共享盘 special node 下面 (不是顶级节点)
         之前组会PPT 显示在 personal 区域 "我的收藏" 下面, 用户期望它在团队共享盘里面
         视觉层级: 🌐 团队共享盘 → 📂 组会PPT → 23 个成员 sub-folder
         depth=1 缩进, 让 CSS 渲染出 "嵌套在团队共享盘下面" 的视觉效果
    -->
    <FolderTreeNode
      v-for="folder in teamRootFolders"
      :key="folder.id"
      :folder="folder"
      :depth="1"
      :expandable="false"
      :selected-folder-id="selectedFolderId"
      :expanded-folder-ids="expandedFolderIds"
      @select="handleFolderSelect"
      @toggle="$emit('toggle-expanded', $event)"
      @context-command="onSubContext"
      @drop-files="$emit('drop-files', $event)"
    />

    <!-- v2 PR18 (2026-07-24, W68 第 14 批 B-2) 团队共享盘 Team Folder
         区别于上面 PR7 的 is_team_default=true 普通 Folder:
         - PR7 = is_team_default=True 普通 Folder 子树 (组会PPT 文件夹级别共享)
         - PR18 = TeamFolder 表 (成员列表显式存为 ARRAY + 4 维审计)
         同一个 "🌐 团队共享盘" 节点下同时挂载 PR7 + PR18 节点 — 用户视觉统一 -->
    <FolderTreeNode
      v-for="team in teamFolders"
      :key="`team-pr18-${team.id}`"
      :folder="teamFolderToTreeNode(team)"
      :depth="1"
      :selected-folder-id="selectedTeamFolderId === team.id ? -team.id : selectedFolderId"
      :expanded-folder-ids="expandedFolderIds"
      @select="(id) => onSelectTeamFolder(team, id)"
      @toggle="$emit('toggle-expanded', $event)"
      @context-command="onSubContext"
      @drop-files="$emit('drop-files', $event)"
    />

    <!-- 快捷 (批次⑥ 对齐视觉稿: 组标题 + 去 emoji, 图标只留 el-icon 一份) -->
    <div class="folder-tree-cap folder-tree-quick-cap">快捷</div>

    <FolderContextMenu :items="favoritesMenuItems" placement="right-start" @command="(cmd) => onFavoritesContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item is-starred"
        :class="{ 'is-active': specialView === 'starred' }"
        title="个人收藏夹, 仅自己可见"
        @click="$emit('update:specialView', 'starred')"
      >
        <el-icon><Star /></el-icon>
        <span>我的收藏</span>
        <span v-if="starredCount != null" class="folder-tree-special-count">{{ starredCount }}</span>
      </div>
    </FolderContextMenu>

    <!-- 最近上传 (批次⑥): 全盘按上传时间倒序 (视觉稿 snav 时钟项, specialView='recent' 由父层加载) -->
    <div
      class="folder-tree-special-item drive-folder-tree-special-item is-recent"
      :class="{ 'is-active': specialView === 'recent' }"
      title="全组最近上传的文件 (按上传时间)"
      @click="$emit('update:specialView', 'recent')"
    >
      <el-icon><Clock /></el-icon>
      <span>最近上传</span>
    </div>

    <!-- 回收站 (PR2 真实接入) -->
    <FolderContextMenu :items="trashMenuItems" placement="right-start" @command="(cmd) => onTrashContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item is-trash"
        :class="{ 'is-active': specialView === 'trash' }"
        @click="$emit('update:specialView', 'trash')"
      >
        <el-icon><Delete /></el-icon>
        <span>回收站</span>
        <span v-if="trashCount != null" class="folder-tree-special-count">{{ trashCount }}</span>
      </div>
    </FolderContextMenu>

    <!-- 批次⑩.81 选型 A: 文件夹删除轻确认 (替换 ElMessageBox, 方案稿 2026-09-08-folder-delete-confirm-4ui) -->
    <FolderDeleteConfirmDialog
      v-model="folderDelete.visible"
      :folder-name="folderDelete.folder?.name || ''"
      :folder-count="folderDelete.folderCount"
      :file-count="folderDelete.fileCount"
      :admin-warning="folderDelete.adminOverride"
      :loading="folderDelete.loading"
      @confirm="confirmFolderDelete"
    />
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让玻璃态侧栏 + 多色 special 生效
// v2.8 (2026-07-10) 右键菜单支持 (5 根项 + sub 节点共用 FolderContextMenu)
import '@/views/drive/drive-view.css'
import { computed, reactive } from 'vue'
import { Folder, FolderOpened, FolderAdd, Delete, Loading, Warning, Star, StarFilled, Share, Promotion, Plus, Bell, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import FolderTreeNode from './FolderTreeNode.vue'
import FolderContextMenu from './FolderContextMenu.vue'
import FolderDeleteConfirmDialog from './FolderDeleteConfirmDialog.vue'
import { useFolderTree } from '@/composables/useFolderTree'

const props = defineProps({
  folderTree: { type: Array, default: () => [] },
  selectedFolderId: { type: [Number, null], default: null },
  expandedFolderIds: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
  loadError: { type: [String, null], default: null },
  specialView: { type: [String, null], default: null },  // 'starred' | 'recent' | 'trash' | 'requests' | null
  // v2 PR18 (W68 第 14 批 B-2): Team Folder 列表 (GET /api/v1/team-folders 返回)
  teamFolders: { type: Array, default: () => [] },
  selectedTeamFolderId: { type: [Number, null], default: null },
  // 批次⑥ 视觉稿对齐: 快捷项 mono 计数 (null = 不显示, 父层按需传)
  starredCount: { type: [Number, null], default: null },
  trashCount: { type: [Number, null], default: null },
  // 批次⑧: 团队共享盘特殊项计数 (视觉稿根节点 .c "471", 父层拉 view=team total)
  teamCount: { type: [Number, null], default: null },
})

// v2.27 (2026-07-12) BUG G 修复: 把 is_team_default=true 的 folder 从 folderTree 中分离
//   顶层 folder 区域只显示 regular folder, team root folder 单独渲染到 团队共享盘 节点下
const regularFolders = computed(() =>
  (props.folderTree || []).filter(f => !f.is_team_default)
)
const teamRootFolders = computed(() =>
  (props.folderTree || []).filter(f => f.is_team_default)
)

const emit = defineEmits([
  'update:selectedFolderId',
  'update:specialView',
  'toggle-expanded',
  'retry',
  // v2.8: 转发 sub folder 右键菜单
  'create-sub-folder',  // (parentId) → parent 弹 CreateFolderDialog
  'rename-folder',      // (folder)   → parent 弹 RenameDialog
  'delete-folder',      // (folder)   → parent 调 useFolderTree.deleteFolder
  // W72 第 2 批 B-1: folder share 入口 (转发 → parent 弹 ShareLinkDialog)
  'share-folder',       // (folder)   → parent 弹 ShareLinkDialog
  // v2.28 (2026-07-12): 空态 CTA "新建文件夹" — 无 parent_id 顶层创建
  'request-new-folder', // () → parent 弹 CreateFolderDialog
  // 批次③ B: 拖拽移动落点 (子节点冒泡) → parent 调 move/batchMove
  'drop-files',         // ({folderId, ids})
])

const { fetchTree, deleteFolder, getChildrenStats } = useFolderTree()

// 批次⑩.81 选型 A: 文件夹删除确认弹窗状态 (替换 ElMessageBox)
const folderDelete = reactive({
  visible: false,
  folder: null,
  folderCount: 0,
  fileCount: 0,
  adminOverride: false,
  loading: false,
})

function handleFolderSelect(folderId) {
  emit('update:selectedFolderId', folderId)
  // 不重置 specialView — 允许在团队共享盘 / 收藏等特殊视图下钻取 sub-folder
}

// === 右键菜单项配置 (rootMenuItems/requestsMenuItems + handler 已删: 模板从未引用的死代码) ===
const favoritesMenuItems = [
  { label: '刷新',          command: 'refresh' },
]
const teamMenuItems = [
  { label: '刷新',          command: 'refresh' },
  { label: '新建子文件夹',   command: 'create-sub' },
]
// 批次⑩.85: 摘掉「恢复全部 / 清空回收站」— handler 只弹 confirm 后发假成功提示,
// 从未真正调接口, 误导用户 (后端无对应批量端点, 需要时逐项恢复即可)
const trashMenuItems = [
  { label: '刷新',          command: 'refresh' },
]

async function onFavoritesContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
}

async function onTeamContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
  else if (cmd === 'create-sub') emit('create-sub-folder', null)
}

async function onTrashContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
}

// === v2.8: sub folder 右键菜单 handler (来自 FolderTreeNode emit) ===
// v2.13: 加第 3 个参数 isAdminOverride (admin 越权删除别人 folder 时弹红字警告)
async function onSubContext(cmd, folder, isAdminOverride = false) {
  if (cmd === 'open') {
    handleFolderSelect(folder.id)
  } else if (cmd === 'create-sub') {
    emit('create-sub-folder', folder.id)
  } else if (cmd === 'rename') {
    emit('rename-folder', folder)
  } else if (cmd === 'share') {
    // W72 第 2 批 B-1 差量: folder share 入口, 上层 DesktopDriveView 接 ShareLinkDialog
    emit('share-folder', folder)
  } else if (cmd === 'delete') {
    // 批次⑩.81 选型 A: ElMessageBox → FolderDeleteConfirmDialog (预查子项计数供弹窗展示)
    // 删除规则不变: 有子项 → 级联 recursive; admin 越权删他人 folder → 弹窗红字警告
    const stats = await getChildrenStats(folder.id)
    folderDelete.folder = folder
    folderDelete.folderCount = stats?.folder_count ?? 0
    folderDelete.fileCount = stats?.file_count ?? 0
    folderDelete.adminOverride = isAdminOverride
    folderDelete.visible = true
  }
}

// 批次⑩.81 选型 A: 弹窗「移入回收站」→ 执行删除 + 结果反馈 (403/404/400/401 区分提示)
async function confirmFolderDelete() {
  const folder = folderDelete.folder
  if (!folder) return
  const folderCount = folderDelete.folderCount
  const fileCount = folderDelete.fileCount
  const doRecursive = folderCount > 0 || fileCount > 0
  folderDelete.loading = true
  try {
    await deleteFolder(folder.id, { recursive: doRecursive })
    if (doRecursive) {
      const sub = []
      if (folderCount > 0) sub.push(`${folderCount} 个子 folder`)
      if (fileCount > 0) sub.push(`${fileCount} 个文件`)
      ElMessage.success(`文件夹 "${folder.name}" + ${sub.join(' + ')} 已全部移入回收站`)
    } else {
      const successMsg = folderDelete.adminOverride
        ? `文件夹 "${folder.name}" (他人拥有) 已移入回收站`
        : `文件夹 "${folder.name}" 已移入回收站`
      ElMessage.success(successMsg)
    }
    folderDelete.visible = false
    // 批次⑩.85: 通知父层刷新侧栏计数 (级联子文件进回收站, trash 计数变化)
    emit('delete-folder', folder)
    await fetchTree()  // 显式重建树 (useFolderTree.deleteFolder 内部已调, 双保险)
  } catch (e) {
    const status = e.response?.status
    const msg = e.response?.data?.detail || e.message
    console.error(`[FolderContextMenu] delete folder ${folder.id} (recursive=${doRecursive}) failed:`, status, msg)
    if (status === 403) {
      // owner-mismatch (403) vs 不存在 (404) 区分, 后者误导用户「Folder不存在」实为越权
      ElMessage.error('删除失败: 该文件夹不属于您 (仅 owner 或 admin 可删除)')
    } else if (status === 404) {
      ElMessage.error(`文件夹不存在 (可能已被删除), 请刷新页面`)
    } else if (status === 400) {
      ElMessage.error('删除失败: ' + msg)
    } else if (status === 401) {
      ElMessage.error('未登录, 请重新登录')
    } else {
      ElMessage.error('删除失败: ' + (msg || '未知错误'))
    }
  } finally {
    folderDelete.loading = false
  }
}

// === v2 PR18 (W68 第 14 批 B-2) Team Folder 适配 ===
// TeamFolder 是独立表 (app/models/team_folder.py), 区别于 Folder
// FolderTreeNode 期望 props.folder 含 {id, name, ...}, 这里做轻量适配
function teamFolderToTreeNode(team) {
  return {
    id: -team.id,         // 用负数 id 与普通 Folder 隔离 (避免 key 冲突)
    name: `👥 ${team.name}`,
    owner_id: team.owner_id,
    is_team_folder: true,
    member_count: (team.member_ids || []).length,
  }
}

function onSelectTeamFolder(team, _id) {
  // v2 PR18 team folder click 行为: 弹 audit 列表 (后续 PR 接入 team folder detail view)
  ElMessage.info(
    `Team Folder "${team.name}" — 成员 ${(team.member_ids || []).length} 人, 请到审计面板查看活动`
  )
}
</script>

<style scoped>
/*
 * v2.0 (2026-07-09) Drive 美化: 全部视觉样式已迁 drive-view.css (.drive-folder-tree-* + .drive-sidebar)
 * 本 scoped 块只保留 forward-compat placeholder (后续如需 layout-flex 细节再加)
 */

/* ── 批次⑥ 对齐视觉稿 style-b .rail snav ── */
.folder-tree-cap { font-size: 10.5px; letter-spacing: .12em; color: var(--color-text-secondary); padding: 10px 10px 4px; }
.folder-tree-quick-cap { margin-top: 4px; }
.folder-tree-special-item { position: relative; }
.folder-tree-special-count {
  margin-left: auto; font-family: var(--font-mono, Consolas, monospace);
  font-size: 10.5px; color: var(--color-text-placeholder);
}
/* 老 drive-view.css 给 team(绿)/trash(红)/starred(黄) special 的激活染色全部收敛为
   视觉稿统一深青 (workbench 与旧页面一致化, 语义色让图标承担) */
.folder-tree-special-item.is-active,
.drive-folder-tree-special-item.is-team.is-active,
.drive-folder-tree-special-item.is-trash.is-active,
.drive-folder-tree-special-item.is-starred.is-active {
  background: var(--color-primary-bg) !important;
  color: var(--color-primary-dark) !important;
  font-weight: var(--font-weight-semibold);
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->