<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    :width="isMobile ? '95vw' : '750px'"
    top="5vh"
    :close-on-click-modal="false"
    @close="reset"
  >
    <!-- 阶段1：输入表单 -->
    <div v-if="stage === 1" class="stage-input">
      <el-form label-width="90px">
        <el-form-item label="会议标题">
          <el-input v-model="form.title" placeholder="留空则 AI 自动生成标题" />
        </el-form-item>
        <el-form-item label="会议时间" required>
          <el-date-picker
            v-model="form.start_time"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择会议时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="参会人员">
          <el-select v-model="form.participants" multiple placeholder="选择参会人员（可选）">
            <el-option v-for="m in members" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="转录文字" required>
          <el-input
            v-model="form.transcript_text"
            type="textarea"
            :rows="12"
            placeholder="请粘贴会议转录文字，支持格式：&#10;【张三】发言内容&#10;李四说：发言内容&#10;或纯文本格式"
          />
        </el-form-item>
      </el-form>
    </div>

    <!-- 阶段2：发言者映射 -->
    <div v-if="stage === 2" class="stage-mapping">
      <el-alert
        v-if="detectionResult"
        :title="`检测到 ${detectionResult.detected_speakers?.length || 0} 位发言者，共 ${detectionResult.total_turns} 次发言`"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <SpeakerMappingPanel
        ref="mappingPanelRef"
        :speakers="detectionResult?.detected_speakers || []"
        :confidence="detectionResult?.confidence || 'medium'"
        :format-type="detectionResult?.format_type || ''"
        @update:mapping="onMappingUpdate"
      />

      <div class="mapping-actions">
        <el-checkbox v-model="skipMapping">
          跳过映射（使用原始发言者标识）
        </el-checkbox>
      </div>
    </div>

    <!-- 阶段3：结果展示 -->
    <div v-if="stage === 3" class="stage-result">
      <div v-if="analyzing" class="analyzing-state">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p>AI 正在分析会议内容...</p>
      </div>

      <AnalysisResultPanel
        v-else
        ref="resultPanelRef"
        :summary="result.summary"
        :key-points="result.key_points"
        :decisions="result.decisions"
        :speaker-stats="result.speaker_stats"
        :tasks-preview="result.tasks_created || []"
      />
    </div>

    <template #footer>
      <!-- 阶段1 footer -->
      <div v-if="stage === 1">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="goDetect" :loading="detecting">
          检测发言者
        </el-button>
      </div>

      <!-- 阶段2 footer -->
      <div v-if="stage === 2">
        <el-button @click="stage = 1">上一步</el-button>
        <el-button type="primary" @click="goAnalyze" :loading="analyzing">
          开始 AI 分析
        </el-button>
      </div>

      <!-- 阶段3 footer -->
      <div v-if="stage === 3 && !analyzing">
        <el-button @click="visible = false">取消</el-button>
        <el-button @click="stage = 2">上一步</el-button>
        <el-button type="success" @click="goSave" :loading="saving">
          保存并创建任务
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import axios from 'axios'
import { useMemberStore } from '@/stores/member'
import SpeakerMappingPanel from '@/components/SpeakerMappingPanel.vue'
import AnalysisResultPanel from '@/components/AnalysisResultPanel.vue'

const emit = defineEmits(['saved'])

const memberStore = useMemberStore()
const members = computed(() => memberStore.members || [])

const isMobile = ref(window.innerWidth <= 768)

const visible = ref(false)
const stage = ref(1)
const detecting = ref(false)
const analyzing = ref(false)
const saving = ref(false)
const skipMapping = ref(false)

const form = ref({
  title: '',
  start_time: '',
  participants: [],
  transcript_text: '',
})

const speakerMapping = ref({})
const detectionResult = ref(null)
const result = ref({
  meeting_id: null,
  summary: '',
  key_points: [],
  decisions: [],
  tasks_created: [],
  speaker_stats: [],
})

const mappingPanelRef = ref(null)
const resultPanelRef = ref(null)

const dialogTitle = computed(() => {
  const titles = { 1: '粘贴会议转录', 2: '确认发言者映射', 3: '分析结果' }
  return titles[stage.value] || '会议分析'
})

