<template>
  <div class="mobile-project-detail-view">
    <PageHeader :title="project?.name || '项目详情'" show-back @back="$router.back()" />

    <main
      class="detail-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <div v-if="loading" class="loading">
        <div class="loading-spinner" />
      </div>

      <div v-else-if="!project" class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-title">未找到该项目</div>
      </div>

      <div v-else class="content">
        <!-- Hero -->
        <section class="hero-card">
          <div class="hero-header">
            <h2 class="hero-name">{{ project.name }}</h2>
            <el-tag :type="getStatusType(project.status)" size="small">
              {{ getStatusLabel(project.status) }}
            </el-tag>
          </div>
          <p v-if="project.description" class="hero-desc">{{ project.description }}</p>
          <div class="hero-progress">
            <div class="progress-label">
              <span>进度</span>
              <span>{{ project.progress || 0 }}%</span>
            </div>
            <el-progress :percentage="project.progress || 0" :stroke-width="8" />
          </div>
        </section>

        <!-- 基本信息 -->
        <section class="info-card">
          <h3 class="info-title">基本信息</h3>
          <div class="info-row">
            <span class="info-label">研究方向</span>
            <span class="info-value">{{ project.research_area || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">开始日期</span>
            <span class="info-value">{{ formatDate(project.start_date) || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">结束日期</span>
            <span class="info-value">{{ formatDate(project.end_date) || '—' }}</span>
          </div>
        </section>

        <!-- 成员 -->
        <section v-if="project.members?.length" class="info-card">
          <h3 class="info-title">项目成员 ({{ project.members.length }})</h3>
          <div class="members-list">
            <button
              v-for="memberId in project.members"
              :key="memberId"
              type="button"
              class="member-tag"
              @click="viewMember(memberId)"
            >
              {{ getMemberName(memberId) }}
            </button>
          </div>
        </section>

        <!-- 里程碑 -->
        <section class="info-card">
          <h3 class="info-title">里程碑</h3>
          <div v-if="milestones.length === 0" class="empty-hint">暂无里程碑</div>
          <div v-else class="milestone-list">
            <div
              v-for="m in milestones"
              :key="m.id"
              class="milestone-item"
              :class="{ done: m.status === 'completed' }"
            >
              <div class="milestone-dot" />
              <div class="milestone-body">
                <div class="milestone-name">{{ m.name }}</div>
                <div v-if="m.description" class="milestone-desc">{{ m.description }}</div>
                <div class="milestone-meta">
                  截止：{{ formatDate(m.due_date) }}
                  <el-tag
                    v-if="m.status === 'completed'"
                    size="small"
                    type="success"
                    style="margin-left:8px"
                  >✓ 已完成</el-tag>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileProjectDetailView.vue — 移动端项目详情页
 *
 * 镜像桌面 ProjectView 的 detail 对话框内容，但用移动 sheet 风格
 * - 项目基本信息（描述/状态/进度/日期）
 * - 成员列表（可点击跳到成员详情）
 * - 里程碑 timeline
 */

import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTag, ElProgress } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import PageHeader from '@/components/mobile/PageHeader.vue'
import { useMemberStore } from '@/stores/member'

const route = useRoute()
const router = useRouter()
const memberStore = useMemberStore()

const project = ref(null)
const milestones = ref([])
const loading = ref(true)

async function fetchProject() {
  const id = route.params.id
  if (!id) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/projects/${id}`)
    project.value = res.data
  } catch (e) {
    console.error('获取项目详情失败:', e)
    project.value = null
  } finally {
    loading.value = false
  }
}

async function fetchMilestones() {
  const id = route.params.id
  if (!id) return
  try {
    const res = await axios.get(`/api/v1/projects/${id}/milestones`)
    milestones.value = res.data || []
  } catch (e) {
    console.error('获取里程碑失败:', e)
  }
}

function viewMember(memberId) {
  router.push(`/mobile/members/${memberId}`)
}

function getMemberName(id) {
  // store 缓存可能未加载，回退显示 ID
  return memberStore.getMemberName?.(id) || `成员 #${id}`
}

function getStatusType(status) {
  const map = { active: 'success', paused: 'warning', completed: 'info', archived: 'info' }
  return map[status] || 'info'
}

function getStatusLabel(status) {
  const map = { active: '进行中', paused: '已暂停', completed: '已完成', archived: '已归档' }
  return map[status] || status
}

function formatDate(t) {
  if (!t) return ''
  return dayjs(t).format('YYYY-MM-DD')
}

onMounted(async () => {
  await fetchProject()
  await fetchMilestones()
  // 确保成员 store 加载（成员名映射）
  if (memberStore.members.length === 0) {
    memberStore.fetchMembers().catch(() => {})
  }
})
</script>

<style scoped>
.mobile-project-detail-view {
  min-height: 100vh;
  background: var(--color-bg-page);
}
.detail-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

.loading {
  text-align: center;
  padding: 60px 20px;
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}
.empty-state {
  text-align: center;
  padding: 80px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  color: var(--color-text-regular);
}
.empty-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
  padding: 12px 0;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hero-card {
  padding: 20px 16px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  /* stylelint-disable-next-line color-named */
  color: white;
}
.hero-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.hero-name {
  margin: 0;
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  flex: 1;
  overflow-wrap: anywhere;
}
.hero-desc {
  margin: 0 0 16px;
  font-size: 13px;
  line-height: 1.6;
  opacity: 0.95;
  white-space: pre-wrap;
}
.hero-progress {
  background: rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-md);
  padding: 12px;
}
.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 6px;
  opacity: 0.95;
}

.info-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
}
.info-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-regular);
}
.info-row {
  display: flex;
  font-size: 13px;
  padding: 6px 0;
}
.info-label {
  flex: 0 0 80px;
  color: var(--color-text-secondary);
}
.info-value {
  flex: 1;
  color: var(--color-text-primary);
  overflow-wrap: anywhere;
}

.members-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.member-tag {
  padding: 6px 12px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  font-size: 13px;
  color: var(--color-text-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.member-tag:active {
  background: var(--color-primary-bg);
  border-color: var(--color-primary);
}

.milestone-list {
  position: relative;
  padding-left: 20px;
}
.milestone-list::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--color-border);
}
.milestone-item {
  position: relative;
  padding: 8px 0 16px;
}
.milestone-item.done .milestone-name {
  color: var(--color-text-secondary);
  text-decoration: line-through;
}
.milestone-dot {
  position: absolute;
  left: -17px;
  top: 14px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-primary);
  border: 2px solid var(--color-bg-card);
  box-shadow: 0 0 0 2px var(--color-primary);
}
.milestone-item.done .milestone-dot {
  background: var(--color-success, #67C23A);
  box-shadow: 0 0 0 2px var(--color-success, #67C23A);
}
.milestone-name {
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
}
.milestone-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
  white-space: pre-wrap;
}
.milestone-meta {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .project-hero {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
}
[data-theme="dark"] .milestone-item {
  background: var(--color-bg-page);
  border: 1px solid var(--color-border-light);
}
[data-theme="dark"] .milestone-item.completed {
  background: var(--color-success-bg);
  border-color: var(--color-success);
}
[data-theme="dark"] .milestone-name {
  color: var(--color-text-primary);
}
[data-theme="dark"] .member-chip {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
</style>
