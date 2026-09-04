<template>
  <!-- 移动端独立抽屉 — 在 el-container 外部，不受 Element Plus aside 样式影响 -->
  <Transition name="mobile-drawer">
    <div v-if="isMobile && showMobileMenu" class="mobile-drawer-root">
      <div class="mobile-drawer-mask" @click="showMobileMenu = false" />
      <div class="mobile-drawer-body">
        <div class="mobile-drawer-brand">
          <div class="mobile-drawer-logo">
            <el-icon size="24"><Aim /></el-icon>
          </div>
          <span>小气助手</span>
        </div>
        <div
          v-for="(item, index) in menuRoutes"
          :key="item.path"
          class="mobile-drawer-item"
          :class="{ active: currentRoute === item.path }"
          :style="{ '--i': index }"
          @click="navigateTo(item.path)"
        >
          <el-icon size="20"><component :is="iconMap[item.meta.icon]" /></el-icon>
          <span>{{ item.meta.title }}</span>
        </div>
      </div>
    </div>
  </Transition>

  <el-container class="layout-container">
    <!-- 桌面端侧边栏 — G 稿「控制台档案」皮肤 (docs/design-proposals/layout-2026-09/G-console.html)
         移动端完全不渲染; 换皮不换骨: 路由/折叠/录音状态全部沿用原有响应式, 可整段回到 el-menu 版 -->
    <el-aside
      v-if="!isMobile"
      :width="sidebarWidth"
      class="aside"
      :class="{ 'is-collapsed': isCollapse }"
    >
      <div class="brand">
        <div class="tile"><svg class="s"><use href="#i-aim" /></svg></div>
        <b v-show="!isCollapse" class="brand-name">小气助手</b>
        <span v-show="!isCollapse" class="ver">v26.09</span>
      </div>

      <nav class="menu">
        <template v-for="(group, gi) in menuGroups" :key="group.label">
          <div v-show="!isCollapse" class="taglabel">{{ group.label }}</div>
          <div v-show="isCollapse" v-if="gi > 0" class="gsep" aria-hidden="true"></div>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="'/' + item.path"
            class="mitem"
            :class="{ active: isActive(item.path) }"
            :title="isCollapse ? item.meta.title : undefined"
          >
            <svg class="s"><use :href="'#' + (iconId[item.meta.icon] || 'i-tag')" /></svg>
            <span v-show="!isCollapse" class="lab">{{ item.meta.title }}</span>
            <span
              v-if="!isCollapse && badgeOf(item.path)"
              class="cnt"
              :class="{ hot: item.path === 'meetings' }"
            >{{ badgeOf(item.path) }}</span>
          </router-link>
        </template>
      </nav>

      <!-- 侧边栏底部 - 项目动态: 档案印章卡 (G 稿升格, 原 .sidebar-bottom-item 平替)
           v31 检索质量已合并到此页 tab; W86 KB 监控合入其 TabStrip 第 3 tab -->
      <div class="sidefoot">
        <button
          type="button"
          class="stamp"
          :class="{ active: currentRoute === '/project-stats' }"
          @click="router.push('/project-stats')"
        >
          <svg class="s"><use href="#i-board" /></svg>
          <span v-show="!isCollapse" class="stamp-txt">
            <span class="t1">项目动态</span>
            <span class="t2">PROJECT STATS · {{ isoWeek }}</span>
          </span>
        </button>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部栏 — 移动端隐藏 (各移动视图自带 PageHeader/MobileHeader;
           主题切换/退出在「我的」设置页, 网盘通知在 Drive 页顶徽标) -->
      <el-header v-if="!isMobile" class="header">
        <div class="header-left">
          <!-- 2026-09-04 G 稿收口: 顶栏换「控制台档案」皮肤 (折叠把手/面包屑/mono 时刻牌/用户标本牌);
               移动端本 el-header 不渲染 (v-if), 各移动视图自带 MobileHeader, 未动 -->
          <span class="fold" role="button" tabindex="0" :title="isCollapse ? '展开导航' : '折叠导航'" @click="toggleSidebar">
            <el-icon><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
          </span>
          <div class="crumbs">
            <span class="home" role="button" tabindex="0" @click="router.push('/')">首页</span>
            <span class="sep">/</span>
            <b>{{ currentTitle }}</b>
          </div>
          <span class="tchip">{{ clockChip }}</span>
        </div>

        <div class="header-right">
          <NotificationBell />
          <ThemeToggleButton />

          <el-dropdown>
            <div class="uchip" role="button" tabindex="0" aria-label="用户菜单" :aria-expanded="false" aria-haspopup="menu">
              <img v-if="userAvatar" class="av img" :src="userAvatar" :alt="username" />
              <span v-else class="av">{{ username?.[0] || '?' }}</span>
              <div class="ud">
                <div class="un">{{ username }}</div>
                <div class="ur">{{ roleChip }}</div>
              </div>
              <svg class="s chev" aria-hidden="true"><use href="#i-chevron"/></svg>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/settings')">个人设置</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main :class="['main', { 'mobile-main': isMobile }]">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <!-- 全局浮动录音指示器 — 有会议正在录音时显示 -->
  <Transition name="recording-banner">
    <div
      v-if="recordingMeetingId"
      class="recording-indicator"
      :class="{ 'is-offline': !network.online.value }"
      role="status"
      aria-label="正在听会，点击返回"
      @click="goToRecording"
    >
      <span class="recording-dot" />
      <span class="recording-text">正在听会</span>
      <span v-if="!network.online.value" class="recording-warning" title="网络已断开，录音暂存本地">⚠</span>
      <span class="recording-title">{{ recordingMeetingTitle }}</span>
      <el-icon class="recording-arrow"><ArrowRight /></el-icon>
    </div>
  </Transition>

  <!-- 移动端底部导航 TabBar（PR #2 新增：基于 NutUI nut-tabbar）
       /chat 路由也显示 TabBar（在 input 框下方），用户偏好 persistent nav -->
  <MobileTabBar v-if="isMobile" />

  <!-- G 稿 16px 图标精灵: 全 app 挂载一次, <use href="#i-xxx"> 引用 -->
  <LayoutIconSprite />
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { useMemberStore } from '@/stores/member'
import { useRecordingState } from '@/composables/useRecordingState'
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { useIsMobile } from '@/composables/useIsMobile'
import MobileTabBar from '@/components/mobile/TabBar.vue'
// G 稿「控制台档案」16px 图标精灵 (MainLayout 挂载一次, 桌面侧栏 <use> 引用)
import LayoutIconSprite from '@/components/LayoutIconSprite.vue'
// v68 (2026-06-26): 桌面端顶栏主题切换按钮（与移动端 MobileHeader 风格一致）
import ThemeToggleButton from '@/components/ThemeToggleButton.vue'
// v2 PR6: 网盘协作通知 (@ 提醒 + 评论) + WS 推送
import NotificationBell from '@/components/common/NotificationBell.vue'
// 2026-07-12: 删除 Bell icon import (旧任务到期提醒铃铛已删除，统一走 NotificationBell)
// 2026-09-04 G 稿: 删除 DataBoard import (项目动态升格为档案印章, 桌面侧栏改走 LayoutIconSprite #i-board)
import { ArrowRight, Aim, Odometer, Cpu, ChatDotRound, List, VideoCamera, Folder, User, Document, Memo, Setting, Fold, Expand, Files } from '@element-plus/icons-vue'

