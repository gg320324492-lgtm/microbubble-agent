<template>
  <div class="knowledge-hypotheses">
    <el-empty v-if="hypothesisList.length === 0" description="暂无假设" />
    <div v-else class="hypothesis-list">
      <div v-for="h in hypothesisList" :key="h.id" class="hypothesis-item">
        <div class="hypothesis-title">{{ h.title }}</div>
        <div class="hypothesis-status">
          <el-tag :type="h.status === 'validated' ? 'success' : h.status === 'rejected' ? 'danger' : 'info'">
            {{ h.status }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  hypothesisList: { type: Array, default: () => [] }
})
</script>
