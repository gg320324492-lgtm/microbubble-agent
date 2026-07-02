<template>
  <div class="project-stats-view">
    <!-- 标题区 -->
    <div class="page-header fade-slide-up">
      <h1 class="page-title">🚀 项目动态</h1>
      <p class="page-subtitle">项目从建立至今的全历程开发信息</p>
    </div>

    <!-- 铁律 31: tab 统一用 <TabStrip> -->
    <div class="tab-strip-wrapper">
      <TabStrip v-model="activeTab" :items="tabItems" aria-label="项目动态视图切换" />
    </div>

    <!-- Tab 1: 项目历程 (原内容) -->
    <div v-show="activeTab === 'overview'" role="tabpanel"
      :aria-labelledby="`tab-strip-overview`" class="tab-panel">
        <!-- 项目体量 -->
        <el-card class="stats-card fade-slide-up stagger-1" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <span class="card-icon">📊</span>
            项目体量
          </span>
        </div>
      </template>
      <div class="stats-grid">
        <div class="stat-box">
          <div class="stat-value" :ref="el => animateNumber(el, stats.total_lines, 'total_lines')">0</div>
          <div class="stat-label">行代码</div>
        </div>
        <div class="stat-box">
          <div class="stat-value" :ref="el => animateNumber(el, stats.total_commits, 'total_commits')">0</div>
          <div class="stat-label">次提交</div>
        </div>
        <div class="stat-box">
          <div class="stat-value" :ref="el => animateNumber(el, stats.dev_days, 'dev_days')">0</div>
          <div class="stat-label">开发天数</div>
        </div>
        <div class="stat-box">
          <div class="stat-value" :ref="el => animateNumber(el, stats.total_files, 'total_files')">0</div>
          <div class="stat-label">个文件</div>
        </div>
      </div>
    </el-card>

    <!-- 代码分布 -->
    <el-card v-if="codeBreakdown.length > 0" class="stats-card fade-slide-up stagger-2" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <span class="card-icon">📝</span>
            代码分布
          </span>
          <el-tag type="info" size="small">12 类文件</el-tag>
        </div>
      </template>
      <div class="code-breakdown">
        <div v-for="lang in codeBreakdown" :key="lang.key" class="lang-row">
          <div class="lang-info">
            <span class="lang-icon">{{ lang.icon }}</span>
            <span class="lang-name">{{ lang.label }}</span>
            <span class="lang-lines">{{ lang.lines.toLocaleString() }} 行</span>
            <span class="lang-files">{{ lang.files }} 文件</span>
          </div>
          <div class="lang-bar-track">
            <div
              class="lang-bar-fill"
              :style="{ width: lang.percent + '%', background: lang.color }"
            ></div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 已解决痛点 -->
    <el-card class="stats-card fade-slide-up stagger-2" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <span class="card-icon">🔧</span>
            已解决痛点
          </span>
        </div>
      </template>
      <div class="pain-points-grid">
        <div v-for="group in data.pain_points" :key="group.category" class="pain-group-card">
          <div class="pain-group-header">
            <span class="pain-icon">{{ group.icon }}</span>
            <span class="pain-category">{{ group.category }}</span>
          </div>
          <ul class="pain-list">
            <li v-for="item in group.items" :key="item" class="pain-item">
              {{ item }}
            </li>
          </ul>
        </div>
      </div>
    </el-card>

    <!-- 待做事项 -->
    <el-card class="stats-card fade-slide-up stagger-3" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <span class="card-icon">🔜</span>
            待做事项
          </span>
        </div>
      </template>
      <div class="todos-grid">
        <div v-for="todo in data.todos" :key="todo.id" class="todo-card">
          <div class="todo-header">
            <span class="todo-phase">Phase {{ todo.id }}</span>
            <el-tag
              :type="todo.priority === '高' ? 'danger' : todo.priority === '中' ? 'warning' : 'info'"
              size="small"
            >
              {{ todo.priority }}
            </el-tag>
          </div>
          <div class="todo-name">{{ todo.name }}</div>
          <div class="todo-cycle">{{ todo.cycle }}</div>
        </div>
      </div>
    </el-card>

    <!-- 更新日志 -->
    <el-card class="stats-card fade-slide-up stagger-4" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <span class="card-icon">📅</span>
            更新日志
          </span>
          <el-tag type="info" size="small">{{ data.changelog.length }} 条记录</el-tag>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="log in data.changelog"
          :key="log.date + log.title"
          :timestamp="log.date"
          placement="top"
          :type="getTimelineType(log.tag)"
        >
          <div class="log-content">
            <div class="log-title">{{ log.title }}</div>
            <div class="log-meta">
              <el-tag :type="getTagType(log.tag)" size="small">{{ log.tag }}</el-tag>
              <span class="log-pain">{{ log.pain_point }}</span>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>
      </div>

    <!-- Tab 2: 检索质量监控 (v31) — 嵌入 AnalyticsView 组件 -->
    <div v-show="activeTab === 'analytics'" role="tabpanel"
      :aria-labelledby="`tab-strip-analytics`" class="tab-panel">
      <AnalyticsView />
    </div>

    <!-- Tab 3: KB 入库监控 (W6 D5) — polling 5min 自动刷新 -->
    <div v-show="activeTab === 'kb_monitor'" role="tabpanel"
      :aria-labelledby="`tab-strip-kb_monitor`" class="tab-panel">
      <el-card class="stats-card fade-slide-up" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="card-title">
              <span class="card-icon">📚</span>
              KB 自动入库实时监控
              <el-tag v-if="kbLoading" type="info" size="small" effect="plain" style="margin-left: 8px">
                <el-icon class="is-loading"><Loading /></el-icon> 刷新中
              </el-tag>
            </span>
            <div class="header-actions">
              <el-button size="small" @click="refreshKb" :icon="Refresh">手动刷新</el-button>
            </div>
          </div>
        </template>

        <!-- 错误提示 -->
        <el-alert v-if="kbError" type="warning" :title="'加载失败: ' + kbError" :closable="false" show-icon />

        <!-- 4 张统计卡 + 1 张趋势图 -->
        <el-row :gutter="20" v-if="summary">
          <el-col :span="6">
            <el-card class="metric-card" shadow="never">
              <div class="metric-label">📊 今日入库</div>
              <div class="metric-value">{{ summary.today_intake || 0 }} <span class="metric-unit">条</span></div>
              <div class="metric-sub">总 {{ summary.total_in_db || 0 }} 条</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="metric-card" shadow="never">
              <div class="metric-label">📈 7日入库</div>
              <div class="metric-value">{{ weeklyIntakeTotal }} <span class="metric-unit">条</span></div>
              <div class="metric-sub">日均 {{ Math.round(weeklyIntakeTotal / 7 * 10) / 10 }} 条</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="metric-card" shadow="never">
              <div class="metric-label">🎯 KB 命中率</div>
              <div class="metric-value">{{ hitRatePct }}<span class="metric-unit">%</span></div>
              <div class="metric-sub">待 W6 反馈模块接入</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="metric-card" shadow="never">
              <div class="metric-label">⚠️ 负反馈率</div>
              <div class="metric-value">{{ negFeedbackPct }}<span class="metric-unit">%</span></div>
              <div class="metric-sub">健康 ({{ negFeedbackPct < 10 ? '✅' : '⚠️' }})</div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 7日趋势 + rollback 警告 + 灰度状态 -->
        <el-row :gutter="20" v-if="summary" style="margin-top: 20px">
          <el-col :span="14">
            <el-card class="trend-card" shadow="never">
              <template #header>
                <div class="trend-header">
                  <span>📊 7日入库趋势 (近 7 天)</span>
                  <span v-if="weeklyIntakeTotal === 0" class="trend-empty-hint">
                    等待数据中...
                  </span>
                </div>
              </template>
              <!-- W6 D5 改进: 全 0 时显示 empty placeholder, 避免 7 个 0px bar 视觉混乱 -->
              <el-empty
                v-if="weeklyIntakeTotal === 0"
                description="近 7 天暂无 KB 入库记录"
                :image-size="80"
              />
              <div v-else class="trend-bars">
                <div
                  v-for="(count, idx) in (summary.weekly_intake || [0,0,0,0,0,0,0])"
                  :key="idx"
                  class="trend-bar-wrapper"
                >
                  <div class="trend-bar-value">{{ count }}</div>
                  <div
                    class="trend-bar"
                    :class="{ 'trend-bar-zero': count === 0 }"
                    :style="{ height: Math.max(6, count / Math.max(...summary.weekly_intake) * 100) + 'px' }"
                  ></div>
                  <div
                    class="trend-bar-day"
                    :class="{ 'trend-bar-day-today': idx === 6 }"
                  >{{ ['昨7','昨6','昨5','昨4','昨3','昨2','今日'][idx] }}</div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="10">
            <el-card class="status-card" shadow="never">
              <template #header>
                <span>🔄 系统状态</span>
              </template>
              <div class="status-item">
                <span class="status-label">灰度开关:</span>
                <el-tag :type="summary.gray_scale_enabled === 0 ? 'info' : 'success'" size="default">
                  {{ grayScaleLabel }}
                </el-tag>
              </div>
              <div class="status-item">
                <span class="status-label">7日 rollback:</span>
                <el-tag :type="(summary.rollback_count || 0) > 0 ? 'danger' : 'success'" size="default">
                  {{ summary.rollback_count || 0 }} 条
                </el-tag>
              </div>
              <div class="status-item">
                <span class="status-label">刷新机制:</span>
                <el-tag type="info" size="default">polling 5min</el-tag>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 空状态 -->
        <el-empty v-if="!summary && !kbLoading" description="暂无数据" />
      </el-card>
    </div>

    <!-- Tab 4: 审计日志 (admin only, v2 PR7) — v78 合并到项目动态, admin 守卫 -->
    <div v-show="activeTab === 'audit' && isAdmin" role="tabpanel"
      :aria-labelledby="`tab-strip-audit`" class="tab-panel">
      <AuditLogView v-if="isAdmin" />
      <el-empty v-else description="仅管理员可查看审计日志" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { Loading, Refresh, DataLine, Histogram, Folder, Document } from '@element-plus/icons-vue'
