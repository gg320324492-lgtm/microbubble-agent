<template>
  <div class="task-list">
    <!-- 任务列表内容 -->
    <slot :tasks="tasks" :loading="loading" />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useTask } from '@/composables/useTask'

const { tasks, loading, fetchTasks } = useTask()

onMounted(() => {
  fetchTasks()
})

defineExpose({ fetchTasks })
</script>
