<template>
  <div class="mobile-memory-view">
    <PageHeader title="长期记忆" show-back @back="$router.back()">
      <template #right>
        <!-- 顶部搜索入口（与 chip 筛选互不冲突） -->
        <button
          type="button"
          class="header-action"
          aria-label="搜索记忆"
          title="搜索记忆"
          @click="showSearch = true"
        >🔍</button>
      </template>
    </PageHeader>

    <main
      class="memory-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 类型筛选 chip -->
      <div class="type-chips">
        <button
          v-for="t in typeOptions"
          :key="t.value"
          type="button"
          class="type-chip"
          :class="{ active: filterType === t.value }"
          @click="setFilterType(t.value)"
        >
          {{ t.label }} <span v-if="getTypeCount(t.value)" class="chip-count">{{ getTypeCount(t.value) }}</span>
        </button>
      </div>

      <!-- 列表 -->
      <div v-if="loading && memoryList.length === 0" class="loading">
        <div v-for="i in 3" :key="i" class="skeleton-card">
          <div class="skeleton-line w-40" />
          <div class="skeleton-line w-90" />
          <div class="skeleton-line w-60" />
        </div>
      </div>

      <div v-else-if="memoryList.length === 0" class="empty-state">
        <div class="empty-icon">🧠</div>
        <div class="empty-title">暂无记忆</div>
        <div class="empty-hint">与小气对话时会自动学习</div>
      </div>

      <div v-else class="memory-list">
        <article
          v-for="item in memoryList"
          :key="item.id"
          class="memory-card"
          @click="editMemory(item)"
        >
          <div class="memory-header">
            <span class="memory-type-tag" :class="`type-${item.memory_type}`">
              {{ typeNameMap[item.memory_type] || item.memory_type }}
            </span>
            <span class="memory-importance">
              ⭐ {{ (item.importance * 100).toFixed(0) }}%
            </span>
          </div>

          <div v-if="item.key" class="memory-key">🔑 {{ item.key }}</div>

          <p class="memory-content">{{ item.content }}</p>

          <div class="memory-footer">
            <span class="memory-time">{{ formatDate(item.created_at) }}</span>
            <button
              type="button"
              class="delete-btn"
              @click.stop="deleteMemory(item)"
            >遗忘</button>
          </div>
        </article>
      </div>

      <!-- 简易分页 -->
      <div v-if="total > pageSize" class="pagination">
        <button
          type="button"
          class="page-btn"
          :disabled="currentPage <= 1"
          @click="onPageChange(currentPage - 1)"
        >上一页</button>
        <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页</span>
        <button
          type="button"
          class="page-btn"
          :disabled="currentPage >= totalPages"
          @click="onPageChange(currentPage + 1)"
        >下一页</button>
      </div>
    </main>

    <!-- 搜索 Sheet -->
    <MobileSearchSheet
      v-model="showSearch"
      v-model:keyword="searchKeyword"
      title="搜索记忆"
      placeholder="搜索记忆内容..."
      @confirm="onSearchConfirm"
    />

    <!-- 编辑 Sheet -->
    <Teleport to="body">
      <Transition name="edit-sheet">
        <div v-if="showEdit" class="sheet-overlay" @click.self="closeEdit">
          <div class="sheet-panel" :style="{ paddingBottom: 'calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))' }">
            <div class="sheet-handle" />
            <h3 class="sheet-title">编辑记忆</h3>
            <textarea
              v-model="editContent"
              class="edit-textarea"
              placeholder="记忆内容"
              rows="6"
              maxlength="500"
            />
            <div class="sheet-actions">
              <button type="button" class="btn-secondary" @click="closeEdit">取消</button>
              <button type="button" class="btn-primary" @click="saveEdit">保存</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
/**
 * MobileMemoryView.vue — 移动端长期记忆列表
 *
 * PR #8a: 简化版（CardList 风格卡片）
 * - 顶部类型筛选 chip
 * - 卡片化列表（无 el-table）
 * - 点击编辑（底部 sheet）
 * - 简易分页
 */

import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import PageHeader from '@/components/mobile/PageHeader.vue'
import MobileSearchSheet from '@/components/mobile/MobileSearchSheet.vue'

const showSearch = ref(false)
const loading = ref(false)
const memoryList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const filterType = ref('')
const searchKeyword = ref('')

const showEdit = ref(false)
const editingMemory = ref(null)
const editContent = ref('')

const typeNameMap = {
  preference: '偏好',
  summary: '摘要',
  entity: '实体关系',
}

const typeOptions = [
  { label: '全部', value: '' },
  { label: '偏好', value: 'preference' },
  { label: '摘要', value: 'summary' },
  { label: '实体关系', value: 'entity' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

// 加载
async function fetchMemories() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (filterType.value) params.memory_type = filterType.value
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const res = await axios.get('/api/v1/memory', { params })
    memoryList.value = res.data?.items || []
    total.value = res.data?.pagination?.total || res.data?.total || 0
  } catch (e) {
    console.error('[MobileMemoryView] load failed:', e)
  } finally {
    loading.value = false
  }
}

