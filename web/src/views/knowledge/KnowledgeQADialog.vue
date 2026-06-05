<template>
  <el-dialog
    v-model="visible"
    title="🤖 AI知识问答"
    :width="isMobile ? '92vw' : '700px'"
    top="5vh"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <div class="qa-dialog">
      <div class="qa-input-row">
        <el-input
          v-model="query"
          placeholder="输入你的问题，AI会从知识库中查找并合成答案..."
          size="large"
          :disabled="loading"
          @keyup.enter="onSubmit"
        >
          <template #append>
            <el-button :loading="loading" @click="onSubmit">
              {{ loading ? '思考中...' : '提问' }}
            </el-button>
          </template>
        </el-input>
      </div>

      <div class="qa-mode-toggle">
        <el-switch v-model="reasonMode" active-text="推理模式" inactive-text="检索模式" size="small" />
      </div>

      <!-- 快捷问题 -->
      <div v-if="!result && !loading" class="qa-suggestions">
        <div class="suggestion-title">💡 试试这些问题</div>
        <div class="suggestion-list">
          <el-tag
            v-for="q in suggestions"
            :key="q"
            class="suggestion-tag"
            @click="onSuggestion(q)"
          >{{ q }}</el-tag>
        </div>
      </div>

      <!-- 回答区域 -->
      <div v-if="loading" class="qa-loading">
        <div class="qa-loading-dots">
          <span v-if="reasonMode">🧠</span>
          <span v-else>🔍</span>
          {{ reasonMode ? '正在遍历知识图谱推理链...' : '正在检索知识库...' }}
        </div>
      </div>

      <div v-if="result" class="qa-result">
        <div class="qa-confidence">
          <span class="confidence-dot" :class="'conf-' + result.confidence"></span>
          {{ confidenceLabel(result.confidence) }}
          <span class="confidence-info">基于 {{ result.search_results?.high || 0 }} 条高相关、{{ result.search_results?.total || 0 }} 条总检索结果</span>
        </div>
        <div class="qa-answer" v-html="renderAnswer(result.answer)"></div>
        <div v-if="result.sources && result.sources.length" class="qa-sources">
          <div class="sources-title">📚 参考来源</div>
          <div v-for="src in result.sources" :key="src.id" class="source-item" @click="$emit('navigate', src.id)">
            <span class="source-title">{{ src.title }}</span>
            <el-tag size="small" :type="src.relevance >= 0.7 ? 'success' : 'warning'">
              {{ (src.relevance * 100).toFixed(0) }}%
            </el-tag>
          </div>
        </div>
        <div v-if="result.research_triggered && result.research_queries?.length" class="qa-research-note">
          <el-alert title="知识库信息不足，已生成研究查询" :description="result.research_queries.join('；')" type="warning" show-icon :closable="false" />
        </div>
      </div>

      <!-- 推理链 -->
      <div v-if="reasonResult" class="qa-result">
        <div class="qa-confidence">
          <span class="confidence-dot" :class="'conf-' + reasonResult.confidence"></span>
          {{ confidenceLabel(reasonResult.confidence) }}
          <span class="confidence-info">推理链使用 {{ reasonResult.nodes_used }} 个节点，{{ reasonResult.hops_used }} 跳</span>
        </div>
        <div class="qa-answer" v-html="renderAnswer(reasonResult.answer)"></div>
        <div v-if="reasonResult.reasoning_chain?.length" class="qa-reasoning-chain">
          <div class="reasoning-title">🧠 推理路径</div>
          <div v-for="(step, i) in reasonResult.reasoning_chain" :key="i" class="reasoning-step">
            <span class="step-number">{{ i + 1 }}</span>
            <span>{{ step }}</span>
          </div>
        </div>
        <div v-if="reasonResult.gap_description" class="qa-gap-note">
          <el-alert :title="'推理缺口: ' + reasonResult.gap_description" type="warning" show-icon :closable="false" />
        </div>
      </div>

      <!-- 错误 -->
      <div v-if="error" class="qa-error">
        <el-alert :title="error" type="error" show-icon :closable="false" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  isMobile: { type: Boolean, default: false }
})

const emit = defineEmits(['navigate'])

const visible = defineModel('visible', { default: false })

const query = ref('')
const loading = ref(false)
const result = ref(null)
const reasonResult = ref(null)
const error = ref('')
const reasonMode = ref(false)

const suggestions = [
  '微纳米气泡在水处理中的应用',
  '臭氧微纳米气泡消毒效果',
  'NTA 粒径测量方法',
  '微纳米气泡在农业中的应用',
  '气泡稳定性影响因素',
]

const confidenceLabel = (level) => {
  const map = { high: '高置信度', medium: '中等置信度', low: '低置信度' }
  return map[level] || level
}

const renderAnswer = (text) => {
  if (!text) return ''
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped.replace(/\[来源:([^\]]+)\]/g, '<span class="qa-citation">📖 $1</span>')
}

const onSuggestion = (q) => {
  query.value = q
  onSubmit()
}

const onSubmit = async () => {
  const q = query.value.trim()
  if (!q) { ElMessage.warning('请输入问题'); return }
  loading.value = true
  result.value = null
  error.value = ''
  reasonResult.value = null
  try {
    if (reasonMode.value) {
      const { data } = await axios.post('/api/v1/knowledge/reason', { question: q, max_hops: 2, top_k: 6 })
      reasonResult.value = data
    } else {
      const { data } = await axios.post('/api/v1/knowledge/qa', { question: q, top_k: 8, auto_research: true })
      result.value = data
    }
  } catch (e) {
    error.value = e.response?.data?.detail || '问答失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>
