<template>
  <div class="analysis-result-panel">
    <!-- 会议摘要 -->
    <div class="section">
      <h4>会议摘要</h4>
      <el-input
        v-model="localSummary" name="localSummary"
        type="textarea"
        :rows="3"
        placeholder="会议摘要"
      />
    </div>

    <!-- 讨论要点 -->
    <div class="section">
      <div class="section-header">
        <h4>讨论要点（{{ localKeyPoints.length }} 条）</h4>
        <el-button size="small" @click="addKeyPoint">添加</el-button>
      </div>
      <div class="editable-list">
        <div v-for="(point, i) in localKeyPoints" :key="'kp-' + i" class="list-item">
          <el-input v-model="localKeyPoints[i]" :name="`analysis-key-points-${i}`" size="small" />
          <el-button
            type="danger"
            size="small"
            :icon="Delete"
            circle
            @click="localKeyPoints.splice(i, 1)"
          />
        </div>
      </div>
    </div>

    <!-- 决策事项 -->
    <div class="section">
      <div class="section-header">
        <h4>决议事项（{{ localDecisions.length }} 条）</h4>
        <el-button size="small" @click="addDecision">添加</el-button>
      </div>
      <div class="editable-list">
        <div v-for="(d, i) in localDecisions" :key="'dec-' + i" class="list-item">
          <el-input v-model="localDecisions[i]" :name="`analysis-decisions-${i}`" size="small" />
          <el-button
            type="danger"
            size="small"
            :icon="Delete"
            circle
            @click="localDecisions.splice(i, 1)"
          />
        </div>
      </div>
    </div>

    <!-- 发言者统计 — 用 v-show 而非 v-if（Vue 3.4 renderer bug 'Cannot destructure property bum' workaround）
         当 speakerStats 从 [] 变 N 时 v-if 会完整 unmount el-table，触发 EP 子组件递归 unmount 中
         vnode.component === null 的崩溃。v-show 保持 el-table 挂载，仅切换可见性 -->
    <div v-show="speakerStats?.length" class="section">
      <h4>发言者统计</h4>
      <el-table :data="speakerStats" size="small" stripe>
        <el-table-column prop="name" label="发言人" width="100" />
        <el-table-column prop="turn_count" label="发言次数" width="90" align="center" />
        <el-table-column prop="word_count" label="字数" width="90" align="center" />
        <el-table-column label="发言占比" width="110" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.speaking_ratio || 0) * 100)"
              :stroke-width="8"
              :show-text="true"
            />
          </template>
        </el-table-column>
        <el-table-column prop="avg_turn_length" label="平均发言长度" width="110" align="center" />
      </el-table>
    </div>

    <!-- 待创建任务预览 — 同样 v-show workaround（见上方发言者统计注释） -->
    <div v-show="tasksPreview?.length" class="section">
      <div class="section-header">
        <h4>待创建任务（{{ tasksPreview?.length || 0 }} 个）</h4>
      </div>
      <el-table :data="tasksPreview" size="small" stripe>
        <el-table-column prop="title" label="任务" min-width="180" />
        <el-table-column label="负责人" width="140">
          <template #default="{ row, $index }">
            <el-select
              :model-value="row.assignee_name || ''"
              filterable
              clearable
              size="small"
              placeholder="选择负责人"
              style="width: 100%"
              @update:model-value="(val) => updateAssignee($index, val)"
            >
              <el-option v-for="m in memberStore.members" :key="m.id" :label="m.name" :value="m.name" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="priorityTag(row.priority)" size="small">
              {{ priorityLabel(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="截止日期" width="110" />
        <el-table-column label="置信度" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.confidence === 'confirmed' ? 'success' : 'warning'" size="small">
              {{ row.confidence === 'confirmed' ? '确认' : '暂定' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Delete } from '@element-plus/icons-vue'
import { useMemberStore } from '@/stores/member'

const memberStore = useMemberStore()

const props = defineProps({
  summary: { type: String, default: '' },
  keyPoints: { type: Array, default: () => [] },
  decisions: { type: Array, default: () => [] },
  speakerStats: { type: Array, default: () => [] },
  tasksPreview: { type: Array, default: () => [] },
})

const emit = defineEmits(['update'])

const localSummary = ref('')
const localKeyPoints = ref([])
const localDecisions = ref([])

watch(() => props.summary, (v) => { localSummary.value = v || '' }, { immediate: true })
watch(() => props.keyPoints, (v) => { localKeyPoints.value = [...(v || [])] }, { immediate: true })
watch(() => props.decisions, (v) => { localDecisions.value = [...(v || [])] }, { immediate: true })

const addKeyPoint = () => localKeyPoints.value.push('')
const addDecision = () => localDecisions.value.push('')

const priorityTag = (p) => ({ high: 'danger', medium: 'warning', low: 'info' }[p] || 'info')
const priorityLabel = (p) => ({ high: '高', medium: '中', low: '低' }[p] || '中')

const updateAssignee = (index, name) => {
  if (props.tasksPreview[index]) {
    props.tasksPreview[index].assignee_name = name || null
  }
}

const getResult = () => ({
  summary: localSummary.value,
  key_points: localKeyPoints.value.filter(Boolean),
  decisions: localDecisions.value.filter(Boolean),
})

defineExpose({ getResult })
</script>

<style scoped>
.analysis-result-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.section h4 {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-semibold);
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}
.section-header h4 {
  margin: 0;
}
.editable-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.list-item {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.list-item .el-input {
  flex: 1;
}
</style>