// 侧边栏/面包屑路由 meta.icon 字符串 → 图标组件映射
// unplugin-vue-components 无法解析动态 <component :is="string">，必须显式 import
// v78: 删除 mic 别名 (声纹已合并到 /workspace 走 Files 图标)
// W86 mini batch 1: 删除 Odometer 别名 (KB 监控入口已合入项目动态 TabStrip, 不再走侧栏)
// 2026-09-03: W86 误删 Odometer — /dashboard meta.icon 仍是 Odometer, 侧栏图标空白;
//             同时补 Cpu (/dft meta.icon, 从未注册过). 删别名前必须 grep router meta.icon
const iconMap = {
  Odometer, Cpu,
  ChatDotRound, List, VideoCamera, Folder,
  User, Document, Memo, Setting, Files,
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const memberStore = useMemberStore()

// 全局录音状态
const { recordingMeetingId, recordingMeetingTitle, checkActiveRecording } = useRecordingState()
const network = useNetworkStatus()

const goToRecording = () => {
  if (recordingMeetingId.value) {
    router.push(`/meetings?resume=${recordingMeetingId.value}`)
  }
}

const isMobile = useIsMobile().isMobile
const isCollapse = ref(false)
const showMobileMenu = ref(false)

// /chat 路由不显示 TabBar（标准 mobile UX：聊天专注模式 + 避免覆盖 MobileInputBar）
const isChatRoute = computed(() => route.path.startsWith('/chat'))

const sidebarWidth = computed(() => {
  if (isMobile.value) return '0px'
  // G 稿: 260 → 240 (标本签分组后 9 项一屏尽收)
  return isCollapse.value ? '64px' : '240px'
})

const currentRoute = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '首页')
const username = computed(() => userStore.username)
const userRole = computed(() => userStore.userRole)
const userAvatar = computed(() => userStore.userInfo?.avatar || '')

