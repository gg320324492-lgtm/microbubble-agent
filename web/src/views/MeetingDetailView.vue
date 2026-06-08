<template>
  <div class="meeting-detail" v-if="meeting">
    <!-- ====== Hero 区域 ====== -->
    <div class="detail-hero">
      <!-- 返回 -->
      <div class="hero-back">
        <el-button text @click="$router.push('/meetings')">
          <el-icon><ArrowLeft /></el-icon> 返回列表
        </el-button>
      </div>

      <!-- 主信息 -->
      <div class="hero-main">
        <!-- 标题（展示/编辑态切换） -->
        <div v-if="!editing" class="hero-title-row">
          <h1 class="hero-title">{{ meeting.title }}</h1>
          <span class="status-badge" :class="'status-' + meeting.status">
            <span class="status-dot" />
            {{ statusLabel(meeting.status) }}
          </span>
        </div>
        <div v-else class="hero-title-row editing">
          <el-input v-model="form.title" class="edit-title-input" />
          <el-tag :type="statusType(meeting.status)" size="default">{{ statusLabel(meeting.status) }}</el-tag>
        </div>

        <!-- 元信息行 -->
        <div class="hero-meta">
          <span class="meta-item">
            <el-icon><Clock /></el-icon>
            <template v-if="!editing">{{ formatDate(meeting.start_time) }}</template>
            <el-date-picker
              v-else
              v-model="form.start_time"
              type="datetime"
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择日期时间"
              size="small"
              style="width: 200px"
              :clearable="false"
            />
          </span>
          <span class="meta-item">
            <el-icon><Location /></el-icon>
            <template v-if="!editing">{{ meeting.location || '未设置' }}</template>
            <el-input v-else v-model="form.location" size="small" style="width:160px" placeholder="地点" />
          </span>
          <span v-if="meeting.audio_duration" class="meta-item">
            <el-icon><Microphone /></el-icon>
            {{ formatDuration(meeting.audio_duration) }}
          </span>
        </div>

        <!-- 参与者头像 -->
        <div class="hero-participants">
          <ParticipantAvatars
            :participants="meeting.participants || []"
            :max-display="8"
            :size="36"
          />
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="hero-actions">
        <template v-if="!editing">
          <el-button @click="enterEdit">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <el-popconfirm title="确定删除此会议？" @confirm="handleDelete">
            <template #reference>
              <el-button type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </template>
        <template v-else>
          <el-button type="primary" @click="saveBasic" :loading="saving">保存</el-button>
          <el-button @click="cancelEdit">取消</el-button>
        </template>
      </div>
    </div>

    <!-- ====== 主体区域 ====== -->
    <div class="detail-body">
      <!-- 左侧 Tab 内容 -->
      <div class="detail-main">
        <el-tabs v-model="activeTab" class="detail-tabs">
          <!-- Tab 1: 会议纪要 -->
          <el-tab-pane label="会议纪要" name="minutes">
            <div class="tab-content">
              <!-- 编辑态 -->
              <template v-if="editingMinutes">
                <div class="section">
                  <h4>摘要</h4>
                  <el-input v-model="minutesForm.summary" type="textarea" :rows="4" placeholder="会议摘要..." />
                </div>
                <div class="section">
                  <h4>讨论要点</h4>
                  <div class="item-list">
                    <div v-for="(p, i) in minutesForm.key_points" :key="'kp'+i" class="item-row">
                      <span class="item-dot" />
                      <el-input v-model="minutesForm.key_points[i]" placeholder="输入要点..." />
                      <el-button :icon="Delete" circle size="small" class="item-del" @click="minutesForm.key_points.splice(i,1)" />
                    </div>
                    <el-button dashed size="small" class="item-add" @click="minutesForm.key_points.push('')">
                      <el-icon><Plus /></el-icon> 添加要点
                    </el-button>
                  </div>
                </div>
                <div class="section">
                  <h4>决议事项</h4>
                  <div class="item-list">
                    <div v-for="(d, i) in minutesForm.decisions" :key="'dc'+i" class="item-row decision">
                      <span class="item-dot decision-dot" />
                      <el-input v-model="minutesForm.decisions[i]" placeholder="输入决议..." />
                      <el-button :icon="Delete" circle size="small" class="item-del" @click="minutesForm.decisions.splice(i,1)" />
                    </div>
                    <el-button dashed size="small" class="item-add decision-add" @click="minutesForm.decisions.push('')">
                      <el-icon><Plus /></el-icon> 添加决议
                    </el-button>
                  </div>
                </div>
                <div class="section-actions">
                  <el-button type="primary" @click="saveMinutes">保存纪要</el-button>
                  <el-button @click="editingMinutes = false">取消</el-button>
                </div>
              </template>

              <!-- 展示态 -->
              <template v-else>
                <div v-if="meeting.summary" class="section">
                  <h4>摘要</h4>
                  <p class="summary-text">{{ meeting.summary }}</p>
                </div>
                <div v-if="groupedKeyPoints.length" class="section">
                  <h4>讨论要点</h4>
                  <div v-for="(group, gi) in groupedKeyPoints" :key="gi" class="speaker-group fade-slide-up" :style="{ animationDelay: (gi * 80) + 'ms' }">
                    <div v-if="group.speaker" class="speaker-row">
                      <el-avatar :size="24" :src="getSpeakerAvatar(group.speaker)" class="speaker-avatar" :alt="`${group.speaker}的头像`">{{ group.speaker[0] }}</el-avatar>
                      <span class="speaker-name">{{ group.speaker }}</span>
                    </div>
                    <ul class="points-list">
                      <li v-for="(item, ii) in group.items" :key="ii" class="point-item" @click="editingPoint = (editingPoint === `key_points.${gi}.${ii}` ? null : `key_points.${gi}.${ii}`)">
                        <span class="point-text">{{ item }}</span>
                        <el-select
                          v-if="editingPoint === `key_points.${gi}.${ii}`"
                          v-model="group._editValues[ii]"
                          size="small"
                          class="inline-speaker-select"
                          filterable
                          @change="(val) => { renameSinglePoint('key_points', group, ii, val); editingPoint = null }"
                          @click.stop
                          @blur="editingPoint = null"
                        >
                          <el-option v-for="m in memberStore.members" :key="m.id" :label="m.name" :value="m.name" />
                        </el-select>
                      </li>
                    </ul>
                  </div>
                </div>
                <div v-if="groupedDecisions.length" class="section">
                  <h4>决议事项</h4>
                  <div v-for="(group, gi) in groupedDecisions" :key="gi" class="speaker-group fade-slide-up" :style="{ animationDelay: (gi * 80) + 'ms' }">
                    <div v-if="group.speaker" class="speaker-row">
                      <el-avatar :size="24" :src="getSpeakerAvatar(group.speaker)" class="speaker-avatar" :alt="`${group.speaker}的头像`">{{ group.speaker[0] }}</el-avatar>
                      <span class="speaker-name">{{ group.speaker }}</span>
                    </div>
                    <ul class="decisions-list">
                      <li v-for="(item, ii) in group.items" :key="ii" class="point-item" @click="editingPoint = (editingPoint === `decisions.${gi}.${ii}` ? null : `decisions.${gi}.${ii}`)">
                        <span class="point-text">{{ item }}</span>
                        <el-select
                          v-if="editingPoint === `decisions.${gi}.${ii}`"
                          v-model="group._editValues[ii]"
                          size="small"
                          class="inline-speaker-select"
                          filterable
                          @change="(val) => { renameSinglePoint('decisions', group, ii, val); editingPoint = null }"
                          @click.stop
                          @blur="editingPoint = null"
                        >
                          <el-option v-for="m in memberStore.members" :key="m.id" :label="m.name" :value="m.name" />
                        </el-select>
                      </li>
                    </ul>
                  </div>
                </div>
                <div v-if="meeting.agenda?.length" class="section">
                  <h4>议程</h4>
                  <ol class="agenda-list">
                    <li v-for="(item, idx) in meeting.agenda" :key="idx">
                      <span :class="{ done: item.done }">{{ item.text || item }}</span>
                      <el-tag v-if="item.done" type="success" size="small">已完成</el-tag>
                    </li>
                  </ol>
                </div>
                <el-button v-if="!editingMinutes" size="small" class="edit-minutes-btn" @click="enterEditMinutes">
                  <el-icon><Edit /></el-icon> 编辑纪要
                </el-button>
                <el-empty
                  v-if="!meeting.summary && !meeting.key_points?.length && !meeting.decisions?.length && !meeting.agenda?.length"
                  description="暂无会议纪要"
                />
              </template>
            </div>
          </el-tab-pane>

          <!-- Tab 2: 转录记录 -->
          <el-tab-pane label="转录记录" name="transcript">
            <div class="tab-content">
              <template v-if="transcriptEntries.length">
                <div
                  v-for="(entry, i) in transcriptEntries"
                  :key="i"
                  class="transcript-entry"
                  :class="{ 'entry-removed': entry.removed }"
                >
                  <div class="transcript-left">
                    <el-avatar :size="28" :src="getSpeakerAvatar(entry.speaker)" class="transcript-avatar" :alt="`${entry.speaker || '未知'}的头像`">
                      {{ (entry.speaker || '?')[0] }}
                    </el-avatar>
                    <div class="transcript-line" />
                  </div>
                  <div class="transcript-body">
                    <div class="transcript-header">
                      <el-select
                        :model-value="entry.speaker || '未知'"
                        size="small"
                        class="transcript-speaker-select"
                        filterable
                        :loading="savingTranscriptSpeaker === i"
                        :disabled="savingTranscriptSpeaker === i"
                        @change="(val) => saveTranscriptSpeaker(i, val)"
                      >
                        <el-option
                          v-for="option in speakerOptions"
                          :key="option"
                          :label="option"
                          :value="option"
                        />
                      </el-select>
                      <el-tag v-if="entry.removed" size="small" type="info" effect="plain">已过滤</el-tag>
                      <el-tag v-else-if="entry.polish_failed" size="small" type="warning" effect="plain">降级</el-tag>
                      <span v-if="entry.ts" class="transcript-ts">{{ formatTs(entry.ts) }}</span>
                    </div>
                    <div v-if="!entry.removed" class="transcript-text">
                      {{ getPolishedText(entry, i) }}
                      <el-tag v-if="polishingIndex === i" size="small" type="warning" class="polish-tag">润色中</el-tag>
                    </div>
                    <div v-else class="transcript-text removed">
                      <el-icon><Delete /></el-icon>
                      <span>{{ entry.text || '(空)' }}</span>
                      <span v-if="entry.reason" class="remove-reason">({{ entry.reason }})</span>
                    </div>
                  </div>
                </div>
              </template>
              <el-empty v-else description="暂无转录记录" />
            </div>
          </el-tab-pane>

          <!-- Tab 3: 发言统计 -->
          <el-tab-pane label="发言统计" name="stats">
            <div class="tab-content">
              <SpeakerStatsCard :stats="meeting.speaker_stats || []" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 右侧边栏 -->
      <div class="detail-side">
        <!-- 录音回放 -->
        <el-card v-if="meeting.audio_url" class="side-card">
          <template #header><span>🎙️ 录音回放</span></template>
          <AudioPlayer :src="getAudioSrc(meeting.audio_url)" />
          <div v-if="meeting.audio_duration" class="audio-meta">
            录音时长: {{ formatDuration(meeting.audio_duration) }}
          </div>
        </el-card>

        <!-- 听会 -->
        <el-card class="side-card">
          <template #header><span>听会</span></template>
          <MeetingRoom v-if="showCallRoom" @call-ended="onCallEnded" style="height: 400px" />
          <div v-else class="call-placeholder" @click="startLiveCall">
            <el-icon size="40" color="#FF7A5C"><Microphone /></el-icon>
            <p>点击开始听会</p>
          </div>
        </el-card>

        <!-- 相关会议 -->
        <el-card v-if="relatedMeetings.length > 0" class="side-card">
          <template #header><span>相关会议</span></template>
          <div v-for="m in relatedMeetings" :key="m.id" class="related-item">
            <router-link :to="`/meetings/${m.id}`" class="related-link">{{ m.title }}</router-link>
            <span class="related-similarity">{{ Math.round(m.similarity * 100) }}%</span>
          </div>
        </el-card>
      </div>
    </div>
  </div>

  <div v-else class="loading-state">
    <el-icon class="is-loading" size="24"><Loading /></el-icon> 加载中...
  </div>

  <!-- 会后处理进度弹窗 -->
  <ProcessingDialog
    v-if="processingDialogVisible && meeting"
    :meeting-id="meeting.id"
    @close="processingDialogVisible = false"
  />
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Edit, Delete, Document, Plus, Loading, Clock, Location, Microphone } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { useMemberStore } from '@/stores/member'
import MeetingRoom from '@/components/MeetingRoom.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'
import ParticipantAvatars from '@/components/ParticipantAvatars.vue'
import SpeakerStatsCard from '@/components/SpeakerStatsCard.vue'
import AudioPlayer from '@/components/AudioPlayer.vue'

