<!--
  ShareView.vue — 网盘公开分享落地页 (批次⑩.9, 2026-09-05)

  /drive/share/:token — 无需登录。此前该路由不存在, 分享链接打开即空白。

  token 双模式探测:
  - 文件夹 token: GET /api/v1/folders/share/{token} → FolderShareTokenAccess
    (folder 概要 + files + subfolders) → 渲染文件夹浏览器, 文件经
    /api/v1/folders/share/{token}/files/{file_id}/download 公开下载 (带提取码)
  - 文件 token: GET /api/v1/drive/share/{token}/info → {file_name, password_required}
    → 需要提取码先 verify-password, 下载走 /api/v1/drive/share/{token}?password=
  - 双 404 → 链接不存在 / 已撤销 / 已过期 错误态
-->
<template>
  <div class="share-page">
    <!-- 加载 -->
    <div v-if="loading" class="sh-card sh-state">
      <span class="sh-spin"></span>
      <p>正在打开分享…</p>
    </div>

    <!-- 错误态 -->
    <div v-else-if="mode === 'error'" class="sh-card sh-state">
      <div class="sh-state-ico">∅</div>
      <h1>{{ errorMsg }}</h1>
      <p class="sh-sub">链接可能已过期, 或已被分享人撤销</p>
      <p class="sh-foot">MicroBubble Lab · 课题组网盘</p>
    </div>

    <!-- 文件夹分享 -->
    <div v-else-if="mode === 'folder'" class="sh-card">
      <header class="sh-head">
        <span class="sh-ico"><svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg></span>
        <div>
          <h1>{{ folderData.folder_name }}</h1>
          <p class="sh-sub">公开分享 · 共 {{ folderData.files.length }} 个文件<span v-if="folderData.subfolders.length"> · {{ folderData.subfolders.length }} 个子文件夹</span><template v-if="folderData.expires_at"> · {{ fmtExp(folderData.expires_at) }} 到期</template></p>
        </div>
      </header>
      <ul class="sh-list">
        <li v-for="f in folderData.files" :key="'f' + f.id">
          <span class="sh-dot" :style="{ background: typeColor(f.file_name) }"></span>
          <span class="sh-name">{{ f.file_name }}</span>
          <span class="sh-size">{{ fmtSize(f.file_size) }}</span>
          <a class="sh-dl" :href="dlUrl(f.id)" title="下载"><svg viewBox="0 0 24 24"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14"/></svg></a>
        </li>
        <li v-for="sf in folderData.subfolders" :key="'s' + sf.id">
          <span class="sh-dot" style="background: var(--sh-primary)"></span>
          <span class="sh-name sh-dir">{{ sf.name }}</span>
          <span class="sh-size">文件夹</span>
          <span class="sh-dl sh-dl--off">—</span>
        </li>
        <li v-if="!folderData.files.length && !folderData.subfolders.length" class="sh-empty">该文件夹还没有内容</li>
      </ul>
      <footer class="sh-foot">MicroBubble Lab · 课题组网盘 公开分享</footer>
    </div>

    <!-- 文件分享 -->
    <div v-else-if="mode === 'file'" class="sh-card">
      <header class="sh-head">
        <span class="sh-ico"><svg viewBox="0 0 24 24"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg></span>
        <div>
          <h1>{{ fileInfo.file_name }}</h1>
          <p class="sh-sub">公开分享<template v-if="fileInfo.expires_at"> · {{ fmtExp(fileInfo.expires_at) }} 到期</template></p>
        </div>
      </header>

      <div v-if="fileInfo.password_required && !passwordOk" class="sh-pwd">
        <label>此分享受提取码保护</label>
        <div class="sh-pwd-row">
          <input v-model="password" class="sh-inp" placeholder="输入 4-8 位数字提取码" inputmode="numeric" maxlength="8" @keydown.enter="verifyPassword" />
          <button class="sh-btn" :disabled="verifying" @click="verifyPassword">{{ verifying ? '验证中…' : '验证' }}</button>
        </div>
        <p v-if="pwdError" class="sh-err">{{ pwdError }}</p>
      </div>
      <div v-else class="sh-dlzone">
        <a class="sh-btn sh-btn--big" :href="fileDlUrl">
          <svg viewBox="0 0 24 24"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14"/></svg>下载文件
        </a>
        <p class="sh-sub" style="margin-top:10px">点击按钮即开始下载</p>
      </div>
      <footer class="sh-foot">MicroBubble Lab · 课题组网盘 公开分享</footer>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const token = route.params.token

