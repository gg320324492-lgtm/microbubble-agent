<template>
  <el-dialog
    v-model="visible"
    :title="editingId ? '编辑会议' : '创建会议'"
    :width="isMobile ? '90vw' : '560px'"
    top="6vh"
    @close="onClose"
  >
    <el-form :model="form" label-width="80px">
      <!-- 模板选择（仅创建模式） -->
      <div v-if="!editingId" class="template-picker">
        <div class="template-picker-header">
          <span class="template-picker-title">
            <el-icon><Document /></el-icon> 快速模板
          </span>
        </div>
        <div class="template-cards">
          <div
            v-for="tpl in builtinTemplates"
            :key="tpl.id"
            class="template-card builtin"
            :class="{ active: form.templateId === tpl.id, disabled: !tpl.is_active }"
            @click="tpl.is_active && applyTemplate(tpl)"
          >
            <!-- v77 P2.6-F.5: builtin 卡片 hover 复制按钮 (CSS 已就绪 + builtin trigger 规则) -->
            <div class="template-card-actions">
              <el-icon
                class="tpl-action"
                title="复制为自定义模板"
                aria-label="复制为自定义模板"
                @click.stop="$emit('clone-template', tpl.id)"
              >
                <DocumentCopy />
              </el-icon>
            </div>
            <div class="template-card-name">{{ tpl.name }}<el-tag size="small" type="info" effect="plain">内置</el-tag></div>
            <div class="template-card-desc">{{ tpl.description || '—' }}</div>
            <div class="template-card-meta">
              <span><el-icon><Clock /></el-icon> {{ tpl.default_duration_minutes || 60 }} 分钟</span>
              <span v-if="tpl.agenda?.length"><el-icon><List /></el-icon> {{ tpl.agenda.length }} 议题</span>
            </div>
            <!-- v77 P2.6-F.5: builtin 卡片右侧 el-switch 启用/禁用 -->
            <el-switch
              :model-value="tpl.is_active"
              class="builtin-active-switch"
              inline-prompt
              active-text="启用"
              inactive-text="禁用"
              @click.stop
              @update:model-value="(val) => $emit('toggle-active', { id: tpl.id, is_active: val })"
            />
          </div>
          <div
            v-for="tpl in customTemplates"
            :key="tpl.id"
            class="template-card custom"
            :class="{ active: form.templateId === tpl.id }"
            @click="applyTemplate(tpl)"
          >
            <!-- v77 P2.6-F.4: hover-reveal 编辑/删除按钮 (meeting-view.css:304-318 CSS 已就绪) -->
            <div class="template-card-actions">
              <!-- 编辑: 复用 save-template emit,MeetingView.onSaveAsTemplate 走编辑模式 -->
              <el-icon
                class="tpl-action"
                title="编辑模板"
                aria-label="编辑模板"
                @click.stop="onEditTpl(tpl)"
              >
                <Edit />
              </el-icon>
              <!-- 删除: el-popconfirm 二次确认 (参考 MeetingView.vue:112-118 模式) -->
              <el-popconfirm
                title="确定删除此模板？此操作不可撤销。"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="$emit('delete-template', tpl.id)"
              >
                <template #reference>
                  <el-icon
                    class="tpl-action danger"
                    title="删除模板"
                    aria-label="删除模板"
                    @click.stop
                  >
                    <Delete />
                  </el-icon>
                </template>
              </el-popconfirm>
            </div>
            <div class="template-card-name">{{ tpl.name }}</div>
            <div class="template-card-desc">{{ tpl.description || '（无说明）' }}</div>
            <div class="template-card-meta">
              <span><el-icon><Clock /></el-icon> {{ tpl.default_duration_minutes || 60 }} 分钟</span>
              <span v-if="tpl.agenda?.length"><el-icon><List /></el-icon> {{ tpl.agenda.length }} 议题</span>
            </div>
          </div>
          <div v-if="customTemplates.length === 0" class="template-empty">
            暂无自定义模板
          </div>
        </div>
      </div>

      <!-- 基本信息 -->
      <el-form-item label="会议主题" required>
        <el-input v-model="form.title" placeholder="请输入会议主题" />
      </el-form-item>
      <el-form-item label="会议时间" required>
        <el-date-picker
          v-model="form.start_time"
          type="datetime"
          format="YYYY-MM-DD HH:mm"
          value-format="YYYY-MM-DD HH:mm:ss"
          placeholder="选择会议时间"
          style="width: 100%"
          :clearable="false"
        />
      </el-form-item>
      <el-form-item label="会议地点">
        <el-input v-model="form.location" placeholder="请输入会议地点" />
      </el-form-item>
      <el-form-item label="参会人员">
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <el-select v-model="form.participants" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择参会人员" style="flex:1;min-width:200px">
            <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
          </el-select>
          <el-button size="small" @click="form.participants = members.map(m=>m.id)">全选</el-button>
        </div>
      </el-form-item>
      <el-form-item label="会议说明">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入会议说明" />
      </el-form-item>
      <el-form-item label="议程">
        <div class="item-list" style="width:100%">
          <div v-for="(item, idx) in form.agenda" :key="idx" class="item-row">
            <span class="item-dot" />
            <el-input v-model="form.agenda[idx]" placeholder="议题描述" />
            <el-button :icon="Delete" circle size="small" class="item-del" @click="form.agenda.splice(idx, 1)" />
          </div>
          <el-button dashed size="small" class="item-add" @click="form.agenda.push('')">
            <el-icon><Plus /></el-icon> 添加议题
          </el-button>
        </div>
      </el-form-item>
      <el-form-item label="提前提醒">
        <el-checkbox v-model="form.remindBefore">会议前 5 分钟企业微信提醒</el-checkbox>
      </el-form-item>

      <!-- 编辑模式：纪要字段 -->
      <template v-if="editingId">
        <el-divider content-position="left">
          <el-icon><Document /></el-icon> 会议纪要
        </el-divider>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" :rows="3" placeholder="会议摘要..." />
        </el-form-item>
        <el-form-item label="讨论要点">
          <div class="item-list">
            <div v-for="(point, i) in form.key_points" :key="'kp'+i" class="item-row">
              <span class="item-dot" />
              <el-input v-model="form.key_points[i]" placeholder="输入要点..." />
              <el-button :icon="Delete" circle size="small" class="item-del" @click="form.key_points.splice(i, 1)" />
            </div>
            <el-button dashed size="small" class="item-add" @click="form.key_points.push('')">
              <el-icon><Plus /></el-icon> 添加要点
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="决议事项">
          <div class="item-list">
            <div v-for="(d, i) in form.decisions" :key="'dc'+i" class="item-row decision">
              <span class="item-dot decision-dot" />
              <el-input v-model="form.decisions[i]" placeholder="输入决议..." />
              <el-button :icon="Delete" circle size="small" class="item-del" @click="form.decisions.splice(i, 1)" />
            </div>
            <el-button dashed size="small" class="item-add decision-add" @click="form.decisions.push('')">
              <el-icon><Plus /></el-icon> 添加决议
            </el-button>
          </div>
        </el-form-item>
      </template>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <!-- v77 P2.6-F.3: '存为新模板' 按钮 - 仅在新建模式显示 -->
      <el-button
        v-if="!editingId"
        type="warning"
        plain
        @click="onSaveAsTemplate"
        title="将当前表单保存为模板, 下次可快速套用"
      >
        <el-icon><Document /></el-icon>
        存为新模板
      </el-button>
      <el-button type="primary" @click="onSubmit">{{ editingId ? '保存' : '创建' }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Clock, List, Plus, Delete, Edit, DocumentCopy } from '@element-plus/icons-vue'
