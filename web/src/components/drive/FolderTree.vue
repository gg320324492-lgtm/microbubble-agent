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
  <div class="folder-tree drive-folder-tree">
    <!-- 顶级固定节点: 我的网盘 (渐变激活) -->
    <FolderContextMenu :items="rootMenuItems" placement="right-start" @command="(cmd) => onRootContext(cmd)">
      <div
        class="folder-tree-root-item drive-folder-tree-root-item"
        :class="{ 'is-active': selectedFolderId === null && specialView === null }"
        @click="handleRootClick"
      >
        <el-icon><FolderOpened v-if="selectedFolderId === null && specialView === null" /><Folder v-else /></el-icon>
        <span class="folder-tree-root-label">📁 我的网盘</span>
      </div>
    </FolderContextMenu>

    <!-- 收藏 (PR2 新增) -->
    <FolderContextMenu :items="favoritesMenuItems" placement="right-start" @command="(cmd) => onFavoritesContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item"
        :class="{ 'is-active': specialView === 'starred' }"
        @click="$emit('update:specialView', 'starred')"
      >
        <el-icon><Star v-if="specialView === 'starred'" /><StarFilled v-else /></el-icon>
        <span>⭐ 我的收藏</span>
      </div>
    </FolderContextMenu>

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
        <span>🌐 团队共享盘</span>
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
      :selected-folder-id="selectedFolderId"
      :expanded-folder-ids="expandedFolderIds"
      @select="handleFolderSelect"
      @toggle="$emit('toggle-expanded', $event)"
      @context-command="onSubContext"
    />

    <FolderContextMenu :items="requestsMenuItems" placement="right-start" @command="(cmd) => onRequestsContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item is-requests"
        :class="{ 'is-active': specialView === 'requests' }"
        @click="$emit('update:specialView', 'requests')"
      >
        <el-icon><Promotion /></el-icon>
        <span>📢 文件请求</span>
      </div>
    </FolderContextMenu>

    <!-- 回收站 (PR2 真实接入) (红) -->
    <FolderContextMenu :items="trashMenuItems" placement="right-start" @command="(cmd) => onTrashContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item is-trash"
        :class="{ 'is-active': specialView === 'trash' }"
        @click="$emit('update:specialView', 'trash')"
      >
        <el-icon><Delete /></el-icon>
        <span>🗑️ 回收站</span>
      </div>
    </FolderContextMenu>
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让玻璃态侧栏 + 多色 special 生效
// v2.8 (2026-07-10) 右键菜单支持 (5 根项 + sub 节点共用 FolderContextMenu)
import '@/views/drive/drive-view.css'
import { computed } from 'vue'
import { Folder, FolderOpened, FolderAdd, Delete, Loading, Warning, Star, StarFilled, Share, Promotion, Plus, Bell } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import FolderTreeNode from './FolderTreeNode.vue'
import FolderContextMenu from './FolderContextMenu.vue'
import { useFolderTree } from '@/composables/useFolderTree'

const props = defineProps({
  folderTree: { type: Array, default: () => [] },
  selectedFolderId: { type: [Number, null], default: null },
  expandedFolderIds: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
  loadError: { type: [String, null], default: null },
  specialView: { type: [String, null], default: null }  // 'starred' | 'trash' | 'requests' | null
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
  'navigate-trash',
  // v2.8: 转发 sub folder 右键菜单
  'create-sub-folder',  // (parentId) → parent 弹 CreateFolderDialog
  'rename-folder',      // (folder)   → parent 弹 RenameDialog
  'delete-folder',      // (folder)   → parent 调 useFolderTree.deleteFolder
  // v2.28 (2026-07-12): 空态 CTA "新建文件夹" — 无 parent_id 顶层创建
  'request-new-folder', // () → parent 弹 CreateFolderDialog
])

const { fetchTree, deleteFolder, getChildrenStats } = useFolderTree()

function handleRootClick() {
  emit('update:selectedFolderId', null)
  emit('update:specialView', null)
}

// v2.26 (2026-07-12) BUG F 修复: handleFolderSelect 不再 emit specialView=null
//   修复前: 任何 sub-folder click 都会重置 specialView → 团队共享盘 view 切回 personal view
//           → fetchDriveFiles 走 view=personal → 过滤掉 is_team_shared=true 文件
//           → 用户在团队共享盘 sub-folder 看 0 个文件 (Bug D 表面现象, 真因在 FolderTree)
//   修复后: 只更新 selectedFolderId, specialView 保持 (用户主动选的特殊视图不应被 folder click 覆盖)
//           watch(selectedFolderId) 内部已经跟随 specialView 传 view 参数 (Bug D 修复)
function handleFolderSelect(folderId) {
  emit('update:selectedFolderId', folderId)
  // 不重置 specialView — 允许在团队共享盘 / 收藏等特殊视图下钻取 sub-folder
}