// 2026-09-04 G 稿顶栏: mono 时刻牌 (NOW · HH:MM · WED, 20s tick) + 标本牌角色角标
const now = ref(new Date())
let _clockTimer = null
const _WD = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
const clockChip = computed(() => {
  const d = now.value
  return 'NOW · ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') + ' · ' + _WD[d.getDay()]
})
const roleChip = computed(() => ({ '管理员': 'ADMIN', '负责人': 'LEADER', '成员': 'MEMBER' }[userRole.value] || String(userRole.value || '').toUpperCase() || 'USER'))
onMounted(() => { _clockTimer = setInterval(() => { now.value = new Date() }, 20000) })
onBeforeUnmount(() => { if (_clockTimer) clearInterval(_clockTimer) })
// qa-bench v3.1 D5: KB 监控入口仅 admin/leader 可见 (raw role, 非展示名)
const isAdmin = computed(() => ['admin', 'leader'].includes(userStore.userInfo?.role))

const menuRoutes = computed(() => {
  const mainRoute = router.options.routes.find(r => r.path === '/')
  // 2026-07-02: PR7 反转后, drive/trash / drive/requests 在 FolderTree 内访问 (主侧边栏不再单独显示)
  const HIDDEN_PATHS = new Set(['drive/trash', 'drive/requests'])
  return (mainRoute?.children || []).filter(r => r.meta?.icon && !HIDDEN_PATHS.has(r.path))
})

// ===== G 稿「控制台档案」: 分组 / sprite 图标 / 计数徽标 =====
// 分组前端硬编码 (G 稿 notes 既定策略), 后续需要再提 route meta.group
const MENU_GROUPS = [
  { label: 'FRONT MATTER · 卷首', paths: ['dashboard'] },
  { label: 'RESEARCH · 研究', paths: ['tasks', 'meetings', 'knowledge', 'dft'] },
  { label: 'COLLAB · 协作', paths: ['chat', 'workspace', 'drive'] },
  { label: 'SYSTEM · 系统', paths: ['settings'] },
]
// meta.icon (EP 组件名字符串) → LayoutIconSprite symbol id
const iconId = {
  Odometer: 'i-gauge', ChatDotRound: 'i-chat', List: 'i-list',
  VideoCamera: 'i-camera', Files: 'i-files', Document: 'i-doc',
  Folder: 'i-folder', Setting: 'i-sliders', Cpu: 'i-cpu',
}
// 侧栏计数徽标 (轻量只读, 拉取失败静默不显示; 勿与 /dashboard/stats 页内数据混用)
const counts = ref({ tasksInProgress: null, knowledgeTotal: null })

const menuGroups = computed(() => {
  const routes = menuRoutes.value
  const used = new Set()
  const groups = MENU_GROUPS.map(g => ({
    label: g.label,
    items: g.paths.map(p => routes.find(r => r.path === p)).filter(Boolean)
      .filter(r => !used.has(r.path) && used.add(r.path)),
  }))
  // 未来新增带 icon 的路由兜底进末组 (SYSTEM), 不会从侧栏消失
  const rest = routes.filter(r => !used.has(r.path))
  if (rest.length) groups[groups.length - 1].items.push(...rest)
  return groups.filter(g => g.items.length)
})

