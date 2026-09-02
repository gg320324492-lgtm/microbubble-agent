<script setup lang="ts">
/**
 * SessionSidebar.vue — 多会话侧栏 (#043 Phase 6 + v78 UI-redesign)
 *
 * v78 改进点:
 * - session 卡片 actions 改 right-click/long-press 弹 ActionSheet（不再 hover-only 5 buttons 重叠标题）
 * - overlap bug 修复：title-row 改 .session-content 用 flex + min-width: 0，actions 永远不绝对定位
 * - sortedSessions 已自动置顶冒泡（chatSessions.ts:v78）
 * - 4-attr a11y 全部 button 加齐
 *
 * 2026-07-01 修复侧边栏点击跳动（bug 2）:
 * - 1) CSS: .session-list 加 overflow-anchor: none（关闭 Chrome scroll anchoring）
 * - 2) JS: onBeforeUpdate/onUpdated 保留 scrollTop（filterKw / v-for reorder 时位置不丢）
 */
import { ref, computed, onBeforeUpdate, onUpdated, nextTick, triggerRef, type Ref } from 'vue'
import { useChatSessionsStore } from '@/stores/chatSessions'
import { useChatHistoryStore } from '@/stores/chatHistory'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search, Edit, Share, Download, CollectionTag, Delete, FolderOpened, Top, Select } from '@element-plus/icons-vue'
import SessionActions from './SessionActions.vue'
import SessionItemRow from './SessionItemRow.vue'  // W100 +45 P3-VIRTUAL RETRY
import { useVirtualList } from '@/composables/useVirtualList'  // W100 +45 P3-VIRTUAL RETRY

const emit = defineEmits(['switch', 'create', 'share', 'export', 'edit-tags'])
const props = defineProps({ collapsed: { type: Boolean, default: false } })

const store = useChatSessionsStore()
const chatHistoryStore = useChatHistoryStore()

// v78: filterKw + context menu state
const filterKw = ref('')
const contextMenuSession = ref(null)
const contextMenuX = ref(0)
const contextMenuY = ref(0)

// W100 +28: 批量操作模式
const batchMode = ref(false)
const selectedIds = ref(new Set())

// W100 +45 P3-VIRTUAL RETRY: session 列表专用虚拟滚动
// ★ 修实际渲染卡片高度 ~64-72px (min-height 64 + padding 10 + border 3 + line-height margin),
//   原 56 偏小 → 卡片虚拟定位 top 间距 56 但实际占 64+, 每对卡片视觉重叠 8px (18/18 overlaps).
// ★ 真实案例: 19 items 触发虚拟化, 18 对全部 overlap. 解决 = virtual item height 严格等于渲染高度.
const SESSION_ITEM_HEIGHT = 72
const SESSION_VIRTUAL_THRESHOLD = 200
const sessionListRef = ref<HTMLElement | null>(null)  // 共享滚动容器
// 实际 virtualList 创建在 groupedSessions / filteredSessions 声明之后 (见下方)
// 3 个 let 变量, 避免 TDZ hoist 报错
let pinnedVirtual: ReturnType<typeof useVirtualList>
let recentVirtual: ReturnType<typeof useVirtualList>
let filteredVirtual: ReturnType<typeof useVirtualList>

const filteredSessions = computed(() => {
  const kw = filterKw.value.trim().toLowerCase()
  let all = store.sortedSessions
  // [CHAT-P1-E E3] 归档区过滤
  if (archiveFilter.value === 'active') {
    all = all.filter((s) => !s.is_archived)
  } else if (archiveFilter.value === 'archived') {
    all = all.filter((s) => s.is_archived)
  }
  if (!kw) return all
  return all.filter((s) => {
    if ((s.title || '').toLowerCase().includes(kw)) return true
    if ((s.tags || []).some((t) => t.toLowerCase().includes(kw))) return true
    // W100 +28: 搜索扩展 - 预览/最后消息也匹配
    if ((s.preview || '').toLowerCase().includes(kw)) return true
    return false
  })
})

const formatTime = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now - d
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour} 小时前`
    const diffDay = Math.floor(diffHour / 24)
    if (diffDay < 7) return `${diffDay} 天前`
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  } catch { return '' }
}

const onCreate = () => {
  emit('create')
}

const onSwitch = (id) => {
  if (store.switchSession(id)) {
    emit('switch', id)
  }
}

// v78: right-click 弹上下文菜单 (替代 hover buttons)
const onContextMenu = (s, e) => {
  e.preventDefault()
  contextMenuSession.value = s
  contextMenuX.value = e.clientX
  contextMenuY.value = e.clientY
  contextMenuOpen.value = true
}
const contextMenuOpen = ref(false)
const closeContextMenu = () => {
  contextMenuOpen.value = false
  contextMenuSession.value = null
}

const onDelete = async (session) => {
  closeContextMenu()
  try {
    await ElMessageBox.confirm(
      `删除会话「${session.title}」？此操作不可撤销。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    store.deleteSession(session.id)
    ElMessage.success('已删除')
  } catch { /* 用户取消 */ }
}