import { useMeeting } from '@/composables/useMeeting'
import { useMemberStore } from '@/stores/member'
import dayjs from 'dayjs'

const props = defineProps({
  isMobile: { type: Boolean, default: false },
  editingId: { type: Number, default: null },
  editingData: { type: Object, default: null },
  templates: { type: Array, default: () => [] }
})

const emit = defineEmits(['success', 'save-template', 'delete-template', 'clone-template', 'toggle-active'])

const visible = defineModel('visible', { default: false })
const { createMeeting, updateMeeting } = useMeeting()
const memberStore = useMemberStore()
const members = computed(() => memberStore.members)

const builtinTemplates = computed(() => props.templates.filter(t => t.is_builtin))
const customTemplates = computed(() => props.templates.filter(t => !t.is_builtin))

const defaultForm = {
  templateId: null,
  title: '',
  start_time: '',
  location: '',
  participants: [],
  description: '',
  summary: '',
  key_points: [],
  decisions: [],
  agenda: [],
  remindBefore: true
}

const form = ref({ ...defaultForm })

// 编辑模式：填充数据
watch(() => props.editingData, (data) => {
  if (data) {
    form.value = {
      templateId: null,
      title: data.title || '',
      start_time: data.start_time || '',
      location: data.location || '',
      participants: data.participants?.map(p => p.member_id) || [],
      description: data.description || '',
      summary: data.summary || '',
      key_points: data.key_points ? [...data.key_points] : [],
      decisions: data.decisions ? [...data.decisions] : [],
      agenda: data.agenda ? [...data.agenda] : [],
      remindBefore: data.remind_before !== false
    }
  }
}, { immediate: true })