const isActive = (path) => {
  const base = '/' + path
  return currentRoute.value === base || currentRoute.value.startsWith(base + '/')
}

const badgeOf = (path) => {
  if (path === 'dashboard') {
    return counts.value.tasksInProgress == null ? null : String(counts.value.tasksInProgress)
  }
  if (path === 'meetings') return recordingMeetingId.value ? '●REC' : null
  if (path === 'knowledge') {
    return counts.value.knowledgeTotal == null ? null : String(counts.value.knowledgeTotal)
  }
  return null
}

// 档案印章副标 WK36 — ISO 周号, 壳层每次加载算一次
const isoWeek = (() => {
  const d = new Date()
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7) + 3)
  const firstThu = new Date(d.getFullYear(), 0, 4)
  firstThu.setDate(firstThu.getDate() - ((firstThu.getDay() + 6) % 7) + 3)
  return 'WK' + (1 + Math.round((d - firstThu) / 604800000))
})()

// PR #2: isMobile 改用 useIsMobile composable（matchMedia + 防抖）
// 不再需要本地 onResize + window resize 监听
// 跨断点组件切换由 useAdaptiveRoute 自动处理

function syncMobileDrawerClose() {
  // 跨断点时强制关闭移动端抽屉
  if (isMobile.value) {
    showMobileMenu.value = false
  }
}

const toggleSidebar = () => {
  if (isMobile.value) {
    showMobileMenu.value = !showMobileMenu.value
  } else {
    isCollapse.value = !isCollapse.value
  }
}

const navigateTo = (path) => {
  showMobileMenu.value = false
  router.push('/' + path)
}

onMounted(async () => {
  userStore.loadFromStorage()

  // 未登录时不发起 API 请求，避免 401 刷屏
  const token = localStorage.getItem('access_token')
  if (!token) return

  memberStore.fetchMembers()
  checkActiveRecording()

  // G 稿侧栏计数徽标: 任务进行中 + 知识库条目 (只读统计, allSettled 静默降级)
  Promise.allSettled([
    axios.get('/api/v1/tasks/stats/overview'),
    axios.get('/api/v1/knowledge/stats'),
  ]).then(([t, k]) => {
    if (t.status === 'fulfilled') counts.value.tasksInProgress = t.value.data?.in_progress ?? null
    if (k.status === 'fulfilled') counts.value.knowledgeTotal = k.value.data?.total ?? null
  })

  // 刷新用户信息，获取新鲜头像 URL
  try {
    const res = await axios.get('/api/v1/auth/me')
    const fresh = res.data
    const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
    Object.assign(stored, fresh)
    localStorage.setItem('user_info', JSON.stringify(stored))
    userStore.loadFromStorage()
  } catch {
    // localStorage 兜底
  }
})

const handleLogout = () => {
  userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

/* ===== 桌面端侧边栏 — G 稿「控制台档案」皮肤 =====
   视觉源 docs/design-proposals/layout-2026-09/G-console.html;
   皮肤 token 局部化在 .aside 上, dark 覆盖在文件底部非 scoped 块 (v60-v67 教训) */
.aside {
  --dg-chrome: #eaece7;
  --dg-card: #fdfefc;
  --dg-ink: #16232a;
  --dg-steel: #5a6b6a;
  --dg-fog: #8ba0a0;
  --dg-hair: #c9d2ca;
  --dg-teal: #0e766e;
  --dg-teal-soft: #dcece5;
  --dg-coral: #ef7256;
  --dg-shadow: rgba(22, 35, 42, 0.14);
  --dg-hover: rgba(14, 118, 110, 0.07);
  --dg-mono: Consolas, 'Courier New', monospace;
  background: var(--dg-chrome);
  border-right: 1px solid var(--dg-hair);
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  overflow: hidden;
}

.aside .s {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  display: block;
}

.brand {
  height: 60px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px dashed var(--dg-hair);
}

.brand .tile {
  width: 32px;
  height: 32px;
  border: 1.5px solid var(--dg-ink);
  border-radius: 7px;
  display: grid;
  place-items: center;
  background: var(--dg-card);
  box-shadow: 2px 2px 0 var(--dg-shadow);
  color: var(--dg-ink);
  flex-shrink: 0;
}

.brand .tile .s { width: 18px; height: 18px; }

.brand-name {
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--dg-ink);
  white-space: nowrap;
}