const route = useRoute()
const router = useRouter()
const memberStore = useMemberStore()

const meeting = ref(null)
const editing = ref(false)
const editingMinutes = ref(false)
const showCallRoom = ref(false)
const saving = ref(false)
const savingTranscriptSpeaker = ref(null)
const polishingIndex = ref(null)

async function polishMergedText(index) {
  if (!meeting.value) return
  polishingIndex.value = index
  try {
    const res = await axios.post(`/api/v1/meetings/${meeting.value.id}/polish-text`, {
      text: transcriptEntries.value[index].text,
    })
    const polished = res.data.polished
    if (polished && polished !== transcriptEntries.value[index].text) {
      // 更新合并前的原始条目中的第一条
      const origIdx = transcriptEntries.value[index]._origIndex ?? index
      if (meeting.value.transcript && meeting.value.transcript[origIdx]) {
        meeting.value.transcript[origIdx].text = polished
      }
      if (meeting.value.transcript_polished && meeting.value.transcript_polished[origIdx]) {
        meeting.value.transcript_polished[origIdx].text = polished
      }
      ElMessage.success('已润色')
    }
  } catch {
    ElMessage.error('润色失败')
  } finally {
    polishingIndex.value = null
  }
}
const activeTab = ref('minutes')

const relatedMeetings = ref([])

