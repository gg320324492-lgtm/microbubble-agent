<!--
  RenameDialog.vue — 课题组网盘 PR3.4 通用重命名对话框
  2026-07-01

  复用场景:
  - 文件重命名 (file title)
  - 文件夹重命名 (folder name)

  字段:
  - name (必填, 1-200 字符)
  - targetType (file / folder, 用于显示不同 icon)
-->
<template>
  <el-dialog
    v-model="visible"
    class="drive-dialog"
    :title="dialogTitle"
    width="420px"
    :close-on-click-modal="false"
    @closed="resetForm"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item :label="nameLabel" prop="name">
        <el-input
          v-model="form.name"
          :placeholder="placeholder"
          maxlength="200"
          show-word-limit
          autofocus
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-dialog 玻璃态生效
import '@/views/drive/drive-view.css'
import { ref, reactive, computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  target: { type: [Object, null], default: null },
  targetType: { type: String, default: 'file' }  // file | folder
})

const emit = defineEmits(['update:modelValue', 'rename'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const formRef = ref(null)
const submitting = ref(false)
const form = reactive({
  name: ''
})

const dialogTitle = computed(() => `重命名${props.targetType === 'folder' ? '文件夹' : '文件'}`)
const nameLabel = computed(() => props.targetType === 'folder' ? '文件夹名' : '文件名')
const placeholder = computed(() => `请输入${nameLabel.value}`)

const rules = {
  name: [
    { required: true, message: '名称不能为空', trigger: 'blur' },
    { min: 1, max: 200, message: '长度 1-200 字符', trigger: 'blur' }
  ]
}

function resetForm() {
  form.name = ''
  formRef.value?.clearValidate()
}

async function onSubmit() {
  try {
    await formRef.value.validate()
    submitting.value = true
    const oldName = props.targetType === 'folder' ? props.target?.name : (props.target?.title || props.target?.file_name)
    emit('rename', {
      id: props.target?.id,
      type: props.targetType,
      oldName,
      newName: form.name.trim()
    })
  } catch (e) {
    // validate 失败
  } finally {
    submitting.value = false
  }
}

// 当 target 变化时, 同步到 form.name (打开 dialog 前由父组件触发)
function syncFromTarget() {
  if (props.target) {
    form.name = props.targetType === 'folder'
      ? props.target.name || ''
      : props.target.title || props.target.file_name || ''
  }
}

defineExpose({ resetForm, syncFromTarget })
</script>

<style scoped>
/* v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块 */
</style>