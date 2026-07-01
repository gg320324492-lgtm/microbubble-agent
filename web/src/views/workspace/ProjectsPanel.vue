<template>
  <div class="projects-panel">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="12" :sm="12" :md="8">
          <el-select v-model="filters.status" name="filters-status" placeholder="项目状态" aria-label="项目状态筛选" clearable>
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
        @click="$emit('open-detail', project)"
      >
        <div class="project-header">
          <el-tag :type="getStatusType(project.status)" size="small">
            {{ getStatusLabel(project.status) }}
          </el-tag>
          <el-dropdown @command="(cmd) => handleCommand(cmd, project)">
            <el-icon aria-label="更多操作"><MoreFilled /></el-icon>
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
          <el-progress :percentage="project.progress || 0" :stroke-width="8" :aria-label="`项目进度 ${project.progress || 0}%`" />
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
            <el-date-picker
              v-model="projectForm.startDate"
              name="project-form-start-date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
              style="flex:1"
              :clearable="true"
            />
            <span>至</span>
            <el-date-picker
              v-model="projectForm.endDate"
              name="project-form-end-date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
              style="flex:1"
              :clearable="true"
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

    <!-- 编辑项目对话框（与创建共享 projectForm） -->
    <el-dialog v-model="showEditDialog" title="编辑项目" :width="isMobile ? '95vw' : '500px'" top="8vh">
      <el-form :model="projectForm" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="projectForm.name" name="projectForm-edit-name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="研究方向">
          <el-input v-model="projectForm.research_area" name="projectForm-edit-research-area" placeholder="如：水处理、农业应用" />
        </el-form-item>
        <el-form-item label="项目周期">
          <div style="display:flex;gap:8px;align-items:center;width:100%">
            <el-date-picker
              v-model="projectForm.startDate"
              name="project-form-edit-start-date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
              style="flex:1"
              :clearable="true"
            />
            <span>至</span>
            <el-date-picker
              v-model="projectForm.endDate"
              name="project-form-edit-end-date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
              style="flex:1"
              :clearable="true"
            />
          </div>
        </el-form-item>
        <el-form-item label="项目成员">
          <el-select
            v-model="projectForm.members"
            name="projectForm-edit-members"
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
            v-model="projectForm.description"
            name="projectForm-edit-description"
            type="textarea"
            :rows="3"
            placeholder="请输入项目描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="updateProject">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * ProjectsPanel.vue — v78 "团队协作" 项目 tab 子组件
 *
 * 从原 web/src/views/ProjectView.vue 拆出 (2026-07-02):
 * - 保留: 项目卡片列表 + 创建/编辑 dialog + filters 状态
 * - 移除: 项目详情 dialog (由父 WorkspaceView 接管, 通过 emit 'open-detail' 触发)
 * - 详情走 WorkspaceView 顶层 el-dialog (统一位置 + 跨 tab 共享)
 */

import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { formatDate } from '@/utils/format'
import { useMemberStore } from '@/stores/member'

defineEmits(['open-detail'])

const memberStore = useMemberStore()
const members = computed(() => memberStore.members)

const isMobile = ref(window.innerWidth <= 768)
const projects = ref([])
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const editingProjectId = ref(null)

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

// 处理下拉命令
const handleCommand = async (cmd, project) => {
  switch (cmd) {
    case 'edit':
      editingProjectId.value = project.id
      // 把项目数据回填到 projectForm（共享 create 表单）
      projectForm.value = {
        name: project.name || '',
        research_area: project.research_area || '',
        startDate: project.start_date || '',
        endDate: project.end_date || '',
        members: Array.isArray(project.members) ? [...project.members] : [],
        description: project.description || '',
      }
      showEditDialog.value = true
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

// 保存项目编辑
const updateProject = async () => {
  if (!projectForm.value.name) {
    ElMessage.warning('请输入项目名称')
    return
  }
  if (!editingProjectId.value) return
  try {
    await axios.put(`/api/v1/projects/${editingProjectId.value}`, {
      name: projectForm.value.name,
      research_area: projectForm.value.research_area,
      start_date: projectForm.value.startDate,
      end_date: projectForm.value.endDate,
      members: projectForm.value.members,
      description: projectForm.value.description,
    })
    ElMessage.success('项目更新成功')
    showEditDialog.value = false
    editingProjectId.value = null
    fetchProjects()
  } catch (e) {
    ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message))
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
})
</script>

<style scoped>
.projects-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: 16px 0;
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
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .project-card {
  background: var(--color-bg-card);
  border-color: var(--color-border);
  box-shadow: var(--shadow-sm);
}
[data-theme="dark"] .project-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
}
</style>