const editingPoint = ref(null)  // 当前编辑的要点 ID

// 单独更改某条要点/决议的发言人（仅影响这一条）
async function renameSinglePoint(type, group, itemIdx, newSpeaker) {
  const arr = type === 'key_points' ? meeting.value.key_points : meeting.value.decisions
  if (!arr) return

  // 在原数组中定位这条
  let foundIdx = -1
  for (let i = 0; i < arr.length; i++) {
    const sp = parseSpeaker(arr[i]) || group.speaker
    if (removeSpeakerPrefix(arr[i]) === group.items[itemIdx] && sp === group.speaker) {
      foundIdx = i
      break
    }
  }
  if (foundIdx < 0) return

  const oldSpeaker = parseSpeaker(arr[foundIdx]) || group.speaker
  arr[foundIdx] = arr[foundIdx].replace(`【${oldSpeaker}】`, `【${newSpeaker}】`)
  group._editValues[itemIdx] = newSpeaker

  try {
    await axios.put(`/api/v1/meetings/${meeting.value.id}`, {
      [type]: [...arr],
    })
    ElMessage.success(`已更新为 ${newSpeaker}`)
  } catch (e) {
    ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message))
  }
}

// 转录记录：优先用 polished，回退到原始 transcript，合并连续同发言人
const transcriptEntries = computed(() => {
  if (!meeting.value) return []
  const raw = meeting.value.transcript_polished?.length
    ? meeting.value.transcript_polished
    : (meeting.value.transcript || [])
  if (!raw.length) return []

  const merged = []
  let current = { ...raw[0], _origIndex: 0 }
  for (let i = 1; i < raw.length; i++) {
    const entry = raw[i]
    if (entry.speaker === current.speaker && !entry.removed) {
      current.text += ' ' + entry.text
      if (entry.ts) current.end_ts = entry.ts
    } else {
      merged.push(current)
      current = { ...entry, _origIndex: i }
    }
  }
  merged.push(current)

  // 标记合并条目，触发自动润色
  merged.forEach((entry, i) => {
    if (entry._origIndex !== undefined && raw[entry._origIndex]?.text !== entry.text) {
      entry._needsPolish = (entry.text || '').length > 20  // 合并过且够长
    }
  })
  return merged
})

