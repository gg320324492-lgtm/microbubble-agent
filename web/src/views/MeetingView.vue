<template>
  <div class="meeting-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="12" :sm="6" :md="4">
          <!--
            2026-06-02 修复 a11y 警告：el-date-picker 在 Element Plus 2.4.x 中
            即使 type="date" 也会用 el-range-input 类（与 daterange 同一底层组件），
            内部 input 仍无 name。改用原生 <input type="date"> 彻底绕过。
            原生 input 触发 change 事件（不是 input），用 ref.value + @change 手动同步。
          -->
          <input
            :value="dateFrom"
            name="meeting-list-date-from"
            type="date"
            class="native-date-input"
            placeholder="开始日期"
            @change="(e) => { dateFrom = e.target.value; fetchMeetings() }"
          />
        </el-col>
        <el-col :xs="12" :sm="6" :md="4">
          <input
            :value="dateTo"
            name="meeting-list-date-to"
            type="date"
            class="native-date-input"
            placeholder="结束日期"
            @change="(e) => { dateTo = e.target.value; fetchMeetings() }"
          />
        </el-col>
        <el-col :xs="24" :sm="12" :md="8">
          <el-input
            v-model="keyword"
            name="meeting-list-keyword"
            placeholder="搜索会议主题"
            clearable
            @keyup.enter="fetchMeetings"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :xs="24" :sm="12" :md="8">
          <div class="top-actions">
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon> 手动创建
            </el-button>
            <el-button type="success" @click="pasteAnalyzeDialogRef?.open()">
              <el-icon><Document /></el-icon> 粘贴转录分析
            </el-button>
            <el-button type="warning" @click="startLiveCall">
              <el-icon><Microphone /></el-icon> 开始听会
            </el-button>
            <el-button @click="showVoiceTest = true">
              🎤 测试
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 会议列表 -->
    <el-card class="meeting-list-card">
      <div v-if="meetings.length === 0" class="empty-state">
        <el-empty description="暂无会议记录" />
      </div>

      <div v-else class="meeting-list">
        <div
          v-for="meeting in meetings"
          :key="meeting.id"
          class="meeting-item"
          @click="viewMeeting(meeting)"
        >
          <div class="meeting-time-block">
            <div class="time-month">{{ formatMonth(meeting.start_time) }}</div>
            <div class="time-day">{{ formatDay(meeting.start_time) }}</div>
            <div class="time-hour">{{ formatHour(meeting.start_time) }}</div>
          </div>

          <div class="meeting-info">
            <div class="meeting-title">{{ meeting.title }}</div>
            <div class="meeting-meta">
              <el-tag :type="getStatusType(meeting.status)" size="small">
                {{ getStatusLabel(meeting.status) }}
              </el-tag>
              <span v-if="meeting.location" class="meeting-location">
                <el-icon><Location /></el-icon>
                {{ meeting.location }}
              </span>
            </div>
            <div v-if="meeting.summary" class="meeting-summary">
              {{ meeting.summary.substring(0, 100) }}...
            </div>
          </div>

          <div class="meeting-actions">
            <el-button type="primary" size="small" @click.stop="viewMeeting(meeting)">
              查看详情
            </el-button>
            <el-popconfirm title="确定删除此会议？" @confirm="deleteMeeting(meeting.id)">
              <template #reference>
                <el-button type="danger" size="small" @click.stop>删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchMeetings"
        />
      </div>
    </el-card>

    <!-- 创建会议对话框 -->
    <el-dialog v-model="showCreateDialog" :title="editingMeetingId ? '编辑会议' : '创建会议'" :width="isMobile ? '90vw' : '560px'" top="6vh" @close="onCreateDialogClose">
      <el-form :model="meetingForm" label-width="80px">
        <!-- 2026-06-03 重构：模板选择从下拉改为卡片式 + 行内 CRUD
             替代独立 MeetingTemplatesView 页面，贴近使用场景 -->
        <div v-if="!editingMeetingId" class="template-picker">
          <div class="template-picker-header">
            <span class="template-picker-title">
              <el-icon><Document /></el-icon> 快速模板
            </span>
            <el-button text type="primary" size="small" @click="showTemplateForm()">
              <el-icon><Plus /></el-icon> 存为新模板
            </el-button>
          </div>
          <div class="template-cards">
            <div
              v-for="tpl in builtinTemplates"
              :key="tpl.id"
              class="template-card builtin"
              :class="{ active: meetingForm.templateId === tpl.id }"
              @click="applyTemplate(tpl)"
            >
              <div class="template-card-name">{{ tpl.name }}<el-tag size="small" type="info" effect="plain">内置</el-tag></div>
              <div class="template-card-desc">{{ tpl.description || '—' }}</div>
              <div class="template-card-meta">
                <span><el-icon><Clock /></el-icon> {{ tpl.default_duration_minutes || 60 }} 分钟</span>
                <span v-if="tpl.agenda?.length"><el-icon><List /></el-icon> {{ tpl.agenda.length }} 议题</span>
              </div>
            </div>
            <div
              v-for="tpl in customTemplates"
              :key="tpl.id"
              class="template-card custom"
              :class="{ active: meetingForm.templateId === tpl.id }"
              @click="applyTemplate(tpl)"
            >
              <div class="template-card-name">
                {{ tpl.name }}
                <span class="template-card-actions" @click.stop>
                  <el-icon class="tpl-action" title="编辑" @click="showTemplateForm(tpl)"><Edit /></el-icon>
                  <el-icon class="tpl-action danger" title="删除" @click="deleteTemplate(tpl)"><Delete /></el-icon>
                </span>
              </div>
              <div class="template-card-desc">{{ tpl.description || '（无说明）' }}</div>
              <div class="template-card-meta">
                <span><el-icon><Clock /></el-icon> {{ tpl.default_duration_minutes || 60 }} 分钟</span>
                <span v-if="tpl.agenda?.length"><el-icon><List /></el-icon> {{ tpl.agenda.length }} 议题</span>
              </div>
            </div>
            <div v-if="customTemplates.length === 0" class="template-empty">
              暂无自定义模板，点击右上"存为新模板"创建
            </div>
          </div>
        </div>
        <el-form-item label="会议主题" required>
          <el-input v-model="meetingForm.title" name="meeting-form-title" placeholder="请输入会议主题" />
        </el-form-item>
        <el-form-item label="会议时间" required>
          <input
    :value="meetingForm.start_time"
    name="meetingForm-start_time"
    type="datetime-local"
    class="native-date-input"
    placeholder="选择会议时间"
    @change="(e) => { const v = e.target.value; meetingForm.start_time = v ? v.replace('T', ' ') + ':00' : ''; }"
  />
        </el-form-item>
        <el-form-item label="会议地点">
          <el-input v-model="meetingForm.location" name="meeting-form-location" placeholder="请输入会议地点" />
        </el-form-item>
        <el-form-item label="参会人员">
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <el-select v-model="meetingForm.participants" name="meeting-form-participants" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择参会人员" style="flex:1;min-width:200px">
              <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
            </el-select>
            <el-button size="small" @click="meetingForm.participants = members.map(m=>m.id)">全选</el-button>
          </div>
        </el-form-item>
        <el-form-item label="会议说明">
          <el-input
            v-model="meetingForm.description"
            name="meeting-form-description"
            type="textarea"
            :rows="3"
            placeholder="请输入会议说明"
          />
        </el-form-item>
        <el-form-item label="议程">
          <div class="item-list" style="width:100%">
            <div v-for="(item, idx) in meetingForm.agenda" :key="idx" class="item-row">
              <span class="item-dot" />
              <el-input v-model="meetingForm.agenda[idx]" :name="`meeting-form-agenda-${idx}`" placeholder="议题描述" />
              <el-button :icon="Delete" circle size="small" class="item-del" @click="meetingForm.agenda.splice(idx, 1)" />
            </div>
            <el-button dashed size="small" class="item-add" @click="meetingForm.agenda.push('')">
              <el-icon><Plus /></el-icon> 添加议题
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="提前提醒">
          <el-checkbox v-model="meetingForm.remindBefore" name="meeting-form-remind-before">会议前 5 分钟企业微信提醒</el-checkbox>
        </el-form-item>

        <!-- 编辑已有会议时显示纪要字段 -->
        <template v-if="editingMeetingId">
          <el-divider content-position="left">
            <el-icon><Document /></el-icon> 会议纪要
          </el-divider>
          <el-form-item label="摘要">
            <el-input
              v-model="meetingForm.summary"
              name="meeting-form-summary"
              type="textarea"
              :rows="3"
              placeholder="会议摘要..."
              class="minutes-textarea"
            />
          </el-form-item>
          <el-form-item label="讨论要点">
            <div class="item-list">
              <div v-for="(point, i) in meetingForm.key_points" :key="'kp'+i" class="item-row">
                <span class="item-dot" />
                <el-input v-model="meetingForm.key_points[i]" :name="`meeting-form-key-points-${i}`" size="default" placeholder="输入要点..." />
                <el-button :icon="Delete" circle size="small" class="item-del" @click="meetingForm.key_points.splice(i, 1)" />
              </div>
              <el-button dashed size="small" class="item-add" @click="meetingForm.key_points.push('')">
                <el-icon><Plus /></el-icon> 添加要点
              </el-button>
            </div>
          </el-form-item>
          <el-form-item label="决议事项">
            <div class="item-list">
              <div v-for="(d, i) in meetingForm.decisions" :key="'dc'+i" class="item-row decision">
                <span class="item-dot decision-dot" />
                <el-input v-model="meetingForm.decisions[i]" :name="`meeting-form-decisions-${i}`" size="default" placeholder="输入决议..." />
                <el-button :icon="Delete" circle size="small" class="item-del" @click="meetingForm.decisions.splice(i, 1)" />
              </div>
              <el-button dashed size="small" class="item-add decision-add" @click="meetingForm.decisions.push('')">
                <el-icon><Plus /></el-icon> 添加决议
              </el-button>
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitMeeting">{{ editingMeetingId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- 2026-06-03 新增：模板编辑对话框（创建/编辑自定义模板） -->
    <el-dialog v-model="showTemplateDialog" :title="editingTemplateId ? '编辑模板' : '存为新模板'" :width="isMobile ? '92vw' : '500px'" top="8vh">
      <el-form :model="templateForm" label-width="80px">
        <el-form-item label="模板名称" required>
          <el-input v-model="templateForm.name" name="template-form-name" placeholder="如：组会、组内复盘..." maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="默认时长">
          <el-input-number v-model="templateForm.default_duration_minutes" name="template-form-duration" :min="15" :max="240" :step="15" />
          <span class="form-hint">分钟</span>
        </el-form-item>
        <el-form-item label="默认地点">
          <el-input v-model="templateForm.default_location" name="template-form-location" placeholder="可选，如：组会室、腾讯会议..." maxlength="100" />
        </el-form-item>
        <el-form-item label="会议说明">
          <el-input v-model="templateForm.description" name="template-form-description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
        <el-form-item label="标题模板">
          <el-input v-model="templateForm.title_template" name="template-form-title-template" placeholder="可选，支持 {date} 占位符" maxlength="100" />
          <div class="form-hint">如：组会 - {date}</div>
        </el-form-item>
        <el-form-item label="默认议题">
          <div class="item-list" style="width:100%">
            <div v-for="(item, idx) in templateForm.agenda" :key="idx" class="item-row">
              <span class="item-dot" />
              <el-input v-model="templateForm.agenda[idx]" :name="`template-form-agenda-${idx}`" placeholder="议题描述" />
              <el-button :icon="Delete" circle size="small" class="item-del" @click="templateForm.agenda.splice(idx, 1)" />
            </div>
            <el-button dashed size="small" class="item-add" @click="templateForm.agenda.push('')">
              <el-icon><Plus /></el-icon> 添加议题
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="默认参与人">
          <el-select v-model="templateForm.default_participant_ids" name="template-form-participants" multiple filterable collapse-tags collapse-tags-tooltip placeholder="可选" style="width:100%">
            <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTemplateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitTemplate">{{ editingTemplateId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- 实时转写对话框（已废弃，录音机模式无需实时转写） -->

    <!-- 会议纪要对话框 -->
    <el-dialog v-model="showMinutesDialog" title="会议纪要" :width="isMobile ? '90vw' : '600px'" top="5vh">
      <div v-if="currentMeeting" class="minutes-content">
        <h3>{{ currentMeeting.title }}</h3>
        <div class="minutes-time">
          {{ formatDate(currentMeeting.start_time) }}
        </div>

        <div v-if="currentMeeting.summary" class="minutes-section">
          <h4>会议摘要</h4>
          <p>{{ currentMeeting.summary }}</p>
        </div>

        <div v-if="currentMeeting.key_points?.length" class="minutes-section">
          <h4>讨论要点</h4>
          <ul>
            <li v-for="(point, i) in currentMeeting.key_points" :key="i">{{ point }}</li>
          </ul>
        </div>

        <div v-if="currentMeeting.decisions?.length" class="minutes-section">
          <h4>决议事项</h4>
          <ul>
            <li v-for="(decision, i) in currentMeeting.decisions" :key="i">{{ decision }}</li>
          </ul>
        </div>
      </div>
    </el-dialog>

    <!-- 听会对话框 -->
    <el-dialog
      v-model="showLiveCallDialog"
      title="听会"
      :width="isMobile ? '95vw' : '800px'"
      top="3vh"
      :close-on-click-modal="false"
      @close="onLiveCallEnd"
    >
      <MeetingRoom
        v-if="showLiveCallDialog"
        ref="meetingRoomRef"
        @call-ended="onCallEnded"
        style="height: 500px"
      />
    </el-dialog>

    <!-- 粘贴转录分析对话框 -->
    <PasteAnalyzeDialog ref="pasteAnalyzeDialogRef" @saved="fetchMeetings" />

    <!-- 声纹测试对话框 -->
    <VoiceTestDialog v-model:visible="showVoiceTest" />

    <!-- 挂断后会后处理进度对话框 -->
    <ProcessingDialog
      v-if="processingDialogVisible && processingMeetingId"
      :meeting-id="processingMeetingId"
      @close="processingDialogVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatDateTime } from '@/utils/format'
