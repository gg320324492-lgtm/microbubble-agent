<template>
  <div class="knowledge-dashboard">
    <!-- 知识库概览 -->
    <el-card class="stats-card">
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-number">{{ statsData.total }}</div>
          <div class="stat-label">全部</div>
        </div>
        <div v-for="(count, cat) in statsData.categories" :key="cat" class="stat-item">
          <div class="stat-number">{{ count }}</div>
          <div class="stat-label">{{ cat }}</div>
        </div>
      </div>
    </el-card>

    <!-- 分类标签云 -->
    <el-card v-if="categories.length > 0" class="tag-cloud-card">
      <div class="tag-cloud">
        <span
          v-for="cat in categories"
          :key="cat.name"
          class="cloud-tag"
          :class="{ 'cloud-tag-active': filterCategory === cat.name }"
          @click="$emit('filter', cat.name)"
        >
          {{ cat.name }} ({{ cat.count }})
        </span>
      </div>
    </el-card>

    <!-- 知识列表 -->
    <slot />
  </div>
</template>

<script setup>
defineProps({
  statsData: { type: Object, default: () => ({ total: 0, categories: {} }) },
  categories: { type: Array, default: () => [] },
  filterCategory: { type: String, default: '' }
})

defineEmits(['filter'])
</script>
