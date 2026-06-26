<template>
  <Teleport to="body">
    <Transition name="form-sheet">
      <div v-if="modelValue" class="sheet-overlay" @click.self="onCancel">
        <div class="sheet-panel" :style="{ paddingBottom: panelPaddingBottom }">
          <div class="sheet-handle" />

          <div class="sheet-header">
            <h3 class="sheet-title">{{ title }}</h3>
            <button
              type="button"
              class="close-btn"
              aria-label="取消"
              title="取消"
              @click="onCancel"
            >✕</button>
          </div>

          <!-- 字段渲染 -->
          <div class="form-fields">
            <div
              v-for="(field, idx) in visibleFields"
              :key="field.key"
              class="form-field"
              :class="{ 'has-error': errors[field.key] }"
            >
              <label
                v-if="field.type !== 'switch' && field.type !== 'checkbox'"
                class="field-label"
              >
                <span v-if="field.required" class="required-mark">*</span>
                {{ field.label }}
              </label>

              <!-- 文本输入 -->
              <input
                v-if="field.type === 'input'"
                type="text"
                class="field-input"
                :value="getValue(field.key)"
                :placeholder="field.placeholder || ''"
                :maxlength="field.maxlength"
                @input="(e) => setValue(field.key, e.target.value)"
              />

              <!-- 多行文本 -->
              <textarea
                v-else-if="field.type === 'textarea'"
                class="field-textarea"
                :value="getValue(field.key)"
                :placeholder="field.placeholder || ''"
                :rows="field.rows || 3"
                :maxlength="field.maxlength"
                @input="(e) => setValue(field.key, e.target.value)"
              />

              <!-- 数字输入 -->
              <input
                v-else-if="field.type === 'number'"
                type="number"
                class="field-input"
                :value="getValue(field.key)"
                :placeholder="field.placeholder || ''"
                :min="field.min"
                :max="field.max"
                :step="field.step"
                @input="(e) => setValue(field.key, e.target.value === '' ? null : Number(e.target.value))"
              />

              <!-- 日期 -->
              <input
                v-else-if="field.type === 'date'"
                type="date"
                class="field-input"
                :value="getValue(field.key)"
                @input="(e) => setValue(field.key, e.target.value)"
              />

              <!-- 单选按钮组 -->
              <div v-else-if="field.type === 'radio'" class="field-options">
                <button
                  v-for="opt in field.options"
                  :key="String(opt.value)"
                  type="button"
                  class="opt-chip"
                  :class="{ active: getValue(field.key) === opt.value }"
                  @click="setValue(field.key, opt.value)"
                >
                  {{ opt.label }}
                </button>
              </div>

              <!-- 多选 -->
              <div v-else-if="field.type === 'checkbox'" class="field-options">
                <button
                  type="button"
                  class="opt-chip"
                  :class="{ active: getValue(field.key) }"
                  @click="setValue(field.key, !getValue(field.key))"
                >
                  {{ field.label }}
                </button>
              </div>

              <!-- 下拉选择 -->
              <div v-else-if="field.type === 'select'" class="field-select-wrap">
                <button
                  type="button"
                  class="field-select"
                  @click="openSelect(field)"
                >
                  <span v-if="getSelectLabel(field)" class="select-label">
                    {{ getSelectLabel(field) }}
                  </span>
                  <span v-else class="select-placeholder">
                    {{ field.placeholder || '请选择' }}
                  </span>
                  <span class="select-arrow">›</span>
                </button>
              </div>

              <!-- 开关 -->
              <button
                v-else-if="field.type === 'switch'"
                type="button"
                class="field-switch"
                :class="{ active: getValue(field.key) }"
                @click="setValue(field.key, !getValue(field.key))"
              >
                <span class="switch-label">{{ field.label }}</span>
                <span class="switch-track">
                  <span class="switch-thumb" />
                </span>
              </button>

              <!-- 文件上传 -->
              <div v-else-if="field.type === 'upload'" class="field-upload">
                <button
                  type="button"
                  class="upload-btn"
                  @click="$emit('upload', field)"
                >
                  <span class="upload-icon">📎</span>
                  <span v-if="getValue(field.key)">{{ getValue(field.key) }}</span>
                  <span v-else>{{ field.placeholder || '选择文件' }}</span>
                </button>
              </div>

              <!-- 自定义 slot -->
              <slot
                v-else-if="field.type === 'custom'"
                :name="`field-${field.key}`"
                :field="field"
                :value="getValue(field.key)"
                :set-value="(v) => setValue(field.key, v)"
              />

              <!-- 错误提示 -->
              <div v-if="errors[field.key]" class="field-error">
                {{ errors[field.key] }}
              </div>
            </div>
          </div>

          <!-- 底部按钮 -->
          <div class="form-actions">
            <button
              v-if="showCancel"
              type="button"
              class="btn-secondary"
              @click="onCancel"
            >{{ cancelText }}</button>
            <button
              type="button"
              class="btn-primary"
              :disabled="submitting"
              @click="onSubmit"
            >
              <span v-if="submitting" class="submit-spinner" />
              <span>{{ submitting ? submittingText : submitText }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 子选择器（select 字段展开） -->
    <Teleport to="body">
      <Transition name="select-picker">
        <div
          v-if="activeSelectField"
          class="picker-overlay"
          @click.self="closeSelect"
        >
          <div class="picker-panel">
            <div class="picker-header">
              <button type="button" class="close-btn" @click="closeSelect">✕</button>
              <h3>{{ activeSelectField.label }}</h3>
              <div class="close-btn" style="visibility: hidden" />
            </div>
            <div class="picker-options">
              <button
                v-for="opt in activeSelectField.options"
                :key="String(opt.value)"
                type="button"
                class="picker-option"
                :class="{ active: getValue(activeSelectField.key) === opt.value }"
                @click="onSelectOption(opt)"
              >
                <span>{{ opt.label }}</span>
                <span v-if="getValue(activeSelectField.key) === opt.value" class="check-mark">✓</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </Teleport>
</template>

<script setup>
/**
 * MobileFormSheet.vue — 通用移动端表单 Sheet（PR #6 核心组件）
 *
 * 替代桌面端 19 个 el-dialog 表单（TaskCreate / MemberEdit / ProjectEdit / MemoryEdit 等）
 *
 * 核心设计：fields[] 配置化渲染
 * - 8 种字段类型：input / textarea / number / date / radio / checkbox / select / switch / upload / custom
 * - 内置验证（rules）
 * - v-model:modelValue 控制显示
 * - v-model:form 双向绑定表单数据
 * - submit 事件带验证后的 form 对象
 *
 * 用法：
 *   const fields = [
 *     { key: 'title', label: '标题', type: 'input', required: true, placeholder: '输入标题' },
 *     { key: 'priority', label: '优先级', type: 'radio', required: true, options: [
 *       { value: 'low', label: '低' }, { value: 'high', label: '高' }
 *     ]},
 *   ]
 *   <MobileFormSheet
 *     v-model:show="showForm"
 *     v-model:form="form"
 *     title="新建任务"
 *     :fields="fields"
 *     @submit="onSubmit"
 *   />
 */

import { ref, computed, reactive, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '表单' },
  /** FieldDef[] */
  fields: { type: Array, default: () => [] },
  /** 表单数据（双向绑定） */
  form: { type: Object, default: () => ({}) },
  /** 提交中文案 */
  submitText: { type: String, default: '确定' },
  submittingText: { type: String, default: '提交中...' },
  cancelText: { type: String, default: '取消' },
  showCancel: { type: Boolean, default: true },
  /** 是否正在提交 */
  submitting: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:modelValue',
  'update:form',
  'submit',
  'cancel',
  'upload',
])