import changelogData from '@/data/changelog.json'
import AnalyticsView from '@/views/admin/AnalyticsView.vue'  // v31 检索质量监控
import AuditLogView from '@/views/admin/AuditLogView.vue'  // v2 PR7 审计日志 (admin only)
import { useKbMonitor } from '@/composables/useKbMonitor'  // W6 D5 KB 入库监控
import { useUserStore } from '@/stores/user'  // v78 admin 守卫
import TabStrip from '@/components/common/TabStrip.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.isAdmin)

// 铁律 29: URL ?tab= 同步双向（VALID_TABS 白名单 + watch + replace）
const VALID_TABS = ['overview', 'analytics', 'kb_monitor', 'audit']
const activeTab = ref(
  route.query.tab && VALID_TABS.includes(String(route.query.tab))
    ? String(route.query.tab)
    : 'overview'
)

// 铁律 30: EP 图标 named import + 通过 props 传入
// audit tab 仅 admin 可见, computed 过滤
const tabItems = computed(() => {
  const items = [
    { key: 'overview',   label: '项目历程',     icon: DataLine },
    { key: 'analytics',  label: '检索质量',     icon: Histogram },
    { key: 'kb_monitor', label: 'KB 入库监控',  icon: Folder },
  ]
  if (isAdmin.value) items.push({ key: 'audit', label: '审计日志', icon: Document })
  return items
})

