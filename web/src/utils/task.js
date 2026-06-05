/**
 * 任务相关工具函数
 */

// 任务状态类型映射（用于 Element Plus Tag 组件的 type 属性）
export function getStatusType(status) {
  const map = {
    todo: 'info',
    in_progress: 'warning',
    blocked: 'danger',
    done: 'success',
    // 会议状态
    scheduled: 'info',
    recording: 'warning',
    processing: 'warning',
    completed: 'success',
    cancelled: 'info',
    error: 'danger',
    // 通用状态
    pending: 'info',
    overdue: 'danger'
  }
  return map[status] || 'info'
}

// 任务优先级类型映射
export function getPriorityType(priority) {
  const map = { high: 'danger', medium: 'warning', low: 'info' }
  return map[priority] || 'info'
}

// 任务状态标签
export function getStatusLabel(status) {
  const map = {
    todo: '进行中',
    in_progress: '进行中',
    blocked: '阻塞',
    done: '已完成',
    // 会议状态
    scheduled: '已预约',
    recording: '录制中',
    processing: '处理中',
    completed: '已完成',
    cancelled: '已取消',
    error: '处理失败',
    // 通用状态
    pending: '待处理',
    overdue: '已逾期'
  }
  return map[status] || status
}

// 任务优先级标签
export function getPriorityLabel(priority) {
  const map = { high: '高', medium: '中', low: '低' }
  return map[priority] || priority
}
