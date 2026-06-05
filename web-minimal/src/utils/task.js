import dayjs from 'dayjs'

/**
 * 任务优先级配置
 */
export const PRIORITY_CONFIG = {
  high: { label: '紧急', color: '#ef4444', bgColor: '#fef2f2' },
  medium: { label: '中等', color: '#f59e0b', bgColor: '#fffbeb' },
  low: { label: '普通', color: '#10b981', bgColor: '#f0fdf4' }
}

/**
 * 任务状态配置
 */
export const STATUS_CONFIG = {
  todo: { label: '待办', color: '#666666', bgColor: '#f0f0f0' },
  in_progress: { label: '进行中', color: '#3b82f6', bgColor: '#eff6ff' },
  done: { label: '已完成', color: '#10b981', bgColor: '#f0fdf4' }
}

/**
 * 获取优先级标签
 * @param {string} priority - 优先级
 * @returns {string}
 */
export const getPriorityLabel = (priority) => {
  return PRIORITY_CONFIG[priority]?.label || '未知'
}

/**
 * 获取优先级颜色
 * @param {string} priority - 优先级
 * @returns {string}
 */
export const getPriorityColor = (priority) => {
  return PRIORITY_CONFIG[priority]?.color || '#666666'
}

/**
 * 获取优先级背景色
 * @param {string} priority - 优先级
 * @returns {string}
 */
export const getPriorityBgColor = (priority) => {
  return PRIORITY_CONFIG[priority]?.bgColor || '#f0f0f0'
}

/**
 * 获取状态标签
 * @param {string} status - 状态
 * @returns {string}
 */
export const getStatusLabel = (status) => {
  return STATUS_CONFIG[status]?.label || '未知'
}

/**
 * 获取状态颜色
 * @param {string} status - 状态
 * @returns {string}
 */
export const getStatusColor = (status) => {
  return STATUS_CONFIG[status]?.color || '#666666'
}

/**
 * 获取状态背景色
 * @param {string} status - 状态
 * @returns {string}
 */
export const getStatusBgColor = (status) => {
  return STATUS_CONFIG[status]?.bgColor || '#f0f0f0'
}

/**
 * 判断是否逾期
 * @param {string|Date} dueDate - 截止日期
 * @returns {boolean}
 */
export const isOverdue = (dueDate) => {
  if (!dueDate) return false
  return dayjs(dueDate).isBefore(dayjs(), 'day')
}

/**
 * 判断是否今天到期
 * @param {string|Date} dueDate - 截止日期
 * @returns {boolean}
 */
export const isDueToday = (dueDate) => {
  if (!dueDate) return false
  return dayjs(dueDate).isSame(dayjs(), 'day')
}

/**
 * 判断是否明天到期
 * @param {string|Date} dueDate - 截止日期
 * @returns {boolean}
 */
export const isDueTomorrow = (dueDate) => {
  if (!dueDate) return false
  return dayjs(dueDate).isSame(dayjs().add(1, 'day'), 'day')
}

/**
 * 获取截止日期显示
 * @param {string|Date} dueDate - 截止日期
 * @returns {string}
 */
export const getDueDateDisplay = (dueDate) => {
  if (!dueDate) return ''
  const d = dayjs(dueDate)
  const now = dayjs()

  if (d.isSame(now, 'day')) {
    return '今天'
  } else if (d.isSame(now.add(1, 'day'), 'day')) {
    return '明天'
  } else if (d.isSame(now.subtract(1, 'day'), 'day')) {
    return '昨天'
  } else if (d.isBefore(now, 'day')) {
    return `逾期${now.diff(d, 'day')}天`
  } else if (d.diff(now, 'day') < 7) {
    return `${d.diff(now, 'day')}天后`
  } else {
    return d.format('MM月DD日')
  }
}

/**
 * 获取截止日期样式类
 * @param {string|Date} dueDate - 截止日期
 * @returns {string}
 */
export const getDueDateClass = (dueDate) => {
  if (!dueDate) return ''
  if (isOverdue(dueDate)) return 'overdue'
  if (isDueToday(dueDate)) return 'today'
  if (isDueTomorrow(dueDate)) return 'tomorrow'
  return ''
}

/**
 * 按优先级排序
 * @param {Array} tasks - 任务列表
 * @returns {Array}
 */
export const sortByPriority = (tasks) => {
  const priorityOrder = { high: 0, medium: 1, low: 2 }
  return [...tasks].sort((a, b) => {
    return (priorityOrder[a.priority] || 2) - (priorityOrder[b.priority] || 2)
  })
}

/**
 * 按截止日期排序
 * @param {Array} tasks - 任务列表
 * @returns {Array}
 */
export const sortByDueDate = (tasks) => {
  return [...tasks].sort((a, b) => {
    if (!a.due_date) return 1
    if (!b.due_date) return -1
    return dayjs(a.due_date).diff(dayjs(b.due_date))
  })
}

/**
 * 按状态排序
 * @param {Array} tasks - 任务列表
 * @returns {Array}
 */
export const sortByStatus = (tasks) => {
  const statusOrder = { in_progress: 0, todo: 1, done: 2 }
  return [...tasks].sort((a, b) => {
    return (statusOrder[a.status] || 2) - (statusOrder[b.status] || 2)
  })
}

/**
 * 筛选任务
 * @param {Array} tasks - 任务列表
 * @param {Object} filters - 筛选条件
 * @returns {Array}
 */
export const filterTasks = (tasks, filters = {}) => {
  let result = [...tasks]

  // 按状态筛选
  if (filters.status && filters.status !== 'all') {
    if (filters.status === 'overdue') {
      result = result.filter(t => isOverdue(t.due_date) && t.status !== 'done')
    } else {
      result = result.filter(t => t.status === filters.status)
    }
  }

  // 按优先级筛选
  if (filters.priority && filters.priority !== 'all') {
    result = result.filter(t => t.priority === filters.priority)
  }

  // 按负责人筛选
  if (filters.assignee_id) {
    result = result.filter(t => t.assignee_id === filters.assignee_id)
  }

  // 按关键词搜索
  if (filters.keyword) {
    const keyword = filters.keyword.toLowerCase()
    result = result.filter(t =>
      t.title.toLowerCase().includes(keyword) ||
      (t.description && t.description.toLowerCase().includes(keyword))
    )
  }

  return result
}

/**
 * 按负责人分组
 * @param {Array} tasks - 任务列表
 * @returns {Object}
 */
export const groupByAssignee = (tasks) => {
  const groups = {}
  tasks.forEach(task => {
    const assigneeId = task.assignee_id || 'unassigned'
    if (!groups[assigneeId]) {
      groups[assigneeId] = {
        assignee_id: assigneeId,
        tasks: []
      }
    }
    groups[assigneeId].tasks.push(task)
  })
  return Object.values(groups)
}