// v31 tab 切换: 'overview' = 项目历程, 'analytics' = 检索质量
// W6 D5: 'kb_monitor' = KB 入库监控 (polling 5min 自动刷新)
// v78: 'audit' = 审计日志 (admin only)
const { summary, lastUpdate, error: kbError, loading: kbLoading, refresh: refreshKb } = useKbMonitor()

// KB 入库监控 - 计算属性
const weeklyIntakeTotal = computed(() => {
  if (!summary.value?.weekly_intake) return 0
  return summary.value.weekly_intake.reduce((a, b) => a + b, 0)
})

const hitRatePct = computed(() => {
  return Math.round((summary.value?.hit_rate || 0) * 100)
})

const negFeedbackPct = computed(() => {
  return Math.round((summary.value?.negative_feedback_rate || 0) * 100)
})

const grayScaleLabel = computed(() => {
  const v = summary.value?.gray_scale_enabled ?? 0
  if (v === 0) return '未开启'
  if (v === 5) return '5% (灰度初期)'
  if (v === 25) return '25% (灰度中期)'
  if (v === 100) return '100% (全量)'
  return `${v}%`
})

const lastUpdateStr = computed(() => {
  if (!lastUpdate.value) return '从未更新'
  const d = lastUpdate.value
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
})

const data = ref(changelogData)
const stats = ref({
  total_lines: 0,
  total_commits: 0,
  dev_days: 0,
  total_files: 0,
  lines_by_type: {},
  files_by_type: {}
})
const showAllLogs = ref(false)