const loading = ref(true)
const mode = ref('error')          // folder | file | error
const errorMsg = ref('分享链接不存在、已撤销或已过期')
const folderData = ref(null)
const fileInfo = ref(null)
const password = ref('')
const passwordOk = ref(false)
const pwdError = ref('')
const verifying = ref(false)

function typeColor(name) {
  const ext = (name || '').split('.').pop().toLowerCase()
  const map = { pdf: '#B3392F', doc: '#2F5D8A', docx: '#2F5D8A', ppt: '#B07C24', pptx: '#B07C24', xls: '#3E7A52', xlsx: '#3E7A52', csv: '#3E7A52', png: '#7C4E96', jpg: '#7C4E96', jpeg: '#7C4E96', mp4: '#A84B6F', mov: '#A84B6F', m4a: '#B07C24', mp3: '#B07C24' }
  return map[ext] || '#8F877B'
}
function fmtSize(bytes) {
  if (bytes == null) return '—'
  const n = Number(bytes) || 0
  if (n < 1024) return n + ' B'
  const u = ['KB', 'MB', 'GB', 'TB']; let v = n / 1024, i = 0
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
  return (v >= 100 ? Math.round(v) : v.toFixed(1)) + ' ' + u[i]
}
function fmtExp(iso) {
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '' : `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function dlUrl(fileId) {
  const pwd = password.value ? `?password=${encodeURIComponent(password.value)}` : ''
  return `/api/v1/folders/share/${token}/files/${fileId}/download${pwd}`
}
const fileDlUrl = `/api/v1/drive/share/${token}`

async function verifyPassword() {
  pwdError.value = ''
  verifying.value = true
  try {
    const resp = await axios.post(`/api/v1/drive/share/${token}/verify-password`, { password: password.value })
    passwordOk.value = !!resp.data?.verified
    if (!passwordOk.value) pwdError.value = '提取码不正确'
  } catch {
    pwdError.value = '提取码不正确'
  } finally {
    verifying.value = false
  }
}

onMounted(async () => {
  // 1. 文件夹 token
  try {
    const resp = await axios.get(`/api/v1/folders/share/${token}`)
    folderData.value = resp.data
    mode.value = 'folder'
    loading.value = false
    return
  } catch { /* 非 folder token, 继续探测文件 */ }
  // 2. 文件 token
  try {
    const resp = await axios.get(`/api/v1/drive/share/${token}/info`)
    fileInfo.value = resp.data
    mode.value = 'file'
    passwordOk.value = !resp.data.password_required
  } catch {
    mode.value = 'error'
  }
  loading.value = false
})
</script>

<style>
:root {
  --sh-primary: #0E766E; --sh-primary-dark: #0B5D56;
  --sh-bg: #F2F0EB; --sh-card: #fff; --sh-line: #E5E1D8; --sh-line-2: #D5D0C3;
  --sh-text: #22302C; --sh-text-2: #52615C; --sh-text-3: #8B968F; --sh-text-4: #B9BFB6;
  --sh-danger: #D94F2B;
  --sh-mono: Consolas, 'JetBrains Mono', 'Courier New', monospace;
}
.share-page {
  min-height: 100vh; background: var(--sh-bg);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 8vh 20px 40px;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', Inter, sans-serif;
  color: var(--sh-text); font-size: 13.5px;
}
.sh-card {
  width: 100%; max-width: 560px;
  background: var(--sh-card); border: 1px solid var(--sh-line);
  border-radius: 12px; box-shadow: 0 24px 64px rgba(10, 20, 16, .18);
  padding: 26px 26px 18px;
}
.sh-state { text-align: center; padding: 52px 26px; }
.sh-state-ico { font-size: 40px; color: var(--sh-text-4); margin-bottom: 12px; }
.sh-state h1 { font-size: 16px; font-weight: 700; margin-bottom: 8px; }
.sh-spin {
  display: inline-block; width: 26px; height: 26px; border-radius: 50%;
  border: 3px solid var(--sh-line-2); border-top-color: var(--sh-primary);
  animation: sh-rotate .8s linear infinite; margin-bottom: 14px;
}
@keyframes sh-rotate { to { transform: rotate(360deg) } }

.sh-head { display: flex; align-items: center; gap: 13px; padding-bottom: 16px; border-bottom: 1px solid var(--sh-line); margin-bottom: 6px; }
.sh-ico {
  width: 42px; height: 42px; border-radius: 10px; flex: none;
  background: linear-gradient(135deg, #0E766E, #12897C);
  display: grid; place-items: center;
}
.sh-ico svg { width: 20px; height: 20px; stroke: #fff; fill: none; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.sh-head h1 { font-size: 16.5px; font-weight: 700; word-break: break-all; }
.sh-sub { font-size: 11.5px; color: var(--sh-text-3); margin-top: 3px; font-family: var(--sh-mono); }

.sh-list { list-style: none; }
.sh-list li {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 4px; border-bottom: 1px solid var(--sh-line);
}
.sh-list li:last-child { border-bottom: none; }
.sh-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.sh-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.sh-name.sh-dir { color: var(--sh-primary-dark); }
.sh-size { flex: none; font-family: var(--sh-mono); font-size: 11.5px; color: var(--sh-text-3); }
.sh-dl {
  flex: none; width: 30px; height: 30px; border-radius: 8px;
  display: grid; place-items: center; color: var(--sh-primary-dark);
  border: 1px solid var(--sh-line-2); background: var(--sh-card);
  transition: all .15s;
}
.sh-dl svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.sh-dl:hover { border-color: rgba(14,118,110,.35); background: rgba(14,118,110,.09); }
.sh-dl--off { color: var(--sh-text-4); border-style: dashed; background: none; }
.sh-empty { text-align: center; color: var(--sh-text-3); padding: 26px 0 !important; }

.sh-pwd { padding: 16px 0 6px; }
.sh-pwd label { display: block; font-size: 12.5px; font-weight: 600; margin-bottom: 8px; }
.sh-pwd-row { display: flex; gap: 8px; }
.sh-inp {
  flex: 1; border: 1px solid var(--sh-line-2); border-radius: 8px;
  padding: 9px 12px; font: inherit; font-size: 13px; letter-spacing: .2em;
  outline: none; background: var(--sh-card); color: var(--sh-text);
  transition: border-color .15s, box-shadow .15s;
}
.sh-inp:focus { border-color: var(--sh-primary); box-shadow: 0 0 0 3px rgba(14,118,110,.1); }
.sh-btn {
  font: inherit; font-size: 12.5px; padding: 8px 16px; border-radius: 8px;
  border: none; background: linear-gradient(135deg, #0E766E, #12897C);
  color: #fff; font-weight: 600; cursor: pointer; text-decoration: none;
  display: inline-flex; align-items: center; gap: 7px; justify-content: center;
  transition: transform .15s, box-shadow .15s;
  box-shadow: 0 2px 8px rgba(14,118,110,.3);
}
.sh-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(14,118,110,.32); }
.sh-btn:disabled { opacity: .6; transform: none; }
.sh-btn--big { padding: 11px 26px; font-size: 13.5px; }
.sh-btn svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.sh-err { margin-top: 8px; font-size: 11.5px; color: var(--sh-danger); }
.sh-dlzone { text-align: center; padding: 20px 0 8px; }
.sh-foot { margin-top: 18px; padding-top: 12px; border-top: 1px dashed var(--sh-line-2); font-family: var(--sh-mono); font-size: 10px; letter-spacing: .12em; color: var(--sh-text-4); text-align: center; }
</style>
