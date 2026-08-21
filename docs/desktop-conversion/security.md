# MicroBubble Desktop — Electron 安全原则 (Phase 0 冻结基线)

> 本文件描述 Electron 客户端的安全约束。
> **冻结于 Phase 0-Impl-1**。后续 Phase 新增能力 (token 加密、文件关联、自动更新) 必须按本文档新增段。

---

## 1. 三大铁律 (任何能力新增必守)

### 铁律 1 — contextIsolation 永久为 true

```ts
new BrowserWindow({
  webPreferences: {
    contextIsolation: true,   // 必须: 渲染进程跑在隔离世界
    nodeIntegration: false,   // 必须: 渲染进程无 Node API
    sandbox: true,            // 必须: preload 之外所有进程沙箱化
    webSecurity: true,        // 必须: 启用同源策略 + CSP
    allowRunningInsecureContent: false  // 必须: 禁 HTTP 资源
  }
})
```

**禁止场景**:
- ❌ `contextIsolation: false` (不安全的 JS 跨境访问)
- ❌ `nodeIntegration: true` (renderer 直接 require)
- ❌ `sandbox: false` (preload 之外赋予文件系统访问)

### 铁律 2 — preload 白名单 + contextBridge 唯一通道

**唯一允许 renderer 触达主进程的方式**:

```ts
// src/preload/index.ts (Phase 0 锁定结构)
const api = {
  ping: (payload?: PingRequest): Promise<PongResponse> =>
    ipcRenderer.invoke(IPC_CHANNELS.PING, payload ?? {})
} as const

contextBridge.exposeInMainWorld('api', api)
```

**Renderer 仅可见**:
- `window.api.*` (白名单方法)
- `window.api.foo()` (不在白名单时返回 undefined, 不抛错)

**Renderer 不可见**:
- ❌ `window.ipcRenderer` (永不暴露)
- ❌ `window.ipcRenderer.send` (永不暴露)
- ❌ `window.require` (因 sandbox + nodeIntegration:false 自然消失)
- ❌ `window.process` (因 sandbox + contextIsolation:true 自然消失)
- ❌ Electron 任何内部模块

### 铁律 3 — CSP 锁死

**`src/renderer/index.html` 现行 CSP (Phase 0 冻结)**:

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data:;
font-src 'self' data:;
connect-src 'self';
object-src 'none';
frame-src 'none';
worker-src 'none';
base-uri 'self';
form-action 'none';
```

**Phase 1 起追加**:
- `connect-src` 加 `https://agent.mnb-lab.cn wss://agent.mnb-lab.cn`

**永久禁止**:
- ❌ `'unsafe-eval'` (禁 eval)
- ❌ `'unsafe-inline'` 用于 `script-src` (内联脚本)
- ❌ HTTP 资源 (`http://` 任何地方)
- ❌ 远程 `object-src` / `frame-src` (Flash / iframe 跨域)

---

## 2. Token 未来存储原则 (Phase 1 实施，本节先冻结策略)

### 2.1 存储分层

| 敏感级别 | 存储位置 | 例子 |
|----------|----------|------|
| **🔴 严禁** | `localStorage` | JWT access token |
| **🔴 严禁** | `sessionStorage` | JWT refresh token |
| **🔴 严禁** | `document.cookie` (无 httpOnly) | 任何认证信息 |
| **🟡 受限** | IndexedDB 加密字段 | 用户偏好 |
| **🟢 推荐** | Electron `safeStorage.encryptString` (主进程) | access / refresh token |
| **🟢 推荐** | `electron-store` (主进程 JSON) | 配置项 (UI / 快捷键 / 主题) |

### 2.2 Phase 1 实施要点

