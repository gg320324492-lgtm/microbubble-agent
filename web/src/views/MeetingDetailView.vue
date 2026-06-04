<template>
  <div class="meeting-detail" v-if="meeting">
    <!-- 顶部导航 -->
    <div class="detail-topbar">
      <el-button text @click="$router.push('/meetings')">
        <el-icon><ArrowLeft /></el-icon> 返回列表
      </el-button>
      <div class="topbar-actions">
        <el-button type="primary" @click="startLiveCall">
          <el-icon><Phone /></el-icon> 声纹通话
        </el-button>
        <el-popconfirm title="确定删除此会议？" @confirm="handleDelete">
          <template #reference>
            <el-button type="danger">删除会议</el-button>
          </template>
        </el-popconfirm>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="detail-body">
      <!-- 左侧：基本信息 -->
      <div class="detail-main">
        <el-card class="section-card">
          <template #header><span>基本信息</span></template>

          <el-form :model="form" label-width="90px">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="标题" required><el-input v-model="form.title" name="meeting-detail-title" /></el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="状态">
                  <el-tag :type="statusType(meeting.status)" size="default">{{ statusLabel(meeting.status) }}</el-tag>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="时间" required>
                  <input
    :value="form.start_time"
    name="form-start_time"
    type="datetime-local"
    class="native-date-input"
    style="width:100%"
    @change="(e) => { const v = e.target.value; form.start_time = v ? v.replace('T', ' ') + ':00' : ''; }"
  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="地点"><el-input v-model="form.location" name="meeting-detail-location" placeholder="会议室/线上" /></el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="参会人员">
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <el-select v-model="form.participants" name="meeting-detail-participants" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择参会人员" style="flex:1;min-width:200px">
                  <el-option v-for="m in memberStore.members" :key="m.id" :label="m.name" :value="m.id" />
                </el-select>
                <el-button size="small" @click="form.participants = memberStore.members.map(m=>m.id)">全选成员</el-button>
                <el-button size="small" @click="form.participants = []">清空</el-button>
              </div>
              <span v-if="form.participants.length === memberStore.members.length && memberStore.members.length > 0" style="color:var(--color-primary);font-size:12px">已选择全体成员（{{ memberStore.members.length }}人）</span>
            </el-form-item>
            <el-form-item label="汇报人员">
              <el-select v-model="form.presenter_ids" name="meeting-detail-presenter-ids" multiple filterable placeholder="选择汇报人员" style="width:100%">
                <el-option v-for="m in memberStore.members" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="说明">
              <el-input v-model="form.description" name="meeting-detail-description" type="textarea" :rows="2" placeholder="会议说明..." />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveBasic" :loading="saving">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 会议纪要 -->
        <el-card v-if="meeting.summary || meeting.key_points?.length || meeting.decisions?.length || (meeting.agenda && meeting.agenda.length) || editingMinutes" class="section-card">
          <template #header>
            <div class="card-header">
              <span><el-icon><Document /></el-icon> 会议纪要</span>
              <el-button v-if="!editingMinutes" size="small" :icon="Edit" @click="editingMinutes = true">编辑纪要</el-button>
              <el-button v-else size="small" type="primary" @click="saveMinutes">保存纪要</el-button>
            </div>
          </template>

          <template v-if="editingMinutes">
            <div class="minutes-section">
              <h4>摘要</h4>
              <el-input v-model="minutesForm.summary" name="meeting-detail-minutes-summary" type="textarea" :rows="4" placeholder="会议摘要..." class="minutes-textarea" />
            </div>
            <div class="minutes-section">
              <h4>讨论要点</h4>
              <div class="item-list">
                <div v-for="(p, i) in minutesForm.key_points" :key="'kp'+i" class="item-row">
                  <span class="item-dot" />
                  <el-input v-model="minutesForm.key_points[i]" :name="`meeting-detail-minutes-key-points-${i}`" placeholder="输入要点..." />
                  <el-button :icon="Delete" circle size="small" class="item-del" @click="minutesForm.key_points.splice(i,1)" />
                </div>
                <el-button dashed size="small" class="item-add" @click="minutesForm.key_points.push('')">
                  <el-icon><Plus /></el-icon> 添加要点
                </el-button>
              </div>
            </div>
            <div class="minutes-section">
              <h4>决议事项</h4>
              <div class="item-list">
                <div v-for="(d, i) in minutesForm.decisions" :key="'dc'+i" class="item-row decision">
                  <span class="item-dot decision-dot" />
                  <el-input v-model="minutesForm.decisions[i]" :name="`meeting-detail-minutes-decisions-${i}`" placeholder="输入决议..." />
                  <el-button :icon="Delete" circle size="small" class="item-del" @click="minutesForm.decisions.splice(i,1)" />
                </div>
                <el-button dashed size="small" class="item-add decision-add" @click="minutesForm.decisions.push('')">
                  <el-icon><Plus /></el-icon> 添加决议
                </el-button>
              </div>
            </div>
          </template>

          <template v-else>
            <div v-if="meeting.summary" class="minutes-section">
              <h4>摘要</h4>
              <p>{{ meeting.summary }}</p>
            </div>
            <div v-if="meeting.key_points?.length" class="minutes-section">
              <h4>讨论要点</h4>
              <ul><li v-for="(p,i) in meeting.key_points" :key="i">{{ p }}</li></ul>
            </div>
            <div v-if="meeting.decisions?.length" class="minutes-section">
              <h4>决议事项</h4>
              <ul><li v-for="(d,i) in meeting.decisions" :key="i">{{ d }}</li></ul>
            </div>
            <!-- Wave 3b: 议程 -->
            <div v-if="meeting.agenda && meeting.agenda.length > 0" class="minutes-section agenda-display">
              <h4>议程</h4>
              <ol class="agenda-list">
                <li v-for="(item, idx) in meeting.agenda" :key="idx">
                  <span :class="{ done: item.done }">{{ item.text || item }}</span>
                  <el-tag v-if="item.done" type="success" size="small" style="margin-left: 8px">已完成</el-tag>
                </li>
              </ol>
            </div>
            <el-empty v-if="!meeting.summary && !meeting.key_points?.length && !meeting.decisions?.length && (!meeting.agenda || !meeting.agenda.length)" description="暂无会议纪要" />
          </template>
        </el-card>

        <!-- Wave 3a: 相关会议 -->
        <div class="related-meetings" v-if="relatedMeetings.length > 0">
          <h3>相关会议</h3>
          <p class="hint">基于内容相似度推荐（pgvector cosine distance）</p>
          <el-checkbox-group v-model="selectedRelated" name="selectedRelated">
            <div
              v-for="m in relatedMeetings"
              :key="m.id"
              class="related-card"
            >
              <el-checkbox :value="m.id">
                <div class="related-content">
                  <div class="related-title">
                    <router-link :to="`/meetings/${m.id}`">{{ m.title }}</router-link>
                    <span class="similarity">{{ Math.round(m.similarity * 100) }}% 相似</span>
                  </div>
                  <div class="related-summary">{{ m.summary?.substring(0, 100) }}</div>
                </div>
              </el-checkbox>
            </div>
          </el-checkbox-group>
          <el-button type="primary" @click="linkRelated" :disabled="selectedRelated.length === 0">
            关联选中的会议
          </el-button>
        </div>
      </div>

      <!-- 右侧：声纹通话 + 发言者统计 -->
      <div class="detail-side">
        <el-card class="section-card">
          <template #header><span>听会</span></template>
          <MeetingRoom v-if="showCallRoom" @call-ended="onCallEnded" style="height: 500px" />
          <div v-else class="call-placeholder" @click="startLiveCall">
            <el-icon size="40" color="#FF7A5C"><Microphone /></el-icon>
            <p>点击开始听会</p>
          </div>
        </el-card>

        <!-- 2026-06-02 L3 全文精润版（如果存在） -->
        <el-card v-if="meeting.transcript_polished && meeting.transcript_polished.length" class="section-card">
          <template #header>
            <div class="card-header">
              <span>✨ AI 精润版转录（已过滤幻觉）</span>
              <el-tag size="small" type="success">
                {{ meeting.transcript_polished.length }} 段
              </el-tag>
            </div>
          </template>
          <div class="polished-transcript">
            <div
              v-for="(entry, i) in meeting.transcript_polished"
              :key="i"
              class="polished-entry"
              :class="{ 'entry-removed': entry.removed }"
            >
              <div class="polished-entry-header">
                <span class="polished-speaker">{{ entry.speaker || '未知说话人' }}</span>
                <el-tag v-if="entry.removed" size="small" type="info" effect="plain">已过滤</el-tag>
                <el-tag v-else-if="entry.polish_failed" size="small" type="warning" effect="plain">降级</el-tag>
                <span v-if="entry.ts" class="polished-ts">{{ formatTs(entry.ts) }}</span>
              </div>
              <div v-if="!entry.removed" class="polished-text">{{ entry.text }}</div>
              <div v-else class="polished-text removed-text">
                <el-icon><Delete /></el-icon>
                <span>{{ entry.text || '(空)' }}</span>
                <span v-if="entry.reason" class="remove-reason">({{ entry.reason }})</span>
              </div>
            </div>
          </div>
        </el-card>

        <el-card v-if="meeting.speaker_stats?.length" class="section-card">
          <template #header><span>发言者统计</span></template>
          <el-table :data="meeting.speaker_stats" size="small" stripe>
            <el-table-column prop="name" label="发言人" width="80" />
            <el-table-column prop="turn_count" label="发言次数" width="65" align="center" />
            <el-table-column prop="word_count" label="字数" width="60" align="center" />
            <el-table-column label="占比" width="80">
              <template #default="{row}">{{ Math.round((row.speaking_ratio||0)*100) }}%</template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </div>
  </div>

  <div v-else class="loading-state"><el-icon class="is-loading" size="24"><Loading /></el-icon> 加载中...</div>

  <!-- 挂断后会后处理进度对话框 -->
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
import { ArrowLeft, Phone, Edit, Delete, Document, Plus, Loading } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { useMemberStore } from '@/stores/member'
import MeetingRoom from '@/components/MeetingRoom.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'