const open = () => {
  stage.value = 1
  form.value = { title: '', start_time: '', participants: [], transcript_text: '' }
  detectionResult.value = null
  result.value = { meeting_id: null, summary: '', key_points: [], decisions: [], tasks_created: [], speaker_stats: [] }
  speakerMapping.value = {}
  skipMapping.value = false
  visible.value = true
}

const reset = () => {
  stage.value = 1
  detecting.value = false
  analyzing.value = false
  saving.value = false
}

// 阶段1 → 阶段2：检测发言者
const goDetect = async () => {
  if (!form.value.start_time) {
    ElMessage.warning('请选择会议时间')
    return
  }
  if (!form.value.transcript_text.trim()) {
    ElMessage.warning('请粘贴转录文字')
    return
  }

  detecting.value = true
  try {
    const res = await axios.post('/api/v1/meetings/detect-speakers', {
      transcript_text: form.value.transcript_text,
    })
    detectionResult.value = res.data

    // 摘要格式：自动填充标题
    if (res.data.format_type === 'summary' && res.data.extracted_title && !form.value.title.trim()) {
      form.value.title = res.data.extracted_title
    }

    if (res.data.detected_speakers?.length <= 1) {
      // 只有一位或没有发言者，跳过映射阶段
      skipMapping.value = true
      await goAnalyze()
      return
    }

    stage.value = 2
  } catch (e) {
    ElMessage.error('发言者检测失败：' + (e.response?.data?.detail || e.message))
  } finally {
    detecting.value = false
  }
}

// 阶段2 → 阶段3：AI 分析
const goAnalyze = async () => {
  analyzing.value = true
  stage.value = 3

  try {
    let mapping = {}
    if (!skipMapping.value && mappingPanelRef.value) {
      mapping = mappingPanelRef.value.getMapping()
    }

    const payload = {
      title: form.value.title,
      start_time: form.value.start_time,
      transcript_text: form.value.transcript_text,
      participants: form.value.participants,
    }

    if (Object.keys(mapping).length > 0) {
      payload.speaker_mapping = mapping
    }

    const res = await axios.post('/api/v1/meetings/analyze-text', payload)

    if (res.data.phase === 'speaker_detection') {
      // 后端返回了检测结果而不是分析结果
      analyzing.value = false
      detectionResult.value = res.data.detection
      stage.value = 2
      ElMessage.info('请先确认发言者映射')
      return
    }

    result.value = {
      meeting_id: res.data.meeting_id,
      summary: res.data.summary || '',
      key_points: res.data.key_points || [],
      decisions: res.data.decisions || [],
      tasks_created: res.data.tasks_created || [],
      speaker_stats: res.data.speaker_stats || [],
    }
  } catch (e) {
    ElMessage.error('分析失败：' + (e.response?.data?.detail || e.message))
    stage.value = 2
  } finally {
    analyzing.value = false
  }
}

// 阶段3：保存编辑后的结果
const goSave = async () => {
  saving.value = true
  try {
    // 如果有编辑，更新会议记录
    if (resultPanelRef.value && result.value.meeting_id) {
      const edited = resultPanelRef.value.getResult()
      await axios.put(`/api/v1/meetings/${result.value.meeting_id}`, {
        summary: edited.summary,
        key_points: edited.key_points,
        decisions: edited.decisions,
      })
    }

    ElMessage.success(`会议分析完成，已创建 ${result.value.tasks_created?.length || 0} 个任务`)
    visible.value = false
    emit('saved')
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

const onMappingUpdate = (mapping) => {
  speakerMapping.value = mapping
}

defineExpose({ open })
</script>

<style scoped>
.stage-input,
.stage-mapping,
.stage-result {
  min-height: 300px;
}
.mapping-actions {
  margin-top: var(--space-4);
  display: flex;
  justify-content: flex-end;
}
.analyzing-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  gap: var(--space-4);
  color: var(--color-text-secondary);
}
.analyzing-state .el-icon {
  color: var(--color-primary);
}
</style>
