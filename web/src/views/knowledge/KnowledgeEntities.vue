<template>
  <div class="knowledge-entities">
    <el-empty v-if="entityList.length === 0" description="暂无实体数据" />
    <div v-else class="entity-list">
      <div v-for="entity in entityList" :key="entity.id" class="entity-item" @click="$emit('select', entity)">
        <div class="entity-name">{{ entity.name }}</div>
        <div class="entity-type">{{ entity.type }}</div>
      </div>
    </div>
    <!-- 分页 -->
    <el-pagination
      v-if="entityTotal > 20"
      :current-page="entityPage"
      :page-size="20"
      :total="entityTotal"
      layout="prev, pager, next"
      @update:current-page="(v) => $emit('page-change', v)"
    />
  </div>
</template>

<script setup>
defineProps({
  entityList: { type: Array, default: () => [] },
  entityTotal: { type: Number, default: 0 },
  entityPage: { type: Number, default: 1 }
})

defineEmits(['select', 'page-change'])
</script>
