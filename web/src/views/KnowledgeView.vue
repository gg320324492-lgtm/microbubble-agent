<template>
  <div class="knowledge-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :span="8">
          <el-input
            v-model="searchQuery"
            placeholder="搜索知识库..."
            clearable
            @keyup.enter="fetchKnowledge"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-select v-model="filterCategory" placeholder="分类" clearable>
            <el-option label="基础知识" value="基础" />
            <el-option label="实验方法" value="方法" />
            <el-option label="文献笔记" value="文献" />
            <el-option label="常见问题" value="FAQ" />
          </el-select>
        </el-col>
        <el-col :span="10">
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            添加知识
          </el-button>
          <el-button @click="showSemanticSearch = true">
            <el-icon><MagicStick /></el-icon>
            AI问答
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 分类标签 -->
    <div class="category-tags">
      <el-tag
        v-for="cat in categories"
        :key="cat.value"
        :type="filterCategory === cat.value ? '' : 'info'"
        :effect="filterCategory === cat.value ? 'dark' : 'plain'"
        @click="filterCategory = filterCategory === cat.value ? '' : cat.value"
        style="cursor: pointer"
      >
        {{ cat.icon }} {{ cat.label }}
      </el-tag>
    </div>

    <!-- 知识列表 -->
    <el-card class="knowledge-list-card">
      <div v-if="knowledgeList.length === 0" class="empty-state">
        <el-empty description="暂无知识条目" />
      </div>

      <div v-else class="knowledge-list">
        <div
          v-for="item in knowledgeList"
          :key="item.id"
          class="knowledge-item"
          @click="viewKnowledge(item)"
        >
          <div class="item-header">
            <div class="item-category">
              <el-tag size="small" :type="getCategoryType(item.category)">
                {{ item.category || '未分类' }}
              </el-tag>
            </div>
            <div class="item-tags">
              <el-tag
                v-for="tag in (item.tags || []).slice(0, 3)"
                :key="tag"
                size="small"
                type="info"
                style="margin-left: 4px"
              >
                {{ tag }}
              </el-tag>
            </div>
          </div>

          <h3 class="item-title">{{ item.title }}</h3>
          <p class="item-content">{{ item.content.substring(0, 150) }}...</p>

          <div class="item-footer">
            <span class="item-time">{{ formatDate(item.created_at) }}</span>
            <div class="item-actions">
              <el-button text type="primary" size="small" @click.stop="editKnowledge(item)">
                编辑
              </el-button>
              <el-button text type="danger" size="small" @click.stop="deleteKnowledge(item)">
                删除
              </el-button>
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
          @current-change="fetchKnowledge"
        />
      </div>
    </el-card>

    <!-- 添加/编辑知识对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingKnowledge ? '编辑知识' : '添加知识'"
      width="600px"
    >
      <el-form :model="knowledgeForm" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="knowledgeForm.title" placeholder="请输入标题" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="knowledgeForm.category" placeholder="选择分类">
            <el-option label="基础知识" value="基础" />
            <el-option label="实验方法" value="方法" />
            <el-option label="文献笔记" value="文献" />
            <el-option label="常见问题" value="FAQ" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="knowledgeForm.tags"
            multiple
            filterable
            allow-create
            placeholder="输入标签"
          >
            <el-option label="气泡" value="气泡" />
            <el-option label="稳定性" value="稳定性" />
            <el-option label="NTA" value="NTA" />
            <el-option label="水处理" value="水处理" />
            <el-option label="农业" value="农业" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input
            v-model="knowledgeForm.content"
            type="textarea"
            :rows="8"
            placeholder="请输入知识内容"
          />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="knowledgeForm.source" placeholder="来源链接或文件路径" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveKnowledge">{{ editingKnowledge ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>

    <!-- AI问答对话框 -->
    <el-dialog v-model="showSemanticSearch" title="AI智能问答" width="600px">
      <div class="semantic-search">
        <el-input
          v-model="semanticQuery"
          placeholder="输入你的问题，AI会从知识库中查找答案..."
          size="large"
          @keyup.enter="semanticSearch"
        >
          <template #append>
            <el-button @click="semanticSearch">
              <el-icon><Search /></el-icon>
            </el-button>
          </template>
        </el-input>

        <div v-if="searchResults.length > 0" class="search-results">
          <div
            v-for="(result, index) in searchResults"
            :key="index"
            class="result-item"
          >
            <div class="result-header">
              <span class="result-title">{{ result.metadata?.title }}</span>
              <el-tag size="small">相似度: {{ (result.score * 100).toFixed(0) }}%</el-tag>
            </div>
            <div class="result-content">{{ result.content }}</div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 知识详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="知识详情" width="600px">
      <div v-if="currentKnowledge" class="knowledge-detail">
        <h2>{{ currentKnowledge.title }}</h2>
        <div class="detail-meta">
          <el-tag :type="getCategoryType(currentKnowledge.category)">
            {{ currentKnowledge.category || '未分类' }}
          </el-tag>
          <span>{{ formatDate(currentKnowledge.created_at) }}</span>
        </div>
        <div class="detail-tags">
          <el-tag
            v-for="tag in (currentKnowledge.tags || [])"
            :key="tag"
            size="small"
            style="margin: 4px"
          >
            {{ tag }}
          </el-tag>
        </div>
        <div class="detail-content">{{ currentKnowledge.content }}</div>
        <div v-if="currentKnowledge.source" class="detail-source">
          来源：{{ currentKnowledge.source }}
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'

