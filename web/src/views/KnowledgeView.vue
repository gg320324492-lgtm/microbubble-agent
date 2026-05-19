<template>
  <div class="knowledge-view">
    <!-- 分类统计面板 -->
    <el-card v-if="statsData.total > 0" class="stats-card">
      <div class="stats-grid">
        <div
          class="stat-item stat-total"
          :class="{ 'stat-active': filterCategory === '' }"
          @click="filterCategory = ''"
        >
          <div class="stat-icon">📊</div>
          <div class="stat-number">{{ statsData.total }}</div>
          <div class="stat-label">全部</div>
        </div>
        <div
          v-for="(count, cat) in statsData.categories"
          :key="cat"
          class="stat-item"
          :class="['stat-' + getCategoryKey(cat), { 'stat-active': filterCategory === cat }]"
          @click="filterCategory = filterCategory === cat ? '' : cat"
        >
          <div class="stat-icon">{{ getCategoryIcon(cat) }}</div>
          <div class="stat-number">{{ count }}</div>
          <div class="stat-label">{{ cat }}</div>
        </div>
      </div>
    </el-card>

    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :sm="12" :md="8">
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
        <el-col :xs="12" :sm="12" :md="6">
          <el-select v-model="filterCategory" placeholder="分类" clearable>
            <el-option label="基础知识" value="基础" />
            <el-option label="实验方法" value="方法" />
            <el-option label="文献笔记" value="文献" />
            <el-option label="常见问题" value="FAQ" />
          </el-select>
        </el-col>
        <el-col :xs="12" :sm="12" :md="10">
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            添加知识
          </el-button>
          <el-button @click="showUploadDialog = true">
            <el-icon><Upload /></el-icon>
            上传文件
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
      <span
        v-for="cat in categories"
        :key="cat.value"
        class="category-tag-item"
        :class="{ 'category-tag-active': filterCategory === cat.value }"
        @click="filterCategory = filterCategory === cat.value ? '' : cat.value"
      >
        <span class="category-tag-icon">{{ cat.icon }}</span>
        <span class="category-tag-text">{{ cat.label }}</span>
      </span>
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
              <span class="category-badge" :class="'cat-' + getCategoryKey(item.category)">
                <span class="category-icon">{{ getCategoryIcon(item.category) }}</span>
                {{ item.category || '未分类' }}
              </span>
            </div>
            <div class="item-tags">
              <span
                v-for="tag in (item.tags || []).slice(0, 4)"
                :key="tag"
                class="tag-chip"
              >
                {{ tag }}
              </span>
              <span v-if="(item.tags || []).length > 4" class="tag-chip tag-more">
                +{{ item.tags.length - 4 }}
              </span>
            </div>
          </div>

          <h3 class="item-title">
            <el-icon v-if="item.file_path" style="margin-right: 4px; color: #409eff"><Document /></el-icon>
            <span v-if="item.source_type === 'conversation'" class="conversation-badge" title="来自对话记录">💬</span>
            {{ item.title }}
          </h3>
          <p v-if="item.summary" class="item-summary">{{ item.summary }}</p>
          <p v-else class="item-content">{{ item.content.substring(0, 150) }}...</p>

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
      :width="isMobile ? '90vw' : '600px'"
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
    <el-dialog v-model="showSemanticSearch" title="AI智能问答" :width="isMobile ? '90vw' : '600px'">
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
              <span class="result-title">{{ result.title }}</span>
              <el-tag size="small">相似度: {{ (result.score * 100).toFixed(0) }}%</el-tag>
            </div>
            <div v-if="result.category" class="result-category">
              <el-tag size="small" :type="getCategoryType(result.category)">{{ result.category }}</el-tag>
            </div>
            <div class="result-content">{{ result.content }}</div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 知识详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="知识详情" :width="isMobile ? '90vw' : '600px'">
      <div v-if="currentKnowledge" class="knowledge-detail">
        <h2>{{ currentKnowledge.title }}</h2>
        <div class="detail-meta">
          <span class="category-badge" :class="'cat-' + getCategoryKey(currentKnowledge.category)">
            <span class="category-icon">{{ getCategoryIcon(currentKnowledge.category) }}</span>
            {{ currentKnowledge.category || '未分类' }}
          </span>
          <span class="detail-date">{{ formatDate(currentKnowledge.created_at) }}</span>
        </div>
        <div v-if="currentKnowledge.tags && currentKnowledge.tags.length" class="detail-tags">
          <span
            v-for="tag in currentKnowledge.tags"
            :key="tag"
            class="tag-chip detail-tag"
          >
            {{ tag }}
          </span>
        </div>
        <div v-if="currentKnowledge.summary" class="detail-summary">
          <div class="summary-label">AI 摘要</div>
          <div class="summary-text">{{ currentKnowledge.summary }}</div>
        </div>
        <div class="detail-content">{{ currentKnowledge.content }}</div>
        <div v-if="currentKnowledge.source || currentKnowledge.file_name || currentKnowledge.source_type === 'conversation'" class="detail-source">
          <div v-if="currentKnowledge.source_type === 'conversation'" class="detail-conversation-source">
            <span>💬</span> 来自对话记录，AI 自动提取
          </div>
          <div v-if="currentKnowledge.source && currentKnowledge.source_type !== 'conversation'">来源：{{ currentKnowledge.source }}</div>
          <div v-if="currentKnowledge.file_name">文件：{{ currentKnowledge.file_name }}</div>
        </div>
      </div>
    </el-dialog>

    <!-- 文件上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传文件到知识库" :width="isMobile ? '90vw' : '500px'">
      <div class="upload-ai-notice">
        <el-icon size="16" color="#409eff"><MagicStick /></el-icon>
        <span>上传后 AI 将自动分析内容，生成摘要、分类和标签</span>
      </div>
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="uploadTitle" placeholder="留空则使用文件名" />
        </el-form-item>
      </el-form>
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md"
        :on-change="onUploadFileChange"
        :on-exceed="() => ElMessage.warning('只能上传一个文件')"
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PDF、Word、Excel、TXT、Markdown，最大 50MB</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          {{ uploading ? '分析中...' : '上传' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, MagicStick, Upload, Document } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'

const isMobile = ref(window.innerWidth <= 768)
const knowledgeList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const filterCategory = ref('')
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const showSemanticSearch = ref(false)
const showUploadDialog = ref(false)
const editingKnowledge = ref(null)
const currentKnowledge = ref(null)
const semanticQuery = ref('')
const searchResults = ref([])
const statsData = ref({ total: 0, categories: {} })
const uploadTitle = ref('')
const uploadFile = ref(null)
const uploading = ref(false)
const uploadRef = ref(null)

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
    fetchStats()
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
    fetchStats()
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

// 获取统计
const fetchStats = async () => {
  try {
    const res = await axios.get('/api/v1/knowledge/stats')
    statsData.value = res.data
  } catch (e) {
    console.error('获取统计失败:', e)
  }
}

// 上传文件变更
const onUploadFileChange = (file) => {
  uploadFile.value = file.raw
}

// 上传文件
const handleUpload = async () => {
  if (!uploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.value)
    if (uploadTitle.value) formData.append('title', uploadTitle.value)

    await axios.post('/api/v1/knowledge/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success('文件上传成功，后台正在分析...')
    showUploadDialog.value = false
    uploadTitle.value = ''
    uploadFile.value = null
    if (uploadRef.value) uploadRef.value.clearFiles()
    fetchKnowledge()
    fetchStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

// 辅助函数
const formatDate = (date) => date ? dayjs(date).format('YYYY-MM-DD') : '-'

const getCategoryType = (category) => {
  const map = { '基础': '', '方法': 'success', '文献': 'warning', 'FAQ': 'info' }
  return map[category] || 'info'
}

const getCategoryIcon = (category) => {
  const map = { '基础': '📚', '方法': '🔬', '文献': '📄', 'FAQ': '❓' }
  return map[category] || '📁'
}

const getCategoryKey = (category) => {
  const map = { '基础': 'base', '方法': 'method', '文献': 'literature', 'FAQ': 'faq' }
  return map[category] || 'unknown'
}

watch(filterCategory, () => {
  currentPage.value = 1
  fetchKnowledge()
})

onMounted(() => {
  fetchKnowledge()
  fetchStats()
})
</script>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.stats-grid {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.stat-item {
  text-align: center;
  cursor: pointer;
  padding: 12px 20px;
  border-radius: 12px;
  transition: all 0.2s;
  color: rgba(255, 255, 255, 0.8);
  min-width: 80px;
}

.stat-item:hover,
.stat-active {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
}

.stat-total {
  color: #fff;
}

.stat-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.stat-number {
  font-size: 24px;
  font-weight: bold;
}

.stat-label {
  font-size: 12px;
  margin-top: 4px;
}

.item-summary {
  font-size: 13px;
  color: #909399;
  line-height: 1.6;
  margin-bottom: 12px;
  font-style: italic;
}

.result-category {
  margin-bottom: 8px;
}

.category-tags {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.category-tag-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 20px;
  background: #fff;
  border: 1px solid #e4e7ed;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
  color: #606266;
}

.category-tag-item:hover {
  border-color: #409eff;
  color: #409eff;
  background: #f0f9ff;
}

.category-tag-active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}

.category-tag-active:hover {
  background: #337ecc;
  border-color: #337ecc;
  color: #fff;
}

.category-tag-icon {
  font-size: 16px;
}

.category-tag-text {
  font-weight: 500;
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
  flex-wrap: wrap;
  gap: 8px;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}

.category-icon {
  font-size: 13px;
}

.cat-base { background: #e8f4fd; color: #1a7fd4; }
.cat-method { background: #e8f8e8; color: #2d8c2d; }
.cat-literature { background: #fff3e0; color: #c77c00; }
.cat-faq { background: #f3e8fd; color: #7b3fa0; }
.cat-unknown { background: #f0f2f5; color: #909399; }

.tag-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  background: #f0f2f5;
  color: #606266;
  margin-left: 4px;
  transition: all 0.2s;
}

.tag-chip:hover {
  background: #e0e2e5;
  color: #303133;
}

.tag-more {
  background: #e8f4fd;
  color: #409eff;
}

.item-title {
  font-size: 16px;
  color: #303133;
  margin-bottom: 8px;
}

.conversation-badge {
  display: inline-block;
  margin-right: 4px;
  font-size: 14px;
  vertical-align: middle;
  opacity: 0.8;
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

.upload-ai-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f0f9ff;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #409eff;
}

.knowledge-detail h2 {
  margin-bottom: 16px;
  color: #303133;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.detail-date {
  font-size: 13px;
  color: #909399;
}

.detail-tags {
  margin-bottom: 20px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-tag {
  font-size: 12px;
}

.detail-summary {
  background: linear-gradient(135deg, #f0f9ff 0%, #e8f4fd 100%);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
  border-left: 4px solid #409eff;
}

.summary-label {
  font-size: 12px;
  color: #409eff;
  font-weight: 600;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.summary-text {
  font-size: 14px;
  line-height: 1.7;
  color: #303133;
}

.detail-content {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
  white-space: pre-wrap;
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.detail-source {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  font-size: 13px;
  color: #909399;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-conversation-source {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #409eff;
  font-weight: 500;
}
</style>
