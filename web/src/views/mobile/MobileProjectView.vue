<template>
  <div class="mobile-project-view">
    <PageHeader title="项目管理" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="项目动态"
          title="项目动态"
          @click="$router.push('/project-stats')"
        >📊</button>
        <button
          type="button"
          class="header-action primary"
          aria-label="新建"
          title="新建"
          @click="showCreate = true"
        >+</button>
      </template>
    </PageHeader>

    <main
      class="project-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 状态快速筛选 -->
      <div class="status-chips">
        <button
          v-for="s in statusFilters"
          :key="s.value"
          type="button"
          class="status-chip"
          :class="{ active: activeStatus === s.value }"
          @click="setStatus(s.value)"
        >{{ s.label }}</button>
      </div>

      <CardList
        :items="projects"
        :field-config="projectFieldConfig"
        :loading="loading"
        empty-icon="📁"
        empty-title="暂无项目"
        empty-hint="点击右上角 + 创建项目"
        @item-click="viewProject"
      >
        <template #item-actions="{ item }">
          <div class="progress-block">
            <div class="progress-info">
              <span>进度</span>
              <span class="progress-num">{{ item.progress || 0 }}%</span>
            </div>
            <div class="progress-bar-wrap">
              <div class="progress-bar" :style="{ width: (item.progress || 0) + '%' }" />
            </div>
          </div>
        </template>
      </CardList>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileProjectView.vue — 移动端项目管理
 *
 * PR #8b: CardList 卡片化 + 状态筛选
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/mobile/PageHeader.vue'
import CardList from '@/components/mobile/CardList.vue'

const router = useRouter()
const projects = ref([])
const loading = ref(false)
const activeStatus = ref('')

const statusFilters = [
  { label: '全部', value: '' },
  { label: '进行中', value: 'active' },
  { label: '已暂停', value: 'paused' },
  { label: '已完成', value: 'completed' },
]

const projectFieldConfig = computed(() => ({
  title: (p) => p.name,
  subtitle: (p) => `${formatDate(p.start_date)} ~ ${formatDate(p.end_date)}`,
  badge: (p) => ({
    label: getStatusLabel(p.status),
    type: getStatusType(p.status),
  }),
  fields: (p) => [
    { key: 'research', label: '方向', value: p.research_area || '—' },
    { key: 'members', label: '成员', value: `${p.members?.length || 0} 人` },
  ],
}))

function formatDate(t) {
  if (!t) return ''
  return dayjs(t).format('YYYY-MM-DD')
}

function getStatusLabel(s) {
  return { active: '进行中', paused: '已暂停', completed: '已完成' }[s] || s || '未知'
}

function getStatusType(s) {
  return { active: 'primary', paused: 'warning', completed: 'success' }[s] || 'info'
}

async function fetchProjects() {
  loading.value = true
  try {
    const params = {}
    if (activeStatus.value) params.status = activeStatus.value
    const res = await axios.get('/api/v1/projects', { params })
    projects.value = res.data?.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function setStatus(v) {
  activeStatus.value = v
  fetchProjects()
}

function viewProject(project) {
  // 跳到移动端项目详情页（新建 MobileProjectDetailView，含里程碑 timeline + 成员列表）
  router.push(`/mobile/projects/${project.id}`)
}

onMounted(() => {
  fetchProjects()
})
</script>

<style scoped>
.mobile-project-view {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.project-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

.status-chips {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.status-chips::-webkit-scrollbar { display: none; }
.status-chip {
  flex-shrink: 0;
  padding: 6px 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.status-chip.active {
  background: var(--color-primary);
  /* stylelint-disable-next-line color-named */
  color: white;
  border-color: var(--color-primary);
}

.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
  margin-left: 4px;
}
.header-action:active { background: var(--color-primary-bg); }
.header-action.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  /* stylelint-disable-next-line color-named */
  color: white;
  font-weight: 600;
  font-size: 22px;
}

/* 进度条 */
.progress-block {
  margin-top: 6px;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}
.progress-num {
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-primary);
}
.progress-bar-wrap {
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-light));
  transition: width 0.3s;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .project-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
}
[data-theme="dark"] .project-card:active {
  background: var(--color-bg-hover);
}
[data-theme="dark"] .project-name {
  color: var(--color-text-primary);
}
[data-theme="dark"] .project-desc {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .progress-bar-wrap {
  background: var(--color-border-light);
}
[data-theme="dark"] .project-meta {
  color: var(--color-text-placeholder);
}
</style>