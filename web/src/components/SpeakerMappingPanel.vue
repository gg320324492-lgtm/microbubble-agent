<template>
  <div class="speaker-mapping-panel">
    <div class="panel-header">
      <h4>检测到 {{ speakers.length }} 位发言者</h4>
      <el-tag :type="confidenceTag" size="small">{{ confidenceText }}</el-tag>
    </div>

    <el-alert
      v-if="formatType === 'summary'"
      title="检测到会议摘要格式，发言人已从「发言人」或「参会人」字段自动提取"
      type="success"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
    />

    <el-table :data="speakers" stripe style="width: 100%">
      <el-table-column prop="original_label" label="原始标识" width="140" />
      <el-table-column label="映射为" min-width="180">
        <template #default="{ row }">
          <el-select
            v-model="mapping[row.original_label]"
            :name="`speaker-mapping-${row.original_label}`"
            filterable
            allow-create
            clearable
            placeholder="选择或输入姓名"
            style="width: 100%"
          >
            <el-option
              v-for="m in memberStore.members"
              :key="m.id"
              :label="m.name"
              :value="m.name"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column prop="turn_count" label="发言次数" width="90" align="center" />
      <el-table-column label="样本语句" min-width="220">
        <template #default="{ row }">
          <div class="sample-lines">
            <div v-for="(line, i) in row.sample_lines?.slice(0, 2)" :key="i" class="sample-line">
              {{ line.substring(0, 80) }}{{ line.length > 80 ? '...' : '' }}
            </div>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="panel-footer">
      <el-button size="small" @click="autoMatch">自动匹配成员</el-button>
      <el-button size="small" @click="clearAll">清空映射</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useMemberStore } from '@/stores/member'

const props = defineProps({
  speakers: { type: Array, default: () => [] },
  confidence: { type: String, default: 'medium' },
  formatType: { type: String, default: '' },
})

const emit = defineEmits(['update:mapping'])

const memberStore = useMemberStore()
const mapping = reactive({})

const confidenceTag = computed(() => {
  const map = { high: 'success', medium: 'warning', low: 'danger' }
  return map[props.confidence] || 'info'
})

const confidenceText = computed(() => {
  const map = { high: '高置信度', medium: '中置信度', low: '低置信度' }
  return map[props.confidence] || '未知'
})

watch(() => props.speakers, (newVal) => {
  newVal.forEach(sp => {
    if (!(sp.original_label in mapping)) {
      mapping[sp.original_label] = sp.suggested_name || ''
    }
  })
}, { immediate: true })

const searchMembers = (query, cb) => {
  const members = memberStore.members || []
  const results = query
    ? members.filter(m => m.name.includes(query)).map(m => ({ value: m.name }))
    : members.map(m => ({ value: m.name }))
  cb(results)
}

const onSelectMember = (label, item) => {
  mapping[label] = item.value
  emitMapping()
}

const autoMatch = () => {
  const members = memberStore.members || []
  props.speakers.forEach(sp => {
    const match = members.find(m =>
      m.name === sp.original_label ||
      m.name.includes(sp.original_label) ||
      sp.original_label.includes(m.name)
    )
    if (match) {
      mapping[sp.original_label] = match.name
    }
  })
  emitMapping()
}

const clearAll = () => {
  props.speakers.forEach(sp => {
    mapping[sp.original_label] = ''
  })
  emitMapping()
}

const emitMapping = () => {
  const result = {}
  props.speakers.forEach(sp => {
    result[sp.original_label] = mapping[sp.original_label] || sp.original_label
  })
  emit('update:mapping', result)
}

const getMapping = () => {
  const result = {}
  props.speakers.forEach(sp => {
    result[sp.original_label] = mapping[sp.original_label] || sp.original_label
  })
  return result
}

defineExpose({ getMapping })
</script>

<style scoped>
.speaker-mapping-panel {
  padding: var(--space-2) 0;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.panel-header h4 {
  margin: 0;
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
}
.sample-lines {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sample-line {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: 1.4;
  padding: 2px 6px;
  background: var(--color-bg-page);
  border-radius: var(--radius-sm);
}
.panel-footer {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
</style>