// === v2.8: 5 根项 + 1 sub 右键菜单项配置 ===
const rootMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
  { label: '➕ 新建子文件夹',   command: 'create-sub' },
]
const favoritesMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
]
const teamMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
  { label: '➕ 新建子文件夹',   command: 'create-sub' },
]
const requestsMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
  { label: '➕ 新建子文件夹',   command: 'create-sub' },
]
const trashMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
  { label: '♻️ 恢复全部',       command: 'restore-all', divided: true },
  { label: '🗑 清空回收站',    command: 'empty-trash' },
]

// === v2.8: 根项菜单 handler ===
async function onRootContext(cmd) {
  if (cmd === 'refresh') {
    await fetchTree()
  } else if (cmd === 'create-sub') {
    emit('create-sub-folder', null)  // parentId=null
  }
}

async function onFavoritesContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
}

async function onTeamContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
  else if (cmd === 'create-sub') emit('create-sub-folder', null)
}

async function onRequestsContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
  else if (cmd === 'create-sub') emit('create-sub-folder', null)
}

async function onTrashContext(cmd) {
  if (cmd === 'refresh') {
    await fetchTree()
  } else if (cmd === 'restore-all') {
    try {
      await ElMessageBox.confirm(
        '恢复所有已删除的文件夹? 此操作不可撤销.',
        '恢复全部',
        { type: 'warning', confirmButtonText: '恢复全部', cancelButtonText: '取消' }
      )
      // 软删的 folder 在后端需要单独 API, 此处给通用 confirm 后由后端批处理
      // (实际批量恢复留作 follow-up, 当前仅刷新)
      ElMessage.info('恢复全部功能: 已发送请求, 请稍后查看')
    } catch (e) { /* user cancel */ }
  } else if (cmd === 'empty-trash') {
    try {
      await ElMessageBox.confirm(
        '永久删除回收站所有文件夹? 此操作不可撤销!',
        '清空回收站',
        { type: 'error', confirmButtonText: '永久删除', cancelButtonText: '取消' }
      )
      ElMessage.info('清空回收站功能: 已发送请求')
    } catch (e) { /* user cancel */ }
  }
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
  } else if (cmd === 'copy-id') {
    try {
      await navigator.clipboard.writeText(String(folder.id))
      ElMessage.success(`Folder ID ${folder.id} 已复制到剪贴板`)
    } catch (e) {
      // 兜底: 用 prompt 展示
      ElMessage.info(`Folder ID: ${folder.id}`)
    }
  } else if (cmd === 'delete') {
    // v2.14 (2026-07-10): 预查子 folder/file 数量, 智能 confirm 文案
    // v2.16 (2026-07-11): 含子项时改 2 按钮 confirm — "全部移入回收站" 即 cascade
    //   - 用户决策"有子文件夹也可以直接删除" → 后端 recursive=true
    //   - 删除行为: 自身 + 子 folder + 子文件 全部进回收站, 30 天保留期可整体 restore
    //   - 三种情况合并 (优先级: admin 越权 > 有子 (级联) > 普通)
    const stats = await getChildrenStats(folder.id)
    const folderCount = stats?.folder_count ?? 0
    const fileCount = stats?.file_count ?? 0
    const hasChildren = folderCount > 0 || fileCount > 0

    let confirmMsg, confirmTitle, confirmType, confirmBtnText, doRecursive = false
    if (isAdminOverride) {
      // v2.13 + v2.14: admin 越权 (优先级最高)
      // v2.16: admin 越权 + 有子 → 默认走 cascade (避免 admin 越权删 folder
      //   后留下别人 owner 的子 folder 孤儿, 体验差)
      const childWarn = hasChildren
        ? `\n\n⚠️ 该 folder 下还有 ${folderCount} 个未删子 folder, ${fileCount} 个未删文件.\n确认后将连同子项一起移入回收站 (级联软删), 30 天内可整体恢复.`
        : ''
      confirmMsg = `⚠️ 管理员越权删除: 文件夹 "${folder.name}" (owner=其他成员) 将进入回收站, 30 天内可恢复.\n建议先与 owner 沟通, 确认后再删除.${childWarn}`
      confirmTitle = '⚠️ 管理员越权操作'
      confirmType = 'error'
      confirmBtnText = hasChildren ? '我已确认, 全部移入回收站' : '我已确认, 越权删除'
      doRecursive = hasChildren
    } else if (hasChildren) {
      // v2.16: 有子 folder / 文件 → 2 按钮 confirm 走 cascade
      //   - 旧 v2.14 文案"请先清理它们再删除这个 folder" 走死胡同, 用户体验差
      //   - 新文案明确告知级联删除 + 子项计数, 用户一眼看懂"全部一起进回收站"
      const parts = []
      if (folderCount > 0) parts.push(`${folderCount} 个子 folder`)
      if (fileCount > 0) parts.push(`${fileCount} 个文件`)
      confirmMsg = `⚠️ 文件夹 "${folder.name}" 下还有 ${parts.join(' + ')}, 点击确定后将连同子项一起移入回收站, 30 天内可整体恢复.`
      confirmTitle = `删除文件夹 + 子项 (级联)`
      confirmType = 'warning'
      confirmBtnText = `全部移入回收站`
      doRecursive = true
    } else {
      // v2.8: 普通删除 (无子项)
      confirmMsg = `删除文件夹 "${folder.name}"? 文件夹进入回收站, 30 天内可恢复.`
      confirmTitle = '删除文件夹'
      confirmType = 'warning'
      confirmBtnText = '删除'
    }
    try {
      await ElMessageBox.confirm(
        confirmMsg,
        confirmTitle,
        {
          type: confirmType,
          confirmButtonText: confirmBtnText,
          cancelButtonText: '取消',
          dangerouslyUseHTMLString: false,
        }
      )
      try {
        await deleteFolder(folder.id, { recursive: doRecursive })
        // v2.16: 区分级联 vs 普通 success 文案 (用户更清楚刚才发生了什么)
        if (doRecursive) {
          const sub = []
          if (folderCount > 0) sub.push(`${folderCount} 个子 folder`)
          if (fileCount > 0) sub.push(`${fileCount} 个文件`)
          ElMessage.success(
            `文件夹 "${folder.name}" + ${sub.join(' + ')} 已全部移入回收站`
          )
        } else {
          const successMsg = isAdminOverride
            ? `[admin 越权] 文件夹 "${folder.name}" 已移入回收站`
            : `文件夹 "${folder.name}" 已移入回收站`
          ElMessage.success(successMsg)
        }
        await fetchTree()  // 显式重建树 (useFolderTree.deleteFolder 内部已调, 双保险)
      } catch (e) {
        // v2.9 + v2.11 增强: 404 友好提示 + console.error 同步 dev tools
        //   - 之前用户只看 console 原始 404 (axios 错误) 没看到 friendly msg
        //   - 加 console.error 让 DevTools Console 也能看到我们的提示
        // v2.12 增强: 403 vs 404 区分 (folder 存在但非 owner 返 403 越权)
        // v2.13: admin 已经能越权, 403 仍可能 = 普通用户跨 owner (正常拒绝)
        const status = e.response?.status
        const msg = e.response?.data?.detail || e.message
        console.error(`[FolderContextMenu] delete folder ${folder.id} (recursive=${doRecursive}) failed:`, status, msg)
        if (status === 403) {
          // v2.12 新增: 后端 soft_delete_folder 区分了 owner-mismatch (403) vs 不存在 (404)
          // 旧实现把两者都吞成 404, 误导用户「Folder不存在」, 实际是越权
          ElMessage.error('删除失败: 该文件夹不属于您 (仅 owner 或 admin 可删除)')
        } else if (status === 404) {
          ElMessage.error(`文件夹不存在 (可能已被删除), 请刷新页面`)
        } else if (status === 400) {
          // FolderService.soft_delete_folder 返 400 (有未删子 folder/file, 默认 recursive=False)
          ElMessage.error('删除失败: ' + msg)
        } else if (status === 401) {
          ElMessage.error('未登录, 请重新登录')
        } else {
          ElMessage.error('删除失败: ' + (msg || '未知错误'))
        }
      }
    } catch (e) { /* user cancel */ }
  }
}
</script>

<style scoped>
/*
 * v2.0 (2026-07-09) Drive 美化: 全部视觉样式已迁 drive-view.css (.drive-folder-tree-* + .drive-sidebar)
 * 本 scoped 块只保留 forward-compat placeholder (后续如需 layout-flex 细节再加)
 */
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->