.brand .ver {
  margin-left: auto;
  font-family: var(--dg-mono);
  font-size: 9px;
  color: var(--dg-fog);
}

nav.menu {
  flex: 1;
  overflow-y: auto;
  padding: 10px 10px 4px;
}

.taglabel {
  font-family: var(--dg-mono);
  font-size: 9px;
  letter-spacing: 0.24em;
  color: var(--dg-fog);
  padding: 10px 8px 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.taglabel::after {
  content: '';
  flex: 1;
  border-top: 1px dashed var(--dg-hair);
}

/* 折叠态分组分隔 (标本签隐藏) */
.gsep {
  border-top: 1px dashed var(--dg-hair);
  margin: 8px 12px;
}

.mitem {
  display: grid;
  grid-template-columns: 16px 1fr auto;
  align-items: center;
  gap: 9px;
  padding: 9px;
  margin-bottom: 2px;
  border-radius: 7px;
  border: 1px solid transparent;
  font-size: 13.5px;
  color: var(--dg-steel);
  cursor: pointer;
  position: relative;
  text-decoration: none;
}

.mitem .lab {
  grid-column: 2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mitem .cnt {
  grid-column: 3;
  font-family: var(--dg-mono);
  font-size: 10.5px;
  color: var(--dg-fog);
}

.mitem .cnt.hot {
  color: var(--dg-coral);
  font-weight: 700;
}

.mitem:hover {
  background: var(--dg-hover);
  color: var(--dg-ink);
}

.mitem.active {
  background: var(--dg-card);
  border-color: var(--dg-hair);
  color: var(--dg-ink);
  font-weight: 600;
  box-shadow: 2px 2px 0 var(--dg-shadow);
}

.mitem.active .s { color: var(--dg-teal); }

.mitem.active::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: var(--dg-teal);
  border-radius: 0 2px 2px 0;
}

/* 折叠态: 图标居中, 悬停出原生 title 提示 */
.el-aside.is-collapsed .mitem {
  grid-template-columns: 1fr;
  justify-items: center;
  padding: 11px 0;
}

.el-aside.is-collapsed .mitem.active::before { left: -10px; }

/* ===== 侧边栏底部 — 项目动态档案印章 ===== */
.sidefoot {
  flex-shrink: 0;
  border-top: 1px solid var(--dg-hair);
  padding: 10px;
}

.stamp {
  display: flex;
  gap: 9px;
  align-items: center;
  width: 100%;
  text-align: left;
  border: 1.5px dashed var(--dg-ink);
  border-radius: 8px;
  padding: 9px 10px;
  cursor: pointer;
  background: transparent;
  color: inherit;
  font-family: inherit;
}

.el-aside.is-collapsed .stamp {
  justify-content: center;
  padding: 9px 0;
}

.stamp:hover { background: var(--dg-card); }

.stamp.active {
  border-style: solid;
  border-color: var(--dg-teal);
  background: var(--dg-card);
}

.stamp .s { width: 17px; height: 17px; color: var(--dg-teal); }

.stamp-txt { display: flex; flex-direction: column; min-width: 0; }

.stamp .t1 {
  font-size: 13px;
  font-weight: 600;
  color: var(--dg-ink);
  white-space: nowrap;
}

.stamp .t2 {
  font-family: var(--dg-mono);
  font-size: 9px;
  color: var(--dg-fog);
  letter-spacing: 0.08em;
  white-space: nowrap;
}

/* ===== 顶部栏 ===== */
.header :deep(.el-avatar) {
  border-radius: var(--radius-lg);
}

/* ===== 桌面端顶栏 — G 稿「控制台档案」皮肤 =====
   视觉源 docs/design-proposals/layout-2026-09/G-console.html .topbar;
   --dg-* token 在 .aside 上不外泄, 此处 .header 局部重定义; dark 翻转走文件底部非 scoped 块 */
.header {
  --dg-card: #fdfefc;
  --dg-ink: #16232a;
  --dg-steel: #5a6b6a;
  --dg-fog: #8ba0a0;
  --dg-hair: #c9d2ca;
  --dg-teal: #0e766e;
  --dg-teal-soft: #dcece5;
  --dg-coral: #ef7256;
  --dg-mono: Consolas, 'Courier New', monospace;
  height: 60px;
  background: var(--dg-card);
  border-bottom: 1px solid var(--dg-hair);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.fold {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  color: var(--dg-steel);
  cursor: pointer;
  font-size: 17px;
}
.fold:hover { background: var(--dg-teal-soft); color: var(--dg-teal); }

.crumbs { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--dg-fog); }
.crumbs .home { cursor: pointer; }
.crumbs .home:hover { color: var(--dg-teal); }
.crumbs .sep { opacity: 0.5; }
.crumbs b { color: var(--dg-ink); font-weight: 600; }

.tchip {
  font-family: var(--dg-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--dg-steel);
  border: 1px solid var(--dg-hair);
  border-radius: 5px;
  padding: 4px 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 铃铛 → 32px util 方阵 (父 deep 覆盖子 scoped 样式);
   主题切换 2026-09-04 起为 E 案「昼夜滑轨」, 自持样式不再方阵化 */
.header-right :deep(.notification-bell-btn) {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  background: transparent;
  border-radius: 7px;
  color: var(--dg-steel);
  cursor: pointer;
  position: relative;
  transition: background 150ms ease, color 150ms ease;
}
.header-right :deep(.notification-bell-btn:hover) { background: var(--dg-teal-soft); color: var(--dg-teal); }

/* 用户标本牌 */
.uchip {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 5px 10px 5px 5px;
  margin-left: 4px;
  border: 1px solid var(--dg-hair);
  border-radius: 8px;
  cursor: pointer;
  color: var(--dg-ink);
}
.uchip:hover { background: var(--dg-teal-soft); }
.uchip .av {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--dg-ink);
  color: var(--dg-card);
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  object-fit: cover;
}
.uchip .ud { text-align: left; }
.uchip .un { font-size: 12.5px; font-weight: 600; line-height: 1.15; }
.uchip .ur { font-family: var(--dg-mono); font-size: 9px; color: var(--dg-fog); letter-spacing: 0.1em; }
.uchip .s { width: 12px; height: 12px; }
.uchip .chev { color: var(--dg-fog); }

.main {
  background-color: var(--color-bg-page);
  padding: 20px;
  overflow-y: auto;
}

.main.mobile-main {
  padding: 12px;
}

/* ===== 移动端独立抽屉 ===== */
.mobile-drawer-root {
  position: fixed;
  inset: 0;
  z-index: 3000;
}

.mobile-drawer-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
}

