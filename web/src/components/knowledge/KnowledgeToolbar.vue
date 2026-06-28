<template>
  <div class="knowledge-toolbar">
    <!-- 搜索框 -->
    <div class="toolbar-search">
      <el-input
        v-model="searchQuery"
        placeholder="搜索知识库..."
        clearable
        @keyup.enter="$emit('search', searchQuery)"
        @clear="$emit('search', '')"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
        <template #append>
          <el-button aria-label="高级筛选" @click="showAdvanced = !showAdvanced">
            <el-icon><Filter /></el-icon>
          </el-button>
        </template>
      </el-input>
    </div>

    <!-- 操作按钮组 -->
    <div class="toolbar-actions">
      <el-button type="primary" @click="$emit('create')">
        <el-icon><Plus /></el-icon>
        <span class="btn-text">添加知识</span>
      </el-button>
      <el-button @click="$emit('upload')">
        <el-icon><Upload /></el-icon>
        <span class="btn-text">上传文件</span>
      </el-button>
      <el-button type="primary" @click="$emit('qa')">
        <el-icon><MagicStick /></el-icon>
        <span class="btn-text">AI问答</span>
      </el-button>
      <el-button @click="$emit('entities')">
        <el-icon><Share /></el-icon>
        <span class="btn-text">实体图谱</span>
      </el-button>
    </div>

    <!-- 高级筛选面板 -->
    <transition name="slide-down">
      <div v-if="showAdvanced" class="advanced-filters">
        <div class="filter-row">
          <div class="filter-item">
            <label>分类</label>
            <el-select
              v-model="filters.category"
              placeholder="全部分类"
              clearable
              @change="applyFilters"
            >
              <el-option
                v-for="cat in categories"
                :key="cat.name"
                :label="`${cat.name} (${cat.count})`"
                :value="cat.name"
              />
            </el-select>
          </div>

          <div class="filter-item">
            <label>来源类型</label>
            <el-select
              v-model="filters.sourceType"
              placeholder="全部来源"
              clearable
              @change="applyFilters"
            >
              <el-option label="文件上传" value="file" />
              <el-option label="对话记录" value="conversation" />
              <el-option label="AI自动研究" value="auto_research" />
              <el-option label="论文" value="paper" />
              <el-option label="笔记" value="notes" />
            </el-select>
          </div>

          <div class="filter-item">
            <label>时间范围</label>
            <el-select
              v-model="filters.timeRange"
              placeholder="全部时间"
              clearable
              @change="applyFilters"
            >
              <el-option label="今天" value="today" />
              <el-option label="本周" value="week" />
              <el-option label="本月" value="month" />
              <el-option label="本年" value="year" />
            </el-select>
          </div>

          <div class="filter-item">
            <label>排序</label>
            <el-select
              v-model="filters.sort"
              placeholder="最新优先"
              @change="applyFilters"
            >
              <el-option label="最新优先" value="newest" />
              <el-option label="最早优先" value="oldest" />
              <el-option label="质量评分" value="quality" />
            </el-select>
          </div>
        </div>

        <div class="filter-actions">
          <el-button text @click="resetFilters">重置筛选</el-button>
          <el-button type="primary" size="small" @click="applyFilters">应用</el-button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { Search, Plus, Upload, MagicStick, Share, Filter } from '@element-plus/icons-vue'

const props = defineProps({
  categories: { type: Array, default: () => [] }
})

const emit = defineEmits(['search', 'create', 'upload', 'qa', 'entities', 'filter'])

const searchQuery = ref('')
const showAdvanced = ref(false)

const filters = reactive({
  category: '',
  sourceType: '',
  timeRange: '',
  sort: 'newest'
})

const applyFilters = () => {
  emit('filter', { ...filters })
}

const resetFilters = () => {
  filters.category = ''
  filters.sourceType = ''
  filters.timeRange = ''
  filters.sort = 'newest'
  applyFilters()
}
</script>

<style scoped>
.knowledge-toolbar {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.toolbar-search {
  display: flex;
  gap: var(--space-3);
}

.toolbar-search .el-input {
  flex: 1;
}

.toolbar-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.toolbar-actions .el-button {
  flex-shrink: 0;
  font-weight: 500;
}

.toolbar-actions .el-button--primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--el-color-white);

  --el-button-hover-bg-color: var(--color-primary-dark);
  --el-button-hover-border-color: var(--color-primary-dark);
  --el-button-hover-text-color: var(--el-color-white);
  --el-button-active-bg-color: var(--color-primary-dark);
  --el-button-active-border-color: var(--color-primary-dark);
}

.btn-text {
  margin-left: var(--space-1);
}

/* 高级筛选面板 */
.advanced-filters {
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light);
}

.filter-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.filter-item label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-medium);
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

/* 动画 */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all var(--duration-normal) var(--ease-out);
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  margin-top: 0;
}

.slide-down-enter-to,
.slide-down-leave-from {
  opacity: 1;
  max-height: 200px;
}

/* 响应式 */
@media (max-width: 768px) {
  .toolbar-actions {
    justify-content: stretch;
  }

  .toolbar-actions .el-button {
    flex: 1;
  }

  .btn-text {
    display: none;
  }

  .filter-row {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 480px) {
  .filter-row {
    grid-template-columns: 1fr;
  }
}
</style>