const errors = reactive({})
const activeSelectField = ref(null)

// 隐藏字段（v-if 条件）
const visibleFields = computed(() => {
  return props.fields.filter((f) => !f.if || f.if(props.form))
})

const panelPaddingBottom = computed(() => {
  return `calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))`
})

// 值读写
function getValue(key) {
  return props.form[key]
}
function setValue(key, value) {
  // 触发 v-model:form 更新
  emit('update:form', { ...props.form, [key]: value })
  // 清除该字段错误
  if (errors[key]) {
    delete errors[key]
  }
}

// 选择器
function openSelect(field) {
  activeSelectField.value = field
}
function closeSelect() {
  activeSelectField.value = null
}
function onSelectOption(opt) {
  if (activeSelectField.value) {
    setValue(activeSelectField.value.key, opt.value)
  }
  closeSelect()
}
function getSelectLabel(field) {
  const value = getValue(field.key)
  if (value === null || value === undefined || value === '') return ''
  const opt = field.options?.find((o) => o.value === value)
  return opt?.label || ''
}

// 验证
function validate() {
  const newErrors = {}
  for (const field of visibleFields.value) {
    if (field.required) {
      const v = getValue(field.key)
      if (v === null || v === undefined || v === '') {
        newErrors[field.key] = `${field.label}不能为空`
        continue
      }
    }
    if (field.rules && Array.isArray(field.rules)) {
      const v = getValue(field.key)
      for (const rule of field.rules) {
        const err = rule(v)
        if (err) {
          newErrors[field.key] = err
          break
        }
      }
    }
  }
  Object.keys(errors).forEach((k) => delete errors[k])
  Object.assign(errors, newErrors)
  return Object.keys(newErrors).length === 0
}

