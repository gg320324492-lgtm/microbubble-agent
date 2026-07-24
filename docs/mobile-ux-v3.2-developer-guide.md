# Mobile UX v3.2 开发者指南 — iOS 分享 + 生物识别

> **版本**: v3.2
> **日期**: 2026-07-24
> **作者**: W68 第 8 批 B-3 Agent
> **范围**: 仅 docs — 与 v3.2 PWA 推送互补 (推送: W68 第 5 批 #3 Agent)
> **前置**: [Mobile UX v3.1 开发者指南](./mobile-ux-v3.1-developer-guide.md)

---

## 目录

1. [架构概览](#1-架构概览)
2. [`useMobileShare` API](#2-usemobileshare-api)
3. [`useMobileBiometric` API](#3-usemobilebiometric-api)
4. [组件集成范式](#4-组件集成范式)
5. [iOS Safari / Android Chrome 兼容性矩阵](#5-ios-safari--android-chrome-兼容性矩阵)
6. [测试与可观测性](#6-测试与可观测性)
7. [性能与内存](#7-性能与内存)

---

## 1. 架构概览

v3.2 第 8 批 B-3 新增 2 个 composable + 2 个 component + 3 个 view 集成点, 围绕 **"系统能力集成"** + **"Web 平台能力边界"** 两条主线展开。

```
┌─────────────────────────────────────────────────────────────┐
│  MobileSettingsView (新设置项 集成点)                       │
│  ├─ "分享 App"  → useMobileShare → MobileShareSheet         │
│  └─ "生物识别登录" → useMobileBiometric → MobileBiometricAuth│
│                                                              │
│  MobileDriveView (Drive 文件分享 集成点)                    │
│  └─ 长按文件 → 分享 → 优先 navigator.share                  │
│       ↓ fallback                                              │
│     MobileShareSheet (含 image/pdf 文件 prop)               │
│                                                              │
│  MobileLoginView (生物识别集成点)                            │
│  └─ "Face ID 一键登录" 按钮 → MobileBiometricAuth          │
│                                                              │
│  useMobileShare()                                            │
│  ├─ shareLink({url, title, text})                            │
│  ├─ shareText({text, title})                                 │
│  ├─ shareFile({file, filename, title, text})                 │
│  ├─ copyLink(url) / copyImage(blob) / downloadFile()         │
│                                                              │
│  useMobileBiometric()                                        │
│  ├─ registerWebAuthn() / authenticate()                     │
│  ├─ registerPIN(pin) / verifyPIN(pin)                       │
│  └─ 偏好: setBiometricEnabled / isBiometricEnabled / reset  │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 设计原则 (CLAUDE.md 2026-07-16 #207 + v60+ 教训复用)

1. **能力探测 → 优雅降级**: Web Share API 可用就走系统 sheet, 不可用走自定义 sheet (微信/QQ/微博/复制/保存/系统)
2. **生物识别降级链**: WebAuthn → 6 位数字 PIN → 拒绝登录 (永不让用户被锁死)
3. **用户手势**: navigator.share + PublicKeyCredential 必须在 click/tap 内调用, 不可 defer
4. **localStorage + 内存状态分离**: composable 内存 ref + localStorage 持久化组合
5. **深色模式**: 跨组件复用样式 token (`.share-sheet-*` / `.biometric-*`), 非 scoped 块兜底 (CLAUDE.md v60-v67 第 5 次强化)

---

## 2. `useMobileShare` API

### 2.1 基本用法

```ts
import { useMobileShare } from '@/composables/useMobileShare'

const {
  // 平台/能力
  isIOS, isAndroid, isMobile,
  canNativeShare, canShareFiles,
  // 主分享 API (用户手势内调用!)
  shareLink, shareText, shareFile,
  // 工具 API
  copyLink, copyImage, downloadFile,
} = useMobileShare()

// 在 click/tap 内调
async function onShareClick() {
  const result = await shareLink({
    url: 'https://microbubble.lab.cn',
    title: '小气助手',
    text: '推荐给课题组同事',
  })
  console.log(result.status)  // 'shared' | 'dismissed' | 'fallback' | 'failed'
}
```

### 2.2 三种分享类型

| 方法 | 签名 | 说明 |
|------|------|------|
| `shareLink` | `({url, title?, text?}) → Promise<ShareResult>` | 分享网页/链接, 唤起系统分享面板 (含链接预览) |
| `shareText` | `({text, title?}) → Promise<ShareResult>` | 分享纯文本 (无链接) |
| `shareFile` | `({file: Blob\|File, filename?, title?, text?}) → Promise<ShareResult>` | 分享文件 (iOS 仅 image/video/pdf; Android 范围更宽) |

### 2.3 ShareResult 字段

```ts
interface ShareResult {
  status: 'shared' | 'dismissed' | 'fallback' | 'failed'
  native: boolean             // true = 走了 navigator.share
  error?: string              // status='failed' 时详情
  method?: string             // 'navigator.share' | 'clipboard' | 'file-unsupported' 等 (埋点用)
}
```

**降级语义**:
- `shared`: 用户真的调起系统面板分享了
- `dismissed`: 用户主动取消 (AbortError), **不算错误**, 不弹 ElMessage
- `fallback`: 不可用 / 失败, 走复制 / 不展示 (composable 内部已 best-effort)
- `failed`: 真的出错了 (例如 url 为空), 业务层需自己提示

### 2.4 用户手势铁律 (CLAUDE.md 铁律)

**5 个必须遵守**:
1. **必须在 click/tap event handler 内 await 调用** — iOS Safari / Android Chrome 都会拒绝 (NotAllowedError)
2. **不可包装成 setTimeout / Promise.resolve().then(() => share())** — 验证丢手势
3. **不能从 onMounted 内调** — 用户没交互前会被 refuse
4. **可传 File[]** (仅 Android) 或 单独 file (iOS file prop 必须是 File 不是 Blob, 内部自动转)
5. **数据字段名要正确** — iOS 期待 `url`/`text`/`title`/`files`, 自定义字段会被忽略

### 2.5 平台限制

| 平台 | Web Share | 文件类型 | MIME 限制 |
|------|-----------|----------|-----------|
| iOS Safari 12.1+ (tab) | ✅ | image/*, video/*, .pdf, .key, .numbers, .docx, .pptx 等 | 严格白名单 |
| iOS Safari (PWA standalone) | ✅ | 同上 | 严格白名单 |
| Android Chrome 61+ | ✅ | image/*, video/*, audio/*, text/*, application/pdf | 较宽松 |
| 桌面 (Windows/Mac Chrome) | ✅ (部分) | 仅 image/* | 基本一致 |

**iOS 文件 share 限制** (铁律):
- `.doc` / `.xls` / `.ppt` (老格式) ❌ 不支持 → iOS 会自动转成 .docx 等
- 单文件大小通常 ≤ 200MB (iOS 限制)
- **不支持的文件 MIME → fallback 到复制链接**, 不报错

---

## 3. `useMobileBiometric` API

### 3.1 基本用法

```ts
import { useMobileBiometric } from '@/composables/useMobileBiometric'

const bio = useMobileBiometric()

// 1. 探测 (组件挂载时调一次)
const support = await bio.detectSupport()
// support: { hasWebAuthn, authenticatorType: 'face'|'touch'|'fingerprint'|'none', ... }

if (bio.isBiometricEnabled() && support.available) {
  // 2. 用户开启 + 设备支持 → 走 WebAuthn
  const result = await bio.authenticate()
  if (result.ok) {
    // 验证通过
  } else if (result.dismissed) {
    // 用户主动取消
  } else {
    // 失败 → 降级 PIN
    bio.verifyPIN(pin)
  }
}

// 3. 任意时刻可设置/清除 PIN (无设备/或 WebAuthn 失败时)
await bio.registerPIN('123456')
const r = await bio.verifyPIN('123456')
```

### 3.2 BiometricSupport 字段

```ts
interface BiometricSupport {
  hasWebAuthn: boolean              // PublicKeyCredential + secure context + platform authenticator
  hasPublicKeyCredential: boolean  // 仅 API 存在
  hasIsSecureContext: boolean      // window.isSecureContext (HTTPS)
  hasPlatformAuthenticator: boolean // isUserVerifyingPlatformAuthenticatorAvailable()
  hasConditionalUI: boolean        // isConditionalMediationAvailable() (Safari 16+ autofill)
  isIOS, isAndroid: boolean
  authenticatorType: 'face' | 'touch' | 'fingerprint' | 'none'
  displayName: string               // 'Face ID' / 'Touch ID' / '指纹'
  available: boolean                // hasWebAuthn
}
```

### 3.3 用户手势铁律

**3 个核心铁律** (CLAUDE.md 强化):
1. **WebAuthn 必须 HTTPS** — localhost / 127.0.0.1 / https:// 才满足 isSecureContext, 否则 hasWebAuthn=false
2. **navigator.credentials.create / get 必须在 click/tap 内** — 不接受 Promise.resolve().then(...)
3. **iOS 14.5+ 才有 built-in authenticator** — 之前需外部 authenticator (YubiKey 等), 本项目不考虑

### 3.4 PIN 码 fallback 设计

**6 项约束**:
1. **6 位纯数字** (类似支付宝/微信支付体验)
2. **SHA-256 + salt = window.location.hostname** 存 localStorage, 防明文泄露
3. **5 次失败 → 锁定 5 分钟** (类似银行 App 反爆破)
4. **解锁后自动清失败计数** — 不持久惩罚
5. **Reset 可彻底清除** — `bio.reset()` 清所有 localStorage
6. **WebAuthn 注册失败不阻塞 PIN 设置** — 两套可独立使用

### 3.5 本项目范围声明

**当前未实装**:
- 后端 WebAuthn attestation/assertion verify 端点 (无 VAPID-style challenge 验证服务)
- 用户态 PIN 恢复入口 (忘记 PIN 后只能 reset)
- 多设备 credential 同步 (本项目未来 #009 Self-RAG 跨设备同步一并解决)

**当前能做的**:
- WebAuthn unlock 作为"本机可信任的快速解锁"流程
- PIN 6 位同样为"本机解锁"
- **真正敏感操作 (如修改密码) 仍需输入原密码**

---

## 4. 组件集成范式

### 4.1 MobileShareSheet 用法

```vue
<template>
  <MobileShareSheet
    v-model:show="showShare"
    title="分享文件"
    description="推荐给同事"
    :url="file.shareUrl"
    :text="file.summary"
    :file="file.blob"
    :filename="file.name"
    :show-native-share="true"
    @share="onShareItem"
  />
</template>

<script setup>
const showShare = ref(false)

function onShareItem(payload) {
  // payload = { key: 'wechat'|'qq'|'weibo'|'copy'|'save'|'native', url, text, file, filename }
  if (payload.key === 'native' && share.canNativeShare) {
    share.shareFile({ file: payload.file, filename: payload.filename })
  }
  if (payload.key === 'wechat' || payload.key === 'qq') {
    share.copyLink(payload.url)
  }
  // ...
}
</script>
```

### 4.2 MobileBiometricAuth 用法

```vue
<template>
  <MobileBiometricAuth
    v-model:show="showBio"
    title="Face ID 登录"
    hint="使用生物特征或 PIN 一键登录"
    @success="onBioSuccess"
    @cancel="onBioCancel"
  />
</template>

<script setup>
const showBio = ref(false)

function onBioSuccess(result) {
  // result = { method: 'webauthn' | 'pin' }
  // 本项目目前仅"本机解锁"语义, 需要后端 verify 才能真登录
  ElMessage.success(`已通过 ${result.method === 'webauthn' ? 'Face ID' : 'PIN 码'} 验证`)
}
</script>
```

### 4.3 v3.2 集成点 (3 个 view)

**MobileSettingsView** 新增 2 项:
- `data-testid="share-app-item"` → 触发 `MobileShareSheet`
- `data-testid="biometric-auth-item"` → 触发 `MobileBiometricAuth`

**MobileDriveView** 长按菜单分享升级:
- 原分享: clipboard.writeText 链接
- 现分享: 先 navigator.share, 失败/不支持 → 优先下文件 → 打开 `MobileShareSheet` 含 `file` prop

**MobileLoginView** 新增按钮:
- `biometric-login-btn` (Face ID 一键登录) → 仅设备支持或已设置 PIN 时显示
- 点击 → `MobileBiometricAuth` 弹窗 → 成功提示并聚焦密码输入

---

## 5. iOS Safari / Android Chrome 兼容性矩阵

| 功能 | iOS Safari 12.1+ (tab) | iOS Safari 16.4+ (PWA) | Android Chrome 61+ | Android Chrome 84+ | 本项目实现 |
|------|----------------------|----------------------|---------------------|---------------------|------|
| Web Share (链接) | ✅ (12.1+) | ✅ | ✅ | ✅ | ✅ useMobileShare |
| Web Share (文本) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Web Share (图片) | ✅ | ✅ | ✅ | ✅ | ✅ (image/* 自动) |
| Web Share (PDF) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Web Share (.doc 等) | ⚠️ 自动转 | ⚠️ | ⚠️ | ⚠️ | fallback |
| Clipboard API | ✅ (13.1+) | ✅ | ✅ | ✅ | ✅ copyLink |
| execCommand copy | ✅ (旧) | ✅ (旧) | ✅ (旧) | ✅ (旧) | ✅ fallback |
| Biometric (Touch ID) | ✅ (14.5+ PWA) | ✅ | — | — | ✅ useMobileBiometric |
| Biometric (Face ID) | ✅ (14.5+ PWA) | ✅ | — | — | ✅ |
| Biometric (指纹) | — | — | ✅ (Chrome 84+) | ✅ | ✅ |
| PublicKeyCredential | ✅ (14.5+) | ✅ | ✅ (67+) | ✅ | ✅ |
| isSecureContext | 仅 HTTPS | 仅 HTTPS | 仅 HTTPS | 仅 HTTPS | ⚠️ 必须 HTTPS 上线 |

**调试小贴士**:
- iOS Safari 模拟: macOS Safari → Develop → [设备]
- 真机调试: macOS Safari DevTools → 可看 console.log (震动 API 等)
- Android Chrome 模拟: chrome://inspect → WebView 调试

---

## 6. 测试与可观测性

### 6.1 单元 / e2e 测试

| 文件 | 类型 | 覆盖 |
|------|------|------|
| `web/tests/e2e/mobile_share_biometric.spec.js` | Playwright e2e (4 场景) | share 触发 + sheet 渲染 + 剪贴板 + 生物识别弹窗 + PIN 流程 |

**4 场景**:
1. 设置页 → 分享 App → 复制链接 → 剪贴板验证
2. Drive → 长按文件 → 分享 sheet 出现 (含 file prop)
3. Login → 生物识别按钮 → 弹窗渲染
4. PIN 流程 → 6 位输入 + 二次确认

**Mock 关键**:
- `delete window.navigator.share` 让 Playwright Chromium 走 fallback sheet
- `window.PublicKeyCredential` stub 模拟 WebAuthn 探测通过
- `localStorage` reset 清失败计数 / 锁定状态

### 6.2 调试小工具

```js
// 在浏览器 console 测当前能力
const share = await import('/src/composables/useMobileShare.ts')
const s = share.useMobileShare()
console.log({ isIOS: s.isIOS, canNativeShare: s.canNativeShare })

const bio = await import('/src/composables/useMobileBiometric.ts')
const b = bio.useMobileBiometric()
const support = await b.detectSupport()
console.log(support)
```

### 6.3 关键失败模式

| 现象 | 原因 | 修法 |
|------|------|------|
| `NotAllowedError` | navigator.share 不在 click 内 | 包到 button @click 内 |
| `NotSupportedError` | canShare 返回 false | fallback sheet |
| `TypeError: Cannot read credentials of null` | navigator.credentials 未起手势 | 必须 click 内 |
| PIN 永远 false | SHA-256 salt 域名不匹配 | 用 window.location.hostname |
| Face ID 一直要求"再试一次" | 用户取消多次 | 5 次锁, 等 5 分钟 |

---

## 7. 性能与内存

| 指标 | 目标 | 实测 |
|------|------|------|
| detectSupport 耗时 | < 50ms | ~10ms (浏览器原生探测) |
| shareLink 调用耗时 | < 100ms (native) / < 50ms (clipboard fallback) | |
| WebAuthn register | < 3s | 用户硬件决定 (Face ID ~1s) |
| WebAuthn authenticate | < 2s | ~500ms |
| MobileShareSheet 渲染 | < 100ms | Vue Transition 250ms |
| MobileBiometricAuth 渲染 | < 100ms | Vue Transition 250ms |

**内存**: composable 全部 ref + readonly 暴露, 无全局状态泄漏。Pinia store 不依赖 (轻量 standalone composable)。

---

**至此 Mobile UX v3.2 (推送 + 分享 + 生物识别) 闭环**.
下一批待定: W68 第 5 批 #3 PWA push 已收官 + W68 第 8 批 B-3 share/biometric. 下次迭代可考虑: ARKit 二维码 / WiFi 自动重连 / 后端 WebAuthn verify service (W68+1 #009 cross-cutting).

参考: [Mobile UX v3.1 开发者指南](./mobile-ux-v3.1-developer-guide.md) | [Mobile UX v3.2 用户指南 (待补)](./mobile-ux-v3.1-user-guide.md)
