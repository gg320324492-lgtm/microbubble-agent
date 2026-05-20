<template>
  <div class="project-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="12" :sm="12" :md="8">
          <el-select v-model="filters.status" placeholder="项目状态" clearable>
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
    <el-dialog v-model="showCreateDialog" title="创建项目" :width="isMobile ? '90vw' : '500px'">
      <el-form :model="projectForm" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="projectForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="研究方向">
          <el-input v-model="projectForm.research_area" placeholder="如：水处理、农业应用" />
        </el-form-item>
        <el-form-item label="项目周期">
          <el-date-picker
            v-model="projectForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="项目成员">
          <el-select
            v-model="projectForm.members"
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
    <el-dialog v-model="showDetailDialog" title="项目详情" :width="isMobile ? '95vw' : '700px'">
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
  dateRange: [],
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
      start_date: projectForm.value.dateRange?.[0],
      end_date: projectForm.value.dateRange?.[1]
    }
    await axios.post('/api/v1/projects', data)
    ElMessage.success('项目创建成功')
    showCreateDialog.value = false
    projectForm.value = { name: '', research_area: '', dateRange: [], members: [], description: '' }
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
.project-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.project-card {
  cursor: pointer;
  transition: all 0.3s;
}

.project-card:hover {
  transform: translateY(-4px);
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.project-name {
  font-size: 18px;
  color: #303133;
  margin-bottom: 8px;
}

.project-desc {
  font-size: 13px;
  color: #909399;
  margin-bottom: 16px;
  line-height: 1.5;
}

.project-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
}

.project-progress {
  margin-top: 12px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.member-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