// 语言元数据定义
const LANG_META = {
  python:     { label: 'Python',     icon: '🐍', color: '#3572A5' },
  vue:        { label: 'Vue',        icon: '🟢', color: '#41B883' },
  javascript: { label: 'JavaScript', icon: '🟨', color: '#F7DF1E' },
  typescript: { label: 'TypeScript', icon: '🔷', color: '#3178C6' },
  css:        { label: 'CSS',        icon: '🎨', color: '#E34F26' },
  html:       { label: 'HTML',       icon: '📄', color: '#E34F26' },
  markdown:   { label: 'Markdown',   icon: '📝', color: '#6B7280' },
  shell:      { label: 'Shell',      icon: '💻', color: '#4EAA25' },
  config:     { label: 'Config',     icon: '⚙️',  color: '#8B5CF6' },
  sql:        { label: 'SQL',        icon: '🗄️',  color: '#00758F' },
  docker:     { label: 'Docker',     icon: '🐳', color: '#2496ED' },
  other:      { label: 'Other',      icon: '📦', color: '#9CA3AF' }
}

// 代码分布计算
const codeBreakdown = computed(() => {
  const linesByType = stats.value.lines_by_type
  const filesByType = stats.value.files_by_type
  if (!linesByType) return []

  const maxLines = Math.max(1, ...Object.values(linesByType))
  const result = Object.entries(LANG_META)
    .filter(([key]) => (linesByType[key] || 0) > 0)
    .map(([key, meta]) => ({
      key,
      ...meta,
      lines: linesByType[key] || 0,
      files: (filesByType && filesByType[key]) || 0,
      percent: Math.round(((linesByType[key] || 0) / maxLines) * 100)
    }))
    .sort((a, b) => b.lines - a.lines)
  return result
})

// 数字动画状态
const animatedValues = ref({
  total_lines: 0,
  total_commits: 0,
  dev_days: 0,
  total_files: 0
})
const animationStarted = ref({
  total_lines: false,
  total_commits: false,
  dev_days: false,
  total_files: false
})

// 数字计数器动画
const animateNumber = (el, target, key) => {
  if (!el || target === undefined || target === null) return
  if (animationStarted.value[key]) return

  const targetNum = Number(target)
  if (isNaN(targetNum) || targetNum === 0) {
    el.textContent = '0'
    return
  }

  animationStarted.value[key] = true
  const duration = 1500
  const startTime = performance.now()

  const animate = (currentTime) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    // easeOutExpo 缓动函数，数字增长越来越快，最后骤停
    const eased = 1 - Math.pow(2, -10 * progress)
    el.textContent = Math.round(eased * targetNum).toLocaleString()
    if (progress < 1) {
      requestAnimationFrame(animate)
    } else {
      el.textContent = targetNum.toLocaleString()
    }
  }
  requestAnimationFrame(animate)
}