```ts
// 主进程: 加密 token
import { safeStorage } from 'electron'

function saveTokens(access: string, refresh: string): void {
  if (!safeStorage.isEncryptionAvailable()) {
    // fallback: 阻止登录 + 提示用户开启 macOS Keychain / Win DPAPI
    throw new Error('System encryption not available')
  }
  const encrypted = safeStorage.encryptString(JSON.stringify({ access, refresh }))
  store.set('tokens', encrypted.toString('base64'))
}

function loadTokens(): { access: string; refresh: string } | null {
  const stored = store.get('tokens') as string | undefined
  if (!stored) return null
  if (!safeStorage.isEncryptionAvailable()) return null
  const buf = Buffer.from(stored, 'base64')
  const plaintext = safeStorage.decryptString(buf)
  return JSON.parse(plaintext)
}
```

### 2.3 安全策略

- ✅ **Token 永远不过 IPC 直接传字符串** (避免日志泄漏; 仅在 login/logout 时走专用 channel)
- ✅ **Refresh 单飞** (复用 web 的 `authRefresh.js` 逻辑; 防并发刷新风暴)
- ✅ **解密失败 = 强制重新登录** (不抛阻塞; E-3 类 20 铁律已沉淀)
- ✅ **Electron `safeStorage`** 利用 OS 级: Win DPAPI / macOS Keychain / Linux libsecret
- ❌ **禁止** 把任何 access/refresh token 写到 `localStorage` / `sessionStorage` / IndexedDB 明文

---

## 3. 外链 / 导航拦截

```ts
// 主进程 webContents 拦截 (Phase 0 锁定)
win.webContents.on('will-navigate', (event) => {
  event.preventDefault()  // 禁止 renderer 内导航
})

win.webContents.setWindowOpenHandler(({ url }) => {
  void shell.openExternal(url)  // 外链一律走系统浏览器
  return { action: 'deny' }
})
```

**禁止场景**:
- ❌ renderer 内跳转外链 (防止被钓鱼)
- ❌ window.open 创建第二个 BrowserWindow (防止隔离逃逸)
- ❌ webview 嵌入第三方页面 (防止插件化攻击)

---

## 4. 进程隔离总结

| 进程 | 权限 |
|------|------|
| **Main** | 全 Node API + 文件系统 + 网络 + safeStorage + electron-store |
| **Preload** (sandboxed) | 仅 `electron` 模块 (ipcRenderer, contextBridge) |
| **Renderer** (sandboxed) | 仅 DOM + Vue 3 + window.api |

**禁止跨层访问**:
- ❌ Renderer 直接 require (sandbox 锁)
- ❌ Preload 暴露 Node API 给 renderer (contextIsolation 锁)
- ❌ Renderer 修改 BrowserWindow 配置 (preload 锁)

---

## 5. 部署期供应链安全

| 措施 | 工具 |
|------|------|
| 依赖锁 | `package-lock.json` commit + `npm ci` |
| 漏洞扫描 | `npm audit --audit-level=high` (Phase 4 CI 加) |
| 源签名 | EV 代码签名证书 (Phase 4 上车) |
| 自动更新签名 | `app-update.yml` ed25519 pubkey (类 20.E-2) |
| NSIS 安装器 | oneClick=false + allowToChangeInstallationDirectory (防静默安装) |

---

## 6. 未来 Phase 安全增项 (留口)

- **Phase 1**: token 加密 + refresh 单飞 + 401/429 处理
- **Phase 4**: EV 证书 + electron-updater signature 校验 + staged rollout
- **Phase 5**: 自动更新推送权限分级 (团队 / 实验室内 / 外网公开)
- **Phase 7 (后续)**: web 安全退役映射 (哪些功能 desktop-only, 哪些 web 仍可用)

---

## Status (2026-08-21 Phase 0-Impl-1 冻结)

- ✅ 三大铁律 baseline
- ✅ preload whitelist + CSP 锁
- ✅ token 未来存储原则 (Phase 1 实施规划)
- ✅ 外链导航拦截
- ⏳ Phase 1 上车 token 加密 + refresh 单飞
- 📂 工作分支: `claude/desktop-conversion-plan-12aa22`
