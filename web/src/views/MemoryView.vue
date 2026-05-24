<template>
  <div class="memory-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :sm="12" :md="8">
          <el-select v-model="filterType" placeholder="记忆类型" clearable>
            <el-option label="全部" value="" />
            <el-option label="偏好" value="preference" />
            <el-option label="摘要" value="summary" />
            <el-option label="实体关系" value="entity" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="12" :md="16">
          <span class="memory-count">共 {{ total }} 条记忆</span>
        </el-col>
      </el-row>
    </el-card>

    <!-- 记忆列表 -->
    <el-card class="memory-list-card">
      <div v-if="memoryList.length === 0" class="empty-state">
        <el-empty description="暂无长期记忆" />
      </div>

      <div v-else class="memory-list">
        <div
          v-for="item in memoryList"
          :key="item.id"
          class="memory-item"
        >
          <div class="memory-header">
            <el-tag
              size="small"
              :type="getTypeTag(item.memory_type)"
            >
              {{ typeNameMap[item.memory_type] || item.memory_type }}
            </el-tag>
            <span v-if="item.key" class="memory-key">{{ item.key }}</span>
            <div class="memory-meta">
              <span class="memory-importance">重要性: {{ (item.importance * 100).toFixed(0) }}%</span>
              <span class="memory-access">访问: {{ item.access_count }}次</span>
            </div>
          </div>
          <div class="memory-content">{{ item.content }}</div>
          <div class="memory-footer">
            <span class="memory-time">{{ formatDate(item.created_at) }}</span>
            <div class="memory-actions">
              <el-button text type="primary" size="small" @click="editMemory(item)">编辑</el-button>
              <el-button text type="danger" size="small" @click="deleteMemory(item)">遗忘</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchMemories"
        />
      </div>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑记忆"
      :width="isMobile ? '90vw' : '500px'"
      top="8vh"
    >
      <el-form label-width="80px">
        <el-form-item label="内容">
          <el-input
            v-model="editContent"
            type="textarea"
            :rows="4"
            placeholder="记忆内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatDateTime } from '@/utils/format'

const isMobile = ref(window.innerWidth <= 768)
const memoryList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const filterType = ref('')
const showEditDialog = ref(false)
const editingMemory = ref(null)
const editContent = ref('')

const typeNameMap = {
  preference: '偏好',
  summary: '摘要',
  entity: '实体关系'
}

// 获取记忆列表
const fetchMemories = async () => {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterType.value) params.memory_type = filterType.value

    const res = await axios.get('/api/v1/memories', { params })
    memoryList.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('获取记忆失败:', e)
  }
}

// 编辑记忆
const editMemory = (item) => {
  editingMemory.value = item
  editContent.value = item.content
  showEditDialog.value = true
}

// 保存编辑
const saveEdit = async () => {
  if (!editContent.value.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }
  try {
    await axios.put(`/api/v1/memories/${editingMemory.value.id}`, {
      content: editContent.value
    })
    ElMessage.success('记忆已更新')
    showEditDialog.value = false
    fetchMemories()
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

// 删除记忆
const deleteMemory = async (item) => {
  try {
    await ElMessageBox.confirm('确定要遗忘这条记忆吗？', '确认遗忘', { type: 'warning' })
    await axios.delete(`/api/v1/memories/${item.id}`)
    ElMessage.success('记忆已遗忘')
    fetchMemories()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

// 辅助函数
const formatDate = (date) => formatDateTime(date)

const getTypeTag = (type) => {
  const map = { preference: '', summary: 'success', entity: 'warning' }
  return map[type] || 'info'
}

watch(filterType, () => {
  currentPage.value = 1
  fetchMemories()
})

onMounted(() => {
  fetchMemories()
})
</script>

<style scoped>
.memory-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.filter-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.memory-list-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) 80ms both;
}

.memory-count {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
}

.memory-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.memory-item {
  padding: var(--space-4);
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.memory-item:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
  transform: translateY(-2px);
}

.memory-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}

.memory-key {
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}

.memory-meta {
  margin-left: auto;
  display: flex;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.memory-content {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  line-height: 1.6;
  margin-bottom: var(--space-3);
  white-space: pre-wrap;
}

.memory-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.memory-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.memory-actions {
  display: flex;
  gap: var(--space-2);
}

.memory-actions .el-button {
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.memory-actions .el-button:hover {
  transform: scale(1.02);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.pagination {
  margin-top: var(--space-5);
  display: flex;
  justify-content: flex-end;
}
</style>