const route = useRoute()
const router = useRouter()
const memberStore = useMemberStore()

const meeting = ref(null)
const editingMinutes = ref(false)
const showCallRoom = ref(false)
const saving = ref(false)

const relatedMeetings = ref([])
const selectedRelated = ref([])

const form = ref({ title: '', start_time: '', location: '', participants: [], presenter_ids: [], description: '' })
const minutesForm = ref({ summary: '', key_points: [], decisions: [] })

const allMemberIds = computed(() => memberStore.members.map(m => m.id))
const isAllMembers = computed(() => {
  const pids = meeting.value?.participants?.map(p => p.member_id) || []
  return pids.length > 0 && allMemberIds.value.length > 0 && allMemberIds.value.every(id => pids.includes(id))
})
const participantDisplay = computed(() => {
  if (isAllMembers.value) return '全体成员'
  if (!meeting.value?.participants?.length) return ''
  return meeting.value.participants.map(p => {
    const m = memberStore.members.find(x => x.id === p.member_id)
    return m?.name || p.member_id
  }).join('、')
})

const fetchMeeting = async () => {
  try {
    const res = await axios.get(`/api/v1/meetings/${route.params.id}`)
    meeting.value = res.data
    // 初始化表单
    form.value = {
      title: res.data.title, start_time: res.data.start_time,
      location: res.data.location || '',
      participants: res.data.participants?.map(p => p.member_id) || [],
      presenter_ids: res.data.presenter_ids || [],
      description: res.data.description || '',
    }
  } catch { ElMessage.error('加载会议失败') }
}

