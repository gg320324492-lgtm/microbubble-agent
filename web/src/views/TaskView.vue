<template>
  <div class="task-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="12" :sm="12" :md="6">
          <el-select v-model="filters.status" placeholder="任务状态" clearable>
            <el-option label="待办" value="todo" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-col>
        <el-col :xs="12" :sm="12" :md="6">
          <el-select v-model="filters.assignee_id" placeholder="负责人" clearable>
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
          </el-select>
        </el-col>
        <el-col :xs="12" :sm="12" :md="6">
          <el-select v-model="filters.priority" placeholder="优先级" clearable>
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-col>
        <el-col :xs="12" :sm="12" :md="6">
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            创建任务
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 任务列表 -->
    <el-card class="task-list-card">
      <div style="overflow-x: auto">
      <el-table :data="tasks" stripe style="width: 100%">
        <el-table-column prop="title" label="任务标题" min-width="200">
          <template #default="{ row }">
            <div class="task-title-cell">
              <el-checkbox
                :model-value="row.status === 'done'"
                @change="toggleTaskStatus(row)"
              />
              <span :class="{ 'task-done': row.status === 'done' }">{{ row.title }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="assignee_id" label="负责人" width="120">
          <template #default="{ row }">
            {{ getMemberName(row.assignee_id) }}
          </template>
        </el-table-column>

        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small">
              {{ getPriorityLabel(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="due_date" label="截止日期" width="120">
          <template #default="{ row }">
            <span :class="{ 'overdue': isOverdue(row) }">
              {{ formatDate(row.due_date) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="8" />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <template v-if="isAdmin || row.created_by === currentUserId">
              <el-button text type="primary" @click="editTask(row)">编辑</el-button>
              <el-button text type="danger" @click="deleteTask(row)">删除</el-button>
            </template>
            <span v-else class="no-permission">--</span>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchTasks"
          @current-change="fetchTasks"
        />
      </div>
    </el-card>

    <!-- 创建/编辑任务对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingTask ? '编辑任务' : '创建任务'"
      :width="isMobile ? '90vw' : '500px'"
    >
      <el-form :model="taskForm" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="taskForm.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-if="isAdmin" v-model="taskForm.assignee_id" placeholder="选择负责人" clearable>
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
          </el-select>
          <el-select v-else v-model="taskForm.assignee_id" disabled>
            <el-option :label="userStore.userInfo?.name" :value="currentUserId" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="taskForm.priority">
            <el-radio label="high">高</el-radio>
            <el-radio label="medium">中</el-radio>
            <el-radio label="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态" v-if="editingTask">
          <el-select v-model="taskForm.status">
            <el-option label="待办" value="todo" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="taskForm.due_date"
            type="datetime"
            placeholder="选择截止日期和时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="提醒设置">
          <div v-for="(reminder, index) in taskForm.reminders" :key="index" class="reminder-item">
            <el-date-picker
              v-model="reminder.remind_at"
              type="datetime"
              placeholder="选择提醒时间"
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 200px"
            />
            <el-select v-model="reminder.remind_type" style="width: 90px; margin-left: 8px;">
              <el-option label="微信" value="wechat" />
              <el-option label="邮件" value="email" />
            </el-select>
            <el-button text type="danger" @click="taskForm.reminders.splice(index, 1)" style="margin-left: 4px;">
              删除
            </el-button>
          </div>
          <el-button text type="primary" @click="taskForm.reminders.push({ remind_at: '', remind_type: 'wechat' })">
            + 添加提醒
          </el-button>
          <div class="reminder-hint">不设置则使用默认提醒（截止前2天 + 截止当天9点）</div>
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input
            v-model="taskForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入任务描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTask">{{ editingTask ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const isAdmin = computed(() => {
  const role = userStore.userInfo?.role
  return role === 'admin' || role === 'leader'
})
const currentUserId = computed(() => userStore.userInfo?.id)

const isMobile = ref(window.innerWidth <= 768)
const tasks = ref([])
const members = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const showCreateDialog = ref(false)
const editingTask = ref(null)

const filters = ref({
  status: '',
  assignee_id: '',
  priority: ''
})

const taskForm = ref({
  title: '',
  assignee_id: null,
  priority: 'medium',
  status: 'todo',
  due_date: '',
  description: '',
  reminders: []
})

// 获取任务列表
const fetchTasks = async () => {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      ...filters.value
    }
    const res = await axios.get('/api/v1/tasks', { params })
    tasks.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('获取任务失败:', e)
  }
}

// 获取成员列表
const fetchMembers = async () => {
  try {
    const res = await axios.get('/api/v1/members')
    members.value = res.data.items || []
  } catch (e) {
    console.error('获取成员失败:', e)
  }
}

// 保存任务
const saveTask = async () => {
  if (!taskForm.value.title) {
    ElMessage.warning('请输入任务标题')
    return
  }

  try {
    if (editingTask.value) {
      await axios.put(`/api/v1/tasks/${editingTask.value.id}`, taskForm.value)
      ElMessage.success('任务更新成功')
    } else {
      await axios.post('/api/v1/tasks', taskForm.value)
      ElMessage.success('任务创建成功')
    }
    showCreateDialog.value = false
    editingTask.value = null
    resetForm()
    fetchTasks()
  } catch (e) {
    const msg = e.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  }
}

// 编辑任务
const editTask = (task) => {
  editingTask.value = task
  taskForm.value = {
    ...task,
    reminders: task.reminders ? [...task.reminders] : []
  }
  showCreateDialog.value = true
}

// 删除任务
const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm('确定要删除这个任务吗？', '确认删除', {
      type: 'warning'
    })
    await axios.delete(`/api/v1/tasks/${task.id}`)
    ElMessage.success('任务删除成功')
    fetchTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 切换任务状态
const toggleTaskStatus = async (task) => {
  const newStatus = task.status === 'done' ? 'todo' : 'done'
  try {
    await axios.put(`/api/v1/tasks/${task.id}`, { status: newStatus })
    fetchTasks()
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

// 重置表单
const resetForm = () => {
  taskForm.value = {
    title: '',
    assignee_id: isAdmin.value ? null : currentUserId.value,
    priority: 'medium',
    status: 'todo',
    due_date: '',
    description: '',
    reminders: []
  }
}

// 辅助函数
const getMemberName = (id) => {
  const member = members.value.find(m => m.id === id)
  return member ? member.name : '未分配'
}

const getPriorityType = (priority) => {
  const map = { high: 'danger', medium: 'warning', low: 'info' }
  return map[priority] || 'info'
}

const getPriorityLabel = (priority) => {
  const map = { high: '高', medium: '中', low: '低' }
  return map[priority] || priority
}

const getStatusType = (status) => {
  const map = { todo: 'info', in_progress: 'warning', blocked: 'danger', done: 'success' }
  return map[status] || 'info'
}

const getStatusLabel = (status) => {
  const map = { todo: '待办', in_progress: '进行中', blocked: '阻塞', done: '已完成' }
  return map[status] || status
}

const formatDate = (date) => {
  if (!date) return '-'
  const d = dayjs(date)
  if (d.hour() !== 0 || d.minute() !== 0) {
    return d.format('YYYY-MM-DD HH:mm')
  }
  return d.format('YYYY-MM-DD')
}

const isOverdue = (task) => {
  if (!task.due_date || task.status === 'done') return false
  return dayjs(task.due_date).isBefore(dayjs())
}

watch(filters, () => {
  currentPage.value = 1
  fetchTasks()
}, { deep: true })

onMounted(() => {
  fetchTasks()
  fetchMembers()
})
</script>

<style scoped>
.task-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card {
  margin-bottom: 0;
}

.task-list-card {
  flex: 1;
}

.task-title-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-done {
  text-decoration: line-through;
  color: #909399;
}

.overdue {
  color: #f56c6c;
  font-weight: bold;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.no-permission {
  color: #c0c4cc;
  font-size: 12px;
}

.reminder-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.reminder-hint {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
</style>