import { getStatusType, getStatusLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import { useUserStore } from '@/stores/user'
import { useMeeting } from '@/composables/useMeeting'
import PasteAnalyzeDialog from '@/components/PasteAnalyzeDialog.vue'
import MeetingRoom from '@/components/MeetingRoom.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'
import VoiceTestDialog from '@/components/VoiceTestDialog.vue'
import { Phone, Edit, Delete, Document, MagicStick, Plus, Microphone, Clock, List } from '@element-plus/icons-vue'

const router = useRouter()
const memberStore = useMemberStore()
const userStore = useUserStore()
const members = computed(() => memberStore.members)

// 使用 composable
const {
  meetings, total, currentPage, pageSize, loading,
  keyword, dateFrom, dateTo, currentMeeting,
  fetchMeetings, createMeeting, updateMeeting, deleteMeeting: deleteMeetingApi
} = useMeeting()

const isMobile = ref(window.innerWidth <= 768)
const showCreateDialog = ref(false)
const showMinutesDialog = ref(false)
const showTranscriptDialog = ref(false)
const liveTranscriptRef = ref(null)
const pasteAnalyzeDialogRef = ref(null)
const meetingRoomRef = ref(null)

// 声纹通话
const showLiveCallDialog = ref(false)
const liveCallMeeting = ref(null)
const showVoiceTest = ref(false)

// 挂断后处理进度弹窗
const processingDialogVisible = ref(false)
const processingMeetingId = ref(null)

function onCallEnded(meetingId) {
  // 关闭听会弹窗，刷新列表
  showLiveCallDialog.value = false
  liveCallMeeting.value = null
  fetchMeetings()
  if (meetingId) {
    router.push(`/meetings/${meetingId}`)
  }
}

// 编辑会议
const editMeeting = (meeting) => {
  meetingForm.value = {
    templateId: null,
    title: meeting.title,
    start_time: meeting.start_time,
    location: meeting.location || '',
    participants: meeting.participants?.map(p => p.member_id) || [],
    description: meeting.description || '',
    summary: meeting.summary || '',
    key_points: meeting.key_points ? [...meeting.key_points] : [],
    decisions: meeting.decisions ? [...meeting.decisions] : [],
    agenda: meeting.agenda ? [...meeting.agenda] : [],
    remindBefore: meeting.remind_before !== false,
  }
  editingMeetingId.value = meeting.id
  showCreateDialog.value = true
}

const editingMeetingId = ref(null)

const deleteMeeting = async (id) => {
  try {
    await deleteMeetingApi(id)
    ElMessage.success('会议已删除')
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 创建/更新会议
const submitMeeting = async () => {
  if (!meetingForm.value.title || !meetingForm.value.start_time) {
    ElMessage.warning('请填写必填项')
    return
  }
  try {
    if (editingMeetingId.value) {
      await updateMeeting(editingMeetingId.value, meetingForm.value)
      ElMessage.success('会议已更新')
    } else {
      await createMeeting(meetingForm.value)
      ElMessage.success('会议创建成功')
    }
    showCreateDialog.value = false
    editingMeetingId.value = null
    meetingForm.value = { templateId: null, title: '', start_time: '', location: '', participants: [], description: '', summary: '', key_points: [], decisions: [], agenda: [], remindBefore: true }
  } catch (e) {
    ElMessage.error(editingMeetingId.value ? '更新失败' : '创建失败')
  }
}

const startLiveCall = () => {
  liveCallMeeting.value = null
  showLiveCallDialog.value = true
}

const meetingForm = ref({
  templateId: null,
  title: '', start_time: '', location: '', participants: [], description: '',
  summary: '', key_points: [], decisions: [],
  agenda: [],  // Wave 3b: 会议议程
  remindBefore: true,
})

// === 2026-06-03 重构：会议模板内嵌到 MeetingView ===
const templates = ref([])
const builtinTemplates = computed(() => templates.value.filter(t => t.is_builtin))
const customTemplates = computed(() => templates.value.filter(t => !t.is_builtin))

async function loadTemplates() {
  try {
    const resp = await axios.get('/api/v1/meeting-templates')
    if (resp.status === 200) templates.value = resp.data
  } catch (e) {
    console.warn('加载会议模板失败', e)
  }
}

// 应用模板：填字段（保留用户已填）+ 提示
function applyTemplate(tpl) {
  if (!tpl) return
  meetingForm.value.templateId = tpl.id
  // 仅在字段为空时填充（用户已填写的优先）
  if (tpl.title_template && !meetingForm.value.title) {
    meetingForm.value.title = tpl.title_template
      .replace('{date}', dayjs().format('YYYY-MM-DD'))
      .replace('{project_name}', '新项目')
  }
  if (tpl.description && !meetingForm.value.description) {
    meetingForm.value.description = tpl.description
  }
  if (tpl.agenda && tpl.agenda.length && (!meetingForm.value.agenda || meetingForm.value.agenda.length === 0)) {
    meetingForm.value.agenda = [...tpl.agenda]
  }
  if (tpl.default_participant_ids && tpl.default_participant_ids.length && (!meetingForm.value.participants || meetingForm.value.participants.length === 0)) {
    meetingForm.value.participants = [...tpl.default_participant_ids]
  }
  if (tpl.default_location && !meetingForm.value.location) {
    meetingForm.value.location = tpl.default_location
  }
  ElMessage.success(`已应用模板：${tpl.name}`)
}

// === 模板 CRUD（行内） ===
const showTemplateDialog = ref(false)
const editingTemplateId = ref(null)
const templateForm = ref({
  name: '',
  description: '',
  title_template: '',
  default_duration_minutes: 60,
  default_location: '',
  default_participant_ids: [],
  agenda: [],
})

function resetTemplateForm() {
  templateForm.value = {
    name: '',
    description: '',
    title_template: '',
    default_duration_minutes: 60,
    default_location: '',
    default_participant_ids: [],
    agenda: [],
  }
  editingTemplateId.value = null
}

function showTemplateForm(tpl = null) {
  if (tpl) {
    // 编辑模式
    editingTemplateId.value = tpl.id
    templateForm.value = {
      name: tpl.name || '',
      description: tpl.description || '',
      title_template: tpl.title_template || '',
      default_duration_minutes: tpl.default_duration_minutes || 60,
      default_location: tpl.default_location || '',
      default_participant_ids: tpl.default_participant_ids || [],
      agenda: tpl.agenda ? [...tpl.agenda] : [],
    }
  } else {
    // 新建模式
    resetTemplateForm()
  }
  showTemplateDialog.value = true
}

async function submitTemplate() {
  if (!templateForm.value.name?.trim()) {
    ElMessage.error('请填写模板名称')
    return
  }
  try {
    const payload = { ...templateForm.value }
    if (editingTemplateId.value) {
      await axios.put(`/api/v1/meeting-templates/${editingTemplateId.value}`, payload)
      ElMessage.success('模板已更新')
    } else {
      await axios.post('/api/v1/meeting-templates', payload)
      ElMessage.success('模板已创建')
    }
    showTemplateDialog.value = false
    await loadTemplates()
  } catch (e) {
    ElMessage.error(`保存失败：${e.response?.data?.detail || e.message}`)
  }
}

async function deleteTemplate(tpl) {
  try {
    await ElMessageBox.confirm(`删除自定义模板 "${tpl.name}"？`, '确认', { type: 'warning' })
  } catch { return }
  try {
    await axios.delete(`/api/v1/meeting-templates/${tpl.id}`)
    ElMessage.success('已删除')
    if (meetingForm.value.templateId === tpl.id) meetingForm.value.templateId = null
    await loadTemplates()
  } catch (e) {
    ElMessage.error(`删除失败：${e.response?.data?.detail || e.message}`)
  }
}

// 关闭会议创建对话框时清理 templateId 高亮
function onCreateDialogClose() {
  editingMeetingId.value = null
  meetingForm.value.templateId = null
}

// 获取成员列表（使用 store）
const fetchMembers = () => memberStore.fetchMembers()

// 查看会议详情 → 跳转全屏详情页
const viewMeeting = (meeting) => {
  router.push(`/meetings/${meeting.id}`)
}

// 查看纪要
const viewMinutes = (meeting) => {
  currentMeeting.value = meeting
  showMinutesDialog.value = true
}

// 开始实时转写
const startTranscript = (meeting) => {
  currentMeeting.value = meeting
  showTranscriptDialog.value = true
}

// 转写完成回调
const onTranscriptComplete = async (transcriptItems) => {
  console.log('转写完成，共', transcriptItems.length, '条记录')
  ElMessage.success(`转写完成，共 ${transcriptItems.length} 条记录`)
  showTranscriptDialog.value = false
  fetchMeetings()
}

// 生成纪要
const generateMinutes = async (meeting) => {
  try {
    ElMessage.info('正在生成会议纪要...')
    await axios.post(`/api/v1/meetings/${meeting.id}/generate-minutes`)
    ElMessage.success('会议纪要生成成功')
    fetchMeetings()
  } catch (e) {
    ElMessage.error('生成失败')
  }
}

// 辅助函数
const formatMonth = (date) => dayjs(date).format('M月')
const formatDay = (date) => dayjs(date).format('D')
const formatHour = (date) => dayjs(date).format('HH:mm')
const formatDate = (date) => formatDateTime(date)

onMounted(() => {
  fetchMeetings()
  fetchMembers()
  loadTemplates()  // Wave 3b
})
</script>

<style scoped>
.meeting-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow: hidden;
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.filter-card {
  flex-shrink: 0;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.filter-card :deep(.el-card__body) {
  padding: var(--space-4) var(--space-5);
}

.top-actions { display: flex; gap: 8px; flex-wrap: wrap; }

/* 2026-06-02 原生 date input 样式（绕过 el-date-picker 内部 input 缺 name 的 a11y 警告） */
.native-date-input {
  width: 100%;
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

.meeting-list-card {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) 80ms both;
}

.meeting-list-card :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.meeting-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.meeting-item {
  display: flex;
  gap: var(--space-5);
  padding: var(--space-4);
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.meeting-item:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
  transform: translateY(-2px);
}

.meeting-time-block {
  min-width: 80px;
  text-align: center;
  padding: var(--space-2);
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
}

.time-month {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.time-day {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-primary);
  line-height: 1.2;
}

.time-hour {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
}

.meeting-info {
  flex: 1;
}

.meeting-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.meeting-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.meeting-location {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.meeting-summary {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  line-height: 1.5;
}

.meeting-actions {
  display: flex;
  flex-direction: row;
  gap: 6px;
  align-items: center;
  flex-shrink: 0;
}

.action-btn {
  width: 34px !important;
  height: 34px !important;
  padding: 0 !important;
  border: 1.5px solid var(--color-border) !important;
  background: #fff !important;
  transition: all 0.2s ease !important;
}
.action-btn:hover {
  transform: translateY(-1px);
}
.action-phone { color: var(--color-primary) !important; border-color: rgba(255,122,92,0.3) !important; }
.action-phone:hover { background: var(--color-primary) !important; color: #fff !important; border-color: var(--color-primary) !important; box-shadow: 0 2px 8px rgba(255,122,92,0.3); }

.action-view { color: #409EFF !important; border-color: rgba(64,158,255,0.3) !important; }
.action-view:hover { background: #409EFF !important; color: #fff !important; border-color: #409EFF !important; box-shadow: 0 2px 8px rgba(64,158,255,0.3); }

.action-generate { color: #67C23A !important; border-color: rgba(103,194,58,0.3) !important; }
.action-generate:hover { background: #67C23A !important; color: #fff !important; border-color: #67C23A !important; box-shadow: 0 2px 8px rgba(103,194,58,0.3); }

.action-edit { color: #909399 !important; border-color: rgba(144,147,153,0.3) !important; }
.action-edit:hover { background: #909399 !important; color: #fff !important; border-color: #909399 !important; box-shadow: 0 2px 8px rgba(144,147,153,0.3); }

.action-delete { color: #F56C6C !important; border-color: rgba(245,108,108,0.3) !important; }
.action-delete:hover { background: #F56C6C !important; color: #fff !important; border-color: #F56C6C !important; box-shadow: 0 2px 8px rgba(245,108,108,0.3); }

/* 纪要编辑列表 */
.minutes-textarea :deep(.el-textarea__inner) { border-radius: var(--radius-md); border-color: var(--color-border); }
.item-list { display: flex; flex-direction: column; gap: 8px; }
.item-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; background: var(--color-bg-page); border-radius: var(--radius-md);
  border: 1px solid transparent; transition: all 0.2s;
}
.item-row:hover, .item-row:focus-within {
  border-color: var(--color-primary-border); background: var(--color-primary-bg);
}
.item-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: var(--color-primary);
}
.decision-dot { background: var(--color-warning); }
.item-row .el-input { flex: 1; }
.item-del { opacity: 0; transition: opacity 0.2s; }
.item-row:hover .item-del { opacity: 1; }
.item-add { width: 100%; justify-content: center; border-style: dashed; }
.decision-add { color: var(--color-warning); border-color: var(--color-warning); }

/* 2026-06-03 新增：模板卡片选择器样式（替代独立 MeetingTemplatesView） */
.template-picker {
  background: var(--color-bg-page, #fafafa);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}
.template-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.template-picker-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}
.template-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}
.template-card {
  border: 1px solid var(--color-border, #e4e7ed);
  border-radius: 6px;
  padding: 10px 12px;
  background: white;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}
.template-card:hover {
  border-color: var(--color-primary, #FF7A5C);
  box-shadow: 0 2px 8px rgba(255, 122, 92, 0.12);
  transform: translateY(-1px);
}
.template-card.active {
  border-color: var(--color-primary, #FF7A5C);
  background: linear-gradient(135deg, rgba(255, 122, 92, 0.04), rgba(255, 179, 71, 0.04));
  box-shadow: 0 2px 8px rgba(255, 122, 92, 0.18);
}
.template-card-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: space-between;
}
.template-card-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.template-card-meta {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: var(--color-text-placeholder);
}
.template-card-meta span {
  display: flex;
  align-items: center;
  gap: 2px;
}
.template-card-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.template-card.custom:hover .template-card-actions { opacity: 1; }
.tpl-action {
  cursor: pointer;
  padding: 2px;
  border-radius: 3px;
  color: var(--color-text-secondary);
}
.tpl-action:hover { background: var(--color-bg-page, #fafafa); }
.tpl-action.danger { color: var(--color-danger); }
.template-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--color-text-placeholder);
  font-size: 12px;
  padding: 16px 0;
}
.form-hint {
  font-size: 11px;
  color: var(--color-text-placeholder);
  margin-left: 8px;
}

@media (max-width: 768px) {
  .meeting-actions { flex-wrap: wrap; }
}

.pagination {
  flex-shrink: 0;
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
  display: flex;
  justify-content: flex-end;
}

.minutes-content h3 {
  margin-bottom: var(--space-2);
}

.minutes-time {
  color: var(--color-text-secondary);
  margin-bottom: var(--space-5);
}

.minutes-section {
  margin-bottom: var(--space-5);
}

.minutes-section h4 {
  margin-bottom: var(--space-2);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-semibold);
}

.minutes-section ul {
  padding-left: var(--space-5);
}

.minutes-section li {
  margin-bottom: var(--space-2);
  line-height: 1.5;
  color: var(--color-text-regular);
}

.transcript-dialog-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.meeting-info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.meeting-info-bar h3 {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}

@media (max-width: 768px) {
  .meeting-item {
    flex-direction: column;
    gap: var(--space-3);
  }
  .meeting-time-block {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: unset;
  }
  .meeting-actions {
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