.mobile-drawer-body {
  position: absolute;
  top: 0;
  left: 0;
  width: 260px;
  height: 100%;
  background: var(--color-bg-card);
  overflow-y: auto;
  padding: 20px 12px;
  box-shadow: var(--shadow-sidebar);
}

.mobile-drawer-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 8px 20px;
  border-bottom: 1px solid #EBEEF5;
  margin-bottom: 8px;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.mobile-drawer-logo {
  width: 40px;
  height: 40px;
  background: var(--gradient-welcome-hero);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-bg-card);
  flex-shrink: 0;
}

.mobile-drawer-item {
  display: flex;
  align-items: center;
  gap: 14px;
  height: 52px;
  padding: 0 12px;
  margin: 4px 0;
  border-radius: 12px;
  color: var(--color-text-primary);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.mobile-drawer-item:active {
  background: rgba(var(--color-primary-rgb), 0.1);
}

.mobile-drawer-item.active {
  background: var(--color-primary);
  color: var(--color-bg-card);
}

/* ===== 移动端抽屉过渡动画 ===== */

/* --- 根容器淡入 --- */
.mobile-drawer-enter-active {
  transition: opacity 0.35s var(--ease-in-out);
}
.mobile-drawer-leave-active {
  transition: opacity 0.3s var(--ease-in);
}
.mobile-drawer-enter-from,
.mobile-drawer-leave-to {
  opacity: 0;
}

/* --- 遮罩：淡入 + backdrop-blur 渐变 --- */
.mobile-drawer-enter-active .mobile-drawer-mask {
  animation: drawer-mask-in 0.35s var(--ease-in-out) both;
}
.mobile-drawer-leave-active .mobile-drawer-mask {
  animation: drawer-mask-out 0.3s var(--ease-in) both;
}

@keyframes drawer-mask-in {
  from { opacity: 0; backdrop-filter: blur(0px); }
  to   { opacity: 1; backdrop-filter: blur(4px); }
}
@keyframes drawer-mask-out {
  from { opacity: 1; backdrop-filter: blur(4px); }
  to   { opacity: 0; backdrop-filter: blur(0px); }
}

/* --- 抽屉主体：弹性滑入 + 干脆滑出 --- */
.mobile-drawer-enter-active .mobile-drawer-body {
  animation: drawer-slide-in 0.4s var(--ease-bounce) both;
}
.mobile-drawer-leave-active .mobile-drawer-body {
  animation: drawer-slide-out 0.28s var(--ease-in) both;
}

@keyframes drawer-slide-in {
  from { transform: translateX(-100%); }
  to   { transform: translateX(0); }
}
@keyframes drawer-slide-out {
  from { transform: translateX(0); }
  to   { transform: translateX(-100%); }
}

/* --- 品牌区：logo 缩放弹出 + 文字淡入 --- */
.mobile-drawer-enter-active .mobile-drawer-logo {
  animation: logo-pop-in 0.4s var(--ease-bounce) both;
  animation-delay: 80ms;
}
.mobile-drawer-enter-active .mobile-drawer-brand span {
  animation: brand-text-in 0.3s var(--ease-out) both;
  animation-delay: 120ms;
}

@keyframes logo-pop-in {
  from { scale: 0; opacity: 0; }
  to   { scale: 1; opacity: 1; }
}
@keyframes brand-text-in {
  from { opacity: 0; transform: translateX(-8px); }
  to   { opacity: 1; transform: translateX(0); }
}

/* --- 菜单项：弹簧逐个弹出 + 反向退出 --- */
.mobile-drawer-enter-active .mobile-drawer-item {
  animation: drawer-item-in 0.45s var(--ease-bounce) both;
  animation-delay: calc(var(--i, 0) * 60ms + 180ms);
}
.mobile-drawer-leave-active .mobile-drawer-item {
  animation: drawer-item-out 0.2s ease-in both;
  animation-delay: calc((3 - var(--i, 0)) * 40ms);
}

@keyframes drawer-item-in {
  from { opacity: 0; transform: translateX(-16px) scale(0.9); }
  to   { opacity: 1; transform: translateX(0) scale(1); }
}
@keyframes drawer-item-out {
  from { opacity: 1; transform: translateX(0) scale(1); }
  to   { opacity: 0; transform: translateX(-16px) scale(0.95); }
}

/* --- 汉堡图标旋转过渡 --- */
.icon-swap-enter-active,
.icon-swap-leave-active {
  transition: var(--transition-all-slow) var(--ease-out);
}
.icon-swap-enter-from {
  opacity: 0;
  transform: rotate(-90deg) scale(0.6);
}
.icon-swap-leave-to {
  opacity: 0;
  transform: rotate(90deg) scale(0.6);
}

/* ===== 全局浮动录音指示器 ===== */
.recording-indicator {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2900;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-danger));
  color: var(--color-bg-card);
  border-radius: 50px;
  box-shadow: 0 4px 20px rgba(var(--color-primary-rgb), 0.4), 0 0 0 2px rgba(255, 255, 255, 0.2);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: var(--transition-all-normal) ease;
  backdrop-filter: blur(12px);
  user-select: none;
}

