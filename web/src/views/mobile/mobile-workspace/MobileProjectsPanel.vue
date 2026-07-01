<template>
  <div class="mobile-projects-panel">
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

    <!-- 项目详情弹层 (替代路由 /projects/:id) -->
    <Teleport to="body">
      <Transition name="detail-sheet">
        <div v-if="showDetail" class="sheet-overlay" @click.self="closeDetail">
          <div class="sheet-panel" :style="{ paddingBottom: 'calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))' }">
            <div class="sheet-handle" />
            <div v-if="detailProject" class="detail-content">
              <section class="hero-card">
                <div class="hero-header">
                  <h2 class="hero-name">{{ detailProject.name }}</h2>
                  <el-tag :type="getStatusType(detailProject.status)" size="small">
                    {{ getStatusLabel(detailProject.status) }}
                  </el-tag>
                </div>
                <p v-if="detailProject.description" class="hero-desc">{{ detailProject.description }}</p>
                <div class="hero-progress">
                  <div class="progress-label">
                    <span>进度</span>
                    <span>{{ detailProject.progress || 0 }}%</span>
                  </div>
                  <el-progress :percentage="detailProject.progress || 0" :stroke-width="8" />
                </div>
              </section>

              <section class="info-card">
                <h3 class="info-title">基本信息</h3>
                <div class="info-row">
                  <span class="info-label">研究方向</span>
                  <span class="info-value">{{ detailProject.research_area || '—' }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">开始日期</span>
                  <span class="info-value">{{ formatDate(detailProject.start_date) || '—' }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">结束日期</span>
                  <span class="info-value">{{ formatDate(detailProject.end_date) || '—' }}</span>
                </div>
              </section>

              <section v-if="detailProject.members?.length" class="info-card">
                <h3 class="info-title">项目成员 ({{ detailProject.members.length }})</h3>
                <div class="members-list">
                  <el-tag
                    v-for="memberId in detailProject.members"
                    :key="memberId"
                    class="member-tag-item"
                  >
                    {{ getMemberName(memberId) }}
                  </el-tag>
                </div>
              </section>

              <section class="info-card">
                <h3 class="info-title">里程碑</h3>
                <div v-if="milestones.length === 0" class="empty-hint">暂无里程碑</div>
                <div v-else class="milestone-list">
                  <div
                    v-for="m in milestones"
                    :key="m.id"
                    class="milestone-item"
                  >
                    <div class="milestone-dot" />
                    <div class="milestone-body">
                      <div class="milestone-name">{{ m.name }}</div>
                      <div v-if="m.description" class="milestone-desc">{{ m.description }}</div>
                      <div class="milestone-meta">截止：{{ formatDate(m.due_date) }}</div>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 接收父级 header + 按钮事件: 弹出创建表单 (MobileFormSheet) -->
    <MobileFormSheet
      v-model:show="showCreate"
      v-model:form="createForm"
      title="创建项目"
      :fields="createFields"
      :submitting="creating"
      @submit="onCreateSubmit"
    />
  </div>
</template>

<script setup>
/**
 * MobileProjectsPanel.vue — v78 "团队协作" 移动端项目 tab
 *
 * 从原 web/src/views/mobile/MobileProjectView.vue 拆出 (2026-07-02):
 * - 保留: 项目卡片网格 + 状态 chip 筛选 + 创建/编辑 form
 * - 移除: 顶部 PageHeader (由父 MobileWorkspaceView 提供)
 * - 移除: 路由跳转 /mobile/projects/:id (原路径不存在, v77 pre-existing bug)
 *   → 改为内嵌 detail sheet 弹层
 * - 接收 window event 'workspace:create-project' 显示创建表单
 */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { ElMessage, ElTag, ElProgress } from 'element-plus'
import { useMemberStore } from '@/stores/member'
import CardList from '@/components/mobile/CardList.vue'
import MobileFormSheet from '@/components/mobile/MobileFormSheet.vue'

const memberStore = useMemberStore()

const projects = ref([])
const loading = ref(false)
const activeStatus = ref('')
const showCreate = ref(false)
const creating = ref(false)

const showDetail = ref(false)
const detailProject = ref(null)
const milestones = ref([])

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

async function viewProject(project) {
  detailProject.value = project
  milestones.value = []
  showDetail.value = true
  try {
    const res = await axios.get(`/api/v1/projects/${project.id}/milestones`)
    milestones.value = res.data || []
  } catch (e) {
    console.error('获取里程碑失败:', e)
  }
}

function closeDetail() {
  showDetail.value = false
  detailProject.value = null
}

function getMemberName(id) {
  return memberStore.getMemberName?.(id) || `成员 #${id}`
}

// ====== 创建项目表单 ======
const createForm = ref({
  name: '',
  research_area: '',
  startDate: '',
  endDate: '',
  members: [],
  description: '',
})

const createFields = computed(() => [
  { key: 'name', label: '项目名称', type: 'input', required: true, placeholder: '请输入项目名称' },
  { key: 'research_area', label: '研究方向', type: 'input', placeholder: '如：水处理、农业应用' },
  { key: 'startDate', label: '开始日期', type: 'date', placeholder: '选择开始日期' },
  { key: 'endDate', label: '结束日期', type: 'date', placeholder: '选择结束日期' },
  { key: 'members', label: '项目成员', type: 'select', multiple: true,
    options: memberStore.members.map((m) => ({ value: m.id, label: m.name })) },
  { key: 'description', label: '项目描述', type: 'textarea', placeholder: '请输入项目描述' },
])

async function onCreateSubmit(form) {
  if (!form.name) {
    ElMessage.warning('请输入项目名称')
    return
  }
  creating.value = true
  try {
    await axios.post('/api/v1/projects', {
      name: form.name,
      research_area: form.research_area,
      description: form.description,
      members: form.members,
      start_date: form.startDate,
      end_date: form.endDate,
    })
    ElMessage.success('项目创建成功')
    showCreate.value = false
    createForm.value = { name: '', research_area: '', startDate: '', endDate: '', members: [], description: '' }
    fetchProjects()
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

// ====== 接收父级 header 按钮事件 ======
function onWorkspaceCreateProject() {
  showCreate.value = true
}

onMounted(async () => {
  await fetchProjects()
  if (memberStore.members.length === 0) {
    memberStore.fetchMembers().catch(() => {})
  }
  window.addEventListener('workspace:create-project', onWorkspaceCreateProject)
})

onBeforeUnmount(() => {
  window.removeEventListener('workspace:create-project', onWorkspaceCreateProject)
})
</script>

<style scoped>
.mobile-projects-panel {
  padding: 12px 16px;
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

.progress-block { margin-top: 6px; }
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

/* ===== 详情 sheet ===== */
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px;
  max-height: 80vh;
  overflow-y: auto;
}
.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 16px;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 0 16px;
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
  background: var(--color-bg-page);
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
.member-tag-item {
  border-radius: 16px;
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

.empty-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
  padding: 12px 0;
}

.detail-sheet-enter-active, .detail-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.detail-sheet-enter-active .sheet-panel, .detail-sheet-leave-active .sheet-panel {
  transition: transform 0.3s var(--ease-sheet);
}
.detail-sheet-enter-from, .detail-sheet-leave-to { opacity: 0; }
.detail-sheet-enter-from .sheet-panel, .detail-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .sheet-panel {
  background: var(--color-bg-card);
}
[data-theme="dark"] .info-card {
  background: var(--color-bg-page);
}
</style>