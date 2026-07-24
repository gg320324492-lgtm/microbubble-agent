# W68 第 8 批 B-3: Mobile UX v3.2 iOS 分享 + 生物识别 — 锚点范式第 95 守恒

> **作者**: W68 第 8 批 B-3 Agent (2026-07-24)
> **分支**: `feat/mobile-v3.2-share-biometric-2026-07-24` (push, 主指挥 merge)
> **commit**: (主指挥来 merge 后记录)
> **范围**: 仅 mobile composables + components + views + e2e + docs + memory
> **0 production code 改动铁律**: 维持 — 与 v3.2 PWA push (W68 第 5 批 #3) 互补, 互补而非冲突

## 摘要

W68 第 5 批 #3 (PWA push) 完成后留待办: "iOS Safari 分享 / 生物识别 仍缺". 此次 B-3 收尾 v3.2 系列 mobile 系统能力集成:

- **2 新增 composable**: `useMobileShare.ts` (250 行) + `useMobileBiometric.ts` (300 行) — Vue 3 + 严格 TS 类型 + readonly 暴露
- **2 新增 component**: `MobileShareSheet.vue` (250 行) + `MobileBiometricAuth.vue` (200 行) — Teleport + safe-area + dark mode
- **3 改动 view**: MobileSettingsView / MobileDriveView / MobileLoginView 三个集成点
- **1 新增 e2e**: `mobile_share_biometric.spec.js` 4 场景 (share text / share file / biometric success / fallback PIN)
- **1 新增 docs**: `mobile-ux-v3.2-developer-guide.md` 含 §2 share + §3 biometric
- **5 新铁律**: Web Share 必须用户手势 / WebAuthn 必须 HTTPS / fallback PIN 必留 / iOS 12.1+ 限制 / Android Chrome MIME 限制

锚点范式单调上升 W68 第 5 批 72 → W68 第 8 批 (B-3 完成时) **95 守恒** (单次 23 守恒, 跨 W68 第 7 批后 +23).

## 1. 任务背景 (W68 第 8 批派工)

**W68 第 1 批 G-1 (Mobile 语音输入)**:
报告 "未来 PR 排期 (W68 路线 G-2 ~ G-N)", 但 G-2 ~ G-N 在 W68 第 8 批前被分散到其他批次 (push / 评论 UI).

**W68 第 5 批 #3 (PWA push)**:
推送 backend 已收官. 但用户实际使用移动端时还有更高频需求:
- 分享 App 给同事 (跨平台 web Share 体验)
- 分享 Drive 文件给同事
- Face ID / 指纹解锁 (免每次输密码)

**B-3 任务定位** = 收尾 v3.2 系列移动端系统能力集成. 与 W68 第 5 批 PWA push 互补, 完成 "PWA × 系统能力" 完整拼图.

## 2. 实施详细

### 2.1 `useMobileShare` Composable

**核心接口** (全部返回 `Promise<ShareResult>`):
- `shareLink({url, title?, text?})` — 链接分享, 唤系统面板
- `shareText({text, title?})` — 纯文本
- `shareFile({file, filename?, title?, text?})` — 文件 (iOS 仅 image/video/pdf)

**降级策略** (5 级):
1. `_canShare(data)` API 检查 → 走 native
2. `AbortError` (用户取消) → 静默, `status='dismissed'`
3. 其他错误 → 降级复制 + `ElMessage.success`
4. 完全无能力 → fallback sheet 让用户选 wechat/qq/weibo/copy/save/native
5. 复制失败 (老 Safari) → `<textarea> + execCommand('copy')` 兜底

**5 工具方法**:
- `copyLink(url)` → navigator.clipboard.writeText + 老 fallback
- `copyImage(blob)` → ClipboardItem (仅现代)
- `downloadFile(blob, filename)` → a[download] pattern

### 2.2 `useMobileBiometric` Composable

**核心流程**:
1. `detectSupport()` — 探测链: PublicKeyCredential → isSecureContext → isUserVerifyingPlatformAuthenticatorAvailable → 综合判断
2. `registerWebAuthn()` — 一键生成 credential (challenge 32 字节随机 + Platform authenticator + ES256/RSA)
3. `authenticate()` — 用 stored credentialId 重挑战 + 签名
4. `registerPIN(pin)` / `verifyPIN(pin)` — 6 位数字 fallback, SHA256+host salt
5. `setBiometricEnabled(bool)` / `isBiometricEnabled()` — 用户偏好开关

**降级链** (3 级):
1. WebAuthn 成功 → 直接通过
2. WebAuthn 失败 → 自动 fallback 到 PIN 输入
3. PIN 5 次错 → 锁定 5 分钟 (类似银行 App)

**平台猜测**:
- iOS: iPhone 1[2-9]/2[0-9]/15 → 'face', 否则 'touch'
- Android: 'fingerprint'
- 其他 / 检测失败: 'none'

**安全**:
- challenge 32 字节随机 (crypto.getRandomValues, djb2 fallback)
- credentialId Base64URL 编码存 localStorage
- PIN hash SHA256 + window.location.hostname salt
- **本项目无后端 WebAuthn verify**, 这是 "本地快速解锁" 语义, 敏感操作仍需密码

### 2.3 `MobileShareSheet` 组件

**设计**:
- Teleport to body + safe-area inset + tabbar height
- 6 个内置 item: 微信/QQ/微博/复制/保存/系统分享
- 每个 item 大圆形彩色背景 + 白色 emoji + 文字标签
- v-model:show 控制 (与 MobileActionSheet 风格一致)
- dark mode 非 scoped 兜底块 (CLAUDE.md v60-v67 教训)

**事件**:
- `@share` emit payload `{key, url, text, file, filename}` — 父组件决定具体动作

**ShareData 4 类型支持**:
- wechat/qq/weibo: 暂未深度集成微信 scheme, 降级为复制链接 + 提示粘贴
- copy: copyLink() + ElMessage
- save: a[download] 下载文件
- native: navigator.share (含 file)

### 2.4 `MobileBiometricAuth` 组件

**Phase 状态机**:
- `choose` — 选择认证方式 (WebAuthn / PIN setup / PIN verify)
- `verify` — WebAuthn authenticate 中
- `pin-setup` — PIN 设置 (二次确认)
- `pin-verify` — PIN 验证

**UI 关键**:
- 大圆形图标 + pulse 动画 (waiting 时)
- PIN 6 dot 显示 (filled / error shake)
- PIN 数字小键盘 (3×4 含 ← 0 ✓)
- 锁定剩余秒数实时倒计时

**事件**:
- `@success({method})` — 验证成功
- `@cancel` — 用户关闭
- `@error` — 错误 (本项目暂未细化)

### 2.5 3 View 集成

**MobileSettingsView**:
- 新加 "分享 App" 设置项 (data-testid="share-app-item")
- 新加 "生物识别登录" 设置项 (data-testid="biometric-auth-item"), 状态: 已启用 / 可用但未启用 / 设备不支持
- onMounted 预探测 biometric 能力 (不阻塞)

**MobileDriveView**:
- 长按菜单分享升级: 原 clipboard 写链接 → 现优先 native share → fallback 弹 MobileShareSheet (含 file prop, image/pdf/video 范围)
- 通过 drive download API 拿 blob → 传 sheet.file + filename

**MobileLoginView**:
- 新加 "Face ID 一键登录" 按钮 (条件渲染: 设备支持或已设置 PIN 时)
- 点击 → MobileBiometricAuth 弹窗 → 成功提示并聚焦密码输入
- onMounted 调 `refreshBioSupport()` 决定是否显示按钮

## 3. 5 条新铁律 (核心沉淀)

### 铁律 1: Web Share 必须用户手势

```ts
// ❌ 反模式
onMounted(async () => {
  await share.shareLink({ url: '...' })  // 报错 NotAllowedError
})

// ✅ 正模式
async function onButtonClick() {
  await share.shareLink({ url: '...' })  // click 内合法
}
```

iOS Safari + Android Chrome 都会拒绝非 click/touch 内的 share call. 即使 Promise.resolve().then(...) 也算 gesture loss. 包到 `@click` handler 内即可.

### 铁律 2: WebAuthn 必须 HTTPS

```ts
// hasWebAuthn = hasPublicKeyCredential
//            && hasIsSecureContext  // window.isSecureContext
//            && hasPlatformAuthenticator

// 本地开发可用 localhost (满足 secure context)
// 部署上线必须 HTTPS, 否则 detectSupport 自动降级到 PIN only
```

无 HTTPS 的部署永远拿不到 Face ID / Touch ID. 本项目生产部署走 cloud nginx + FRP tunnel (CLAUDE.md 历史), 全部 HTTPS 已就绪.

### 铁律 3: 必须保留 PIN fallback

```ts
// 即便设备有 Face ID, 也必须:
const autoFallbackPin = computed(() => support.available)  // WebAuthn 失败时降级
```

理由:
- 设备可能临时识别失败 (汗湿 / 戴口罩 / 多人共用)
- 用户可能没注册 WebAuthn, 想用 PIN
- 老设备 / 桌面浏览器无 WebAuthn

UI 上必须显示 "改用 PIN 码" 入口, 让用户永远有 fallback.

### 铁律 4: iOS 12.1+ 才有 navigator.share

- iOS 11 及以下 → canNativeShare = false → fallback sheet
- iOS 12.0 (仅 Chrome 数据) → 仍无 → fallback
- iOS 12.1+ → 可用

本项目 iOS Safari 14.5+ 假设 (主流 PWA 用户均满足), 但代码侧 hasShare 检查已做兜底.

### 铁律 5: Android Chrome share file MIME 受限

优先支持: image/* / video/* / audio/* / text/* / application/pdf
边缘支持: .docx / .pptx / .xlsx (新版 Chrome 接受)
不支持: .doc / .xls / .ppt (老格式) → fallback

实现: `shareFile` 内部直接试 navigator.canShare, 失败 fallback 到 URL only sheet.

## 4. 0 production code 改动铁律 维持

✅ 不动后端 `/api/v1/auth/*` 或 `/api/v1/drive/*` 或 `/api/v1/notifications/*`
✅ 不动 alembic migrations
✅ 不动 docker-compose / nginx / frp 配置
✅ 不动 App.vue / router/index.js / Pinia stores
✅ 仅在 mobile frontend (composables / components / views / e2e) 增量

## 5. 测试与可观测性

### 5.1 e2e 4 场景

```js
// web/tests/e2e/mobile_share_biometric.spec.js
场景 1: 设置页 → 分享 App → 复制链接 → 剪贴板验证
场景 2: Drive → 长按文件 → 分享 sheet 出现 (含 file prop)
场景 3: Login → 生物识别按钮 → 弹窗出现 (mock WebAuthn)
场景 4: PIN 流程 → 6 位输入 + 二次确认
```

### 5.2 调试小工具

```js
// 在浏览器 console
const { useMobileShare } = await import('/src/composables/useMobileShare.ts')
const s = useMobileShare()
console.log({ isIOS: s.isIOS, canNativeShare: s.canNativeShare })

const { useMobileBiometric } = await import('/src/composables/useMobileBiometric.ts')
const b = useMobileBiometric()
const support = await b.detectSupport()
console.log(support)
// { hasWebAuthn: true, authenticatorType: 'face', displayName: 'Face ID', available: true, ... }
```

## 6. 未来方向 (W68+1 候选)

1. **后端 WebAuthn verify service** — 服务端 challenge verify, 让 WebAuthn 真能登录 (非纯本机解锁)
2. **PIN 跨设备同步** — 当聊天历史跨设备同步 (2026-06-29 #043) 加 WebAuthn 跨设备
3. **微信 scheme 深度集成** — Universal Link / URL scheme 唤起微信分享
4. **Web Share Target API** — Android Chrome 86+, 让 PWA 注册为分享接收方
5. **Passkey (FIDO2)** — iOS 16+ / Android 9+ 跨设备同步凭据, 比 WebAuthn 更用户友好

## 7. 工期与 commit

| 文件 | 行数 | 改动类型 |
|------|------|----------|
| `web/src/composables/useMobileShare.ts` | +250 | 新增 |
| `web/src/composables/useMobileBiometric.ts` | +300 | 新增 |
| `web/src/components/mobile/MobileShareSheet.vue` | +250 | 新增 |
| `web/src/components/mobile/MobileBiometricAuth.vue` | +200 | 新增 |
| `web/src/views/mobile/MobileSettingsView.vue` | +60 | 修改 |
| `web/src/views/mobile/MobileDriveView.vue` | +50 | 修改 |
| `web/src/views/mobile/MobileLoginView.vue` | +60 | 修改 |
| `web/tests/e2e/mobile_share_biometric.spec.js` | +200 | 新增 |
| `docs/mobile-ux-v3.2-developer-guide.md` | +250 | 新增 |
| `memory/w68-route-8-b3-mobile-share-biometric-2026-07-24.md` | +200 | 本文件 |

**总: 10 文件, ~1820 行, 单 commit**.

## 8. 复盘 (post-completion)

**做对的**:
1. 复用 useHaptic + useMobileSafeArea + ElMessage 等已有 utilities, 不重新发明轮子
2. composable 全部 readonly ref 暴露, 父组件 ref 解构也不会破坏响应式
3. component 全部 Teleport + safe-area, 不破坏 Element Plus 假设
4. dark mode 双块结构 (scoped + 非 scoped 兜底), 完美兼容 v60-v67 第 5 次强化教训
5. e2e mock 合理 (delete navigator.share, stub PublicKeyCredential), 不依赖真实设备

**有改进空间** (W68+1 候选):
1. 后端 WebAuthn verify 端点未实装, 目前仅"本机解锁"语义, 真敏感操作仍需密码
2. 微信/QQ/微博 scheme 未深度集成, 降级为复制链接 (留作未来 PR)
3. PIN 忘记后无 recovery 入口, 仅 `bio.reset()` 清空
4. 触觉反馈 (haptic) 仅在 sheet item click 调用, 验证成功/失败也可加强

---

**Commit 信息模板**:
```
feat(mobile-v3.2): iOS Safari 分享 + 生物识别集成 (W68 第 8 批 B-3)

useMobileShare.ts (Web Share API + fallback sheet + 5 工具方法)
useMobileBiometric.ts (WebAuthn + 6 位 PIN fallback + 5次锁5分钟)
MobileShareSheet.vue (6 item 自定义分享面板)
MobileBiometricAuth.vue (Face ID/Touch/指纹 + PIN 二次确认)
MobileSettingsView (分享 App + 生物识别登录设置项)
MobileDriveView (文件分享 → 优先 native → fallback sheet)
MobileLoginView (Face ID 一键登录按钮)
mobile_share_biometric.spec.js (4 场景 e2e)
mobile-ux-v3.2-developer-guide.md (§2 share + §3 biometric)
memory 沉淀 (锚点范式第 95 守恒 + 5 新铁律)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

锚点范式第 95 守恒 + v3.2 移动端系统能力集成完整闭环.
