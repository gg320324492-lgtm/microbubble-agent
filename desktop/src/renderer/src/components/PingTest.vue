<script setup lang="ts">
import { ref } from 'vue'
import type { PongResponse } from '@shared/preload-api'

// IPC 链路验证：
//   renderer: window.api.ping()  (本组件)
//     ↓
//   preload:  contextBridge (src/preload/index.ts)
//     ↓
//   main:     ipcMain.handle('app:ping') (src/main/ipc.ts)
//
// 期望返回: { success:true, message:'pong', timestamp:<ms>, echo?:string }
const status = ref<'idle' | 'loading' | 'ok' | 'error'>('idle')
const response = ref<PongResponse | null>(null)
const error = ref<string | null>(null)

async function handlePing(): Promise<void> {
  status.value = 'loading'
  error.value = null
  try {
    const result = await window.api.ping({ message: 'hello from renderer' })
    response.value = result
    status.value = result.success ? 'ok' : 'error'
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    status.value = 'error'
  }
}
</script>

<template>
  <div class="ping-card">
    <h2>IPC 验证</h2>
    <p class="desc">
      点击按钮通过 <code>window.api.ping()</code> 调到主进程 <code>ipcMain.handle('app:ping')</code>，
      走完整 3 进程链路验证。
    </p>
    <button class="ping-btn" :disabled="status === 'loading'" @click="handlePing">
      {{ status === 'loading' ? 'Pinging…' : 'Send Ping' }}
    </button>

    <div v-if="response" class="result-block ok">
      <div class="result-label">Response</div>
      <pre>{{ response }}</pre>
    </div>

    <div v-if="error" class="result-block error">
      <div class="result-label">Error</div>
      <pre>{{ error }}</pre>
    </div>

    <div class="security-info">
      <strong>Security baseline (active):</strong>
      <ul>
        <li>contextIsolation: true</li>
        <li>nodeIntegration: false</li>
        <li>sandbox: true</li>
        <li>CSP locked (no eval, no inline script)</li>
        <li>Preload whitelist via contextBridge only</li>
        <li>window.ipcRenderer NOT exposed</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.ping-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 1.5rem;
  max-width: 640px;
}
.ping-card h2 {
  margin: 0 0 0.6rem;
  font-size: 1.2rem;
}
.desc {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: #94a3b8;
}
.desc code {
  background: #0f172a;
  padding: 0.1em 0.4em;
  border-radius: 3px;
  font-size: 0.85em;
  color: #fbbf24;
}
.ping-btn {
  background: #f97316;
  color: #fff;
  border: 0;
  padding: 0.5rem 1.2rem;
  border-radius: 4px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.15s;
}
.ping-btn:hover:not(:disabled) {
  background: #ea580c;
}
.ping-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.result-block {
  margin-top: 1rem;
  padding: 0.75rem;
  border-radius: 4px;
  font-size: 0.85rem;
}
.result-block.ok {
  background: #064e3b;
  border-left: 3px solid #10b981;
}
.result-block.error {
  background: #7f1d1d;
  border-left: 3px solid #ef4444;
}
.result-label {
  font-weight: 600;
  margin-bottom: 0.3rem;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
}
pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.security-info {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #334155;
  font-size: 0.85rem;
}
.security-info ul {
  margin: 0.5rem 0 0;
  padding-left: 1.5rem;
  color: #94a3b8;
}
.security-info li {
  margin: 0.2rem 0;
  font-family: monospace;
}
</style>
