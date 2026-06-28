<!-- KnowledgeMemoryTab.vue — v77 P2.6-E.3 拆分自 KnowledgeView.vue -->
<template>
  <div>
    <div class="memory-toolbar">
      <el-input
        v-model="memorySearch.keyword"
        name="memorySearch-keyword"
        placeholder="搜索记忆内容..."
        clearable
        style="width:280px;margin-right:12px"
        @keyup.enter="fetchMemories"
      />
      <el-select
        v-model="memorySearch.type"
        name="memorySearch-type"
        placeholder="类型"
        clearable
        style="width:140px;margin-right:12px"
        @change="fetchMemories"
      >
        <el-option label="全部" value="" />
        <el-option label="偏好" value="preference" />
        <el-option label="用户事实" value="user_fact" />
        <el-option label="任务上下文" value="task_ctx" />
        <el-option label="实体关系" value="entity" />
      </el-select>
      <el-button type="primary" :loading="memoryLoading" @click="fetchMemories">搜索</el-button>
    </div>

    <div v-if="memoryLoading && memoryList.length === 0" class="memory-loading">
      <div v-for="i in 3" :key="i" class="skeleton-card">
        <div class="skeleton-line w-40" />
        <div class="skeleton-line w-90" />
        <div class="skeleton-line w-60" />
      </div>
    </div>

    <div v-else-if="memoryList.length === 0" class="empty-state">
      <el-empty description="还没有记忆，与小气对话时会自动学习" :image-size="80" />
    </div>

    <div v-else class="memory-list">
      <article v-for="item in memoryList" :key="item.id" class="memory-card">
        <div class="memory-header">
          <span class="memory-type-tag" :class="`type-${item.memory_type}`">
            {{ memoryTypeNameMap[item.memory_type] || item.memory_type }}
          </span>
          <span class="memory-importance">
            ⭐ {{ Math.round((item.importance || 0) * 100) }}%
          </span>
        </div>
        <div v-if="item.key" class="memory-key">🔑 {{ item.key }}</div>
        <p class="memory-content">{{ item.content }}</p>
        <div class="memory-footer">
          <span class="memory-time">{{ formatMemoryDate(item.created_at) }}</span>
          <el-button text type="danger" size="small" @click="forgetMemory(item)">遗忘</el-button>
        </div>
      </article>
    </div>

    <div v-if="memoryTotal > memoryPageSize" class="pagination">
      <el-pagination
        v-model:current-page="memoryCurrentPage"
        :page-size="memoryPageSize"
        :total="memoryTotal"
        layout="total, prev, pager, next"
        @current-change="fetchMemories"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * KnowledgeMemoryTab.vue — 我的长期记忆 tab（v77 P2.6-E.3 从 KnowledgeView.vue 拆分）
 *
 * 父组件: KnowledgeView.vue (lazy-loaded tab-pane)
 * Emits: 无（独立数据生命周期）
 */
import { ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '@/utils/format'

const memoryList = ref([])
const memoryTotal = ref(0)
const memoryCurrentPage = ref(1)
const memoryPageSize = ref(20)
const memoryLoading = ref(false)
const memorySearch = ref({ keyword: '', type: '' })

const memoryTypeNameMap = {
  preference: '偏好',
  user_fact: '用户事实',
  task_ctx: '任务上下文',
  summary: '摘要',
  entity: '实体关系',
}

const fetchMemories = async () => {
  memoryLoading.value = true
  try {
    const params = {
      page: memoryCurrentPage.value,
      page_size: memoryPageSize.value,
    }
    if (memorySearch.value.keyword) params.keyword = memorySearch.value.keyword
    if (memorySearch.value.type) params.memory_type = memorySearch.value.type
    const res = await axios.get('/api/v1/memories', { params })
    memoryList.value = res.data.items || []
    memoryTotal.value = res.data.total || 0
  } catch (e) {
    console.error('[KnowledgeMemoryTab] 获取长期记忆失败:', e)
    ElMessage.error('获取长期记忆失败')
  } finally {
    memoryLoading.value = false
  }
}

const forgetMemory = async (item) => {
  try {
    await ElMessageBox.confirm(`确定遗忘「${(item.content || '').slice(0, 30)}...」？`, '遗忘确认', {
      type: 'warning',
      confirmButtonText: '遗忘',
      cancelButtonText: '取消',
    })
    await axios.delete(`/api/v1/memories/${item.id}`)
    ElMessage.success('已遗忘')
    fetchMemories()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

const formatMemoryDate = (d) => formatDateTime(d)

// v77 P2.6-E.3: 暴露 fetchMemories 给父组件 onTabSwitch 调用
defineExpose({ fetchMemories })
</script>

<style scoped>
.memory-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.memory-loading {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.memory-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.memory-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: 10px;
  padding: 14px 16px;
  transition: all var(--duration-fast) var(--ease-out);
}

.memory-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.15);
}

.memory-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.memory-type-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.memory-type-tag.type-preference { background: var(--color-primary-bg); color: var(--color-primary); }
.memory-type-tag.type-user_fact { background: var(--color-success-bg); color: var(--color-success); }
.memory-type-tag.type-task_ctx { background: var(--color-warning-bg); color: var(--color-warning); }
.memory-type-tag.type-summary { background: var(--color-primary-bg); color: var(--color-primary); }
.memory-type-tag.type-entity { background: var(--color-primary-bg); color: var(--color-primary); }

.memory-importance {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.memory-key {
  font-size: 12px;
  color: var(--color-primary);
  margin-bottom: 6px;
}

.memory-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-primary);
  margin: 0 0 10px;
}

.memory-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.skeleton-card {
  background: var(--color-bg-card);
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--color-border-light);
}
.skeleton-line {
  height: 12px;
  background: var(--color-border-light);
  border-radius: 4px;
  margin-bottom: 8px;
}
.skeleton-line.w-40 { width: 40%; }
.skeleton-line.w-90 { width: 90%; }
.skeleton-line.w-60 { width: 60%; }

.empty-state {
  padding: var(--space-10) 0;
}

.pagination {
  margin-top: var(--space-5);
  display: flex;
  justify-content: flex-end;
}
</style>

<style>
/* v77 P2.6-E.3: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .memory-card {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .memory-card:hover {
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.25);
}
[data-theme="dark"] .memory-type-tag.type-preference {
  background: rgba(30, 64, 175, 0.18);
  color: var(--color-primary);
}
[data-theme="dark"] .memory-type-tag.type-user_fact {
  background: rgba(6, 95, 70, 0.22);
  color: var(--color-success);
}
[data-theme="dark"] .memory-type-tag.type-task_ctx {
  background: rgba(146, 64, 14, 0.22);
  color: var(--color-warning);
}
[data-theme="dark"] .memory-type-tag.type-summary {
  background: rgba(55, 48, 163, 0.22);
  color: var(--color-primary);
}
[data-theme="dark"] .memory-type-tag.type-entity {
  background: rgba(159, 18, 57, 0.22);
  color: var(--color-primary);
}
[data-theme="dark"] .memory-content {
  color: var(--color-text-regular);
}
[data-theme="dark"] .skeleton-line {
  background: var(--color-border-base);
}
</style>