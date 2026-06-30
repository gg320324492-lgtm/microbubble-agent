<!--
  TemplatesPanel.vue — 模板管理子面板 (v78 UI redesign)

  2026-06-30 从 web/src/views/admin/TemplatesView.vue 搬到此处:
  - 作为子组件嵌入 MeetingView 的 "模板管理" tab
  - sidebar "模板管理" 项已删 (route 移除), 单入口在 /meetings
  - 复用 MeetingView 已有的 MeetingTemplateDialog (v77 P2.6-F.2 抽出)

  复用:
  - MeetingView.onDeleteTemplate / onCloneTemplate / onToggleActive (line 339/351/363)
  - MeetingView.onSaveAsTemplate (line 332, 处理"存为新模板"事件)
  - MeetingView.editingTemplate + showTemplateDialog (line 319-320)

  emits:
  - edit(template): 点击"编辑"按钮 → 父 MeetingView 打开 MeetingTemplateDialog
  - delete(id) / clone(id) / toggle-active({id, is_active})
  - batch-toggle-active({ids, is_active}) / batch-delete(ids)
-->
<template>
  <div class="templates-panel">
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
          <el-select v-model="filters.type" placeholder="全部" clearable style="width: 120px" @change="handleSearch">
            <el-option label="全部" :value="null" />
            <el-option label="内置" value="builtin" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px" @change="handleSearch">
            <el-option label="全部" :value="null" />
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon> 搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格卡 + 批量操作 -->
    <el-card class="table-card" shadow="never" style="margin-top: 16px">
      <div class="batch-toolbar">
        <div class="batch-toolbar-left">
          <el-button @click="toggleEditMode">
            <el-icon><Edit /></el-icon>
            {{ editMode ? '取消' : '批量编辑' }}
          </el-button>
          <template v-if="editMode">
            <span class="selected-count">已选 {{ selectedRows.length }} 项</span>
            <el-button type="success" :disabled="!selectedRows.length" @click="$emit('batch-toggle-active', { ids: selectedRows.map(r => r.id), is_active: true })">
              批量启用
            </el-button>
            <el-button type="warning" :disabled="!selectedRows.length" @click="$emit('batch-toggle-active', { ids: selectedRows.map(r => r.id), is_active: false })">
              批量禁用
            </el-button>
            <el-button type="danger" :disabled="!selectedRows.length" @click="handleBatchDeleteClick">
              批量删除
            </el-button>
          </template>
        </div>
        <div class="batch-toolbar-right">
          <span>共 {{ total }} 个模板</span>
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
            <el-tag v-if="row.is_builtin" size="small" type="info" effect="plain" style="margin-left: 6px">
              内置
            </el-tag>
            <el-tag v-else-if="row.cloned_from_id" size="small" effect="plain" style="margin-left: 6px">
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
              :disabled="false"
              @update:model-value="(val) => $emit('toggle-active', { id: row.id, is_active: val })"
            />
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column label="议题数" width="80" align="center">
          <template #default="{ row }">{{ row.agenda?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="时长" width="90" align="center">
          <template #default="{ row }">{{ row.default_duration_minutes || 60 }} 分钟</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="$emit('edit', row)">编辑</el-button>
            <el-button v-if="row.is_builtin" link type="primary" size="small" @click="$emit('clone', row.id)">
              复制为自定义
            </el-button>
            <el-popconfirm
              v-if="!row.is_builtin"
              title="确定删除此模板?此操作不可撤销"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="$emit('delete', row.id)"
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
        layout="total, sizes, prev, pager, next"
        @current-change="fetchTemplates"
        @size-change="handleSizeChange"
        class="pagination"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, defineEmits, defineExpose } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Edit } from '@element-plus/icons-vue'
import axios from 'axios'

const emit = defineEmits([
  'edit', 'delete', 'clone', 'toggle-active',
  'batch-toggle-active', 'batch-delete', 'refresh',
])

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
      include_inactive: true,
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

function handleSizeChange(s) {
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

function selectable(row) {
  return !row.is_builtin
}

function handleBatchDeleteClick() {
  if (!selectedRows.value.length) return
  emit('batch-delete', selectedRows.value.map((r) => r.id))
}

function formatTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('zh-CN', { hour12: false })
}

// 暴露 fetchTemplates 给父调用 (用于父组件 refresh)
defineExpose({ fetchTemplates })

onMounted(fetchTemplates)
</script>

<style scoped>
.templates-panel {
  /* 不需要额外容器, el-card 自带 padding */
}

/* 与原 TemplatesView 保持一致的 batch toolbar 样式 */
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
.selected-count {
  color: var(--color-text-secondary);
  font-size: 13px;
  margin-left: 4px;
}
.batch-toolbar-right {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.tpl-name {
  font-weight: 500;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
  display: flex;
}
</style>
