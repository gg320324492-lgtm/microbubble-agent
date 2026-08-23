<template>
  <div class="settings-mock">
    <div class="nav-panel">
      <div class="nav-item" v-for="item in navItems" :key="item.id"
           :class="{ active: activeNav === item.id }" @click="activeNav = item.id">
        {{ item.icon }} {{ item.label }}
      </div>
    </div>
    <div class="content-panel">
      <div v-if="activeNav === 'model'">
        <h3>模型提供商</h3>
        <div class="provider-item" v-for="p in providers" :key="p.name">
          <div class="provider-name">{{ p.name }}</div>
          <div class="provider-status" :class="p.status">
            {{ p.status === 'connected' ? '已连接' : '未配置' }}
          </div>
          <div class="provider-model" v-if="p.model">{{ p.model }}</div>
        </div>
        <h3>API密钥管理</h3>
        <div class="api-key-item" v-for="k in apiKeys" :key="k.name">
          <span>{{ k.name }} API Key: ****</span>
          <button class="btn-verify">验证</button>
          <button class="btn-delete">删除</button>
        </div>
      </div>
      <div v-if="activeNav === 'storage'">
        <h3>知识库存储</h3>
        <div class="storage-info">
          <div>本地存储: {{ storage.used }} GB / {{ storage.used + storage.available }} GB</div>
          <div class="storage-bar">
            <div class="storage-fill" :style="{ width: (storage.used / (storage.used + storage.available)) * 100 + '%' }"></div>
          </div>
        </div>
        <button class="btn-action">清理缓存</button>
        <button class="btn-action">导出数据</button>
      </div>
      <div v-if="activeNav === 'profile'">
        <h3>用户信息</h3>
        <div class="profile-field">
          <label>姓名</label>
          <input type="text" value="研究员" />
        </div>
        <div class="profile-field">
          <label>机构</label>
          <input type="text" value="微纳米气泡课题组" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const activeNav = ref('model')

const navItems = [
  { id: 'model', icon: '🤖', label: '模型' },
  { id: 'storage', icon: '💾', label: '知识库' },
  { id: 'profile', icon: '👤', label: '用户' }
]

const providers = [
  { name: 'MIMO', status: 'connected', model: 'mimo-7b' },
  { name: 'MiniMax', status: 'connected', model: 'minimax-text' },
  { name: 'Ollama', status: 'disconnected', model: null }
]

const apiKeys = [
  { name: 'MIMO' },
  { name: 'MiniMax' }
]

const storage = { used: 2.3, available: 47.7 }
</script>

<style scoped>
.settings-mock { display: flex; height: 100%; }
.nav-panel { width: 180px; border-right: 1px solid #e2e8f0; padding: 16px; }
.nav-item { padding: 8px 12px; border-radius: 4px; font-size: 13px; cursor: pointer; margin-bottom: 4px; }
.nav-item.active { background: #eff6ff; color: #2563eb; font-weight: 500; }
.content-panel { flex: 1; padding: 24px; }
.provider-item { display: flex; align-items: center; gap: 12px; padding: 10px; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 8px; }
.provider-name { font-weight: 500; font-size: 13px; }
.provider-status { font-size: 12px; padding: 2px 8px; border-radius: 3px; }
.provider-status.connected { background: #dcfce7; color: #166534; }
.provider-status.disconnected { background: #f1f5f9; color: #64748b; }
.provider-model { font-size: 11px; color: #64748b; }
.api-key-item { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-bottom: 8px; }
.btn-verify { font-size: 11px; padding: 2px 8px; background: #2563eb; color: white; border: none; border-radius: 3px; cursor: pointer; }
.btn-delete { font-size: 11px; padding: 2px 8px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; }
.btn-action { font-size: 12px; padding: 6px 12px; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 4px; cursor: pointer; margin-right: 8px; }
.storage-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 8px 0; }
.storage-fill { height: 100%; background: #2563eb; border-radius: 3px; }
.profile-field { margin-bottom: 12px; }
.profile-field label { display: block; font-size: 12px; color: #64748b; margin-bottom: 4px; }
.profile-field input { width: 300px; padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 13px; }
h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
</style>
