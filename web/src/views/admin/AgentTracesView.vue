<script setup>
/**
 * AgentTracesView.vue — Admin 监控页
 *
 * 表格 + 详情抽屉（el-drawer）
 * - 顶部筛选：用户ID / 日期范围 / 关键词
 * - 表格列：时间 / 用户 / 工具数 / Rich Block 数 / Token / 耗时 / 错误
 * - 行点击：打开抽屉显示完整 tool_calls / rich_blocks JSON
 */
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const traces = ref([])
const total = ref(0)
const loading = ref(false)
const drawerVisible = ref(false)
const activeTrace = ref(null)
const detailLoading = ref(false)

// 筛选
const filters = ref({
  user_id: null,
  date_from: null,
  date_to: null,
  // 2026-06-14 方案 C Stage 3：按状态过滤
  status: '',
})

const formatDate = (iso) => {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return iso }
}

const fetchTraces = async () => {
  loading.value = true
  try {
    const params = {}
    if (filters.value.user_id) params.user_id = filters.value.user_id
    if (filters.value.date_from) params.date_from = filters.value.date_from
    if (filters.value.date_to) params.date_to = filters.value.date_to
    if (filters.value.status) params.status = filters.value.status
    params.limit = 100
    const r = await axios.get('/api/v1/admin/agent-traces', { params })
    traces.value = r.data.traces || []
    total.value = r.data.total || 0
  } catch (e) {
    if (e.response?.status === 403) {
      ElMessage.error('需要管理员权限')
    } else {
      ElMessage.error(e.response?.data?.detail || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

const onRowClick = async (row) => {
  activeTrace.value = row
  drawerVisible.value = true
  detailLoading.value = true
  try {
    const r = await axios.get(`/api/v1/admin/agent-traces/${row.id}`)
    activeTrace.value = { ...row, ...r.data }
  } catch (e) {
    ElMessage.error('详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

// 2026-06-14 方案 C Stage 3：辅助函数
const intentZh = (cat) => ({
  recommend_person: '推荐人',
  search_info: '找资料',
  explain_concept: '解释概念',
  execute_action: '执行操作',
  data_query: '数据查询',
  casual_chat: '闲聊',
}[cat] || cat || '-')

const critiqueColor = (score) => {
  if (score == null) return 'info'
  if (score >= 8) return 'success'
  if (score >= 6) return 'warning'
  return 'danger'
}

const statusZh = (s) => ({
  completed: '已完成',
  aborted: '已中断',
  error: '异常',
  low_score_fallback: '低分降级',
  in_progress: '进行中',
}[s] || s || '-')

const statusColor = (s) => ({
  completed: 'success',
  aborted: 'warning',
  error: 'danger',
  low_score_fallback: 'warning',
  in_progress: 'info',
}[s] || 'info')

onMounted(fetchTraces)
</script>

<template>
  <div class="agent-traces-view">
    <div class="page-header">
      <h2>🤖 Agent Trace 监控</h2>
      <p class="desc">每次 chat 的工具调用链 / Rich Block / Token 消耗 / 响应耗时</p>
    </div>

    <!-- 筛选 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters" size="default">
        <el-form-item label="用户 ID">
          <el-input v-model.number="filters.user_id" placeholder="可选" style="width: 120px;" clearable />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="filters.date_from" type="date" placeholder="可选" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="filters.date_to" type="date" placeholder="可选" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="状态" style="width: 140px;">
          <el-select v-model="filters.status" placeholder="全部" clearable>
            <el-option label="已完成" value="completed" />
            <el-option label="已中断" value="aborted" />
            <el-option label="异常" value="error" />
            <el-option label="低分降级" value="low_score_fallback" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchTraces">查询</el-button>
          <el-button @click="filters = { user_id: null, date_from: null, date_to: null, status: '' }; fetchTraces()">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <el-table :data="traces" v-loading="loading" @row-click="onRowClick" stripe style="cursor: pointer;">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="时间" width="160">
          <template #default="{ row }">
            <span class="time">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="user_name" label="用户" width="100" />
        <el-table-column prop="session_id" label="会话" width="140" show-overflow-tooltip />
        <el-table-column label="工具" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.tool_count > 0" type="success" size="small">{{ row.tool_count }}</el-tag>
            <span v-else class="muted">0</span>
          </template>
        </el-table-column>
        <el-table-column label="Block" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.rich_block_count > 0" type="warning" size="small">{{ row.rich_block_count }}</el-tag>
            <span v-else class="muted">0</span>
          </template>
        </el-table-column>
        <el-table-column label="Token" width="90">
          <template #default="{ row }">
            <span v-if="row.total_tokens">{{ row.total_tokens }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="80">
          <template #default="{ row }">
            <span v-if="row.total_duration_ms">{{ (row.total_duration_ms / 1000).toFixed(1) }}s</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="消息" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.message }}
          </template>
        </el-table-column>
        <el-table-column label="错误" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.error" type="danger" size="small">有错误</el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <!-- 2026-06-14 方案 C Stage 3 新增列 -->
        <el-table-column label="意图" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.intent_category" class="intent-tag">
              {{ intentZh(row.intent_category) }}
              <small v-if="row.intent_confidence != null" class="muted">
                {{ (row.intent_confidence * 100).toFixed(0) }}%
              </small>
            </span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="自评" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.critique_score != null" :type="critiqueColor(row.critique_score)" size="small">
              {{ row.critique_score }}/10
            </el-tag>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusColor(row.status)" size="small">{{ statusZh(row.status) }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div class="total-info">共 {{ total }} 条记录</div>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="`Trace #${activeTrace?.id} 详情`" size="60%" direction="rtl">
      <div v-loading="detailLoading" class="trace-detail">
        <h3>📋 消息</h3>
        <pre class="json">{{ activeTrace?.message }}</pre>

        <h3>🔧 工具调用 ({{ activeTrace?.tool_count || 0 }})</h3>
        <div v-for="(tc, i) in (activeTrace?.tool_calls || [])" :key="i" class="tool-call">
          <div class="tc-header">
            <el-tag size="small" type="success">{{ tc.name }}</el-tag>
            <span class="duration">{{ tc.duration_ms }}ms</span>
            <el-tag v-if="tc.error" type="danger" size="small">ERROR</el-tag>
          </div>
          <details>
            <summary>Input 字段: {{ (tc.input_keys || []).join(', ') }}</summary>
            <pre class="json">{{ JSON.stringify(tc, null, 2) }}</pre>
          </details>
        </div>
        <div v-if="!activeTrace?.tool_calls?.length" class="muted">无工具调用</div>

        <h3>🎨 Rich Blocks ({{ activeTrace?.rich_block_count || 0 }})</h3>
        <div v-for="(rb, i) in (activeTrace?.rich_blocks || [])" :key="i" class="rich-block-tag">
          <el-tag size="small" type="warning">{{ rb.type }}</el-tag>
          <span v-if="rb.title" class="rb-title">{{ rb.title }}</span>
        </div>
        <div v-if="!activeTrace?.rich_blocks?.length" class="muted">无富文本块</div>

        <h3 v-if="activeTrace?.brief">📝 Brief 摘要</h3>
        <pre v-if="activeTrace?.brief" class="json">{{ activeTrace.brief.slice(0, 1000) }}{{ activeTrace.brief.length > 1000 ? '...(已截断)' : '' }}</pre>

        <h3 v-if="activeTrace?.detail">📄 Detail 详细</h3>
        <pre v-if="activeTrace?.detail" class="json">{{ activeTrace.detail.slice(0, 3000) }}{{ activeTrace.detail.length > 3000 ? '...(已截断)' : '' }}</pre>

        <h3 v-if="activeTrace?.error">❌ 错误</h3>
        <pre v-if="activeTrace?.error" class="json error">{{ activeTrace.error }}</pre>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.agent-traces-view { padding: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 22px; color: #2d2d2d; }
.page-header .desc { margin: 0 0 20px; color: #999; font-size: 13px; }
.filter-card, .table-card { margin-bottom: 16px; }
.time { font-family: monospace; font-size: 12px; color: #555; }
.muted { color: #ccc; }
.total-info { text-align: right; color: #999; font-size: 12px; margin-top: 12px; }
.trace-detail h3 { font-size: 14px; margin: 16px 0 8px; color: #FF7A5C; }
.trace-detail .json {
  background: #fafbfc; padding: 10px 12px; border-radius: 6px;
  font-size: 12px; color: #333; max-height: 300px; overflow: auto;
  white-space: pre-wrap; word-break: break-all;
}
.trace-detail .json.error { color: #f56c6c; }
.tool-call { padding: 8px 12px; background: #fafbfc; border-radius: 6px; margin-bottom: 6px; }
.tc-header { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.tc-header .duration { font-size: 11px; color: #999; }
.rich-block-tag { display: inline-flex; gap: 6px; padding: 4px 0; margin-right: 8px; }
.rb-title { font-size: 12px; color: #666; }
</style>
