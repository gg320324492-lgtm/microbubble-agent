<template>
  <!-- 折叠态：仅显示图标 -->
  <div v-if="collapsed" class="stats-collapsed" title="项目动态">
    <el-icon size="20"><DataBoard /></el-icon>
  </div>

  <!-- 展开态：标题 + 点击展开弹窗 -->
  <div v-else class="stats-wrapper">
    <div class="stats-title-bar" @click="showDialog = true">
      <span class="stats-title">🚀 项目动态</span>
      <el-icon class="stats-arrow"><ArrowRight /></el-icon>
    </div>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="showDialog"
      title="🚀 项目动态"
      width="400px"
      :append-to-body="true"
      :lock-scroll="true"
      class="stats-dialog"
    >
      <div class="stats-content">
        <!-- 项目体量 -->
        <div class="stats-card">
          <div class="card-title">📊 项目体量</div>
          <div class="card-divider"></div>
          <div class="stat-item">
            <span class="stat-icon">📝</span>
            <span class="stat-text">{{ formatNumber(stats.total_lines) }} 行代码</span>
          </div>
          <div class="stat-item">
            <span class="stat-icon">🔀</span>
            <span class="stat-text">{{ formatNumber(stats.total_commits) }} 次提交</span>
          </div>
          <div class="stat-item">
            <span class="stat-icon">⏱️</span>
            <span class="stat-text">开发 {{ stats.dev_days }} 天</span>
          </div>
          <div class="stat-item">
            <span class="stat-icon">📁</span>
            <span class="stat-text">{{ formatNumber(stats.total_files) }} 个文件</span>
          </div>
        </div>

        <!-- 已解决痛点 -->
        <div class="stats-card">
          <div class="card-title">🔧 已解决痛点</div>
          <div class="card-divider"></div>
          <div v-for="group in data.pain_points" :key="group.category" class="pain-group">
            <div class="pain-header">
              <span class="pain-icon">{{ group.icon }}</span>
              <span class="pain-category">{{ group.category }}</span>
            </div>
            <ul class="pain-list">
              <li v-for="item in group.items" :key="item" class="pain-item">
                · {{ item }}
              </li>
            </ul>
          </div>
        </div>

        <!-- 待做事项 -->
        <div class="stats-card">
          <div class="card-title">🔜 待做事项</div>
          <div class="card-divider"></div>
          <div v-for="todo in data.todos" :key="todo.id" class="todo-item">
            <span class="todo-phase">Phase {{ todo.id }}</span>
            <span class="todo-name">{{ todo.name }}</span>
          </div>
        </div>

        <!-- 更新日志 -->
        <div class="stats-card">
          <div class="card-title">📅 更新日志</div>
          <div class="card-divider"></div>
          <div
            v-for="(log, index) in displayedLogs"
            :key="log.date + log.title"
            class="log-item"
          >
            <span class="log-date">{{ formatDate(log.date) }}</span>
            <span class="log-title">{{ log.title }}</span>
          </div>
          <div
            v-if="data.changelog.length > 5"
            class="log-toggle"
            @click="showAll = !showAll"
          >
            {{ showAll ? '收起' : '查看全部 →' }}
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import changelogData from '@/data/changelog.json'
import { DataBoard, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  collapsed: {
    type: Boolean,
    default: false
  }
})

const data = ref(changelogData)
const stats = ref({
  total_lines: 0,
  total_commits: 0,
  dev_days: 0,
  total_files: 0
})
const showAll = ref(false)
const showDialog = ref(false)

const displayedLogs = computed(() => {
  if (showAll.value) {
    return data.value.changelog
  }
  return data.value.changelog.slice(0, 5)
})

const formatNumber = (num) => {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString()
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  if (parts.length === 3) {
    return `${parts[1]}-${parts[2]}`
  }
  return dateStr
}

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
/* 折叠态 */
.stats-collapsed {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: color var(--duration-fast) var(--ease-out);
}
.stats-collapsed:hover {
  color: var(--color-primary);
}

/* 展开态 */
.stats-wrapper {
  padding: 8px;
}

.stats-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: background var(--duration-fast) var(--ease-out);
}

.stats-title-bar:hover {
  background: rgba(255, 122, 92, 0.1);
}

.stats-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.stats-arrow {
  font-size: 12px;
  color: var(--color-text-secondary);
  transition: transform var(--duration-fast) var(--ease-out);
}

.stats-title-bar:hover .stats-arrow {
  transform: translateX(2px);
  color: var(--color-primary);
}

/* 弹窗内容 */
.stats-content {
  max-height: 60vh;
  overflow-y: auto;
}

/* 卡片 */
.stats-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 12px;
  margin-bottom: 10px;
}

.stats-card:last-child {
  margin-bottom: 0;
}

.card-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.card-divider {
  height: 1px;
  background: var(--color-border);
  margin-bottom: 8px;
}

/* 体量指标 */
.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.stat-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.stat-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* 痛点 */
.pain-group {
  margin-bottom: 10px;
}

.pain-group:last-child {
  margin-bottom: 0;
}

.pain-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.pain-icon {
  font-size: 14px;
}

.pain-category {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
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
  padding: 2px 0 2px 26px;
  line-height: 1.4;
}

/* 待做事项 */
.todo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.todo-phase {
  font-size: var(--font-size-sm);
  color: var(--color-text-placeholder);
  min-width: 60px;
}

.todo-name {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* 更新日志 */
.log-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 0;
}

.log-date {
  font-size: var(--font-size-sm);
  color: var(--color-text-placeholder);
  min-width: 45px;
  flex-shrink: 0;
}

.log-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-toggle {
  font-size: var(--font-size-sm);
  color: var(--color-primary);
  cursor: pointer;
  padding: 8px 0 0;
  text-align: center;
}

.log-toggle:hover {
  text-decoration: underline;
}
</style>