const saveBasic = async () => {
  saving.value = true
  try {
    const payload = {
      title: form.value.title, start_time: form.value.start_time,
      location: form.value.location, description: form.value.description,
      participants: form.value.participants,
    }
    await axios.put(`/api/v1/meetings/${meeting.value.id}`, payload)
    ElMessage.success('已保存'); fetchMeeting()
  } catch { ElMessage.error('保存失败') }
  finally { saving.value = false }
}

const saveMinutes = async () => {
  try {
    await axios.put(`/api/v1/meetings/${meeting.value.id}`, {
      summary: minutesForm.summary,
      key_points: minutesForm.key_points.filter(Boolean),
      decisions: minutesForm.decisions.filter(Boolean),
    })
    ElMessage.success('纪要已保存'); editingMinutes.value = false; fetchMeeting()
  } catch { ElMessage.error('保存失败') }
}

const startLiveCall = () => {
  showCallRoom.value = true
  // 初始化纪要编辑表单
  minutesForm.value = {
    summary: meeting.value.summary || '',
    key_points: meeting.value.key_points ? [...meeting.value.key_points] : [],
    decisions: meeting.value.decisions ? [...meeting.value.decisions] : [],
  }
}

const onCallEnd = () => { showCallRoom.value = false; fetchMeeting() }

