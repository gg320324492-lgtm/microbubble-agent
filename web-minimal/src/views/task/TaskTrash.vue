<template>
  <div class="task-trash">
    <header class="header">
      <div class="header-left">
        <h2>任务垃圾桶</h2>
        <p>已删除的任务（3天后自动清除）</p>
      </div>
      <div class="header-right">
        <button class="btn btn-danger" @click="handlePurgeAll">清空垃圾桶</button>
      </div>
    </header>

    <div class="trash-list">
      <div v-for="task in tasks" :key="task.id" class="trash-item">
        <div class="task-content">
          <div class="task-title">{{ task.title }}</div>
          <div class="task-meta">
            <span class="task-tag" :style="{ background: getPriorityBgColor(task.priority), color: getPriorityColor(task.priority) }">
              {{ getPriorityLabel(task.priority) }}
            </span>
            <span class="delete-time">删除于 {{ task.deleted_at }}</span>
          </div>
        </div>
        <div class="task-actions">
          <button class="btn btn-secondary btn-small" @click="$emit('restore', task)">恢复</button>
          <button class="btn btn-danger btn-small" @click="$emit('purge', task)">永久删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { getPriorityLabel, getPriorityColor, getPriorityBgColor } from '@/utils/task'

defineProps({
  tasks: {
    type: Array,
    default: () => []
  }
})

defineEmits(['restore', 'purge', 'purgeAll'])

const handlePurgeAll = () => {
  if (confirm('确定要永久删除所有任务吗？此操作不可恢复。')) {
    // emit('purgeAll')
  }
}
</script>

<style scoped>
.task-trash {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

.trash-list {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.trash-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
  transition: all var(--duration-fast) var(--ease-out);
}

.trash-item:last-child {
  border-bottom: none;
}

.trash-item:hover {
  background: var(--color-bg-hover);
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

.task-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.task-tag {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.delete-time {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.task-actions {
  display: flex;
  gap: 8px;
}
</style>
