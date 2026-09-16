# 桌面端重做骨架设计（M0-M2）

> 2026-09-13 · 基于 9-08 蓝本《desktop-ui-migration-and-release.md》展开，补齐开工前三块缺口：
> **账号模型 / 本地数据模型 / 模块 v1 范围**。安全基线与登录页视觉规格自归档 tag
> `archive/desktop-before-redo-20260913` 回收。本设计定稿后，N1/N2/N3 可直接开工。

## 0. 决策记录

| # | 决策 | 结论 | 来源 |
|---|------|------|------|
| D1 | 技术栈 | Electron + electron-vite + Vue 3 + TS + Pinia + Element Plus + better-sqlite3 | 9-08 蓝本 |
| D2 | 定位 | 真桌面原生软件，不加载 web/dist，断网核心功能可用 | 9-08 蓝本 |
| D3 | 一致性 | pnpm monorepo 共享包（design-tokens / shared-types / api-client / ui） | 9-08 蓝本 |
| D4 | **账号模型** | **本地账号注册/登录 + 可选绑定网页端账号** | 2026-09-13 用户拍板 |
| D5 | **协作数据** | **能本地尽本地（修订）**：各模块主数据一律本地 SQLite/文件存储，云端降级为可选的"导入/同步"来源；实际验收不过的功能直接从桌面端删除、保留网页端（见 §3.1 淘汰机制） | 2026-09-13 用户拍板（两次修订） |
| D6 | 分发 | GitHub 存源码 + 阿里云 OSS/CDN（`releases.mnb-lab.cn`）+ electron-updater | 9-08 蓝本 |
| D7 | 旧实现 | 全部删除，归档 tag 可查；只回收安全基线 / 登录页规格 / 发布门禁清单 | 2026-09-12 拍板 |

## 1. 账号与登录

### 1.1 模型

```
首启检测 users 表为空 ──> 「创建管理员账号」页（复用登录页视觉，标题/文案切换）
users 表非空          ──> 登录页（本地校验，scrypt，不依赖网络）
登录成功              ──> 主界面；协作模块是否可用取决于云端绑定状态
```

- **本地账号**：`users` 表（id / username / display_name / password_hash / role / is_active / created_at / updated_at）。密码哈希沿用旧版已验证格式 `scrypt$16384$8$1$salt$hash`（实现参考归档 `desktop/src/main/services/security/auth.service.ts`）。
- **首启注册**：单机软件自己就是管理员——第一注册人自动 `role=admin`，后续注册由管理员在设置页创建（不再出现旧版"请联系系统管理员"的死锁文案）。
- **会话**：`user_sessions` 表 + 32 字节随机 token，60min 滑动续期；session token 只存主进程内存 + 表，**永不过 IPC 暴露给 renderer**（renderer 只持 `user` 对象与过期时间）。
- **云端绑定（可选）**：设置页「绑定网页端账号」→ 调 `POST /auth/login`（云端）→ refresh token 进 `safeStorage`（Win DPAPI）加密落盘。绑定的用途：**从网页端一次性导入数据到本地库**（§3 M2）+ 后续可选的双向同步（M5）。不绑定则除导入外全部功能可用。
- **多用户**：同机多账号互相切换；聊天历史、偏好按 `user_id` 隔离。

### 1.2 断网行为矩阵

| 功能 | 断网 | 未绑定云端 |
|------|------|-----------|
| 本地注册/登录 | ✅ | ✅ |
| AI 助手（对话） | ❌ 云端模型不可用（本地模型后置） | ✅（用户自配模型 key 即可用） |
| 知识库 / 会议档案 | ✅ 导入后本地可用（检索/浏览/编辑） | ✅（联网仅"导入"动作需要） |
| 设置 / 偏好 | ✅ | ✅ |

### 1.3 旧断点修复验收（铁律）

登录**只走本地 IPC** `auth:local:*` 通道，任何登录路径不得发起网络请求。验收：断网状态从头注册→登录→进主界面全流程可跑。登录页视觉沿用归档《2026-08-26-desktop-login-ui-design.md》（双栏/令牌/a11y 全保留），仅改两处文案：首启态"创建管理员账号"、副文案"账号保存在本机"现在是真实行为。

## 2. 本地 SQLite 数据模型（v1 只建 M0-M2 所需）

新建迁移链 `001 → …`，**不搬运**旧版 19 个迁移；每个里程碑按需追加一个迁移。

| 迁移 | 表 | 服务于 |
|------|----|--------|
| 001 | `users`, `user_sessions` | 账号（§1） |
| 002 | `settings`（key-value，含 per-user 作用域） | 偏好/窗口状态/模型配置 |
| 003 | `chat_sessions`, `chat_messages` | M1 AI 助手 |
| 004 | `knowledge_documents`（含标签/来源） + FTS5 虚表 | M2 知识库（本地全文检索；向量检索后置 sqlite-vec） |
| 005 | `meetings`, `transcripts`, `attachments`（本地文件引用） | M2 会议档案 |
| （后置） | `tasks` 等协作表、ELN/稿件表 | M3+ 各里程碑自行追加 |

原则：**模块主数据一律本地表**（D5 修订）；云端只是导入/同步来源，不再是运行时依赖。

## 3. 模块范围切分（六项 IA → 里程碑）