const knowledgeList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const filterCategory = ref('')
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const showSemanticSearch = ref(false)
const editingKnowledge = ref(null)
const currentKnowledge = ref(null)
const semanticQuery = ref('')
const searchResults = ref([])

const categories = [
  { value: '基础', label: '基础知识', icon: '📚' },
  { value: '方法', label: '实验方法', icon: '🔬' },
  { value: '文献', label: '文献笔记', icon: '📄' },
  { value: 'FAQ', label: '常见问题', icon: '❓' }
]

const knowledgeForm = ref({
  title: '',
  category: '',
  tags: [],
  content: '',
  source: ''
})

// 获取知识列表
const fetchKnowledge = async () => {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (searchQuery.value) params.keyword = searchQuery.value
    if (filterCategory.value) params.category = filterCategory.value

    const res = await axios.get('/api/v1/knowledge', { params })
    knowledgeList.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('获取知识失败:', e)
  }
}

// 保存知识
const saveKnowledge = async () => {
  if (!knowledgeForm.value.title || !knowledgeForm.value.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }

  try {
    if (editingKnowledge.value) {
      await axios.put(`/api/v1/knowledge/${editingKnowledge.value.id}`, knowledgeForm.value)
      ElMessage.success('知识更新成功')
    } else {
      await axios.post('/api/v1/knowledge', knowledgeForm.value)
      ElMessage.success('知识添加成功')
    }
    showCreateDialog.value = false
    editingKnowledge.value = null
    resetForm()
    fetchKnowledge()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

// 编辑知识
const editKnowledge = (item) => {
  editingKnowledge.value = item
  knowledgeForm.value = { ...item }
  showCreateDialog.value = true
}

// 删除知识
const deleteKnowledge = async (item) => {
  try {
    await ElMessageBox.confirm('确定要删除这条知识吗？', '确认删除', { type: 'warning' })
    await axios.delete(`/api/v1/knowledge/${item.id}`)
    ElMessage.success('知识删除成功')
    fetchKnowledge()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 查看知识详情
const viewKnowledge = (item) => {
  currentKnowledge.value = item
  showDetailDialog.value = true
}

// 语义搜索
const semanticSearch = async () => {
  if (!semanticQuery.value) return

  try {
    const res = await axios.get('/api/v1/knowledge/search/semantic', {
      params: { query: semanticQuery.value }
    })
    searchResults.value = res.data || []

    if (searchResults.value.length === 0) {
      ElMessage.info('未找到相关知识')
    }
  } catch (e) {
    ElMessage.error('搜索失败')
  }
}

// 重置表单
const resetForm = () => {
  knowledgeForm.value = {
    title: '',
    category: '',
    tags: [],
    content: '',
    source: ''
  }
}

// 辅助函数
const formatDate = (date) => date ? dayjs(date).format('YYYY-MM-DD') : '-'

const getCategoryType = (category) => {
  const map = { '基础': '', '方法': 'success', '文献': 'warning', 'FAQ': 'info' }
  return map[category] || 'info'
}

watch(filterCategory, () => {
  currentPage.value = 1
  fetchKnowledge()
})

onMounted(() => {
  fetchKnowledge()
})
</script>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.category-tags {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.knowledge-item {
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  cursor: pointer;
  transition: all 0.3s;
}

.knowledge-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.1);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.item-title {
  font-size: 16px;
  color: #303133;
  margin-bottom: 8px;
}

.item-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin-bottom: 12px;
}

.item-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.item-time {
  font-size: 12px;
  color: #909399;
}

.item-actions {
  display: flex;
  gap: 8px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.semantic-search {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.search-results {
  max-height: 400px;
  overflow-y: auto;
}

.result-item {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 12px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.result-title {
  font-weight: bold;
  color: #303133;
}

.result-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.knowledge-detail h2 {
  margin-bottom: 16px;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.detail-tags {
  margin-bottom: 20px;
}

.detail-content {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
  white-space: pre-wrap;
}

.detail-source {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  font-size: 13px;
  color: #909399;
}
</style>
