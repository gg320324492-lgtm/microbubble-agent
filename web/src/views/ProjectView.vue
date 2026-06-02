<template>
  <div class="project-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="12" :sm="12" :md="8">
          <el-select v-model="filters.status" name="filters-status" placeholder="项目状态" clearable>
            <el-option label="进行中" value="active" />
            <el-option label="已暂停" value="paused" />
            <el-option label="已完成" value="completed" />
          </el-select>
        </el-col>
        <el-col :xs="12" :sm="12" :md="8">
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            创建项目
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 项目卡片列表 -->
    <div class="project-grid">
      <el-card
        v-for="project in projects"
        :key="project.id"
        class="project-card"
        shadow="hover"
        @click="viewProject(project)"
      >
        <div class="project-header">
          <el-tag :type="getStatusType(project.status)" size="small">
            {{ getStatusLabel(project.status) }}
          </el-tag>
          <el-dropdown @command="(cmd) => handleCommand(cmd, project)">
            <el-icon><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="pause">暂停</el-dropdown-item>
                <el-dropdown-item command="complete">完成</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <h3 class="project-name">{{ project.name }}</h3>
        <p class="project-desc">{{ project.description || '暂无描述' }}</p>

        <div class="project-meta">
          <div class="meta-item">
            <el-icon><Calendar /></el-icon>
            <span>{{ formatDate(project.start_date) }} - {{ formatDate(project.end_date) }}</span>
          </div>
          <div class="meta-item">
            <el-icon><User /></el-icon>
            <span>{{ project.members?.length || 0 }} 人</span>
          </div>
        </div>

        <div class="project-progress">
          <div class="progress-label">
            <span>进度</span>
            <span>{{ project.progress || 0 }}%</span>
          </div>
          <el-progress :percentage="project.progress || 0" :stroke-width="8" />
        </div>
      </el-card>
    </div>

    <!-- 创建项目对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建项目" :width="isMobile ? '90vw' : '500px'" top="8vh">
      <el-form :model="projectForm" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="projectForm.name" name="projectForm-name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="研究方向">
          <el-input v-model="projectForm.research_area" name="projectForm-research_area" placeholder="如：水处理、农业应用" />
        </el-form-item>
        <el-form-item label="项目周期">
          <div style="display:flex;gap:8px;align-items:center;width:100%">
            <!--
              2026-06-02 修复 a11y 警告：Element Plus 2.4.4 的 el-date-picker 即使
              type="date" 也会用 el-range-input 类（与 daterange 同一底层组件），
              内部 input 仍无 name。改用原生 <input type="date">。
            -->
            <input
              :value="projectForm.startDate"
              name="project-form-start-date"
              type="date"
              class="native-date-input"
              placeholder="开始日期"
              style="flex:1"
              @change="(e) => projectForm.startDate = e.target.value"
            />
            <span>至</span>
            <input
              :value="projectForm.endDate"
              name="project-form-end-date"
              type="date"
              class="native-date-input"
              placeholder="结束日期"
              style="flex:1"
              @change="(e) => projectForm.endDate = e.target.value"
            />
          </div>
        </el-form-item>
        <el-form-item label="项目成员">
          <el-select
            v-model="projectForm.members" name="projectForm-members"
            multiple
            placeholder="选择项目成员"
          >
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="projectForm.description" name="projectForm-description"
            type="textarea"
            :rows="3"
            placeholder="请输入项目描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createProject">创建</el-button>
      </template>
    </el-dialog>

    <!-- 项目详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="项目详情" :width="isMobile ? '95vw' : '700px'" top="5vh">
      <div v-if="currentProject" class="project-detail">
        <h2>{{ currentProject.name }}</h2>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentProject.status)">
              {{ getStatusLabel(currentProject.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="研究方向">{{ currentProject.research_area || '-' }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ formatDate(currentProject.start_date) }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ formatDate(currentProject.end_date) }}</el-descriptions-item>
          <el-descriptions-item label="项目描述" :span="2">{{ currentProject.description || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-top: 20px;">项目成员</h4>
        <div class="member-tags">
          <el-tag
            v-for="memberId in currentProject.members"
            :key="memberId"
            style="margin: 4px"
          >
            {{ getMemberName(memberId) }}
          </el-tag>
        </div>

        <h4 style="margin-top: 20px;">里程碑</h4>
        <el-timeline>
          <el-timeline-item
            v-for="milestone in milestones"
            :key="milestone.id"
            :timestamp="formatDate(milestone.due_date)"
            placement="top"
          >
            <el-card>
              <h4>{{ milestone.name }}</h4>
              <p>{{ milestone.description }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatDate } from '@/utils/format'
import { useMemberStore } from '@/stores/member'

const memberStore = useMemberStore()
const members = computed(() => memberStore.members)

const isMobile = ref(window.innerWidth <= 768)
const projects = ref([])
const milestones = ref([])
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const currentProject = ref(null)

const filters = ref({
  status: ''
})

const projectForm = ref({
  name: '',
  research_area: '',
  startDate: '',
  endDate: '',
  members: [],
  description: ''
})

// 获取项目列表
const fetchProjects = async () => {
  try {
    const res = await axios.get('/api/v1/projects', { params: filters.value })
    projects.value = res.data.items || []
  } catch (e) {
    console.error('获取项目失败:', e)
  }
}

// 获取成员列表（使用 store）
const fetchMembers = () => memberStore.fetchMembers()

// 创建项目
const createProject = async () => {
  if (!projectForm.value.name) {
    ElMessage.warning('请输入项目名称')
    return
  }

  try {
    const data = {
      name: projectForm.value.name,
      research_area: projectForm.value.research_area,
      description: projectForm.value.description,
      members: projectForm.value.members,
      start_date: projectForm.value.startDate,
      end_date: projectForm.value.endDate
    }
    await axios.post('/api/v1/projects', data)
    ElMessage.success('项目创建成功')
    showCreateDialog.value = false
    projectForm.value = { name: '', research_area: '', startDate: '', endDate: '', members: [], description: '' }
    fetchProjects()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

// 查看项目详情
const viewProject = async (project) => {
  currentProject.value = project
  showDetailDialog.value = true

  // 获取里程碑
  try {
    const res = await axios.get(`/api/v1/projects/${project.id}/milestones`)
    milestones.value = res.data || []
  } catch (e) {
    console.error('获取里程碑失败:', e)
  }
}

// 处理下拉命令
const handleCommand = async (cmd, project) => {
  switch (cmd) {
    case 'edit':
      // TODO: 编辑项目
      break
    case 'pause':
      await updateProjectStatus(project, 'paused')
      break
    case 'complete':
      await updateProjectStatus(project, 'completed')
      break
    case 'delete':
      await deleteProject(project)
      break
  }
}

// 更新项目状态
const updateProjectStatus = async (project, status) => {
  try {
    await axios.put(`/api/v1/projects/${project.id}`, { status })
    ElMessage.success('状态更新成功')
    fetchProjects()
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

// 删除项目
const deleteProject = async (project) => {
  try {
    await ElMessageBox.confirm('确定要删除这个项目吗？', '确认删除', { type: 'warning' })
    await axios.delete(`/api/v1/projects/${project.id}`)
    ElMessage.success('项目删除成功')
    fetchProjects()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 辅助函数
const getMemberName = (id) => memberStore.getMemberName(id)

const getStatusType = (status) => {
  const map = { active: 'success', paused: 'warning', completed: 'info', archived: 'info' }
  return map[status] || 'info'
}

const getStatusLabel = (status) => {
  const map = { active: '进行中', paused: '已暂停', completed: '已完成', archived: '已归档' }
  return map[status] || status
}

watch(filters, () => fetchProjects(), { deep: true })

onMounted(() => {
  fetchProjects()
  fetchMembers()
})
</script>

<style scoped>
/* 2026-06-02 原生 date input 样式（绕过 el-date-picker 内部 input 缺 name 的 a11y 警告） */
.native-date-input {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: var(--radius-md, 4px);
  background: #fff;
  color: var(--color-text-primary, #303133);
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.2s;
}
.native-date-input:focus {
  outline: none;
  border-color: var(--color-primary, #FF7A5C);
}

.project-view {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.filter-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
}

.project-card {
  cursor: pointer;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.project-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-primary);
  border-color: var(--color-primary);
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.project-name {
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.project-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
  line-height: 1.5;
}

.project-meta {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
}

.meta-item .el-icon {
  color: var(--color-primary);
  flex-shrink: 0;
}

.project-progress {
  margin-top: var(--space-3);
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  margin-bottom: var(--space-2);
}

.member-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.member-tags .el-tag {
  border-radius: var(--radius-full);
  transition: all var(--duration-fast) var(--ease-out);
}

.member-tags .el-tag:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.project-detail h2 {
  color: var(--color-text-primary);
  margin-bottom: var(--space-5);
}

.project-detail h4 {
  color: var(--color-text-primary);
  margin-bottom: var(--space-3);
  font-weight: var(--font-weight-semibold);
}
</style>
