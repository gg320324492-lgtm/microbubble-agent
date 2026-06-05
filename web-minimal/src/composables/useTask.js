import { ref, computed } from 'vue'
import axios from 'axios'
import { useMemberStore } from '@/stores/member'
import {
  filterTasks,
  sortByPriority,
  sortByDueDate,
  sortByStatus,
  groupByAssignee,
  isOverdue
} from '@/utils/task'

export function useTask() {
  const tasks = ref([])
  const loading = ref(false)
  const error = ref(null)
  const filters = ref({
    status: 'all',
    priority: 'all',
    assignee_id: null,
    keyword: ''
  })

  const memberStore = useMemberStore()

  // 计算属性
  const filteredTasks = computed(() => {
    return filterTasks(tasks.value, filters.value)
  })

  const sortedTasks = computed(() => {
    return sortByDueDate(sortByPriority(filteredTasks.value))
  })

  const groupedTasks = computed(() => {
    return groupByAssignee(sortedTasks.value)
  })

  const inProgressTasks = computed(() => {
    return tasks.value.filter(t => t.status === 'in_progress')
  })

  const overdueTasks = computed(() => {
    return tasks.value.filter(t => isOverdue(t.due_date) && t.status !== 'done')
  })

  const doneTasks = computed(() => {
    return tasks.value.filter(t => t.status === 'done')
  })

  const todoTasks = computed(() => {
    return tasks.value.filter(t => t.status === 'todo')
  })

  const stats = computed(() => ({
    total: tasks.value.length,
    in_progress: inProgressTasks.value.length,
    overdue: overdueTasks.value.length,
    done: doneTasks.value.length,
    todo: todoTasks.value.length
  }))

  // 获取任务列表
  const fetchTasks = async (params = {}) => {
    loading.value = true
    error.value = null
    try {
      const response = await axios.get('/api/v1/tasks', { params })
      tasks.value = response.data
    } catch (err) {
      error.value = err.response?.data?.detail || '获取任务列表失败'
      console.error('获取任务列表失败:', err)
    } finally {
      loading.value = false
    }
  }

  // 获取单个任务
  const fetchTask = async (taskId) => {
    try {
      const response = await axios.get(`/api/v1/tasks/${taskId}`)
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = response.data
      } else {
        tasks.value.push(response.data)
      }
      return response.data
    } catch (err) {
      console.error('获取任务详情失败:', err)
      return null
    }
  }

  // 创建任务
  const createTask = async (taskData) => {
    try {
      const response = await axios.post('/api/v1/tasks', taskData)
      tasks.value.push(response.data)
      return { success: true, data: response.data }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '创建任务失败'
      }
    }
  }

  // 更新任务
  const updateTask = async (taskId, taskData) => {
    try {
      const response = await axios.put(`/api/v1/tasks/${taskId}`, taskData)
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = response.data
      }
      return { success: true, data: response.data }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '更新任务失败'
      }
    }
  }

  // 删除任务
  const deleteTask = async (taskId) => {
    try {
      await axios.delete(`/api/v1/tasks/${taskId}`)
      tasks.value = tasks.value.filter(t => t.id !== taskId)
      return { success: true }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '删除任务失败'
      }
    }
  }

  // 完成任务
  const completeTask = async (taskId) => {
    return updateTask(taskId, { status: 'done' })
  }

  // 恢复任务
  const restoreTask = async (taskId) => {
    return updateTask(taskId, { status: 'todo', deleted_at: null })
  }

  // 永久删除任务
  const purgeTask = async (taskId) => {
    try {
      await axios.delete(`/api/v1/tasks/${taskId}/purge`)
      tasks.value = tasks.value.filter(t => t.id !== taskId)
      return { success: true }
    } catch (err) {
      return {
        success: false,
        message: err.response?.data?.detail || '永久删除任务失败'
      }
    }
  }

  // 设置筛选条件
  const setFilters = (newFilters) => {
    filters.value = { ...filters.value, ...newFilters }
  }

  // 重置筛选条件
  const resetFilters = () => {
    filters.value = {
      status: 'all',
      priority: 'all',
      assignee_id: null,
      keyword: ''
    }
  }

  // 获取任务负责人姓名
  const getAssigneeName = (assigneeId) => {
    return memberStore.getMemberName(assigneeId)
  }

  // 获取任务负责人头像
  const getAssigneeAvatar = (assigneeId) => {
    return memberStore.getMemberAvatar(assigneeId)
  }

  // 获取任务负责人首字母
  const getAssigneeInitial = (assigneeId) => {
    return memberStore.getMemberInitial(assigneeId)
  }

  return {
    tasks,
    loading,
    error,
    filters,
    filteredTasks,
    sortedTasks,
    groupedTasks,
    inProgressTasks,
    overdueTasks,
    doneTasks,
    todoTasks,
    stats,
    fetchTasks,
    fetchTask,
    createTask,
    updateTask,
    deleteTask,
    completeTask,
    restoreTask,
    purgeTask,
    setFilters,
    resetFilters,
    getAssigneeName,
    getAssigneeAvatar,
    getAssigneeInitial
  }
}