.recording-indicator:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(255, 107, 107, 0.5), 0 0 0 2px rgba(255, 255, 255, 0.3);
}

.recording-dot {
  width: 10px;
  height: 10px;
  background: var(--color-bg-card);
  border-radius: 50%;
  flex-shrink: 0;
  animation: var(--animation-recording-pulse);
}

.recording-text {
  white-space: nowrap;
}

/* 离线状态 — 胶囊变橙红色，加警告图标 */
.recording-indicator.is-offline {
  background: linear-gradient(135deg, var(--color-danger), var(--color-primary-light));
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.5);
}
.recording-indicator.is-offline:hover {
  box-shadow: 0 6px 24px rgba(245, 108, 108, 0.6), 0 0 0 2px rgba(255, 255, 255, 0.3);
}
.recording-warning {
  font-size: 14px;
  animation: recording-pulse 1s var(--ease-in-out) infinite;
}

.recording-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
  opacity: 0.9;
  font-weight: 500;
}

.recording-arrow {
  flex-shrink: 0;
  transition: transform 0.2s;
}

.recording-indicator:hover .recording-arrow {
  transform: translateX(3px);
}

/* 录音指示器入场/退场动画 */
.recording-banner-enter-active {
  animation: var(--animation-banner-in);
}
.recording-banner-leave-active {
  animation: var(--animation-banner-out);
}

