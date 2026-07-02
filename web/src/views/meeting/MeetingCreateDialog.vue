<template>
  <el-dialog
    v-model="visible"
    :title="editingId ? '编辑会议' : '创建会议'"
    :width="isMobile ? '90vw' : '560px'"
    top="6vh"
    @close="onClose"
  >
    <el-form :model="form" label-width="80px">
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
      <el-button type="primary" @click="onSubmit">{{ editingId ? '保存' : '创建' }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * MeetingCreateDialog.vue — 创建/编辑会议对话框
 *
 * 2026-07-03: 模板管理 (template-picker / save-template / clone-template / delete-template /
 *            toggle-active / builtin + custom 模板卡 / LongPress / MobileActionSheet) 已彻底删除.
 *            用户决策"模板管理没用" - 前后端 + UI 全部清空, 只剩创建/编辑会议核心表单.
 */
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Plus, Delete } from '@element-plus/icons-vue'
import { useMeeting } from '@/composables/useMeeting'
import { useMemberStore } from '@/stores/member'

const props = defineProps({
  isMobile: { type: Boolean, default: false },
  editingId: { type: Number, default: null },
  editingData: { type: Object, default: null },
})

const emit = defineEmits(['success'])

const visible = defineModel('visible', { default: false })
const { createMeeting, updateMeeting } = useMeeting()
const memberStore = useMemberStore()
const members = computed(() => memberStore.members)

const defaultForm = {
  templateId: null,  // 兼容旧数据保留, 不再写入
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

// 2026-07-03 修复 TDZ: form 必须在 watch 之前声明 (immediate: true 同步触发 callback)
// 编辑模式：填充数据
const form = ref({ ...defaultForm })
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

const onClose = () => {
  form.value = { ...defaultForm }
}
</script>

<style scoped>
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