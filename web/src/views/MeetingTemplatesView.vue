<template>
  <div class="templates-view">
    <h2>会议模板</h2>
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header><span>内置模板（只读）</span></template>
          <div v-for="t in builtin" :key="t.id" class="tpl-item">
            <h4>{{ t.name }} <el-tag v-if="t.is_builtin" size="small" type="info">内置</el-tag></h4>
            <p class="tpl-desc">{{ t.description }}</p>
            <div class="tpl-meta">
              <el-tag size="small">{{ t.default_duration_minutes || 60 }} 分钟</el-tag>
              <el-tag v-if="t.agenda && t.agenda.length" size="small" type="success">
                {{ t.agenda.length }} 个议题
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>我的模板</span>
              <el-button type="primary" size="small" @click="onCreateCustom">+ 新建</el-button>
            </div>
          </template>
          <div v-for="t in custom" :key="t.id" class="tpl-item">
            <h4>{{ t.name }}</h4>
            <p class="tpl-desc">{{ t.description || '（无说明）' }}</p>
            <div class="tpl-meta">
              <el-tag size="small">{{ t.default_duration_minutes || 60 }} 分钟</el-tag>
              <el-button size="small" link @click="onEdit(t)">编辑</el-button>
              <el-button size="small" link type="danger" @click="onDelete(t)">删除</el-button>
            </div>
          </div>
          <el-empty v-if="custom.length === 0" description="还没有自定义模板" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const templates = ref([])

const builtin = computed(() => templates.value.filter(t => t.is_builtin))
const custom = computed(() => templates.value.filter(t => !t.is_builtin))

async function load() {
  const resp = await axios.get('/api/v1/meeting-templates')
  if (resp.status === 200) templates.value = resp.data
}

async function onCreateCustom() {
  try {
    const { value } = await ElMessageBox.prompt('请输入模板名', '新建模板', { confirmButtonText: '下一步' })
    const resp = await axios.post('/api/v1/meeting-templates', { name: value })
    if (resp.status === 201) {
      ElMessage.success('已创建')
      await load()
    }
  } catch (e) { /* 用户取消 */ }
}

async function onEdit(t) {
  ElMessageBox.alert('编辑功能见后续 PR', '编辑 ' + t.name)
}

async function onDelete(t) {
  try {
    await ElMessageBox.confirm(`删除模板 "${t.name}"？`, '确认', { type: 'warning' })
  } catch { return }
  await axios.delete(`/api/v1/meeting-templates/${t.id}`)
  await load()
}

onMounted(load)
</script>

<style scoped>
.templates-view { padding: 24px; }
.tpl-item { padding: 12px 0; border-bottom: 1px solid #eee; }
.tpl-item:last-child { border-bottom: none; }
.tpl-desc { color: #666; font-size: 13px; margin: 4px 0; }
.tpl-meta { display: flex; gap: 6px; align-items: center; }
</style>
