<!--
  KnowledgeUploadDialog.vue — v2 PR3 双模上传
  2026-07-01

  顶部 tabs: "入知识库 (kb)" | "入网盘 (drive)"
  - kb 模式: 老逻辑, 调 POST /knowledge/upload (触发 LLM 提取 + 多模态 OCR)
  - drive 模式: 调 POST /drive/files/upload (folder_id + visibility 表单)
-->
<template>
  <el-dialog
    v-model="visible"
    :title="isDriveMode ? '上传到网盘' : '上传文件到知识库'"
    :width="isMobile ? '90vw' : '500px'"
    top="10vh"
    destroy-on-close
  >
    <!-- v2 PR3 双模 tabs -->
    <el-tabs v-model="activeTab" class="upload-mode-tabs">
      <el-tab-pane label="入知识库 (kb)" name="kb">
        <template #label>
          <span class="tab-label">
            <el-icon><MagicStick /></el-icon>
            <span>入知识库</span>
          </span>
        </template>
      </el-tab-pane>
      <el-tab-pane label="入网盘 (drive)" name="drive">
        <template #label>
          <span class="tab-label">
            <el-icon><Folder /></el-icon>
            <span>入网盘</span>
          </span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- KB 模式: AI 自动分析提示 -->
    <div v-if="!isDriveMode" class="upload-ai-notice">
      <el-icon size="16" color="#409eff"><MagicStick /></el-icon>
      <span>上传后 AI 将自动分析内容，生成摘要、分类、标签和知识关联</span>
    </div>
    <div v-if="!isDriveMode && isPdfOrPptx" class="upload-multimodal-notice">
      <el-icon size="16" color="#67c23a"><Picture /></el-icon>
      <span>PDF / PPTX 将自动提取图片、公式（LaTeX）、表格和图表说明（多模态 OCR）</span>
    </div>

    <!-- Drive 模式: folder + visibility -->
    <div v-if="isDriveMode" class="upload-drive-notice">
      <el-icon size="16" color="#e6a23c"><InfoFilled /></el-icon>
      <span>文件直接存入课题组网盘，不触发 AI 分析（需要时可在文件卡片中转知识库）</span>
    </div>

    <el-form label-width="80px">
      <el-form-item label="标题" v-if="!isDriveMode">
        <el-input v-model="title" placeholder="留空则使用文件名" />
      </el-form-item>

      <!-- Drive 模式独占字段 -->
      <template v-if="isDriveMode">
        <el-form-item label="目标文件夹">
          <el-tree-select
            v-model="folderId"
            :data="folderTree"
            :props="folderTreeProps"
            node-key="id"
            placeholder="顶级（不选则存到我的网盘根目录）"
            clearable
            check-strictly
            :render-after-expand="false"
            class="upload-folder-tree-select"
          />
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="visibility">
            <el-radio-button value="private">🔒 私有</el-radio-button>
            <el-radio-button value="team">👥 全组</el-radio-button>
            <el-radio-button value="public">🌐 公开</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </template>

      <el-form-item label="文件">
        <el-upload
          ref="uploadRef"
          drag
          :auto-upload="false"
          :limit="1"
          :accept="isDriveMode ? undefined : '.pdf,.docx,.xlsx,.pptx,.txt,.md'"
          :on-change="onFileChange"
          :on-exceed="() => ElMessage.warning('只能上传一个文件')"
        >
          <el-icon class="el-icon--upload"><Upload /></el-icon>
          <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
          <template #tip>
            <div class="el-upload__tip">
              <template v-if="isDriveMode">
                网盘模式支持任意格式文件，最大 2GB
              </template>
              <template v-else>
                支持 PDF、Word(.docx)、Excel(.xlsx)、TXT、Markdown，最大 50MB
              </template>
            </div>
          </template>
        </el-upload>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="uploading" @click="onUpload">
        {{ uploading ? '上传中...' : '上传' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Upload, Picture, Folder, InfoFilled } from '@element-plus/icons-vue'
import axios from 'axios'
import { useRoute } from 'vue-router'
import { useFolderTree } from '@/composables/useFolderTree'

const props = defineProps({
  isMobile: { type: Boolean, default: false }
})

const emit = defineEmits(['success', 'drive-uploaded'])

const visible = defineModel('visible', { default: false })

// v2 PR3 双模: activeTab 切换 KB/Drive
const activeTab = ref('kb')

// KB 模式字段
const title = ref('')
const file = ref(null)
const uploading = ref(false)
const uploadRef = ref(null)

// Drive 模式字段
const folderId = ref(null)
const visibility = ref('team')

const route = useRoute()

const isDriveMode = computed(() => activeTab.value === 'drive')

// v2 PR3: 复用 PR1 的 folder tree composable, 只加载顶级 + 子级
const { folderTree, fetchTree } = useFolderTree()

// el-tree-select props (后端 tree 数据是 {id, name, children, ...})
const folderTreeProps = {
  label: 'name',
  value: 'id',
  children: 'children',
}

// 切到 drive 模式时懒加载 folder tree
watch(isDriveMode, async (newMode) => {
  if (newMode && (!folderTree.value || folderTree.value.length === 0)) {
    try {
      await fetchTree()
    } catch (e) {
      // 静默 — 用户可手输入 / 跳到 /drive 看
    }
  }
})

const isPdfOrPptx = computed(() => {
  if (!file.value) return false
  const name = file.value.name || ''
  return /\.pdf$|\.pptx$/i.test(name)
})

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
    if (isDriveMode.value) {
      // v2 PR3: drive 模式调 /drive/files/upload
      const formData = new FormData()
      formData.append('file', file.value)
      formData.append('visibility', visibility.value)
      if (folderId.value !== null && folderId.value !== undefined) {
        formData.append('folder_id', String(folderId.value))
      }

      const resp = await axios.post(
        '/api/v1/drive/files/upload',
        formData,
        { timeout: 180000 }
      )
      ElMessage.success(`已存入网盘: ${resp.data.file_name}`)
      visible.value = false
      resetForm()
      emit('drive-uploaded', resp.data)
      // v2 PR3: 调 drive 模式后建议跳到 /drive 看 (不进 KB 不触发 KB refresh)
      emit('success')
    } else {
      // 老 KB 模式 (compat)
      const formData = new FormData()
      formData.append('file', file.value)
      if (title.value) formData.append('title', title.value)

      await axios.post('/api/v1/knowledge/upload', formData, { timeout: 180000 })
      const tip = isPdfOrPptx.value
        ? '文件上传成功，后台正在分析（文本 + 多模态 OCR 约 30-60s）'
        : '文件上传成功，后台正在分析...'
      ElMessage.success(tip)
      visible.value = false
      resetForm()
      emit('success')
    }
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

const resetForm = () => {
  title.value = ''
  file.value = null
  folderId.value = null
  visibility.value = 'team'
  if (uploadRef.value) uploadRef.value.clearFiles()
}
</script>

<style scoped>
.upload-mode-tabs {
  margin-bottom: 12px;
}

.upload-mode-tabs :deep(.el-tabs__nav-prev),
.upload-mode-tabs :deep(.el-tabs__nav-wrap)::after {
  height: 1px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.upload-ai-notice,
.upload-multimodal-notice,
.upload-drive-notice {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-regular, #606266);
}

.upload-ai-notice {
  background: var(--color-primary-bg);
}

.upload-multimodal-notice {
  background: var(--color-success-bg);
  margin-top: -4px;
}

.upload-drive-notice {
  background: var(--color-warning-bg, #fdf6ec);
}

.upload-folder-tree-select {
  width: 100%;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块 (本组件 drive 模式色块用了
  --color-warning-bg token, 自动跟随 6 主题, 无需 dark 块)
-->
