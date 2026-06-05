<template>
  <div class="knowledge-search">
    <el-input
      v-model="query"
      placeholder="搜索知识库..."
      clearable
      @keyup.enter="onSearch"
    >
      <template #append>
        <el-button @click="onSearch">
          <el-icon><Search /></el-icon>
        </el-button>
      </template>
    </el-input>

    <div v-if="loading" class="loading">搜索中...</div>
    <div v-else-if="results.length === 0 && query" class="empty">未找到相关知识</div>
    <div v-else class="search-results">
      <div v-for="item in results" :key="item.id" class="result-item" @click="$emit('select', item)">
        <div class="result-title">{{ item.title }}</div>
        <div class="result-score">相关度: {{ Math.round(item.score * 100) }}%</div>
        <div class="result-content">{{ item.content?.substring(0, 100) }}...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { useKnowledge } from '@/composables/useKnowledge'

const { loading, searchKnowledge, searchResults } = useKnowledge()
const query = ref('')

const onSearch = async () => {
  if (query.value) {
    await searchKnowledge(query.value)
  }
}

defineEmits(['select'])
</script>