// 存储润色后的文本
const polishedTexts = ref({})

async function autoPolishIfNeeded() {
  if (!meeting.value) return
  for (let i = 0; i < transcriptEntries.value.length; i++) {
    const entry = transcriptEntries.value[i]
    if (!entry._needsPolish || polishedTexts.value[i]) continue
    try {
      const res = await axios.post(`/api/v1/meetings/${meeting.value.id}/polish-text`, {
        text: entry.text,
      })
      const polished = res.data.polished
      if (polished && polished !== entry.text) {
        polishedTexts.value[i] = polished
      }
    } catch { /* 静默 */ }
  }
}

function getPolishedText(entry, index) {
  return polishedTexts.value[index] || entry.text
}

const speakerOptions = computed(() => {
  const options = new Set()
  memberStore.members.forEach(m => {
    if (m.name) options.add(m.name)
  })
  ;(transcriptEntries.value || []).forEach(entry => {
    if (entry?.speaker) options.add(entry.speaker)
  })
  ;['发言人A', '发言人B', '发言人C', '发言人D', '未知'].forEach(name => options.add(name))
  return Array.from(options)
})

// 解析条目中的发言人（如 "【杜同贺】介绍了..." → "杜同贺"）
function parseSpeaker(text) {
  const match = text.match(/^【(.+?)】/)
  return match ? match[1] : null
}