| 里程碑 | 内容 | 明确不做（本期） |
|--------|------|------------------|
| **M0 骨架+账号** | monorepo 起步、无边框窗口+自绘标题栏、侧边栏/状态栏壳、本地注册/登录、设置壳 | 托盘/快捷键/命令面板 |
| **M1 AI 助手** | 对话界面 + 流式 + 模型网关（用户自配 MiMo/MiniMax key，参考归档 model-gateway）+ 会话历史（SQLite） | 文件操作 ReAct 循环（归档 FileAgentLoop 方案，M4+ 再议） |
| **M2 知识库+会议** | **本地知识库**（本地表 + FTS5 全文检索 + Markdown/附件本地文件）与**本地会议档案**（纪要/转录/附件）；「从网页端导入」向导（绑定云端后拉取既有数据写入本地库，一次性/可重复增量） | 实时声纹通话、录音、向量化语义检索 |
| M3 ELN+稿件 | 本机数据，本地建表 | — |
| M4 桌面集成 | 托盘、原生通知、全局快捷键、命令面板（= 蓝本 N4） | — |
| M5 同步引擎 | 本地库 ⇄ 云端**双向同步/备份**（本地是主库，云端是协作副本；= 蓝本 N5 方向对调，届时单独出设计） | — |
| M6 发布 | electron-updater + 阿里云 OSS/CDN 通道（= 蓝本 N6+第二节） | — |

### 3.1 本地优先与验收淘汰机制（2026-09-13 用户拍板）

1. **能本地尽本地**：每个模块设计时先问"断网能不能用"——数据存本地、交互在本地完成；唯一允许的外部依赖是**模型推理 API**（用户自配 key，聊天历史/配置仍全本地）。
2. **验收底线 = 断网可用**：每个里程碑验收时拔网线测；不过线就修到过线。
3. **淘汰制**：某功能实际验收后确实做不好本地版（成本/体验不成立），**直接从桌面端删除该功能，不回退成云端依赖**——该功能继续留在网页端使用。桌面端宁缺毋滥。
4. 验收期网页端保持原样不动，作为功能兜底。

> 开放点 A：蓝本六项 IA 没有「任务/网盘」入口。按新原则建议做**本地任务表 + 网页端导入**（M2 或 M3 附加），验收后决定去留。待拍板。
> 开放点 B：实时声纹会议是否进桌面，影响 M3+ 排期，待拍板。

## 4. 工程结构（N1 起步）

```
microbubble-agent/
├─ packages/
│  └─ design-tokens/        # web variables.css 迁入，两端 import（蓝本 N1）
├─ apps/desktop/            # electron-vite 三进程（src/main | preload | renderer）
├─ web/                     # 不动；共享包接入后置（蓝本 N6）
└─ docs/superpowers/        # 本设计所在
```

第一阶段**只做** `packages/design-tokens` + `apps/desktop`，不做 web 的 monorepo 改造（降低对生产 web 的扰动）；`shared-types`/`api-client` 在 M2 接云端时再抽。

## 5. 安全基线（自归档 security.md 全量回收，与旧版同等效力）

- **三铁律**：`contextIsolation: true` / `nodeIntegration: false` / `sandbox: true`；CSP 锁死（`connect-src` 仅加 `https://agent.mnb-lab.cn` 及 `wss://`）。
- **IPC 白名单**：renderer 仅见 `window.api.*`，channel 按域命名（`auth:local:login`、`auth:cloud:bind`、`chat:stream`、`cloud:request`、`settings:get/set`…）；禁止暴露 `ipcRenderer` 裸通道。
- **Token 分级**：本地 session 留主进程；云端 refresh token 只进 `safeStorage`（DPAPI），解密失败=强制重新绑定，不抛阻塞；localStorage/sessionStorage 禁存任何凭据。
- **导航拦截**：`will-navigate` preventDefault；外链 `shell.openExternal`；禁 `window.open`/webview。
- **供应链**：`npm ci` + lock 提交；NSIS `oneClick=false`；更新签名 ed25519（M6）。

## 6. 测试策略

- TDD 沿用旧纪律：契约测试先行（登录页组件测试即归档范例）。
- 每个 IPC channel 一条契约测试（白名单即测试清单）。
- Playwright 冒烟自 M1 起：注册→登录→发起对话→收到流式回复。
- 每批门禁：`vitest` + `typecheck` + `build` + **保护路径守卫**（回收归档 R0 思路：开发 desktop 期间 `app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*` 零改动，脚本校验）。

## 7. 发布执行清单（补全蓝本第二节，M6 前细化）

版本通道 latest/beta 分文件；`.blockmap` 增量更新；发布检查单 = 签名记录 + 干净机安装/升级/卸载重装 + 断网冒烟 + 更新源三件套同版本校验 + 回滚预案（保留上一版 exe 与 latest.yml 备份）。

## 8. M0 验收标准（下一双手的活）

1. `pnpm i && pnpm --filter desktop dev` 起应用：无边框窗口、自绘标题栏可拖拽/最小化/关闭、侧边栏六项导航壳、底部状态栏（版本号）。
2. 断网状态：创建管理员账号 → 退出 → 登录 → 进主界面（§1.3 铁律验收）。
3. `vitest` / `typecheck` / `build` 全绿；保护路径守卫通过。
4. electron-builder 产出可安装 exe（未签名可接受，安装后可跑通第 2 条）。
