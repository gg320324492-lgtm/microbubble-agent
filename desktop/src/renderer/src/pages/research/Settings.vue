<script setup lang="ts">
/**
 * 系统设置 — 模型配置/知识库/用户。
 */
import { ref } from 'vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const activeTab = ref('model')
const tabs = [
  { id: 'model', label: '模型配置', icon: '🤖' },
  { id: 'knowledge', label: '知识库管理', icon: '📚' },
  { id: 'user', label: '用户研究方向', icon: '👤' },
  { id: 'api', label: 'API 设置', icon: '🔑' },
]

const providers = [
  { name: 'MIMO', model: 'mimo-7b', status: 'connected' },
  { name: 'MiniMax', model: 'minimax-text', status: 'connected' },
  { name: 'Ollama', model: 'qwen3:8b', status: 'disconnected' },
]

const storage = { used: 2.3, total: 50 }
</script>

<template>
  <div class="settings">
    <h1 class="settings__title">系统设置</h1>

    <div class="settings__tabs">
      <div v-for="t in tabs" :key="t.id" class="settings__tab" :class="{ 'settings__tab--active': activeTab === t.id }" @click="activeTab = t.id">
        {{ t.icon }} {{ t.label }}
      </div>
    </div>

    <!-- 模型配置 -->
    <div v-if="activeTab === 'model'" class="settings__content">
      <div class="settings__section">
        <h3>在线模型配置</h3>
        <div class="settings__field"><label>首选模型</label><select><option>MB-Researcher Pro</option></select></div>
        <div class="settings__field"><label>备用模型</label><select><option>MB-Researcher Lite</option></select></div>
        <div class="settings__field"><label>模型温度</label><input type="range" min="0" max="1" step="0.05" value="0.25" /><span>0.25</span></div>
        <div class="settings__field"><label>最大输出 Tokens</label><input type="number" value="4096" /></div>
      </div>
      <div class="settings__section">
        <h3>API 提供商状态</h3>
        <div class="settings__provider" v-for="p in providers" :key="p.name">
          <span class="settings__provider-name">{{ p.name }}</span>
          <span class="settings__provider-model">{{ p.model }}</span>
          <StatusBadge :status="p.status === 'connected' ? 'success' : 'neutral'" :label="p.status === 'connected' ? '已连接' : '未配置'" />
        </div>
      </div>
      <div class="settings__section">
        <h3>知识库存储</h3>
        <div class="settings__storage">
          <div class="settings__storage-bar"><div class="settings__storage-fill" :style="{ width: (storage.used / storage.total * 100) + '%' }" /></div>
          <span>{{ storage.used }} GB / {{ storage.total }} GB</span>
        </div>
      </div>
    </div>

    <!-- 知识库管理 -->
    <div v-if="activeTab === 'knowledge'" class="settings__content">
      <div class="settings__section">
        <h3>知识库设置</h3>
        <div class="settings__field"><label>默认检索库</label><select><option>全部知识库</option></select></div>
        <div class="settings__field"><label>检索策略</label><select><option>混合检索（关键词 + 向量）</option></select></div>
        <div class="settings__field"><label>结果数量</label><input type="number" value="12" /></div>
        <div class="settings__field"><label>相似度阈值</label><input type="range" min="0" max="1" step="0.05" value="0.35" /><span>0.35</span></div>
      </div>
    </div>

    <!-- 用户研究方向 -->
    <div v-if="activeTab === 'user'" class="settings__content">
      <div class="settings__section">
        <h3>账户信息</h3>
        <div class="settings__field"><label>姓名</label><input type="text" value="王天志" /></div>
        <div class="settings__field"><label>所属团队</label><input type="text" value="微纳米气泡课题组" /></div>
        <div class="settings__field"><label>研究方向</label><input type="text" value="微纳米气泡水处理技术" /></div>
      </div>
    </div>

    <!-- API 设置 -->
    <div v-if="activeTab === 'api'" class="settings__content">
      <div class="settings__section">
        <h3>API 密钥管理</h3>
        <div class="settings__api-item">
          <span>MIMO API Key</span>
          <input type="password" value="************" disabled />
          <button class="settings__btn">验证</button>
        </div>
        <div class="settings__api-item">
          <span>MiniMax API Key</span>
          <input type="password" value="************" disabled />
          <button class="settings__btn">验证</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings { padding: 24px 28px; max-width: 1000px; }
.settings__title { margin: 0 0 16px; font-size: 20px; font-weight: 700; color: #0f172a; }
.settings__tabs { display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 1px solid #e5e7eb; }
.settings__tab { padding: 10px 16px; font-size: 13px; color: #64748b; cursor: pointer; border-bottom: 2px solid transparent; transition: all .15s; }
.settings__tab--active { color: #2563eb; border-bottom-color: #2563eb; font-weight: 500; }
.settings__tab:hover { color: #1e293b; }
.settings__content { display: flex; flex-direction: column; gap: 16px; }
.settings__section { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; }
.settings__section h3 { margin: 0 0 14px; font-size: 14px; font-weight: 600; color: #0f172a; }
.settings__field { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.settings__field label { font-size: 13px; color: #64748b; min-width: 100px; }
.settings__field select, .settings__field input[type="number"] { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; min-width: 200px; }
.settings__field input[type="range"] { flex: 1; max-width: 200px; }
.settings__field span { font-size: 13px; color: #475569; }
.settings__provider { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.settings__provider-name { font-size: 13px; font-weight: 500; color: #1e293b; min-width: 80px; }
.settings__provider-model { font-size: 12px; color: #64748b; flex: 1; }
.settings__storage { display: flex; align-items: center; gap: 10px; }
.settings__storage-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.settings__storage-fill { height: 100%; background: #3b82f6; border-radius: 4px; }
.settings__api-item { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 13px; }
.settings__api-item input { flex: 1; max-width: 300px; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; }
.settings__btn { padding: 6px 14px; background: #2563eb; color: #fff; border: none; border-radius: 6px; font-size: 12px; cursor: pointer; }
.settings__btn:hover { background: #1d4ed8; }
</style>
