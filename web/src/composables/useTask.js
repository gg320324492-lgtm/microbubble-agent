import { ref, computed } from 'vue'
import axios from 'axios'

export function useTask() {
  // 状态
  const tasks = ref([])
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(100)
  const loading = ref(false)
  const filters = ref({
    status: '',
    assignee_id: '',
    project_id: '',
    search: ''
  })

  // 垃圾桶
  const trashTasks = ref([])
  const trashTotal = ref(0)
  const trashPage = ref(1)
  const trashPageSize = ref(20)
  const trashCount = ref(0)

  // API 调用
  const fetchTasks = async (params = {}) => {
    loading.value = true
    try {
      // 过滤掉空值参数
      const activeFilters = Object.fromEntries(
        Object.entries(filters.value).filter(([_, v]) => v !== '' && v !== null && v !== undefined)
      )
      const queryParams = {
        page: currentPage.value,
        page_size: pageSize.value,
        include_deleted: false,
        ...activeFilters,
        ...params
      }
      const res = await axios.get('/api/v1/tasks', { params: queryParams })
      tasks.value = res.data.items || []
      total.value = res.data.pagination?.total || res.data.total || 0
    } finally {
      loading.value = false
    }
  }

  const fetchTrashTasks = async () => {
    loading.value = true
    try {
      const res = await axios.get('/api/v1/tasks', {
        params: {
          page: trashPage.value,
          page_size: trashPageSize.value,
          include_deleted: true
        }
      })
      trashTasks.value = res.data.items || []
      trashTotal.value = res.data.pagination?.total || res.data.total || 0
    } finally {
      loading.value = false
    }
  }

  const createTask = async (taskData) => {
    const res = await axios.post('/api/v1/tasks', taskData)
    await fetchTasks()
    return res.data
  }

  const updateTask = async (taskId, taskData) => {
    const res = await axios.put(`/api/v1/tasks/${taskId}`, taskData)
    await fetchTasks()
    return res.data
  }

  const deleteTask = async (taskId) => {
    await axios.delete(`/api/v1/tasks/${taskId}`)
    await fetchTasks()
    await fetchTrashTasks()
  }

  const restoreTask = async (taskId) => {
    await axios.post(`/api/v1/tasks/${taskId}/restore`)
    await fetchTasks()
    await fetchTrashTasks()
  }

  const permanentlyDeleteTask = async (taskId) => {
    await axios.delete(`/api/v1/tasks/${taskId}/permanent`)
    await fetchTrashTasks()
  }

  // 计算属性
  const activeTasks = computed(() => tasks.value.filter(t => t.status !== 'done'))
  const doneTasks = computed(() => tasks.value.filter(t => t.status === 'done'))

  return {
    // 状态
    tasks, total, currentPage, pageSize, loading, filters,
    trashTasks, trashTotal, trashPage, trashPageSize, trashCount,
    // 计算属性
    activeTasks, doneTasks,
    // 方法
    fetchTasks, fetchTrashTasks, createTask, updateTask,
    deleteTask, restoreTask, permanentlyDeleteTask
  }
}
