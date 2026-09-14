<script setup lang="ts">
// 设置页模型服务区块 — Provider 增删改 + 连接测试 + 默认切换（key 加密存本机，永不明文回显）
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ModelProvider, ModelProtocol } from '@shared/types'

const PRESETS: { name: string; protocol: ModelProtocol; baseUrl: string; model: string }[] = [
  { name: 'DeepSeek', protocol: 'openai', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat' },
  { name: 'Kimi / Moonshot', protocol: 'openai', baseUrl: 'https://api.moonshot.cn', model: 'moonshot-v1-8k' },
  { name: 'MiniMax', protocol: 'openai', baseUrl: 'https://api.minimax.chat', model: 'abab6.5s-chat' },
  { name: 'MiMo (小米)', protocol: 'anthropic', baseUrl: 'https://token-plan-cn.xiaomimimo.com/anthropic', model: 'mimo-v2.5' },
  { name: '自定义 OpenAI 兼容', protocol: 'openai', baseUrl: 'https://', model: '' }
]

const providers = ref<ModelProvider[]>([])
const editing = ref(false)
const form = ref({ id: '', name: '', protocol: 'openai' as ModelProtocol, baseUrl: '', model: '', apiKey: '' })
const testing = ref(false)
const saving = ref(false)

async function refresh(): Promise<void> {
  providers.value = await window.api.model.list()
}

function onPresetChange(name: string): void {
  const preset = PRESETS.find((p) => p.name === name)
  if (preset) {
    form.value.protocol = preset.protocol
    form.value.baseUrl = preset.baseUrl
    form.value.model = preset.model
  }
}

function startAdd(): void {
  editing.value = true
  form.value = { id: '', name: PRESETS[0].name, protocol: PRESETS[0].protocol, baseUrl: PRESETS[0].baseUrl, model: PRESETS[0].model, apiKey: '' }
}

function startEdit(p: ModelProvider): void {
  editing.value = true
  form.value = { id: p.id, name: p.name, protocol: p.protocol, baseUrl: p.baseUrl, model: p.model, apiKey: '' }
}

function cancelEdit(): void {
  editing.value = false
}

async function onSave(): Promise<void> {
  if (!form.value.name || !form.value.baseUrl || !form.value.model) {
    ElMessage.warning('请填写名称、Base URL 和模型 ID')
    return
  }
  if (!form.value.id && !form.value.apiKey) {
    ElMessage.warning('请填写 API Key')
    return
  }
  saving.value = true
  try {
    await window.api.model.save({
      id: form.value.id || undefined,
      name: form.value.name,
      protocol: form.value.protocol,
      baseUrl: form.value.baseUrl,
      model: form.value.model,
      apiKey: form.value.apiKey || undefined
    })
    editing.value = false
    await refresh()
    ElMessage.success('已保存（API Key 已加密存本机）')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function onTest(): Promise<void> {
  testing.value = true
  try {
    const { ok, message } = await window.api.model.test({
      id: form.value.id || undefined,
      name: form.value.name,
      protocol: form.value.protocol,
      baseUrl: form.value.baseUrl,
      model: form.value.model,
      apiKey: form.value.apiKey || undefined
    })
    if (ok) ElMessage.success(message)
    else ElMessage.error(`连接失败：${message}`)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '测试失败')
  } finally {
    testing.value = false
  }
}

async function onDelete(p: ModelProvider): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除模型配置「${p.name}」？`, '删除', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    await window.api.model.remove(p.id)
    await refresh()
    ElMessage.success('已删除')
  } catch {
    /* 取消 */
  }
}

async function onSetDefault(p: ModelProvider): Promise<void> {
  await window.api.model.setDefault(p.id)
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <section class="card block">
    <div class="block-head">
      <h2>模型服务</h2>
      <button v-if="!editing" class="add-btn" @click="startAdd">＋ 添加</button>
    </div>

    <!-- 配置列表 -->
    <div v-if="providers.length && !editing" class="provider-list">
      <div v-for="p in providers" :key="p.id" class="provider" :class="{ 'is-default': p.isDefault }">
        <div class="provider-main">
          <span class="provider-name">{{ p.name }} <span class="proto-badge">{{ p.protocol }}</span></span>
          <span class="provider-meta">{{ p.baseUrl }} · {{ p.model }}</span>
          <span class="provider-key">Key {{ p.apiKeyMasked ?? '未设置' }}</span>
        </div>
        <div class="provider-actions">
          <span v-if="p.isDefault" class="default-tag">默认</span>
          <button v-else class="mini-btn" @click="onSetDefault(p)">设为默认</button>
          <button class="mini-btn" @click="startEdit(p)">编辑</button>
          <button class="mini-btn mini-danger" @click="onDelete(p)">删除</button>
        </div>
      </div>
    </div>
    <p v-else-if="!editing" class="hint">还没有配置。添加一个 OpenAI 兼容或 Anthropic 协议的服务即可开始真实模型对话；API Key 使用系统级加密（Windows DPAPI）保存在本机。</p>

    <!-- 编辑表单 -->
    <div v-if="editing" class="form">
      <div class="form-row">
        <label>预设</label>
        <select :value="form.name" @change="onPresetChange(($event.target as HTMLSelectElement).value)">
          <option v-for="p in PRESETS" :key="p.name" :value="p.name">{{ p.name }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>名称</label>
        <input v-model="form.name" type="text" placeholder="显示名称" />
      </div>
      <div class="form-row">
        <label>协议</label>
        <select v-model="form.protocol">
          <option value="openai">OpenAI 兼容</option>
          <option value="anthropic">Anthropic</option>
        </select>
      </div>
      <div class="form-row">
        <label>Base URL</label>
        <input v-model="form.baseUrl" type="url" placeholder="https://api.example.com" />
      </div>
      <div class="form-row">
        <label>模型 ID</label>
        <input v-model="form.model" type="text" placeholder="例如 deepseek-chat" />
      </div>
      <div class="form-row">
        <label>API Key</label>
        <input v-model="form.apiKey" type="password" :placeholder="form.id ? '留空则保留原 Key' : 'sk-…'" autocomplete="off" />
      </div>
      <div class="form-actions">
        <button class="btn-primary" :disabled="saving" @click="onSave">{{ saving ? '保存中…' : '保存' }}</button>
        <button class="btn-secondary" :disabled="testing" @click="onTest">{{ testing ? '测试中…' : '测试连接' }}</button>
        <button class="btn-ghost" @click="cancelEdit">取消</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}
.block-head h2 {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
}
.add-btn {
  padding: 6px 14px;
  border: 1px dashed rgba(var(--color-primary-rgb), 0.5);
  border-radius: var(--radius-md);
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.provider-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.provider {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.provider.is-default {
  border-color: rgba(var(--color-primary-rgb), 0.45);
  background: var(--color-primary-bg);
}
.provider-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.provider-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.proto-badge {
  margin-left: 4px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
  font-size: 10px;
  font-weight: var(--font-weight-normal);
}
.provider-meta,
.provider-key {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  word-break: break-all;
}
.provider-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.default-tag {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: #fff;
  font-size: 11px;
}
.mini-btn {
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-card);
  color: var(--color-text-regular);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.mini-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.mini-danger:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.form-row {
  display: grid;
  grid-template-columns: 90px 1fr;
  align-items: center;
  gap: var(--space-3);
}
.form-row label {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
}
.form-row input,
.form-row select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}
.form-row input:focus,
.form-row select:focus {
  outline: none;
  border-color: var(--color-primary);
}
.form-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-2);
}
.btn-primary {
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.btn-secondary {
  padding: 8px 20px;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.btn-ghost {
  padding: 8px 20px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
</style>
