<!--
  CreateFolderDialog.vue — 课题组网盘 PR3.4 新建文件夹对话框
  2026-07-01

  字段:
  - name (必填, 1-200 字符)
  - visibility (private / team / public, 默认 team)
  - parentId (从父组件传入, 顶级 null)

  校验:
  - name 必填, 长度 1-200
  - visibility 三选一 (后端 service 已校验 inherited)

  提交:
  - emit('create', { name, parent_id, visibility })
  - 父组件 (DesktopDriveView) 调 useFolderTree.createFolder
-->
<template>
  <el-dialog
    v-model="visible"
    title="新建文件夹"
    width="420px"
    :close-on-click-modal="false"
    @closed="resetForm"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="名称" prop="name">
        <el-input
          v-model="form.name"
          placeholder="请输入文件夹名称"
          maxlength="200"
          show-word-limit
          autofocus
        />
      </el-form-item>

      <el-form-item label="可见性" prop="visibility">
        <el-radio-group v-model="form.visibility">
          <el-radio value="private">
            🔒 私有 <span class="visibility-hint">(仅自己可见)</span>
          </el-radio>
          <el-radio value="team">
            👥 团队 <span class="visibility-hint">(全员可见)</span>
          </el-radio>
          <el-radio value="public">
            🌐 公开 <span class="visibility-hint">(含外部分享链接)</span>
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="parentFolder" label="父文件夹">
        <span class="parent-folder-path">
          📁 {{ parentFolder.name }} (depth={{ parentFolder.depth }})
        </span>
        <span v-if="parentFolder.depth >= 4" class="parent-folder-warning">
          ⚠️ 已是 5 层, 此文件夹内不能再新建子文件夹
        </span>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  parentId: { type: [Number, null], default: null },
  parentFolder: { type: [Object, null], default: null }
})

const emit = defineEmits(['update:modelValue', 'create'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const formRef = ref(null)
const submitting = ref(false)
const form = reactive({
  name: '',
  visibility: 'team'
})

const rules = {
  name: [
    { required: true, message: '请输入文件夹名称', trigger: 'blur' },
    { min: 1, max: 200, message: '长度 1-200 字符', trigger: 'blur' }
  ],
  visibility: [
    { required: true, message: '请选择可见性', trigger: 'change' }
  ]
}

function resetForm() {
  form.name = ''
  form.visibility = 'team'
  formRef.value?.clearValidate()
}

async function onSubmit() {
  try {
    await formRef.value.validate()
    submitting.value = true
    emit('create', {
      name: form.name.trim(),
      parent_id: props.parentId,
      visibility: form.visibility
    })
    // 父组件成功后会关闭 dialog (visible=false)
  } catch (e) {
    // validate 失败时 formRef.validate 抛错, 不需处理
  } finally {
    submitting.value = false
  }
}

defineExpose({ resetForm })
</script>

<style scoped>
.visibility-hint {
  font-size: 11px;
  color: var(--color-text-secondary, #909399);
  margin-left: 4px;
}

.parent-folder-path {
  font-size: 13px;
  color: var(--color-text-primary, #303133);
}

.parent-folder-warning {
  display: block;
  font-size: 12px;
  color: var(--color-warning, #e6a23c);
  margin-top: 4px;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->