const formatNumber = (num) => {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString()
}

const getTagType = (tag) => {
  const types = {
    '功能': 'primary',
    '修复': 'danger',
    '优化': 'success',
    '安全': 'warning'
  }
  return types[tag] || 'info'
}

const getTimelineType = (tag) => {
  const types = {
    '功能': 'primary',
    '修复': 'danger',
    '优化': 'success',
    '安全': 'warning'
  }
  return types[tag] || 'primary'
}

// 铁律 29: tab → URL 同步（router.replace 不污染 history, 合并其他 query）
watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})

// 铁律 29: URL → tab 反向同步（浏览器前进/后退）
watch(() => route.query.tab, (t) => {
  if (t && VALID_TABS.includes(String(t)) && String(t) !== activeTab.value) {
    activeTab.value = String(t)
  }
})

onMounted(async () => {
  try {
    const res = await axios.get('/api/v1/dashboard/project-stats')
    stats.value = res.data
  } catch (e) {
    console.error('获取项目统计失败:', e)
  }
})
</script>

<style scoped>
.project-stats-view {
  max-width: 1200px;
  padding-bottom: 30px;
}

/* 铁律 31: tab-strip-wrapper + tab-panel 容器 */
.tab-strip-wrapper {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}
.tab-panel {
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

/* 页面标题 */
.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin: 0 0 8px 0;
}

.page-subtitle {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: 0;
}

/* 卡片 */
.stats-card {
  border-radius: var(--radius-lg);
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-md);
}

.card-icon {
  font-size: 18px;
}

/* 体量统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-box {
  text-align: center;
  padding: 24px 16px;
  background: var(--color-bg-warm);
  border-radius: var(--radius-lg);
  transition: transform var(--duration-normal) var(--ease-out);
}

.stat-box:hover {
  transform: translateY(-4px);
}

.stat-value {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: 8px;
}

/* 痛点网格 */
.pain-points-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.pain-group-card {
  background: var(--color-bg-warm);
  border-radius: var(--radius-lg);
  padding: 16px;
  transition: transform var(--duration-normal) var(--ease-out);
}

.pain-group-card:hover {
  transform: translateY(-2px);
}

.pain-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.pain-icon {
  font-size: 20px;
}