function onSearchConfirm({ keyword }) {
  searchKeyword.value = keyword
  currentPage.value = 1
  fetchMemories()
}

function setFilterType(value) {
  filterType.value = value
  currentPage.value = 1
  fetchMemories()
}

function onPageChange(page) {
  currentPage.value = page
  fetchMemories()
}

// 实时统计每个类型的记忆数量（从已加载的 memoryList）
// 注意：仅在当前页数据内统计，跨页需后端 /memory/stats 端点支持
function getTypeCount(type) {
  if (!type) return null
  const count = memoryList.value.filter((m) => (m.memory_type || m.type) === type).length
  return count > 0 ? count : null
}

function formatDate(t) {
  if (!t) return ''
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

// 编辑
function editMemory(item) {
  editingMemory.value = item
  editContent.value = item.content
  showEdit.value = true
}

function closeEdit() {
  showEdit.value = false
  editingMemory.value = null
}

async function saveEdit() {
  if (!editingMemory.value) return
  try {
    await axios.put(`/api/v1/memory/${editingMemory.value.id}`, {
      content: editContent.value,
    })
    ElMessage.success('已保存')
    closeEdit()
    fetchMemories()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

// 删除
async function deleteMemory(item) {
  try {
    await ElMessageBox.confirm(
      `确定遗忘"${item.content.slice(0, 30)}..."？`,
      '遗忘记忆',
      { confirmButtonText: '遗忘', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  try {
    await axios.delete(`/api/v1/memory/${item.id}`)
    ElMessage.success('已遗忘')
    fetchMemories()
  } catch (e) {
    ElMessage.error('遗忘失败')
  }
}

onMounted(() => {
  fetchMemories()
})
</script>

<style scoped>
.mobile-memory-view {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.memory-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 类型筛选 */
.type-chips {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.type-chips::-webkit-scrollbar { display: none; }
.type-chip {
  flex-shrink: 0;
  padding: 6px 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  display: flex;
  align-items: center;
  gap: 4px;
}
.type-chip.active {
  background: var(--color-primary);
  /* stylelint-disable-next-line color-named */
  color: white;
  border-color: var(--color-primary);
}
.chip-count {
  font-size: 11px;
  padding: 0 5px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 8px;
}

/* 列表 */
.memory-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.memory-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 12px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.memory-card:active { background: var(--color-bg-hover); }

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.memory-type-tag {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: var(--font-weight-medium, 500);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
.type-summary { background: var(--color-success-bg); color: var(--color-success, #67C23A); }
.type-entity { background: var(--color-warning-bg); color: var(--color-warning, #E6A23C); }

.memory-importance {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.memory-key {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
  font-style: italic;
}

.memory-content {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.6;
  margin: 0 0 8px;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.memory-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.memory-time {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.delete-btn {
  background: transparent;
  border: none;
  font-size: 12px;
  color: var(--color-danger, #F56C6C);
  cursor: pointer;
  padding: 4px 8px;
}

/* 加载 / 空 */
.loading, .empty-state {
  padding: 20px 0;
}
.empty-state {
  text-align: center;
  padding: 60px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  color: var(--color-text-regular);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.skeleton-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 8px;
}
.skeleton-line {
  height: 12px;
  background: var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
  position: relative;
  overflow: hidden;
}
.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--color-bg-warm), transparent);
  animation: shimmer 1.5s infinite;
}
.skeleton-line.w-60 { width: 60%; }
.skeleton-line.w-90 { width: 90%; }
.skeleton-line.w-40 { width: 40%; }
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  margin-top: 12px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
}
.page-btn {
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--color-bg-page);
  font-size: 12px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info {
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* Header action */
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-action:active { background: var(--color-primary-bg); }

/* Edit Sheet */
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px;
}
[data-theme="dark"] .sheet-panel { background: var(--color-bg-card); }
.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
}
.sheet-title {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}
.edit-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  resize: vertical;
  margin-bottom: 16px;
}
.sheet-actions {
  display: flex;
  gap: 8px;
}
.btn-secondary, .btn-primary {
  flex: 1;
  padding: 12px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 14px;
  cursor: pointer;
}
.btn-secondary {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}
.btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  /* stylelint-disable-next-line color-named */
  color: white;
}

.edit-sheet-enter-active, .edit-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.edit-sheet-enter-active .sheet-panel,
.edit-sheet-leave-active .sheet-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.edit-sheet-enter-from, .edit-sheet-leave-to { opacity: 0; }
.edit-sheet-enter-from .sheet-panel,
.edit-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>