/* 窄屏适配（PR #2 增强：考虑 TabBar + Safe Area） */
@media (max-width: 768px) {
  /* 主内容区底部预留 TabBar 高度 + safe-area */
  .mobile-main {
    /* 给底部 TabBar 留出空间 */
    padding-bottom: calc(var(--tabbar-height, 56px) + var(--sab, 0px));
  }

  /* 录音指示器在 TabBar 上方 */
  .recording-indicator {
    bottom: calc(var(--tabbar-height, 56px) + var(--sab, 0px) + 12px);
    right: 16px;
    left: 16px;
    padding: 14px 18px;
    justify-content: center;
  }
  .recording-title {
    max-width: 120px;
  }

  .brand-name {
    font-size: 18px;
  }

  .header {
    padding: 0 var(--mobile-padding-x, 16px);
  }

  .header-right {
    gap: 8px;
  }

}
</style>

<!-- v69 P0: MainLayout dark mode 覆盖（v60-v67 教训：dark 跨组件规则必须放非 scoped 块） -->
<style>
  /* === 侧边栏 (G 稿 dossier skin dark 覆盖, 对齐 shot-G 夜览态) === */
  [data-theme="dark"] .aside {
    --dg-chrome: #0c1215;
    --dg-card: #18232a;
    --dg-ink: #dfe9e6;
    --dg-steel: #9ab0ae;
    --dg-fog: #6b8286;
    --dg-hair: #27363e;
    --dg-teal: #35c2a4;
    --dg-teal-soft: #12312b;
    --dg-shadow: rgba(0, 0, 0, 0.5);
    --dg-hover: rgba(53, 194, 164, 0.08);
    background: var(--dg-chrome);
    border-right-color: var(--dg-hair);
    box-shadow: none;
  }
  [data-theme="dark"] .brand .tile { color: var(--dg-ink); }
  [data-theme="dark"] .mitem.active { background: var(--dg-card); color: var(--dg-ink); }
  [data-theme="dark"] .stamp:hover,
  [data-theme="dark"] .stamp.active { background: var(--dg-card); }
  [data-theme="dark"] .stamp .t1 { color: var(--dg-ink); }

  /* === 顶栏 (G 稿 dark 翻转, 与 .aside 色板同源; 后置声明压过 scoped 同名 token) === */
  [data-theme="dark"] .header {
    --dg-card: #18232a;
    --dg-ink: #dfe9e6;
    --dg-steel: #9ab0ae;
    --dg-fog: #6b8286;
    --dg-hair: #27363e;
    --dg-teal: #35c2a4;
    --dg-teal-soft: #12312b;
    background: var(--dg-card);
    border-bottom-color: var(--dg-hair);
  }
  [data-theme="dark"] .header .fold { color: var(--dg-steel); }
  [data-theme="dark"] .header .crumbs b { color: var(--dg-ink); }
  [data-theme="dark"] .header .uchip { color: var(--dg-ink); }

  /* === 录音 banner + 浮动胶囊 === */
  [data-theme="dark"] .recording-banner,
  [data-theme="dark"] .global-recorder-pulse {
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-base);
    color: var(--color-text-primary);
  }

  /* === 移动端 drawer === */
  [data-theme="dark"] .mobile-drawer { background: var(--color-bg-card) !important; }
</style>
