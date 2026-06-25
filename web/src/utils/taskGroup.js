import dayjs from 'dayjs'

/**
 * 按负责人分组任务（移动端 / 桌面端共用）
 *
 * 2026-06-26: 从 TaskView.vue 抽出，移动端"按人分组"视图复用。
 *
 * @param {Array} taskList - 任务列表（任意状态）
 * @returns {Array<{assignee_id: (number|string), tasks: Array}>} - 按任务数倒序排序的分组
 *
 * 行为约定：
 * - assignee_id 为 null/undefined 的任务归入 'unassigned' 组
 * - 组内按优先级（高→中→低）→ 截止日期（早→晚）排序
 * - 组间按任务数（多→少）排序（任务多的负责人排前面）
 */
export function groupTasksByAssignee(taskList) {
  const groups = {}
  for (const task of taskList) {
    // 用 != null 兼容 null/undefined（CLAUDE.md 沉淀的"任务配对布局"模式）
    const id = task.assignee_id != null ? task.assignee_id : 'unassigned'
    if (!groups[id]) {
      groups[id] = { assignee_id: id, tasks: [] }
    }
    groups[id].tasks.push(task)
  }
  // 组内排序：优先级（高>中>低），同优先级按截止日期（早→晚）
  const priorityOrder = { high: 3, medium: 2, low: 1 }
  for (const g of Object.values(groups)) {
    g.tasks.sort((a, b) => {
      const pDiff = (priorityOrder[b.priority] || 0) - (priorityOrder[a.priority] || 0)
      if (pDiff !== 0) return pDiff
      if (!a.due_date && !b.due_date) return 0
      if (!a.due_date) return 1
      if (!b.due_date) return -1
      return dayjs(a.due_date).diff(dayjs(b.due_date))
    })
  }
  // 组间排序：任务总数多→少
  return Object.values(groups).sort((a, b) => b.tasks.length - a.tasks.length)
}