const onRename = async (session) => {
  closeContextMenu()
  try {
    const { value } = await ElMessageBox.prompt('新会话标题：', '重命名', {
      inputValue: session.title,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    store.renameSession(session.id, value.trim() || session.title)
  } catch { /* 用户取消 */ }
}

const onShare = (session) => {
  closeContextMenu()
  emit('share', session)
}

const onExport = (session) => {
  closeContextMenu()
  emit('export', session)
}

const onEditTags = (session) => {
  closeContextMenu()
  emit('edit-tags', session)
}

// v78: 长按触发 context menu（移动端兼容）
let longPressTimer = null
const onTouchStart = (s, e) => {
  longPressTimer = setTimeout(() => {
    const t = e.touches?.[0]
    if (t) {
      contextMenuSession.value = s
      contextMenuX.value = t.clientX
      contextMenuY.value = t.clientY
      contextMenuOpen.value = true
    }
  }, 500)
}
const onTouchEnd = () => {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
}

// v78: 切换置顶（保留 #043 setPinned helper）
const onTogglePinned = (session) => {
  closeContextMenu()
  store.setPinned(session.id, !session.is_pinned)
}

// [CHAT-P1-E E3] 归档/恢复 (复用 chatSessions.ts:497-502 setArchived, store API 已存在)
const onToggleArchive = async (session) => {
  closeContextMenu()
  try {
    await store.setArchived(session.id, !session.is_archived)
    ElMessage.success(session.is_archived ? '已恢复' : '已归档')
  } catch (e) {
    ElMessage.error(session.is_archived ? '恢复失败' : '归档失败')
  }
}

// [CHAT-P1-E E3] 顶栏 tab 切换 全部/未归档/已归档
const archiveFilter = ref('active')  // 'all' | 'active' | 'archived'

// W100 +28: 分组显示 (置顶 / 最近)
const groupedSessions = computed(() => {
  const list = filteredSessions.value
  const pinned = list.filter(s => s.is_pinned)
  const recent = list.filter(s => !s.is_pinned)
  return { pinned, recent }
})

// W100 +45 P3-VIRTUAL RETRY: 虚拟滚动实例初始化
// 必须在 groupedSessions / filteredSessions 之后, 这样 items 能绑到 computed
// 注意: 这是 setup 阶段同步初始化, 3 个 useVirtualList 共享 sessionListRef 容器
// 但各自维护 visibleItems (基于自己的 items ref 分组)
// 滚动事件通过容器自带的 scroll listener (useVirtualList 内部) 共享
const pinnedItemsRef = computed(() => groupedSessions.value.pinned) as unknown as Ref<readonly any[]>
const recentItemsRef = computed(() => groupedSessions.value.recent) as unknown as Ref<readonly any[]>
const filteredItemsRef = computed(() => filteredSessions.value) as unknown as Ref<readonly any[]>
pinnedVirtual = useVirtualList({
  containerRef: sessionListRef as unknown as Ref<HTMLElement | null>,
  items: pinnedItemsRef,
  itemHeight: SESSION_ITEM_HEIGHT,
  threshold: SESSION_VIRTUAL_THRESHOLD,
  overscan: 3,
})
recentVirtual = useVirtualList({
  containerRef: sessionListRef as unknown as Ref<HTMLElement | null>,
  items: recentItemsRef,
  itemHeight: SESSION_ITEM_HEIGHT,
  threshold: SESSION_VIRTUAL_THRESHOLD,
  overscan: 3,
})
filteredVirtual = useVirtualList({
  containerRef: sessionListRef as unknown as Ref<HTMLElement | null>,
  items: filteredItemsRef,
  itemHeight: SESSION_ITEM_HEIGHT,
  threshold: SESSION_VIRTUAL_THRESHOLD,
  overscan: 3,
})

// W100 +28: 批量操作
const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  if (!batchMode.value) selectedIds.value.clear()
}

const toggleSelect = (id) => {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  triggerRef(selectedIds)  // 强制重触 ref,防 Vue collection Proxy reactivity quirk
}

const selectAll = () => {
  filteredSessions.value.forEach(s => selectedIds.value.add(s.id))
  triggerRef(selectedIds)
}

const clearSelection = () => {
  // 清空所有已选 (Vue ref collection reactivity quirk workaround: use triggerRef)
  // ★ 2026-08-21: 强制让 vite content hash 变化, 触发新 bundle 释放客户端 1 年 immutable cache
  selectedIds.value.clear()
  triggerRef(selectedIds)
}

const batchArchive = async () => {
  if (!selectedIds.value.size) return
  try {
    await ElMessageBox.confirm(
      `归档 ${selectedIds.value.size} 个会话？归档后可在"已归档"tab 恢复。`,
      '批量归档',
      { type: 'warning', confirmButtonText: '归档', cancelButtonText: '取消' }
    )
    for (const id of [...selectedIds.value]) {
      await store.setArchived(id, true)
    }
    ElMessage.success(`已归档 ${selectedIds.value.size} 个会话`)
    batchMode.value = false
    triggerRef(selectedIds)
    selectedIds.value.clear()
    triggerRef(selectedIds)
  } catch { /* 用户取消 */ }
}

const batchDelete = async () => {
  if (!selectedIds.value.size) return
  try {
    await ElMessageBox.confirm(
      `永久删除 ${selectedIds.value.size} 个会话？此操作不可撤销。`,
      '批量删除',
      { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    for (const id of [...selectedIds.value]) {
      store.deleteSession(id)
    }
    ElMessage.success(`已删除 ${selectedIds.value.size} 个会话`)
    batchMode.value = false
    triggerRef(selectedIds)
    selectedIds.value.clear()
    triggerRef(selectedIds)
  } catch { /* 用户取消 */ }
}

// ★ 2026-07-01 修复 bug 2.4: 侧边栏 scroll 位置保留
// 切会话 / filterKw 变化 / v-for reorder 时,Vue 会 re-render .session-item 列表
// Chrome 浏览器会尝试 scroll anchoring 自动调整 scrollTop → 用户感知为"跳动"
// 解决: 渲染前快照 scrollTop, 渲染后 nextTick 恢复
// W100 +45 P3-VIRTUAL: sessionListRef 已在文件顶部声明 (供 useVirtualList 共享容器)
let pendingScrollTop = null

// 类 20.152 + 类 20.153: SessionItem.active 状态时 SessionActions 显示 (pin-btn/archive-btn/delete-btn)
//   鼠标 hover 在按钮上时 wheel 事件 target 是按钮, 默认不冒泡 → SessionList 滚轮失效
//   解决: 在 SessionList 上加 @wheel 监听, 强制 scrollBy 接管 (无论 target)
//   浏览器仍可 click 按钮 (click vs wheel 分离)
const onListWheel = (e: WheelEvent) => {
  if (sessionListRef.value) {
    sessionListRef.value.scrollTop += e.deltaY
  }
}

onBeforeUpdate(() => {
  if (sessionListRef.value) {
    pendingScrollTop = sessionListRef.value.scrollTop
  }
})
onUpdated(() => {
  if (pendingScrollTop != null && sessionListRef.value) {
    const target = pendingScrollTop
    pendingScrollTop = null
    nextTick(() => {
      if (sessionListRef.value) sessionListRef.value.scrollTop = target
    })
  }
})
</script>

<template>
  <aside class="session-sidebar" :class="{ collapsed }" @click="closeContextMenu">
    <div class="sidebar-header">
      <el-button
        v-if="!collapsed"
        id="chat-new-session-btn"
        name="chat-new-session"
        type="primary"
        size="small"
        class="new-btn"
        aria-label="新建对话"
        title="新建对话"
        @click.stop="onCreate"
      >
        <el-icon><Edit /></el-icon>
        <span class="new-btn-text">新对话</span>
      </el-button>
      <el-button
        v-else
        id="chat-new-session-btn-collapsed"
        name="chat-new-session-collapsed"
        text size="small"
        @click.stop="onCreate"
        aria-label="新建对话"
        title="新建对话"
      >
        <el-icon><Edit /></el-icon>
      </el-button>
      <!-- v78: 搜索保留 (按 title + tags 过滤) -->
      <div v-if="!collapsed" class="sidebar-search">
        <el-input
          v-model="filterKw"
          id="chat-sidebar-filter"
          name="chat-sidebar-filter"
          aria-label="过滤会话"
          title="过滤会话标题或标签"
          placeholder="过滤会话标题或标签"
          size="small"
          clearable
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
      <!-- [CHAT-P1-E E3] 归档区过滤 tab -->
      <div v-if="!collapsed" class="archive-filter-tabs">
        <button
          type="button"
          class="archive-tab"
          :class="{ active: archiveFilter === 'all' }"
          @click="archiveFilter = 'all'"
        >全部</button>
        <button
          type="button"
          class="archive-tab"
          :class="{ active: archiveFilter === 'active' }"
          @click="archiveFilter = 'active'"
        >未归档</button>
        <button
          type="button"
          class="archive-tab"
          :class="{ active: archiveFilter === 'archived' }"
          @click="archiveFilter = 'archived'"
        >已归档</button>
      </div>
      <!-- W100 +28: 批量操作 toggle -->
      <div v-if="!collapsed" class="batch-toggle-row">
        <button
          type="button"
          class="batch-toggle-btn"
          :class="{ active: batchMode }"
          @click="toggleBatchMode"
        >
          <el-icon><Select /></el-icon>
          <span>{{ batchMode ? '退出批量' : '批量管理' }}</span>
        </button>
        <template v-if="batchMode">
          <button type="button" class="batch-mini-btn" @click="selectAll">全选</button>
          <button type="button" class="batch-mini-btn" @click="clearSelection" :disabled="!selectedIds.size">清空</button>
        </template>
      </div>
    </div>
    <!-- 同步状态徽章 -->
    <div v-if="!collapsed && chatHistoryStore.syncStatus === 'syncing'" class="sync-badge sync-loading">
      <span class="sync-icon rotating">⟳</span>
      <span class="sync-text">同步中...</span>
    </div>
    <div v-else-if="!collapsed && chatHistoryStore.syncStatus === 'error' && chatHistoryStore.syncError" class="sync-badge sync-error">
      <span class="sync-icon">⚠</span>
      <span class="sync-text" :title="chatHistoryStore.syncError">同步失败</span>
    </div>
    <div v-if="!collapsed" class="session-list" ref="sessionListRef" tabindex="0" aria-label="会话列表" @wheel.passive="onListWheel">
      <!-- W100 +28: 分组显示 (非批量模式) -->
      <template v-if="!batchMode">
        <!-- 置顶组 -->
        <div v-if="groupedSessions.pinned.length" class="session-group-header" role="heading" aria-level="3">
          <span class="group-icon">📌</span><span>置顶</span>
        </div>
        <!-- W100 +45 P3-VIRTUAL: 置顶组虚拟化 -->
        <template v-if="pinnedVirtual.isVirtualized.value">
          <div
            class="virtual-list-spacer"
            :style="{ position: 'relative', height: pinnedVirtual.totalHeight.value + 'px' }"
          >
            <SessionItemRow
              v-for="entry in pinnedVirtual.visibleItems.value"
              :key="`pinned-${entry.item.id}-${entry.index}`"
              :session="entry.item"
              :active="entry.item.id === store.currentId"
              :store="store"
              :format-time="formatTime"
              :on-switch="onSwitch"
              :on-context-menu="onContextMenu"
              :on-touch-start="onTouchStart"
              :on-touch-end="onTouchEnd"
              :on-toggle-pinned="onTogglePinned"
              :on-toggle-archive="onToggleArchive"
              :on-delete="onDelete"
              :toggle-select="toggleSelect"
              :is-virtual="true"
              :virtual-top="entry.index * pinnedVirtual.itemHeight"
              @switch="onSwitch"
              @toggle="toggleSelect"
            />
          </div>
        </template>
        <template v-else>
          <div
            v-for="s in groupedSessions.pinned"
            :key="s.id"
            :data-session-id="s.id"
            class="session-item"
            :class="{ active: s.id === store.currentId }"
            @click="onSwitch(s.id)"
            @contextmenu="onContextMenu(s, $event)"
            @touchstart="onTouchStart(s, $event)"
            @touchend="onTouchEnd"
            @touchmove="onTouchEnd"
          >
            <div class="session-content">
              <div class="session-title">
                <span class="session-title-text">{{ s.title || '新对话' }}</span>
                <span v-if="s.is_pinned" class="pinned-mark" title="已收藏" aria-label="已收藏">📌</span>
                <span v-if="s._isLocalOnly" class="local-only-tag" title="仅本地（未同步到云端）">本地</span>
                <span v-else-if="s._syncStatus === 'synced'" class="synced-tag" title="已同步到云端" aria-label="已同步到云端">✓</span>
                <span v-else-if="s._syncStatus === 'error'" class="error-tag" title="同步失败" aria-label="同步失败">⚠</span>
                <el-tag
                  v-for="tag in (s.tags || []).slice(0, 2)"
                  :key="tag"
                  size="small"
                  effect="plain"
                  class="session-tag-chip"
                >{{ tag }}</el-tag>
                <el-tag
                  v-if="(s.tags || []).length > 2"
                  size="small"
                  effect="plain"
                  class="session-tag-more"
                >+{{ s.tags.length - 2 }}</el-tag>
              </div>
              <div class="session-meta">
                <span class="time">{{ formatTime(s.updatedAt) }}</span>
                <span v-if="s.messageCount" class="count">{{ s.messageCount }} 条</span>
              </div>
              <div v-if="s.preview" class="session-preview">{{ s.preview }}</div>
            </div>
            <SessionActions
              mode="sidebar"
              :session="s"
              @pin="onTogglePinned"
              @archive="onToggleArchive"
              @delete="onDelete"
            />
          </div>
        </template>
        <!-- 最近组 -->
        <div v-if="groupedSessions.recent.length" class="session-group-header" role="heading" aria-level="3">
          <span class="group-icon">🕒</span><span>最近</span>
        </div>
        <!-- W100 +45 P3-VIRTUAL: 最近组虚拟化 -->
        <template v-if="recentVirtual.isVirtualized.value">
          <div
            class="virtual-list-spacer"
            :style="{ position: 'relative', height: recentVirtual.totalHeight.value + 'px' }"
          >
            <SessionItemRow
              v-for="entry in recentVirtual.visibleItems.value"
              :key="`recent-${entry.item.id}-${entry.index}`"
              :session="entry.item"
              :active="entry.item.id === store.currentId"
              :store="store"
              :format-time="formatTime"
              :on-switch="onSwitch"
              :on-context-menu="onContextMenu"
              :on-touch-start="onTouchStart"
              :on-touch-end="onTouchEnd"
              :on-toggle-pinned="onTogglePinned"
              :on-toggle-archive="onToggleArchive"
              :on-delete="onDelete"
              :toggle-select="toggleSelect"
              :is-virtual="true"
              :virtual-top="entry.index * recentVirtual.itemHeight"
              @switch="onSwitch"
              @toggle="toggleSelect"
            />
          </div>
        </template>
        <template v-else>
          <div
            v-for="s in groupedSessions.recent"
            :key="s.id"
            :data-session-id="s.id"
            class="session-item"
            :class="{ active: s.id === store.currentId }"
            @click="onSwitch(s.id)"
            @contextmenu="onContextMenu(s, $event)"
            @touchstart="onTouchStart(s, $event)"
            @touchend="onTouchEnd"
            @touchmove="onTouchEnd"
          >
            <div class="session-content">
              <div class="session-title">
                <span class="session-title-text">{{ s.title || '新对话' }}</span>
                <span v-if="s.is_pinned" class="pinned-mark" title="已收藏" aria-label="已收藏">📌</span>
                <span v-if="s._isLocalOnly" class="local-only-tag" title="仅本地（未同步到云端）">本地</span>
                <span v-else-if="s._syncStatus === 'synced'" class="synced-tag" title="已同步到云端" aria-label="已同步到云端">✓</span>
                <span v-else-if="s._syncStatus === 'error'" class="error-tag" title="同步失败" aria-label="同步失败">⚠</span>
                <el-tag
                  v-for="tag in (s.tags || []).slice(0, 2)"
                  :key="tag"
                  size="small"
                  effect="plain"
                  class="session-tag-chip"
                >{{ tag }}</el-tag>
                <el-tag
                  v-if="(s.tags || []).length > 2"
                  size="small"
                  effect="plain"
                  class="session-tag-more"
                >+{{ s.tags.length - 2 }}</el-tag>
              </div>
              <div class="session-meta">
                <span class="time">{{ formatTime(s.updatedAt) }}</span>
                <span v-if="s.messageCount" class="count">{{ s.messageCount }} 条</span>
              </div>
              <div v-if="s.preview" class="session-preview">{{ s.preview }}</div>
            </div>
            <SessionActions
              mode="sidebar"
              :session="s"
              @pin="onTogglePinned"
              @archive="onToggleArchive"
              @delete="onDelete"
            />
          </div>
        </template>
      </template>
      <!-- W100 +28: 批量模式 (flat list + checkbox) -->
      <template v-else>
        <!-- W100 +45 P3-VIRTUAL: 批量模式统一虚拟化 -->
        <template v-if="filteredVirtual.isVirtualized.value">
          <div
            class="virtual-list-spacer"
            :style="{ position: 'relative', height: filteredVirtual.totalHeight.value + 'px' }"
          >
            <SessionItemRow
              v-for="entry in filteredVirtual.visibleItems.value"
              :key="`filtered-${entry.item.id}-${entry.index}`"
              :session="entry.item"
              :active="entry.item.id === store.currentId"
              :selected="selectedIds.has(entry.item.id)"
              :show-batch-checkbox="true"
              :store="store"
              :format-time="formatTime"
              :on-switch="onSwitch"
              :on-context-menu="onContextMenu"
              :on-touch-start="onTouchStart"
              :on-touch-end="onTouchEnd"
              :on-toggle-pinned="onTogglePinned"
              :on-toggle-archive="onToggleArchive"
              :on-delete="onDelete"
              :toggle-select="toggleSelect"
              :is-virtual="true"
              :virtual-top="entry.index * filteredVirtual.itemHeight"
              @switch="onSwitch"
              @toggle="toggleSelect"
            />
          </div>
        </template>
        <template v-else>
          <div
            v-for="s in filteredSessions"
            :key="s.id"
            :data-session-id="s.id"
            class="session-item batch-item"
            :class="{ active: s.id === store.currentId, selected: selectedIds.has(s.id) }"
            @click="toggleSelect(s.id)"
          >
            <label class="batch-checkbox" @click.stop>
              <input
                type="checkbox"
                :checked="selectedIds.has(s.id)"
                @change="toggleSelect(s.id)"
                :aria-label="`选择 ${s.title || '新对话'}`"
              />
            </label>
            <div class="session-content">
              <div class="session-title">
                <span class="session-title-text">{{ s.title || '新对话' }}</span>
                <span v-if="s.is_pinned" class="pinned-mark">📌</span>
                <span v-if="s.is_archived" class="archived-mark" title="已归档">🗄️</span>
              </div>
              <div class="session-meta">
                <span class="time">{{ formatTime(s.updatedAt) }}</span>
                <span v-if="s.messageCount" class="count">{{ s.messageCount }} 条</span>
              </div>
            </div>
          </div>
        </template>
      </template>
      <div v-if="!filteredSessions.length && !store.sessions.length" class="empty">暂无会话</div>
      <div v-else-if="!filteredSessions.length" class="empty">没有匹配「{{ filterKw }}」的会话</div>
    </div>

    <!-- W100 +28: 批量操作 action bar -->
    <div v-if="!collapsed && batchMode" class="batch-action-bar" data-testid="batch-action-bar">
      <span class="batch-count">已选 {{ selectedIds.size }} 个</span>
      <div class="batch-actions">
        <button
          type="button"
          class="batch-action-btn"
          :disabled="!selectedIds.size"
          @click="batchArchive"
        >
          <el-icon><FolderOpened /></el-icon>
          <span>归档</span>
        </button>
        <button
          type="button"
          class="batch-action-btn danger"
          :disabled="!selectedIds.size"
          @click="batchDelete"
        >
          <el-icon><Delete /></el-icon>
          <span>删除</span>
        </button>
      </div>
    </div>

    <!-- v78: 右键/长按 上下文菜单 -->
    <ul
      v-if="contextMenuOpen && contextMenuSession"
      class="session-context-menu"
      :style="{ top: contextMenuY + 'px', left: contextMenuX + 'px' }"
      role="menu"
      aria-label="会话操作菜单"
      @click.stop
    >
      <li role="menuitem" class="ctx-item" @click="onRename(contextMenuSession)">
        <el-icon><Edit /></el-icon><span>重命名</span>
      </li>
      <li role="menuitem" class="ctx-item" @click="onTogglePinned(contextMenuSession)">
        <span>{{ contextMenuSession.is_pinned ? '📍' : '📌' }}</span>
        <span>{{ contextMenuSession.is_pinned ? '取消置顶' : '置顶会话' }}</span>
      </li>
      <!-- [CHAT-P1-E E3] 归档/恢复 (归档区显示"恢复", 否则显示"归档") -->
      <li role="menuitem" class="ctx-item" @click="onToggleArchive(contextMenuSession)">
        <el-icon><Delete /></el-icon>
        <span>{{ contextMenuSession.is_archived ? '✅ 恢复会话' : '🗄️ 归档会话' }}</span>
      </li>
      <li role="menuitem" class="ctx-item" @click="onShare(contextMenuSession)">
        <el-icon><Share /></el-icon><span>分享</span>
      </li>
      <li role="menuitem" class="ctx-item" @click="onExport(contextMenuSession)">
        <el-icon><Download /></el-icon><span>导出</span>
      </li>
      <li role="menuitem" class="ctx-item" @click="onEditTags(contextMenuSession)">
        <el-icon><CollectionTag /></el-icon><span>编辑标签</span>
      </li>
      <li role="separator" class="ctx-sep" />
      <li role="menuitem" class="ctx-item danger" @click="onDelete(contextMenuSession)">
        <el-icon><Delete /></el-icon><span>删除</span>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.session-sidebar {
  height: 100%; min-height: 0;
  display: flex; flex-direction: column;
  width: 260px;
  background: var(--color-bg-warm);
  border-right: 1px solid var(--color-border-light);
  transition: width var(--duration-normal, 200ms) ease;
  flex-shrink: 0;
  position: relative;
}
.session-sidebar.collapsed { width: 0; overflow: hidden; border-right: none; }
.sidebar-header { padding: 12px; border-bottom: 1px solid var(--color-border-light); display: flex; flex-direction: column; gap: 8px; }
.new-btn { width: 100%; }
.new-btn-text { margin-left: 4px; }
.icon { font-size: 16px; margin-right: 4px; }

/* [CHAT-P1-E E3] 归档过滤 tab */
.archive-filter-tabs {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}
.archive-tab {
  flex: 1;
  padding: 4px 8px;
  font-size: 12px;
  background: transparent;
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  cursor: pointer;
  color: var(--color-text-secondary);
  -webkit-tap-highlight-color: transparent;
}
.archive-tab:hover { background: var(--color-bg-hover); }
.archive-tab.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}
.session-list { flex: 1; overflow-y: auto; padding: 8px 0; overflow-anchor: none; }
.session-item {
  padding: 10px 12px;
  margin: 2px 8px 8px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s;
  /* ★ 2026-07-01 修复 bug 2.3: 默认 border-left 透明占位 3px,active 切换只改色不改尺寸 */
  border-left: 3px solid transparent;
  /* ★ 2026-07-01 修复 bug 2.1: 关闭 Chrome scroll anchoring,避免 .active 切换触发 scroll 跳变 */
  overflow-anchor: none;
  /* W100 +28: flex 布局让 SessionActions 对齐右侧 */
  display: flex;
  align-items: center;
  gap: 4px;
  /* ★ ★ 修复 sidebar 卡片重叠: 用户实测 18/18 仍有重叠.
     此处用 !important 强约束覆盖任何其他规则 (scoped 优先级/继承 line-height).
     防御: SessionActions ::before tap target = 44px, 默认 flex-shrink: 1
     把 .session-content 压扁. min-height + flex-shrink: 0 + overflow:hidden
     + position:relative 四件套 */
  min-height: 64px !important;
  overflow: hidden !important;
  position: relative !important;
  box-sizing: border-box !important;
  /* ★ ★ 用户视觉感知修复: 用 box-shadow 替代 border 立体感 + 增加可见间距 (margin-bottom 8px),
     让卡片间有清晰视觉分隔, 不再看起来"挤成一坨" */
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.session-item:hover { background: #f8f6f3; }
.session-item.active { background: #fff5f2; border-left-color: #FF7A5C; }
.session-item.selected { background: rgba(64, 158, 255, 0.08); border-left-color: var(--el-color-primary); }

/* W100 +28: 分组 header */
.session-group-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.session-group-header .group-icon { font-size: 12px; }

/* W100 +28: 批量操作 toggle */
.batch-toggle-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}
.batch-toggle-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  font-size: 12px;
  background: transparent;
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  cursor: pointer;
  color: var(--color-text-secondary);
  -webkit-tap-highlight-color: transparent;
}
.batch-toggle-btn:hover { background: var(--color-bg-hover); }
.batch-toggle-btn.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}
.batch-mini-btn {
  padding: 4px 8px;
  font-size: 12px;
  background: transparent;
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  cursor: pointer;
  color: var(--color-text-secondary);
  -webkit-tap-highlight-color: transparent;
}
.batch-mini-btn:hover { background: var(--color-bg-hover); }
.batch-mini-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* W100 +28: 批量模式 checkbox */
.batch-checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  cursor: pointer;
}
.batch-checkbox input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}
.batch-item { cursor: pointer; }
.batch-item .session-content { flex: 1; min-width: 0; }