.pain-category {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.pain-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.pain-item {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  padding: 4px 0;
  border-bottom: 1px dashed var(--color-border);
}

.pain-item:last-child {
  border-bottom: none;
}

/* 待做事项网格 */
.todos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.todo-card {
  background: var(--color-bg-warm);
  border-radius: var(--radius-lg);
  padding: 16px;
  transition: transform var(--duration-normal) var(--ease-out);
}

.todo-card:hover {
  transform: translateY(-2px);
}

.todo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.todo-phase {
  font-size: var(--font-size-sm);
  color: var(--color-text-placeholder);
  font-weight: var(--font-weight-medium);
}

.todo-name {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.todo-cycle {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

/* 代码分布 */
.code-breakdown {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.lang-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.lang-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.lang-icon {
  font-size: 18px;
  width: 28px;
  text-align: center;
  flex-shrink: 0;
}

.lang-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  min-width: 80px;
}

.lang-lines {
  font-size: var(--font-size-sm);
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
  min-width: 80px;
}

.lang-files {
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
  margin-left: auto;
}

.lang-bar-track {
  width: 100%;
  height: 10px;
  background: var(--color-border-light);
  border-radius: 5px;
  overflow: hidden;
}

.lang-bar-fill {
  height: 100%;
  border-radius: 5px;
  transition: width 1.2s var(--ease-bounce);
  min-width: 4px;
}

/* 更新日志 */
.log-content {
  padding: 4px 0;
}

.log-title {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
  margin-bottom: 8px;
}

.log-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* v76.6 fix: 更新日志 el-tag 文字加深 + 字重 700 + 边框加粗
   原因: EP el-tag default effect = 浅色背景 (--el-color-primary-light-9 ≈ #FDF2EF)
   + 主色文字 (--el-color-primary). 在 6 主题下 coral/ocean/forest 文字都是中亮色,
   浅背景+中亮文字对比度仅 ~2.5:1, 不到 WCAG AA 4.5:1.
   修法: scoped 强制覆盖 text-color 用 EP 自带 dark 变体 + 字重 700 + 边框 2px.
   兼容 6 主题: --el-color-*-dark-2 在 6 主题全定义, 不需写 6 套. */
.log-meta .el-tag {
  font-weight: 700 !important;
  border-width: 2px !important;
}

.log-meta .el-tag.el-tag--primary {
  --el-tag-text-color: var(--el-color-primary-dark-2);
}

.log-meta .el-tag.el-tag--success {
  --el-tag-text-color: var(--el-color-success-dark-2);
}

.log-meta .el-tag.el-tag--danger {
  --el-tag-text-color: var(--el-color-danger-dark-2);
}

.log-meta .el-tag.el-tag--warning {
  --el-tag-text-color: var(--el-color-warning-dark-2);
}

.log-meta .el-tag.el-tag--info {
  --el-tag-text-color: var(--el-color-info-dark-2);
}

.log-pain {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* 响应式 */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .pain-points-grid {
    grid-template-columns: 1fr;
  }

  .todos-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* W6 D5: KB 入库监控 tab 样式 */
.kb-monitor-tab {
  /* metric card 4 列 */
  .metric-card {
    background: var(--color-bg-card);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }
  .metric-label {
    font-size: 13px;
    color: var(--color-text-secondary);
    margin-bottom: 8px;
  }
  .metric-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--color-primary);
    line-height: 1.2;
  }
  .metric-unit {
    font-size: 14px;
    font-weight: 400;
    color: var(--color-text-secondary);
  }
  .metric-sub {
    font-size: 11px;
    color: var(--color-text-secondary);
    margin-top: 4px;
  }
  .trend-card,
  .status-card {
    background: var(--color-bg-card);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 16px;
  }
  .trend-bars {
    display: flex;
    align-items: flex-end;
    justify-content: space-around;
    height: 180px;
    padding: 12px 0;
    gap: 8px;
  }
  .trend-bar-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    min-width: 40px;
  }
  .trend-bar-value {
    font-size: 12px;
    color: var(--color-text-secondary);
    margin-bottom: 4px;
    font-weight: 600;
  }
  .trend-bar {
    width: 100%;
    max-width: 48px;
    background: linear-gradient(180deg, var(--color-primary) 0%, var(--color-accent) 100%);
    border-radius: 4px 4px 0 0;
    transition: height 0.3s ease;
  }
  .trend-bar-zero {
    background: var(--color-border);  /* W6 D5 改进: 0 时用灰色, 视觉上区别"有数据" vs "全 0" */
    opacity: 0.3;
  }
  .trend-bar-day {
    font-size: 11px;
    color: var(--color-text-secondary);
    margin-top: 4px;
  }
  .trend-bar-day-today {
    color: var(--color-primary);  /* 突出"今日" */
    font-weight: 600;
  }
  .trend-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }
  .trend-empty-hint {
    font-size: 12px;
    color: var(--color-text-secondary);
    font-style: italic;
  }
  .status-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid var(--color-border);
  }
  .status-item:last-child {
    border-bottom: none;
  }
  .status-label {
    color: var(--color-text-secondary);
    font-size: 14px;
  }
  .header-actions {
    margin-left: auto;
  }
}
</style>