// 提交
function onSubmit() {
  if (!validate()) return
  emit('submit', { ...props.form })
}

// 取消
function onCancel() {
  Object.keys(errors).forEach((k) => delete errors[k])
  emit('cancel')
  emit('update:modelValue', false)
}

// 重置（外部切换表单时）
watch(
  () => props.modelValue,
  (v) => {
    if (!v) {
      Object.keys(errors).forEach((k) => delete errors[k])
    }
  }
)
</script>

<style scoped>
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px;
  max-height: 90vh;
  overflow-y: auto;
}
[data-theme="dark"] .sheet-panel {
  background: var(--color-bg-card);
}

.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
}

.sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}
.sheet-title {
  margin: 0;
  font-size: 17px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}
.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.close-btn:active { background: var(--color-bg-hover); }

/* 字段 */
.form-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-field.has-error .field-input,
.form-field.has-error .field-textarea,
.form-field.has-error .field-select {
  border-color: var(--color-danger, #F56C6C);
}
.field-label {
  font-size: 13px;
  color: var(--color-text-regular);
  font-weight: var(--font-weight-medium, 500);
}
.required-mark {
  color: var(--color-danger, #F56C6C);
  margin-right: 2px;
}

.field-input,
.field-textarea,
.field-select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: 15px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
}
.field-textarea {
  resize: vertical;
  min-height: 80px;
}
.field-input:focus,
.field-textarea:focus,
.field-select:focus {
  border-color: var(--color-primary);
}
.field-select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  cursor: pointer;
}
.select-label { color: var(--color-text-primary); }
.select-placeholder { color: var(--color-text-placeholder); }
.select-arrow {
  transform: rotate(90deg);
  color: var(--color-text-secondary);
  font-size: 18px;
}

/* radio / checkbox 横向排列 */
.field-options {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.opt-chip {
  padding: 6px 14px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.opt-chip.active {
  background: var(--color-primary);
  /* stylelint-disable-next-line color-named */
  color: white;
  border-color: var(--color-primary);
}

/* switch */
.field-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  background: transparent;
  border: none;
  font-size: 14px;
  color: var(--color-text-primary);
  cursor: pointer;
  width: 100%;
  text-align: left;
}
.switch-track {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: var(--color-border);
  position: relative;
  transition: background 0.2s;
}
.field-switch.active .switch-track {
  background: var(--color-primary);
}
.switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-bg-card);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  transition: transform 0.2s;
}
.field-switch.active .switch-thumb {
  transform: translateX(20px);
}

/* upload */
.field-upload {
  width: 100%;
}
.upload-btn {
  width: 100%;
  padding: 14px;
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.upload-btn:active { background: var(--color-bg-page); }
.upload-icon { font-size: 18px; }

/* 错误 */
.field-error {
  font-size: 12px;
  color: var(--color-danger, #F56C6C);
}

/* 操作按钮 */
.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}
.btn-secondary, .btn-primary {
  flex: 1;
  padding: 14px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 15px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.btn-secondary {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border);
}
.btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  /* stylelint-disable-next-line color-named */
  color: white;
}
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.submit-spinner {
  width: 14px;
  height: 14px;
  /* stylelint-disable-next-line color-named */
  border: 2px solid white;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 进出动画 */
.form-sheet-enter-active, .form-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.form-sheet-enter-active .sheet-panel,
.form-sheet-leave-active .sheet-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.form-sheet-enter-from, .form-sheet-leave-to { opacity: 0; }
.form-sheet-enter-from .sheet-panel,
.form-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}

/* 子选择器 Picker */
.picker-overlay {
  position: fixed;
  inset: 0;
  z-index: 4600;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.picker-panel {
  width: 100%;
  max-height: 70vh;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  display: flex;
  flex-direction: column;
}
.picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.picker-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
}
.picker-options {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.picker-option {
  width: 100%;
  padding: 14px 20px;
  background: transparent;
  border: none;
  font-size: 15px;
  color: var(--color-text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  -webkit-tap-highlight-color: transparent;
}
.picker-option:active { background: var(--color-bg-hover); }
.picker-option.active {
  color: var(--color-primary);
  font-weight: var(--font-weight-medium, 500);
}
.check-mark {
  color: var(--color-primary);
  font-weight: bold;
}

.select-picker-enter-active, .select-picker-leave-active {
  transition: opacity 0.2s ease;
}
.select-picker-enter-active .picker-panel,
.select-picker-leave-active .picker-panel {
  transition: transform 0.25s ease;
}
.select-picker-enter-from, .select-picker-leave-to { opacity: 0; }
.select-picker-enter-from .picker-panel,
.select-picker-leave-to .picker-panel {
  transform: translateY(100%);
}
</style>