/* W100 +28: 批量操作 action bar */
.batch-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-bg-card);
  gap: 8px;
}
.batch-count {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}
.batch-actions {
  display: flex;
  gap: 6px;
}
.batch-action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  font-size: 12px;
  background: transparent;
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  cursor: pointer;
  color: var(--color-text-primary);
  -webkit-tap-highlight-color: transparent;
}
.batch-action-btn:hover:not(:disabled) { background: var(--color-bg-hover); }
.batch-action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.batch-action-btn.danger { color: var(--color-danger); border-color: var(--el-color-danger-light-5); }
.batch-action-btn.danger:hover:not(:disabled) { background: rgba(245, 108, 108, 0.1); }
.batch-action-btn .el-icon { font-size: 14px; }

.archived-mark { font-size: 10px; }

/* v78: session-content 用 flex + min-width: 0 让 title-text 自然收缩，actions 绝对定位重叠 bug 修复
   ★ ★ 修复 sidebar UI 重叠: 删 width: 100% + 加 flex: 1 + flex-shrink: 0, 防止
      .session-actions (flex-shrink:0, 高度 44px 含 ::before) 把 .session-content
      flex-shrink:1 压缩到 44px, 导致 title/meta/preview 三行文字叠加. */
.session-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
  flex-shrink: 0;
}
.session-title {
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  font-size: 13px; font-weight: 500; color: var(--color-text-primary);
  min-width: 0;
}
.session-title-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
  /* v78: 移除写死 max-width: 160px，改 flex 自然收缩 */
}
.session-meta { display: flex; gap: 8px; font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; flex-shrink: 0; }
.session-preview {
  font-size: 11px; color: var(--color-text-secondary); margin-top: 4px;
  /* ★ 用户实测: preview 数据含 \n 换行, 旧 nowrap 渲染出多行. 改用 -webkit-line-clamp 2 行截断 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-word;
  /* 防止 flex 容器把 preview 撑开, 强制单卡固定高度可预测 */
  flex-shrink: 0;
}

