<script setup>
/**
 * RAGEvalPanel.vue — RAG 离线评估报告 Admin Dashboard (PR5 W91 +10)
 *
 * PR5 RAGEvaluator 真召回率激活:
 * - 表格: 最近 N 条 RAGEvaluationReport (eval_time / ground_truth_total / NDCG@10 / MRR / hit_rate)
 * - 触发: 「跑一次评估」按钮 → POST /admin/rag-eval/run
 * - 详情: 点击单条 → 弹出 per-question JSON 详情
 * - 实时刷新: 5min polling (useRAGEval 内置 lastUpdate)
 *
 * 路径修正事实:
 * - 派工 brief 列 pwa/src/pages/admin/RAGEvalPanel.tsx (不存在)
 * - 经 DERIVE-18 §13 仓库实情真查, 修正为 web/src/views/admin/RAGEvalPanel.vue (PR6 模式)
 * - PR6 SearchLogs.vue 同模式, web/src/views/admin/ 已 6 个 *.vue 兄弟文件
 * - v1.2 §11.2 第 544 行明确修正, 类 20 #24 brief 错配据实上报
 *
 * 主题: 全走 var(--color-*) token, dark mode 自动适配 (跟 KbMonitorView 一致)
 * 数据源: useRAGEval composable (PR5 W91 +11):
 *   - GET  /api/v1/admin/rag-eval/reports?limit=10
 *   - POST /api/v1/admin/rag-eval/run {limit}
 *   - GET  /api/v1/admin/rag-eval/reports/{id}
 *
 * 派工 v11 段 7 E30 vitest: 必跑 vitest PASS (Web 单元测试)
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Play, DataAnalysis } from '@element-plus/icons-vue'
import { useRAGEval } from '@/composables/useRAGEval'

const { reports, loading, error, lastUpdate, listReports, runEvaluation, fetchReportDetail } = useRAGEval()

const limit = ref(10)
const detailReport = ref(null)
const detailVisible = ref(false)
const running = ref(false)

let pollTimer = null

async function refresh() {
  if (limit.value > 0) {
    await listReports(limit.value)
  }
}

async function onRun() {
  running.value = true
  try {
    const report = await runEvaluation(22)
    ElMessage.success(
      `评估完成: NDCG@10=${report?.ndcg_at_10 ?? '-'} MRR=${report?.mrr ?? '-'} hit_rate=${report?.hit_rate ?? '-'}`
    )
  } catch (e) {
    ElMessage.error(`评估失败: ${e?.message || e}`)
  } finally {
    running.value = false
  }
}

async function onShowDetail(id) {
  try {
    const r = await fetchReportDetail(id)
    detailReport.value = r
    detailVisible.value = true
  } catch (e) {
    ElMessage.error(`详情加载失败: ${e?.message || e}`)
  }
}

function fmtTime(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

function fmtPct(v) {
  if (v == null) return '-'
  return `${(v * 100).toFixed(1)}%`
}

onMounted(async () => {
  await refresh()
  // 5min polling (与 KbMonitorView 同模式)
  pollTimer = setInterval(refresh, 5 * 60 * 1000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div class="rag-eval-panel">
    <el-card class="header" shadow="never">
      <div class="header-row">
        <div class="title">
          <el-icon><DataAnalysis /></el-icon>
          <span>RAG 离线评估报告</span>
          <el-tag v-if="lastUpdate" type="info" size="small">
            刷新: {{ fmtTime(lastUpdate.toISOString()) }}
          </el-tag>
        </div>
        <div class="actions">
          <el-input-number v-model="limit" :min="1" :max="100" size="small" />
          <el-button :loading="loading" @click="refresh">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button type="primary" :loading="running" @click="onRun">
            <el-icon><Play /></el-icon> 跑一次评估
          </el-button>
        </div>
      </div>
    </el-card>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" style="margin: 12px 0" />

    <el-table :data="reports" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.eval_time) }}</template>
      </el-table-column>
      <el-table-column prop="ground_truth_total" label="题数" width="80" />
      <el-table-column label="NDCG@10" width="120">
        <template #default="{ row }">{{ fmtPct(row.ndcg_at_10) }}</template>
      </el-table-column>
      <el-table-column label="MRR" width="120">
        <template #default="{ row }">{{ fmtPct(row.mrr) }}</template>
      </el-table-column>
      <el-table-column label="命中率" width="120">
        <template #default="{ row }">{{ fmtPct(row.hit_rate) }}</template>
      </el-table-column>
      <el-table-column label="per-question" width="120">
        <template #default="{ row }">{{ row.per_question_count ?? 0 }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button text type="primary" @click="onShowDetail(row.id)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="detailVisible" title="per-question 详情" width="60%">
      <pre v-if="detailReport" class="detail-pre">{{ JSON.stringify(detailReport, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped>
.rag-eval-panel {
  padding: 16px;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-pre {
  max-height: 60vh;
  overflow: auto;
  background: var(--color-bg-secondary, #f5f7fa);
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
}
</style>