// 挂断后处理进度弹窗
const processingDialogVisible = ref(false)
const onCallEnded = () => {
  // 关闭嵌入式通话卡片，弹出会后处理进度对话框
  showCallRoom.value = false
  fetchMeeting()
  processingDialogVisible.value = true
}

const handleDelete = async () => {
  try {
    await axios.delete(`/api/v1/meetings/${meeting.value.id}`)
    ElMessage.success('已删除'); router.push('/meetings')
  } catch { ElMessage.error('删除失败') }
}

const formatDate = (d) => dayjs(d).format('YYYY-MM-DD HH:mm')
const formatTs = (sec) => {  // 2026-06-02 L3 精润版时间戳格式
  const s = Math.floor(sec || 0)
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m.toString().padStart(2, '0')}:${r.toString().padStart(2, '0')}`
}
const statusLabel = (s) => ({ scheduled: '已预约', recording: '录制中', completed: '已完成' }[s] || s)
const statusType = (s) => ({ scheduled: 'info', recording: 'warning', completed: 'success' }[s] || '')

onMounted(async () => {
  await memberStore.fetchMembers()
  await fetchMeeting()
  await loadRelated()
})

async function loadRelated() {
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  try {
    const resp = await fetch(`${apiUrl}/meetings/${meeting.value.id}/related?top_k=3`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
    })
    if (resp.ok) {
      relatedMeetings.value = await resp.json()
    }
  } catch (e) {}
}

async function linkRelated() {
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  await fetch(`${apiUrl}/meetings/${meeting.value.id}/related`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(selectedRelated.value),
  })
  ElMessage.success('已关联')
  selectedRelated.value = []
}
</script>

<style scoped>

/* 2026-06-02 原生 date input 样式（绕过 el-date-picker 内部 input 缺 name 的 a11y 警告） */
.native-date-input {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: var(--radius-md, 4px);
  background: #fff;
  color: var(--color-text-primary, #303133);
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.2s;
}
.native-date-input:focus {
  outline: none;
  border-color: var(--color-primary, #FF7A5C);
}

.meeting-detail { display: flex; flex-direction: column; height: calc(100vh - 120px); padding: 16px 20px; gap: 16px; overflow: hidden; }
.detail-topbar { display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }
.detail-body { flex: 1; display: flex; gap: 16px; overflow: hidden; }
.detail-main { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.detail-side { width: 400px; flex-shrink: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }

.section-card { border-radius: var(--radius-lg); }
.card-header { display: flex; justify-content: space-between; align-items: center; }

/* 2026-06-02 L3 全文精润版转录 */
.polished-transcript { display: flex; flex-direction: column; gap: 12px; }
.polished-entry {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-left: 3px solid #67c23a;
  border-radius: var(--radius-md);
}
.polished-entry.entry-removed {
  border-left-color: #999;
  opacity: 0.5;
}
.polished-entry-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}
.polished-speaker { color: #ff7a5c; font-weight: 500; }
.polished-ts { color: #999; font-family: monospace; margin-left: auto; }
.polished-text { color: #eee; line-height: 1.6; white-space: pre-wrap; }
.removed-text { display: flex; align-items: center; gap: 6px; font-style: italic; text-decoration: line-through; }
.remove-reason { font-size: 11px; color: #999; }

.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-item.full { grid-column: span 2; }
.info-item label { font-size: 12px; color: var(--color-text-secondary); }
.info-item span { font-size: 14px; color: var(--color-text-primary); }

.minutes-section { margin-bottom: 16px; }
.minutes-section h4 { margin: 0 0 8px; font-size: 14px; color: var(--color-text-primary); }
.minutes-section p { margin: 0; line-height: 1.6; font-size: 14px; }
.minutes-section ul { padding-left: 18px; margin: 0; }
.minutes-section li { margin-bottom: 6px; font-size: 14px; line-height: 1.5; }

.call-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; cursor: pointer; border: 2px dashed var(--color-border); border-radius: var(--radius-lg); transition: all 0.2s; }
.call-placeholder:hover { border-color: var(--color-primary); background: var(--color-primary-bg); }
.loading-state { display: flex; align-items: center; justify-content: center; height: 200px; gap: 8px; color: var(--color-text-secondary); }

/* 共用编辑列表样式 */
.minutes-textarea :deep(.el-textarea__inner) { border-radius: var(--radius-md); border-color: var(--color-border); }
.item-list { display: flex; flex-direction: column; gap: 8px; }
.item-row { display: flex; align-items: center; gap: 10px; padding: 6px 10px; background: var(--color-bg-page); border-radius: var(--radius-md); border: 1px solid transparent; transition: all 0.2s; }
.item-row:hover, .item-row:focus-within { border-color: var(--color-primary-border); background: var(--color-primary-bg); }
.item-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: var(--color-primary); }
.decision-dot { background: var(--color-warning); }
.item-row .el-input { flex: 1; }
.item-del { opacity: 0; transition: opacity 0.2s; }
.item-row:hover .item-del { opacity: 1; }
.item-add { width: 100%; justify-content: center; border-style: dashed; }
.decision-add { color: var(--color-warning); border-color: var(--color-warning); }

/* 相关会议 */
.related-meetings { margin-top: 16px; padding: 16px; background: #fff; border-radius: var(--radius-lg); border: 1px solid var(--color-border); }
.related-meetings h3 { margin: 0 0 4px; font-size: 15px; color: var(--color-text-primary); }
.related-meetings .hint { margin: 0 0 12px; font-size: 12px; color: var(--color-text-secondary); }
.related-card { padding: 10px; margin-bottom: 8px; background: var(--color-bg-page); border-radius: var(--radius-md); transition: all 0.2s; }
.related-card:hover { background: var(--color-primary-bg); }
.related-content { margin-left: 8px; }
.related-title { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.related-title a { color: var(--color-primary); font-weight: 500; text-decoration: none; }
.related-title a:hover { text-decoration: underline; }
.similarity { color: var(--color-text-secondary); font-size: 12px; }
.related-summary { font-size: 13px; color: var(--color-text-regular); margin-top: 4px; line-height: 1.5; }

@media (max-width: 768px) {
  .meeting-detail { height: auto; }
  .detail-body { flex-direction: column; }
  .detail-side { width: 100%; }
  .info-grid { grid-template-columns: 1fr; }
  .info-item.full { grid-column: span 1; }
}
</style>
