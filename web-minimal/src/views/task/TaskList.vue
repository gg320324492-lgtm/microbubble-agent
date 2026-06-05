<template>
  <div class="task-list">
    <div v-for="task in tasks" :key="task.id" class="task-item">
      <div
        class="task-checkbox"
        :class="{ checked: task.status === 'done' }"
        @click="$emit('complete', task)"
      ></div>
      <div class="task-content">
        <div class="task-title" :class="{ completed: task.status === 'done' }">
          {{ task.title }}
        </div>
        <div class="task-meta">
          <span
            class="task-tag"
            :style="{ background: getPriorityBgColor(task.priority), color: getPriorityColor(task.priority) }"
          >
            {{ getPriorityLabel(task.priority) }}
          </span>
          <span
            class="task-tag"
            :style="{ background: getStatusBgColor(task.status), color: getStatusColor(task.status) }"
          >
            {{ getStatusLabel(task.status) }}
          </span>
        </div>
      </div>
      <div class="task-due" :class="getDueDateClass(task.due_date)">
        {{ getDueDateDisplay(task.due_date) }}
      </div>
      <div class="task-actions">
        <button class="btn btn-ghost btn-small" @click="$emit('edit', task)">编辑</button>
        <button class="btn btn-ghost btn-small" @click="$emit('delete', task)">删除</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  getPriorityLabel,
  getPriorityColor,
  getPriorityBgColor,
  getStatusLabel,
  getStatusColor,
  getStatusBgColor,
  getDueDateDisplay,
  getDueDateClass
} from '@/utils/task'

defineProps({
  tasks: {
    type: Array,
    default: () => []
  }
})

defineEmits(['complete', 'edit', 'delete'])
</script>

<style scoped>
.task-list {
  display: flex;
  flex-direction: column;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
  transition: all var(--duration-fast) var(--ease-out);
}

.task-item:last-child {
  border-bottom: none;
}

.task-item:hover {
  background: var(--color-bg-hover);
}

.task-checkbox {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.task-checkbox:hover {
  border-color: var(--color-primary);
}

.task-checkbox.checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.task-checkbox.checked::after {
  content: '✓';
  color: white;
  font-size: 12px;
}

.task-content {
  flex: 1;
}

.task-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.task-title.completed {
  text-decoration: line-through;
  color: var(--color-text-tertiary);
}

.task-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.task-tag {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.task-due {
  font-size: 13px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

.task-due.overdue {
  color: var(--color-danger);
  font-weight: 500;
}

.task-due.today {
  color: var(--color-warning);
  font-weight: 500;
}

.task-actions {
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.task-item:hover .task-actions {
  opacity: 1;
}
</style>