/* v78: 上下文菜单（原 .session-actions hover 区彻底删除） */
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 12px; }
.session-context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 160px;
  list-style: none;
  padding: 4px 0;
  margin: 0;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  font-size: 13px;
}
.ctx-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px;
  cursor: pointer;
  user-select: none;
  color: var(--color-text-primary);
}
.ctx-item:hover { background: var(--color-bg-hover); }
.ctx-item.danger { color: var(--color-danger); }
.ctx-sep { height: 1px; margin: 4px 0; background: var(--color-border-light); list-style: none; }
.ctx-item .el-icon { font-size: 14px; }

/* tags inline chip */
.session-tag-chip { margin-left: 2px; }
.session-tag-more { margin-left: 2px; opacity: 0.7; }
.pinned-mark { font-size: 10px; }

/* 同步状态徽章 */
.sync-badge {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; margin: 4px 8px;
  border-radius: 4px; font-size: 11px;
}
.sync-badge.sync-loading {
  background: rgba(64, 158, 255, 0.1);
  /* W98 a11y: 蓝底 0.1 alpha + --el-color-primary (#FF7A5C) 2.33 < AA 4.5.
     改用 rgb 数字深蓝 6.43 > AA 4.5. dark 主题接管 light-3. */
  color: rgb(32, 100, 168);
}
[data-theme="dark"] .sync-badge.sync-loading {
  color: var(--el-color-primary-light-3);
}
.sync-badge.sync-error {
  background: rgba(245, 108, 108, 0.1);
  /* W98 a11y fix: projects customizes --el-color-danger-light-3 to #f89898 (过浅,
     浅底对比度 1.91 < AA 4.5). 浅色主题下用 rgb() 数字字面量深红 rgb(118,41,41)
     (8.93 > AA 4.5) 避开 stylelint hex 禁用规则. dark 主题下让项目自定义的
     light-3 (#f89898) 接管 — dark 底上对比度 6.16. */
  color: rgb(118, 41, 41);
}
[data-theme="dark"] .sync-badge.sync-error {
  color: var(--el-color-danger-light-3);
}
.sync-icon { font-size: 12px; }
.sync-icon.rotating {
  display: inline-block;
  animation: mb-sync-rotate 1s linear infinite;
}
@keyframes mb-sync-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 同步状态小标记（session-title 右侧） */
.local-only-tag {
  display: inline-block; margin-left: 6px; padding: 0 4px;
  border-radius: 2px;
  background: var(--color-text-placeholder, #c0c4cc);
  color: var(--el-color-white);
  font-size: 9px; line-height: 14px; vertical-align: middle;
}
.synced-tag { margin-left: 6px; color: var(--el-color-success); font-size: 10px; vertical-align: middle; }
.error-tag { margin-left: 6px; font-size: 10px; vertical-align: middle; /* W98 a11y fix: 同 .sync-text, rgb(118,41,41) 深红 8.93 > AA 4.5, dark 主题接管 light-3. 用 rgb() 数字避开 stylelint hex 规则. */ color: rgb(118, 41, 41); }
[data-theme="dark"] .error-tag { color: var(--el-color-danger-light-3); }
</style>

<!-- v69 P1b fix-2 + v78 SessionSidebar dark 覆盖（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .session-sidebar {
  background: var(--color-bg-card);
  border-right-color: var(--color-border-base);
}
[data-theme="dark"] .sidebar-header {
  border-bottom-color: var(--color-border-light);
}
[data-theme="dark"] .session-item:hover {
  background: var(--color-primary-bg);
}
[data-theme="dark"] .session-item.active {
  background: var(--color-primary-bg);
}
[data-theme="dark"] .session-title { color: var(--color-text-primary); }
[data-theme="dark"] .session-meta { color: var(--color-text-secondary); }
[data-theme="dark"] .session-preview { color: var(--color-text-secondary); }
[data-theme="dark"] .empty { color: var(--color-text-secondary); }

/* v78 dark 模式覆盖（context menu） */
[data-theme="dark"] .session-context-menu {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .ctx-item { color: var(--color-text-primary); }
[data-theme="dark"] .ctx-item:hover { background: var(--color-bg-hover); }
[data-theme="dark"] .ctx-item.danger { color: var(--color-danger); }
[data-theme="dark"] .ctx-sep { background: var(--color-border-light); }

/* 同步状态 dark 模式 */
[data-theme="dark"] .sync-badge.sync-loading {
  background: rgba(64, 158, 255, 0.18);
  color: var(--el-color-primary-light-3);
}
[data-theme="dark"] .sync-badge.sync-error {
  background: rgba(245, 108, 108, 0.18);
  color: var(--el-color-danger-light-3);
}
[data-theme="dark"] .local-only-tag {
  background: var(--color-text-secondary, #909399);
}

/* W100 +28: dark 模式覆盖 (批量操作 + 分组) */
[data-theme="dark"] .session-group-header { color: var(--color-text-secondary); }
[data-theme="dark"] .batch-toggle-btn { color: var(--color-text-secondary); border-color: var(--color-border-light); }
[data-theme="dark"] .batch-toggle-btn:hover { background: var(--color-bg-hover); }
[data-theme="dark"] .batch-toggle-btn.active { background: var(--color-primary); color: white; border-color: var(--color-primary); }
[data-theme="dark"] .batch-mini-btn { color: var(--color-text-secondary); border-color: var(--color-border-light); }
[data-theme="dark"] .batch-action-bar { background: var(--color-bg-card); border-top-color: var(--color-border-light); }
[data-theme="dark"] .batch-action-btn { color: var(--color-text-primary); border-color: var(--color-border-light); }
[data-theme="dark"] .batch-action-btn:hover:not(:disabled) { background: var(--color-bg-hover); }
[data-theme="dark"] .batch-action-btn.danger { color: var(--color-danger); }
[data-theme="dark"] .session-item.selected { background: rgba(64, 158, 255, 0.15); }

/* ═══ 档案语言 (2026-09, A 方案): 虚线分隔 + mono 元数据 ═══ */
.session-item {
  border-radius: 0;
  border-bottom: 1px dashed var(--color-border-light, #dcdfe6);
}
.session-meta {
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 10px;
  letter-spacing: 0.06em;
}
</style>