// 去掉发言人前缀
function removeSpeakerPrefix(text) {
  return text.replace(/^【.+?】/, '')
}

// 合并所有同一发言者的条目（非连续也合并）
function groupBySpeaker(items) {
  if (!items?.length) return []
  const map = new Map()  // speaker → items[]
  const order = []       // 保持发言人首次出现顺序
  for (const item of items) {
    const speaker = parseSpeaker(item)
    const text = speaker ? removeSpeakerPrefix(item) : item
    if (speaker) {
      if (!map.has(speaker)) {
        map.set(speaker, [])
        order.push(speaker)
      }
      map.get(speaker).push(text)
    } else {
      // 无发言人前缀的条目单独显示
      order.push(null)
      map.set(null, [text])
    }
  }
  // 去重：同一发言人的相同内容只保留一条
  const result = []
  const seen = new Set()
  for (const speaker of order) {
    const items = map.get(speaker)
    const unique = items.filter(item => {
      const key = item.trim()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    if (unique.length) {
      result.push({ speaker, items: unique, _editValues: unique.map(() => speaker) })
    }
  }
  return result
}

// 分组后的讨论要点和决议
const groupedKeyPoints = computed(() => groupBySpeaker(meeting.value?.key_points))
const groupedDecisions = computed(() => groupBySpeaker(meeting.value?.decisions))

const form = ref({ title: '', start_time: '', location: '', participants: [], presenter_ids: [], description: '' })
const minutesForm = ref({ summary: '', key_points: [], decisions: [] })

// 挂断后处理进度弹窗
const processingDialogVisible = ref(false)

// ===== 数据加载 =====

const fetchMeeting = async () => {
  try {
    const res = await axios.get(`/api/v1/meetings/${route.params.id}`)
    meeting.value = res.data
    // 延迟触发自动润色（等 DOM 渲染完）
    setTimeout(() => autoPolishIfNeeded(), 500)
    // 如果没有发言统计但有转录，自动获取统计数据
    if (!meeting.value.speaker_stats && meeting.value.transcript?.length) {
      try {
        const analyticsRes = await axios.get(`/api/v1/meetings/${route.params.id}/analytics`)
        meeting.value.speaker_stats = analyticsRes.data.speaker_stats || []
      } catch { /* 静默失败 */ }
    }
  } catch {
    ElMessage.error('加载会议失败')
  }
}

// ===== 编辑模式 =====

function enterEdit() {
  // 确保日期格式兼容 el-date-picker (YYYY-MM-DD HH:mm:ss)
  let startTime = meeting.value.start_time || ''
  if (startTime && startTime.includes('T')) {
    startTime = startTime.replace('T', ' ').replace(/\.\d+$/, '')
  }
  form.value = {
    title: meeting.value.title,
    start_time: startTime,
    location: meeting.value.location || '',
    participants: meeting.value.participants?.map(p => p.member_id) || [],
    presenter_ids: meeting.value.presenter_ids || [],
    description: meeting.value.description || '',
  }
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

const saveBasic = async () => {
  saving.value = true
  try {
    await axios.put(`/api/v1/meetings/${meeting.value.id}`, {
      title: form.value.title,
      start_time: form.value.start_time,
      location: form.value.location,
      description: form.value.description,
      participants: form.value.participants,
    })
    ElMessage.success('已保存')
    editing.value = false
    await fetchMeeting()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// ===== 纪要编辑 =====

function enterEditMinutes() {
  minutesForm.value = {
    summary: meeting.value.summary || '',
    key_points: meeting.value.key_points ? [...meeting.value.key_points] : [],
    decisions: meeting.value.decisions ? [...meeting.value.decisions] : [],
  }
  editingMinutes.value = true
}

const saveMinutes = async () => {
  try {
    await axios.put(`/api/v1/meetings/${meeting.value.id}`, {
      summary: minutesForm.value.summary,
      key_points: minutesForm.value.key_points.filter(Boolean),
      decisions: minutesForm.value.decisions.filter(Boolean),
    })
    ElMessage.success('纪要已保存')
    editingMinutes.value = false
    await fetchMeeting()
  } catch {
    ElMessage.error('保存失败')
  }
}

async function saveTranscriptSpeaker(displayIndex, speaker) {
  if (!meeting.value || !speaker) return
  savingTranscriptSpeaker.value = displayIndex
  // 用合并前的原始索引（如果有的话）
  const entry = transcriptEntries.value[displayIndex]
  const realIndex = entry?._origIndex ?? displayIndex
  try {
    const res = await axios.patch(`/api/v1/meetings/${meeting.value.id}/transcript-speaker`, {
      entry_index: realIndex,
      speaker,
    })
    meeting.value.transcript = res.data.transcript
    meeting.value.transcript_polished = res.data.transcript_polished
    meeting.value.speaker_mapping = res.data.speaker_mapping
    meeting.value.speaker_stats = res.data.speaker_stats
    ElMessage.success('发言人已更新')
  } catch {
    ElMessage.error('更新发言人失败')
  } finally {
    savingTranscriptSpeaker.value = null
  }
}

// ===== 听会 =====

function startLiveCall() {
  showCallRoom.value = true
}

function onCallEnded() {
  showCallRoom.value = false
  fetchMeeting()
  processingDialogVisible.value = true
}

// ===== 删除 =====

const handleDelete = async () => {
  try {
    await axios.delete(`/api/v1/meetings/${meeting.value.id}`)
    ElMessage.success('已删除')
    router.push('/meetings')
  } catch {
    ElMessage.error('删除失败')
  }
}

// ===== 相关会议 =====

async function loadRelated() {
  try {
    const resp = await fetch(`/api/v1/meetings/${meeting.value.id}/related?top_k=3`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
    })
    if (resp.ok) relatedMeetings.value = await resp.json()
  } catch { /* ignore */ }
}

// ===== 辅助函数 =====

function getSpeakerAvatar(name) {
  if (!name) return null
  const member = memberStore.members.find(m => m.name === name)
  return member?.avatar || null
}

function getAudioSrc(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return `/minio/microbubble/${url}`
}

const formatDate = (d) => {
  if (!d) return ''
  // 数据库存储 UTC 时间，显示北京时间（UTC+8）
  return dayjs(d).add(8, 'hour').format('YYYY-MM-DD HH:mm')
}
const formatTs = (sec) => {
  const s = Math.floor(sec || 0)
  return `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`
}
const formatDuration = (sec) => {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}
const statusLabel = (s) => ({ scheduled: '已预约', recording: '录制中', processing: '处理中', completed: '已完成', cancelled: '已取消', error: '处理失败' }[s] || s)
const statusType = (s) => ({ scheduled: 'info', recording: 'warning', processing: 'warning', completed: 'success', cancelled: 'info', error: 'danger' }[s] || '')

onMounted(async () => {
  await memberStore.fetchMembers()
  await fetchMeeting()
  await loadRelated()
})
</script>

<style scoped>
/* ====== 布局 ====== */
.meeting-detail {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  padding: 16px 20px;
  gap: 16px;
  overflow: hidden;
}

/* ====== Hero ====== */
.detail-hero {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px 24px;
  background: linear-gradient(180deg, #fff 0%, var(--color-bg-page, #f5f7fa) 100%);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--color-border, #ebeef5);
  flex-shrink: 0;
}

.hero-back { flex-shrink: 0; }

.hero-main { flex: 1; min-width: 0; }

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary, #2d2d2d);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hero-title-row.editing { gap: 12px; }
.edit-title-input { max-width: 400px; }

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--radius-full, 9999px);
  font-size: 13px;
  font-weight: 500;
  flex-shrink: 0;
}
.status-badge .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-badge.status-scheduled { background: #f4f4f5; color: #909399; }
.status-badge.status-scheduled .status-dot { background: #909399; }
.status-badge.status-recording { background: #fff0ed; color: #FF7A5C; }
.status-badge.status-recording .status-dot { background: #FF7A5C; animation: dot-pulse 1.2s infinite; }
.status-badge.status-processing { background: #fdf6ec; color: #E6A23C; }
.status-badge.status-processing .status-dot { background: #E6A23C; animation: dot-pulse 1.5s infinite; }
.status-badge.status-completed { background: #f0f9eb; color: #67C23A; }
.status-badge.status-completed .status-dot { background: #67C23A; }
.status-badge.status-cancelled { background: #f4f4f5; color: #909399; }
.status-badge.status-cancelled .status-dot { background: #909399; opacity: 0.5; }
.status-badge.status-error { background: #fef0f0; color: #F56C6C; }
.status-badge.status-error .status-dot { background: #F56C6C; }

@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.4); }
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: var(--color-text-regular, #606266);
}
.meta-item .el-icon { color: var(--color-text-secondary, #909399); }

.hero-participants { margin-top: 4px; }

.hero-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
  align-self: flex-start;
}

/* ====== 主体 ====== */
.detail-body {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;
}

.detail-main {
  flex: 1;
  overflow-y: auto;
  background: #fff;
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--color-border, #ebeef5);
}

.detail-tabs {
  height: 100%;
}
.detail-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 20px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: var(--radius-lg, 12px) var(--radius-lg, 12px) 0 0;
}
.detail-tabs :deep(.el-tabs__content) {
  height: calc(100% - 40px);
  overflow-y: auto;
}
.detail-tabs :deep(.el-tab-pane) {
  height: 100%;
}

.tab-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ====== 侧边栏 ====== */
.detail-side {
  width: 320px;
  flex-shrink: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.side-card {
  border-radius: var(--radius-lg, 12px);
}
.side-card :deep(.el-card__header) {
  font-weight: 600;
  font-size: 14px;
  padding: 12px 16px;
}

.audio-meta {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

.call-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  cursor: pointer;
  border: 2px dashed var(--color-border, #ebeef5);
  border-radius: var(--radius-lg, 12px);
  transition: all 0.2s;
}
.call-placeholder:hover {
  border-color: var(--color-primary, #FF7A5C);
  background: var(--color-primary-bg, #fff0ed);
}
.call-placeholder p {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--color-text-secondary, #909399);
}

/* ====== 纪要 ====== */
.section h4 {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #2d2d2d);
}
.summary-text {
  margin: 0;
  line-height: 1.7;
  font-size: 14px;
  color: var(--color-text-regular, #606266);
}
.speaker-group {
  margin-bottom: 12px;
}
.speaker-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.speaker-avatar {
  flex-shrink: 0;
}
.speaker-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-primary, #FF7A5C);
}
.point-item {
  cursor: pointer;
  transition: background 0.15s;
  border-radius: var(--radius-sm, 4px);
  padding: 2px 4px;
  margin-left: -4px;
}
.point-item:hover {
  background: var(--color-bg-page, #f5f7fa);
}
.inline-speaker-select {
  width: 84px;
}
.transcript-speaker-select {
  width: 90px;
}
.polish-text-btn {
  margin-left: 6px;
  font-size: 12px;
  vertical-align: middle;
}
.point-text {
  flex: 1;
}
.points-list, .decisions-list {
  padding-left: 20px;
  margin: 0;
}
.points-list li, .decisions-list li {
  margin-bottom: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-regular, #606266);
}
.decisions-list li::marker {
  color: var(--color-warning, #E6A23C);
}
.agenda-list {
  padding-left: 20px;
  margin: 0;
}
.agenda-list li {
  margin-bottom: 6px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.agenda-list .done {
  text-decoration: line-through;
  color: var(--color-text-secondary, #909399);
}
.edit-minutes-btn {
  margin-top: 8px;
  align-self: flex-start;
}
.section-actions {
  display: flex;
  gap: 8px;
}

/* ====== 转录记录 ====== */
.transcript-entry {
  display: flex;
  gap: 12px;
}
.transcript-entry.entry-removed {
  opacity: 0.5;
}
.transcript-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}
.transcript-avatar {
  flex-shrink: 0;
}
.transcript-line {
  flex: 1;
  width: 2px;
  background: var(--color-border, #ebeef5);
  margin: 4px 0;
}
.transcript-entry:last-child .transcript-line {
  display: none;
}
.transcript-body {
  flex: 1;
  padding-bottom: 16px;
}
.transcript-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.transcript-speaker {
  font-weight: 600;
  font-size: 14px;
  color: var(--color-primary, #FF7A5C);
}
.transcript-ts {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  margin-left: auto;
}
.transcript-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-regular, #606266);
}
.transcript-text.removed {
  display: flex;
  align-items: center;
  gap: 6px;
  font-style: italic;
  text-decoration: line-through;
  color: var(--color-text-secondary, #909399);
}
.remove-reason {
  font-size: 12px;
  color: var(--color-text-placeholder, #c0c4cc);
}

/* ====== 相关会议 ====== */
.related-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border, #ebeef5);
}
.related-item:last-child { border-bottom: none; }
.related-link {
  font-size: 13px;
  color: var(--color-primary, #FF7A5C);
  text-decoration: none;
  font-weight: 500;
}
.related-link:hover { text-decoration: underline; }
.related-similarity {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

/* ====== 编辑态表单 ====== */
.hero-meta .el-date-editor {
  --el-date-editor-width: 200px;
}

/* ====== 纪要编辑列表 ====== */
.item-list { display: flex; flex-direction: column; gap: 8px; }
.item-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; background: var(--color-bg-page, #f5f7fa); border-radius: var(--radius-md, 8px);
  border: 1px solid transparent; transition: all 0.2s;
}
.item-row:hover, .item-row:focus-within { border-color: rgba(255, 122, 92, 0.3); background: var(--color-primary-bg, #fff0ed); }
.item-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: var(--color-primary, #FF7A5C); }
.decision-dot { background: var(--color-warning, #E6A23C); }
.item-row .el-input { flex: 1; }
.item-del { opacity: 0; transition: opacity 0.2s; }
.item-row:hover .item-del { opacity: 1; }
.item-add { width: 100%; justify-content: center; border-style: dashed; }
.decision-add { color: var(--color-warning, #E6A23C); border-color: var(--color-warning, #E6A23C); }

/* ====== 加载态 ====== */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 8px;
  color: var(--color-text-secondary, #909399);
}

/* ====== 入场动画 ====== */
.fade-slide-up {
  animation: fadeSlideUp 300ms ease-out both;
}
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ====== 响应式 ====== */
@media (max-width: 768px) {
  .meeting-detail { height: auto; }
  .detail-hero { flex-direction: column; }
  .hero-actions { flex-direction: row; align-self: stretch; }
  .detail-body { flex-direction: column; }
  .detail-side { width: 100%; }
  .hero-title { font-size: 18px; }
}
</style>