const applyTemplate = (tpl) => {
  if (!tpl) return
  form.value.templateId = tpl.id
  if (tpl.title_template && !form.value.title) {
    form.value.title = tpl.title_template
      .replace('{date}', dayjs().format('YYYY-MM-DD'))
      .replace('{project_name}', '新项目')
  }
  if (tpl.description && !form.value.description) {
    form.value.description = tpl.description
  }
  if (tpl.agenda && tpl.agenda.length && (!form.value.agenda || form.value.agenda.length === 0)) {
    form.value.agenda = [...tpl.agenda]
  }
  if (tpl.default_participant_ids && tpl.default_participant_ids.length && (!form.value.participants || form.value.participants.length === 0)) {
    form.value.participants = [...tpl.default_participant_ids]
  }
  if (tpl.default_location && !form.value.location) {
    form.value.location = tpl.default_location
  }
  ElMessage.success(`已应用模板：${tpl.name}`)
}

const onSubmit = async () => {
  if (!form.value.title || !form.value.start_time) {
    ElMessage.warning('请填写必填项')
    return
  }
  try {
    if (props.editingId) {
      await updateMeeting(props.editingId, form.value)
      ElMessage.success('会议已更新')
    } else {
      await createMeeting(form.value)
      ElMessage.success('会议创建成功')
    }
    visible.value = false
    emit('success')
  } catch (e) {
    ElMessage.error(props.editingId ? '更新失败' : '创建失败')
  }
}

// v77 P2.6-F.3: '存为新模板' 按钮处理
// 将当前 form 数据转换为 MeetingTemplateDialog editingTemplate 格式, emit 'save-template'
// 父 MeetingView 接收后打开 MeetingTemplateDialog (editingTemplate = templateData, 走编辑模式)
const onSaveAsTemplate = () => {
  // 双重防御: v-if !editingId 在 UI 层隐藏按钮, 函数层再检查一次
  // 防止程序化调用 (如 console / 测试 / 快捷键) 在编辑模式下意外触发
  if (props.editingId) {
    ElMessage.warning('编辑模式下不能保存为模板')
    return
  }
  if (!form.value.title?.trim()) {
    ElMessage.warning('请先填写会议主题, 再保存为模板')
    return
  }
  const templateData = {
    name: form.value.title,           // 用会议主题做模板名
    title_template: form.value.title,  // 标题模板 (简单复用)
    description: form.value.description || '',
    default_duration_minutes: 60,     // 默认 60 分钟 (MeetingCreateDialog 无此字段)
    default_location: form.value.location || '',
    default_participant_ids: form.value.participants || [],
    agenda: (form.value.agenda || []).filter(a => a?.trim()),
  }
  emit('save-template', templateData)
  // 不关闭 dialog — 让用户在 MeetingTemplateDialog 中继续编辑/提交
  // 父组件接 event 后会:
  //   1. 关闭 MeetingCreateDialog (showCreateDialog = false)
  //   2. 打开 MeetingTemplateDialog (showTemplateDialog = true, editingTemplate = templateData)
}

// v77 P2.6-F.4: 编辑已有的 custom template
// 复用 P2.6-F.3 的 save-template emit — id 字段让 MeetingTemplateDialog 走 PUT 而非 POST (line 156)
const onEditTpl = (tpl) => {
  if (!tpl) return
  emit('save-template', {
    id: tpl.id,                                              // 关键: 走 PUT path
    name: tpl.name,
    title_template: tpl.title_template,
    description: tpl.description,
    default_duration_minutes: tpl.default_duration_minutes,
    default_location: tpl.default_location,
    default_participant_ids: tpl.default_participant_ids ? [...tpl.default_participant_ids] : [],
    agenda: tpl.agenda ? [...tpl.agenda] : [],
  })
}

const onClose = () => {
  form.value = { ...defaultForm }
}
</script>

<style scoped>
.template-picker {
  margin-bottom: 16px;
}
.template-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.template-picker-title {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 4px;
}
.template-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.template-card {
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition-all-normal);
  min-width: 120px;
}
.template-card:hover {
  border-color: var(--color-primary);
}
.template-card.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}
.template-card-name {
  font-weight: 600;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.template-card-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 4px 0;
}
.template-card-meta {
  font-size: 11px;
  color: var(--color-text-secondary);
  display: flex;
  gap: 8px;
}
.template-empty {
  font-size: 12px;
  color: var(--color-text-secondary);
  padding: 8px;
}
.item-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.item-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}
.item-dot.decision-dot {
  background: var(--color-success);
}
.item-del {
  flex-shrink: 0;
}
.item-add {
  margin-top: 4px;
}
</style>
