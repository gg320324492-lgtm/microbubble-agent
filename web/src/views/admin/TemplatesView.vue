<template>
  <div class="page-container templates-view">
    <!-- 顶部 page-header -->
    <div class="page-header">
      <h2>模板管理</h2>
      <p class="page-desc">管理所有会议模板(builtin + custom), 支持批量启用/禁用/删除</p>
    </div>

    <!-- 筛选卡 + 搜索 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters" @submit.prevent="handleSearch">
        <el-form-item label="搜索">
          <el-input
            v-model="filters.search"
            placeholder="按名称模糊搜索"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="类型">
          <el-select
            v-model="filters.type"
            placeholder="全部"
            clearable
            style="width: 120px"
            @change="handleSearch"
          >
            <el-option label="全部" :value="null" />
            <el-option label="内置" value="builtin" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filters.status"
            placeholder="全部"
            clearable
            style="width: 120px"
            @change="handleSearch"
          >
            <el-option label="全部" :value="null" />
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数据卡: 工具栏 + el-table + 分页 -->
    <el-card class="table-card" shadow="never">
      <div class="batch-toolbar">
        <div class="batch-toolbar-left">
          <el-button @click="toggleEditMode">
            <el-icon><Edit /></el-icon>
            {{ editMode ? '取消' : '批量编辑' }}
          </el-button>
          <template v-if="editMode">
            <span class="selected-count">已选 {{ selectedRows.length }} 项</span>
            <el-button
              type="success"
              :disabled="!selectedRows.length"
              @click="handleBatchEnable"
            >
              <el-icon><Check /></el-icon>批量启用
            </el-button>
            <el-button
              type="warning"
              :disabled="!selectedRows.length"
              @click="handleBatchDisable"
            >
              <el-icon><Close /></el-icon>批量禁用
            </el-button>
            <el-button
              type="danger"
              :disabled="!selectedRows.length"
              @click="handleBatchDelete"
            >
              <el-icon><Delete /></el-icon>批量删除
            </el-button>
          </template>
        </div>
        <div class="batch-toolbar-right">
          <span class="total-info">共 {{ total }} 个模板</span>
        </div>
      </div>

      <el-table
        ref="tableRef"
        :data="templates"
        v-loading="loading"
        stripe
        @selection-change="handleSelectionChange"
        :selectable="selectable"
        empty-text="暂无模板"
      >
        <el-table-column v-if="editMode" type="selection" width="45" />
        <el-table-column prop="name" label="名称" min-width="160">
          <template #default="{ row }">
            <span class="tpl-name">{{ row.name }}</span>
            <el-tag v-if="row.is_builtin" size="small" type="info" effect="plain">内置</el-tag>
            <el-tag v-else-if="row.cloned_from_id" size="small" effect="plain">
              克隆自 #{{ row.cloned_from_id }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_builtin ? 'warning' : 'success'" size="small">
              {{ row.is_builtin ? '内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              inline-prompt
              active-text="启用"
              inactive-text="禁用"
              @update:model-value="(val) => handleToggleSingle(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column
          prop="description"
          label="说明"
          min-width="200"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            {{ row.description || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="议题数" width="80" align="center">
          <template #default="{ row }">
            {{ row.agenda?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="时长" width="90" align="center">
          <template #default="{ row }">
            {{ row.default_duration_minutes || 60 }} 分钟
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.is_builtin"
              link
              type="primary"
              size="small"
              @click="handleClone(row)"
            >
              复制为自定义
            </el-button>
            <el-button
              v-else
              link
              type="primary"
              size="small"
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-popconfirm
              v-if="!row.is_builtin"
              title="确定删除此模板？此操作不可撤销。"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="handleDeleteSingle(row)"
            >
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
        class="pagination"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Check, Close, Delete } from '@element-plus/icons-vue'
import axios from 'axios'

const templates = ref([])
const total = ref(0)
const loading = ref(false)
const editMode = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)

const filters = reactive({
  search: '',
  type: null,
  status: null,
  page: 1,
  page_size: 20,
})

async function fetchTemplates() {
  loading.value = true
  try {
    const params = {
      page: filters.page,
      page_size: filters.page_size,
      include_inactive: true, // v77 P2.6-G.2: 页面显示全部 builtin + custom
    }
    if (filters.search) params.search = filters.search
    if (filters.type) params.type = filters.type
    if (filters.status) params.status = filters.status
    const res = await axios.get('/api/v1/meeting-templates', { params })
    templates.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error(`加载模板失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  filters.page = 1
  fetchTemplates()
}

function handleReset() {
  filters.search = ''
  filters.type = null
  filters.status = null
  filters.page = 1
  fetchTemplates()
}

function handlePageChange(p) {
  filters.page = p
  fetchTemplates()
}

function handleSizeChange(s) {
  filters.page_size = s
  filters.page = 1
  fetchTemplates()
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

function toggleEditMode() {
  editMode.value = !editMode.value
  if (!editMode.value) {
    selectedRows.value = []
    tableRef.value?.clearSelection()
  }
}

// v77 P2.6-G.2: builtin 不可选 (与 batch_delete 服务端跳过 builtin 一致)
function selectable(row) {
  return !row.is_builtin
}

async function handleBatchEnable() {
  await batchToggleActive(true)
}

async function handleBatchDisable() {
  await batchToggleActive(false)
}

async function batchToggleActive(isActive) {
  if (!selectedRows.value.length) return
  try {
    const res = await axios.post('/api/v1/meeting-templates/batch-toggle-active', {
      ids: selectedRows.value.map((r) => r.id),
      is_active: isActive,
    })
    ElMessage.success(`已批量${isActive ? '启用' : '禁用'} ${res.data.updated} 个模板`)
    selectedRows.value = []
    tableRef.value?.clearSelection()
    fetchTemplates()
  } catch (e) {
    ElMessage.error(`批量操作失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function handleBatchDelete() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定批量删除 ${selectedRows.value.length} 个模板?此操作不可撤销,内置模板自动跳过。`,
      '批量删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return // 用户取消
  }
  try {
    const res = await axios.post('/api/v1/meeting-templates/batch-delete', {
      ids: selectedRows.value.map((r) => r.id),
    })
    const skipMsg = res.data.skipped_builtin.length
      ? `, ${res.data.skipped_builtin.length} 个内置模板已跳过`
      : ''
    ElMessage.success(`已删除 ${res.data.deleted} 个模板${skipMsg}`)
    selectedRows.value = []
    tableRef.value?.clearSelection()
    fetchTemplates()
  } catch (e) {
    ElMessage.error(`批量删除失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function handleToggleSingle(row, val) {
  try {
    await axios.put(`/api/v1/meeting-templates/${row.id}`, { is_active: val })
    ElMessage.success(val ? '已启用' : '已禁用')
    fetchTemplates()
  } catch (e) {
    ElMessage.error(`操作失败: ${e.response?.data?.detail || e.message}`)
  }
}

async function handleDeleteSingle(row) {
  try {
    await axios.delete(`/api/v1/meeting-templates/${row.id}`)
    ElMessage.success('已删除')
    fetchTemplates()
  } catch (e) {
    ElMessage.error(`删除失败: ${e.response?.data?.detail || e.message}`)
  }
}

function handleClone(row) {
  axios
    .post(`/api/v1/meeting-templates/${row.id}/clone`)
    .then(() => {
      ElMessage.success('已复制为自定义模板')
      fetchTemplates()
    })
    .catch((e) =>
      ElMessage.error(`复制失败: ${e.response?.data?.detail || e.message}`),
    )
}

function handleEdit() {
  // v77 P2.6-G.2 范围聚焦批量管理, 完整 inline edit 留未来
  // 简化: 提示用户去 /meetings 快速模板区编辑
  ElMessage.info('请到 /meetings 的快速模板区编辑自定义模板')
}

function formatTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => fetchTemplates())
</script>

<style scoped>
.templates-view { padding: 24px; }
.page-header { margin-bottom: 16px; }
.filter-card { margin-bottom: 16px; }
.batch-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.batch-toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.batch-toolbar-right {
  font-size: 14px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
  display: flex;
}
.selected-count {
  color: var(--color-primary);
  margin: 0 12px;
  font-weight: 500;
}
.tpl-name {
  margin-right: 8px;
  font-weight: 500;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 (Vue scoped 编译器把 [data-theme="dark"] + 后代选择器处理错) -->
<style>
[data-theme="dark"] .templates-view .page-header h2 {
  color: var(--color-text-primary);
}
[data-theme="dark"] .templates-view .page-desc {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .templates-view .batch-toolbar-right {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .templates-view .total-info {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .templates-view .selected-count {
  color: var(--color-primary);
}
[data-theme="dark"] .templates-view .tpl-name {
  color: var(--color-text-primary);
}
</style>
