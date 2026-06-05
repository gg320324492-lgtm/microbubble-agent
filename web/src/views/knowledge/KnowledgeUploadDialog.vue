<template>
  <el-dialog
    v-model="visible"
    title="上传文件到知识库"
    :width="isMobile ? '90vw' : '500px'"
    top="10vh"
    destroy-on-close
  >
    <div class="upload-ai-notice">
      <el-icon size="16" color="#409eff"><MagicStick /></el-icon>
      <span>上传后 AI 将自动分析内容，生成摘要、分类、标签和知识关联</span>
    </div>
    <el-form label-width="80px">
      <el-form-item label="标题">
        <el-input v-model="title" placeholder="留空则使用文件名" />
      </el-form-item>
    </el-form>
    <el-upload
      ref="uploadRef"
      drag
      :auto-upload="false"
      :limit="1"
      accept=".pdf,.docx,.xlsx,.pptx,.txt,.md"
      :on-change="onFileChange"
      :on-exceed="() => ElMessage.warning('只能上传一个文件')"
    >
      <el-icon class="el-icon--upload"><Upload /></el-icon>
      <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
      <template #tip>
        <div class="el-upload__tip">支持 PDF、Word(.docx)、Excel(.xlsx)、TXT、Markdown，最大 50MB</div>
      </template>
    </el-upload>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="uploading" @click="onUpload">
        {{ uploading ? '分析中...' : '上传' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Upload } from '@element-plus/icons-vue'
import axios from 'axios'

const props = defineProps({
  isMobile: { type: Boolean, default: false }
})

const emit = defineEmits(['success'])

const visible = defineModel('visible', { default: false })

const title = ref('')
const file = ref(null)
const uploading = ref(false)
const uploadRef = ref(null)

const onFileChange = (f) => {
  file.value = f.raw
}

const onUpload = async () => {
  if (!file.value) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    if (title.value) formData.append('title', title.value)

    await axios.post('/api/v1/knowledge/upload', formData, { timeout: 180000 })
    ElMessage.success('文件上传成功，后台正在分析...')
    visible.value = false
    title.value = ''
    file.value = null
    if (uploadRef.value) uploadRef.value.clearFiles()
    emit('success')
  } catch (e) {
    if (e.code === 'ECONNABORTED') {
      ElMessage.error('上传超时，请检查网络或尝试更小的文件')
    } else if (!e.response) {
      ElMessage.error('网络连接失败，请检查网络后重试')
    } else {
      const detail = e.response?.data?.detail
      if (Array.isArray(detail)) {
        ElMessage.error(detail.map(d => d.msg || JSON.stringify(d)).join('; '))
      } else if (typeof detail === 'string') {
        ElMessage.error(detail)
      } else if (typeof e.response?.data === 'string') {
        ElMessage.error('服务器错误，请稍后重试')
      } else {
        ElMessage.error('上传失败')
      }
    }
  } finally {
    uploading.value = false
  }
}
</script>
