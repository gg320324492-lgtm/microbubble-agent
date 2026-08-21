# MicroBubble Desktop 转换 v1 — 总计划 (Phase 0 起步版)

> **锚点范式**: 本计划为 W100 +N 全新 grand closure 项目。起点 = 当前 W100 +N 据实累计。
>
> **决策链 (2026-08-21 用户拍板 5 件)**:
> - 框架 = **Electron** (最完善 + 彻底; Node 主进程 = 团队栈)
> - 连接深度 = **纯 C — 全新原生客户端** (Vue 3 Renderer 全重写, 直接调后端 API)
> - 平台 = **Windows 首批**
> - 分发 = **公网 + Win EV 证书 + electron-updater 自动更新**
> - 节奏 = **2-3 月发 v1.0**

---

## 0. 现状与目标

| 维度 | 当前 | 目标 |
|------|------|------|
| 客户端形态 | 100% web 浏览器 | Web 保留 + 桌面端 .exe |
| 后端 | FastAPI (107 alembic head) | 0 改动 |
| 团队体验 | 跨浏览器 + PWA 缓存 | 系统托盘 + 原生通知 + 全局快捷键 |
| 分发 | nginx + FRP 隧道 | 安装器 + 自动更新 |
| 节奏 | 持续 web PWA 迭代 | 渐进迁移 → 退役 web |

---

## 1. 用户原始需求 (逐字)

1. "先转换桌面端的计划"
2. **"网页端也保留，会留下一个桌面端的下载按钮"**
3. **"之后我们逐步转到桌面端"** ← 关键词：逐步
4. "不再使用网页端" ← 长期目标

---

## 2. Phase 分解 (~70 工作日 / ~62 commits 据实累计)

| Phase | 时长 | 交付物 |
|-------|------|--------|
| **Phase 0** | 3d | Electron 三进程骨架 + 登录 PoC + 类 20.E 沉淀 ← **当前** |
| **Phase 1** | 7d | Vue Router + Pinia + 鉴权完整 + IPC 白名单 |
| **Phase 2** | 25d | P0 六模块迁移: 仪表盘/任务/知识库/会议/文件/提醒 |
| **Phase 3** | 15d | P1 四模块 + 托盘/通知/快捷键/文件关联 |
| **Phase 4** | 7d | EV 证书 + electron-updater + electron-builder + CI |
| **Phase 5** | 5d | 团队内测 + web 改造 (下载按钮 + 下载页) |
| **Phase 6** | 持续 | 公测 + web 渐进退役 |

---

## 3. 仓库布局

```
microbubble-agent/
├── web/                           (legacy, 保留)
├── desktop/                       (NEW, 本计划主体)
│   ├── src/{main,preload,renderer,shared}/
│   ├── resources/                 (icon / tray / installer)
│   ├── electron.vite.config.ts
│   ├── electron-builder.yml
│   └── package.json
└── docs/desktop-conversion/
    ├── plan-v1.md                 (本文件)
    ├── architecture.md            (3 客户端关系图)
    ├── security.md                (Electron 安全原则)
    └── runbook.md                 (Phase 0 后续)
```

---

## 4. 5 件套守恒

| 件 | 守恒目标 |
|---|----------|
| 1 alembic | 0 后端 migration 改动 |
| 2 pytest | web 零影响; desktop vitest 独立 |
| 3 PWA build | web PWA 继续; desktop build 加入 CI |
| 4 0 production code | web 端不动; desktop 是新模块 |
| 5 锚点范式 | W100 +N 据实累计 |

---

## 5. 类 20.E 新铁律 (Phase 0 沉淀)

| 编号 | 主题 |
|------|------|
| **E-1** | electron-vite + Win Electron cache 必须并发安全 |
| **E-2** | electron-updater `app-update.yml` 必须含 ed25519 pubkey |
| **E-3** | Win DPAPI token 加密失败 fallback 重新登录，不抛阻塞 |
| **E-4** | ASAR unpack 必要资源 (icon / tray / native) |
| **E-5** | IPC contextBridge 严格白名单，禁直接暴露 `ipcRenderer.send` |

---

## 6. Phase 0 当前进度 (Phase 0-Impl-1 完成)

- [x] desktop/ 工程脚手架 (package.json / tsconfig 三件 / vite / builder)
- [x] main / preload / renderer 三进程骨架
- [x] IPC 链路验证 (ping/pong demo)
- [x] 安全基线 (contextIsolation + sandbox + CSP + preload whitelist)
- [x] docs 三件套 (本文件 + architecture + security)
- [x] npm install / dev / build / tsc 三件套验证
- [x] 1 commit (Phase 0-Impl-1)

---

## 7. Open Decisions (主拍确认)

1. EV 证书供应商 (Tucanos / Certum / DigiCert)
2. 公网分发 endpoint (GitHub Releases / 自建 releases.mnb-lab.cn)
3. Phase 1 起步授权

---

## Status (2026-08-21 起步)

- ✅ Phase 0-Impl-1 完成
- ⏳ Phase 1 起步待主拍确认
- 📂 工作分支: `claude/desktop-conversion-plan-12aa22`
