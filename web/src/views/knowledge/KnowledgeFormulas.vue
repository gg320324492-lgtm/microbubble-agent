<template>
  <div class="knowledge-formulas">
    <el-empty v-if="formulaList.length === 0" description="暂无公式" />
    <div v-else class="formula-list">
      <div v-for="f in formulaList" :key="f.id" class="formula-item" @click="$emit('select', f)">
        <div class="formula-name">{{ f.name }}</div>
        <div class="formula-category">{{ f.category }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  formulaList: { type: Array, default: () => [] }
})

defineEmits(['select'])
</script>
