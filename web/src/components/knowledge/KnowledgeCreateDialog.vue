<!-- KnowledgeCreateDialog.vue — v77 P2.6-E.3 拆分自 KnowledgeView.vue -->
<template>
  <el-dialog
    v-model="visible"
    :title="editingItem ? '编辑知识' : '添加知识'"
    :width="isMobile ? '90vw' : '600px'"
    top="8vh"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" name="knowledgeForm-title" placeholder="请输入标题" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="form.category" name="knowledgeForm-category" placeholder="选择分类" filterable allow-create clearable>
          <el-option-group label="预设分类">
            <el-option label="📄 论文" value="论文" />
            <el-option label="🔬 方法" value="方法" />
            <el-option label="📏 标准" value="标准" />
            <el-option label="📖 综述" value="综述" />
            <el-option label="💡 案例" value="案例" />
            <el-option label="❓ FAQ" value="FAQ" />
            <el-option label="📝 笔记" value="笔记" />
            <el-option label="📚 手册" value="手册" />
          </el-option-group>
          <el-option-group label="动态分类" v-if="categories.length > 0">
            <el-option
              v-for="cat in categories"
              :key="cat.name"
              :label="`${cat.name} (${cat.count})`"
              :value="cat.name"
            />
          </el-option-group>
        </el-select>
      </el-form-item>
      <el-form-item label="标签">
        <el-select
          v-model="form.tags" name="knowledgeForm-tags"
          multiple
          filterable
          allow-create
          placeholder="输入标签"
        >
          <el-option
            v-for="tag in hotTags"
            :key="tag.name"
            :label="`${tag.name} (${tag.count})`"
            :value="tag.name"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="内容" required>
        <el-input
          v-model="form.content" name="knowledgeForm-content"
          type="textarea"
          :rows="8"
          placeholder="请输入知识内容"
        />
      </el-form-item>
      <el-form-item label="来源">
        <el-input v-model="form.source" name="knowledgeForm-source" placeholder="来源链接或文件路径" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">
        {{ editingItem ? '保存' : '添加' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * KnowledgeCreateDialog.vue — 添加/编辑知识对话框（v77 P2.6-E.3 从 KnowledgeView.vue 拆分）
 *
 * 父组件: KnowledgeView.vue
 * Props: modelValue (v-model:show) / editingItem / categories / hotTags / isMobile
 * Emits: update:modelValue / saved
 */
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  editingItem: { type: Object, default: null },
  categories: { type: Array, default: () => [] },
  hotTags: { type: Array, default: () => [] },
  isMobile: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'saved'])

// v77 P2.6-E.3: 用 computed + setter 让 el-dialog v-model 双向同步到 prop + emit
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const form = ref({
  title: '',
  category: '',
  tags: [],
  content: '',
  source: ''
})

const saving = ref(false)

// v77 P2.6-E.3: 监听 editingItem 变化回填表单
watch(() => props.editingItem, (val) => {
  if (val) {
    form.value = { ...val }
  } else {
    resetForm()
  }
}, { immediate: true })

const resetForm = () => {
  form.value = { title: '', category: '', tags: [], content: '', source: '' }
}

const handleSave = async () => {
  if (!form.value.title || !form.value.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  saving.value = true
  try {
    if (props.editingItem) {
      await axios.put(`/api/v1/knowledge/${props.editingItem.id}`, form.value)
      ElMessage.success('知识更新成功')
    } else {
      await axios.post('/api/v1/knowledge', form.value)
      ElMessage.success('知识添加成功')
    }
    emit('update:modelValue', false)
    emit('saved')
    resetForm()
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    saving.value = false
  }
}
</script>