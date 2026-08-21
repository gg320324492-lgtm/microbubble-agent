# MicroBubble Desktop — 3 客户端架构

> 本文件描述 MicroBubble Agent 的客户端拓扑关系。
> **冻结于 Phase 0-Impl-1**。后续 Phase 改动需在 PR 中同步更新本文档。

---

## 1. 三方拓扑

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       小气实验室 / 外网用户电脑                              │
│                                                                          │
│   ┌──────────────────────┐                ┌──────────────────────────┐  │
│   │   Browser Client     │                │   Desktop Client         │  │
│   │   (web/ — legacy)    │                │   (desktop/ — NEW)       │  │
│   │                      │                │                          │  │
│   │  Vue 3 + Vite        │                │  Electron +              │  │
│   │  Element Plus        │                │  Vue 3 + TS              │  │
│   │  浏览器内 PWA         │                │  独立进程 + 系统集成     │  │
│   │                      │                │                          │  │
│   │  ★ 跨平台               │                │  ★ Win 首批 (Phase 5+ 加 Mac)  │  │
│   │  ★ 即开即用               │                │  ★ 系统托盘 + 通知 + 快捷键    │  │
│   └──────────┬───────────┘                └────────────┬─────────────┘  │
│              │                                          │                │
│              │  HTTPS (JWT)                  HTTPS (JWT)               │
│              │  + WS                          + WS                      │
└──────────────┼──────────────────────────────────────────┼────────────────┘
               │                                          │
               ▼                                          ▼
      ┌──────────────────────────────────────────────────────────┐
      │                                                          │
      │              FastAPI Backend (app/)                      │
      │              (Legacy — 完全不动)                           │
      │                                                          │
      │   ┌────────────────┐  ┌─────────────────┐                │
      │   │ 31 API 端点   │  │ WebSocket 推送  │                │
      │   │ JWT 鉴权       │  │ Celery 异步     │                │
      │   │ 4 限流 tier   │  │ Redis 缓存      │                │
      │   └────────────────┘  └─────────────────┘                │
      │                                                          │
      └──────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │   PostgreSQL + Redis + OSS    │
                  │   (legacy — 完全不动)         │
                  └──────────────────────────────┘
```

---

## 2. 客户端分工

### 2.1 Browser Client (`web/`)

**角色**: Web 端 legacy / fallback

**保留原因 (用户决策)**:
1. 渐进过渡期间必须可用，不能强制升级
2. 无需安装，跨平台访问门槛低
3. 校外 / 偶尔访问用户首选

**Phase 0 行为**:
- 0 改动，100% 保留
- 未来 Phase 5 加 "🖥️ 下载桌面端" 按钮 + DownloadView

---

### 2.2 Desktop Client (`desktop/`)

**角色**: 主客户端 (Phase 0 起步，Phase 6 公测)

**目标体验**:
1. Win 系统级安装 (.exe 安装器)
2. 系统托盘常驻 + 关闭主窗口不退出进程
3. 原生通知 (会议 / 任务提醒 / AI 思考完成)
4. 全局快捷键 (Ctrl+Shift+A 新会议)
5. 自动后台更新 (electron-updater)

**与 Browser 共享**:
- 后端 API (完全相同)
- 数据库 (完全相同)
- JWT 鉴权体系 (Desktop 不另立账号)

**与 Browser 不共享**:
- UI 渲染层 (完全独立的 Vue 3 工程)
- 状态管理 (Pinia vs Web 的 useXxx composable)
- 路由表 (1:1 映射但独立维护)

---

### 2.3 FastAPI Backend (`app/`)

**角色**: 服务端 (legacy — 完全不动)

**接口总数**: 31 个 REST 端点 + N 个 WebSocket

**鉴权**: JWT bearer，所有 31 端点已 require_auth

**Desktop 消费关系**:
- 0 后端代码改动
- 全部 31 端点视为可消费 API
- 后端无需为 Desktop 加任何特殊处理

---

## 3. 通信协议

### 3.1 三层通信栈

| 层 | 协议 | 用途 |
|---|------|------|
| 桌面端 → 后端 | HTTPS + JWT | REST API 调用 |
| 桌面端 → 后端 | WSS (Secure WebSocket) | 实时推送 (通知 / 任务状态) |
| 桌面端内部 (main ↔ renderer) | Electron IPC | contextBridge 暴露的 invoke/on 子集 |

### 3.2 后端 URL

| 用途 | URL |
|------|-----|
| 生产 API base | `https://agent.mnb-lab.cn/api/v1` |
| 生产 WS base | `wss://agent.mnb-lab.cn/api/v1/ws` |
| 开发 (本地后端) | `http://localhost:8000/api/v1` (Phase 1 启用) |

Phase 0 不连真后端，Renderer 仅跑 ping/pong demo 验证本地 IPC。

---

## 4. Desktop 内部架构

```
┌──────────────────────────────────────────────────────┐
│                  Electron App                         │
│                                                        │
│  ┌────────────────┐  ┌────────────────┐               │
│  │ Main Process   │  │ Preload Script │               │
│  │ (Node.js)      │  │ (sandboxed)    │               │
│  │                │  │                │               │
│  │ app lifecycle  │◄─┤ contextBridge  │               │
│  │ BrowserWindow  │  │ → window.api   │               │
│  │ IPC handler    │  │                │               │
│  │ safeStorage    │  │ (Phase 1+)     │               │
│  │ electron-store │  │                │               │
│  └────────────────┘  └────────────────┘               │
│         ▲                                              │
│         │ IPC (ipcMain.handle / on)                    │
│         ▼                                              │
│  ┌──────────────────────────────────┐                  │
│  │ Renderer (Chromium)              │                  │
│  │                                  │                  │
│  │ Vue 3 + Pinia + Element Plus     │                  │
│  │ CSP locked (no eval / inline)    │                  │
│  │ webSecurity: true                │                  │
│  └──────────────────────────────────┘                  │
└──────────────────────────────────────────────────────┘
```

---

## 5. 镜像工作流 (Phase 0 起步)

| 步骤 | 输出 |
|------|------|
| Phase 0-Impl-1 ✅ | desktop/ 工程 + 三进程骨架 + IPC demo + 安全基线 + docs |
| Phase 1 (规划) | 完整鉴权 + Pinia + IPC 白名单扩到所有 31 端点 |
| Phase 2 (规划) | P0 六模块迁移 (Vue 3 全重写 1:1) |
| Phase 3 (规划) | P1 四模块 + 原生通道 |
| Phase 4 (规划) | EV 证书 + electron-updater 自动发布 |

---

## Status (2026-08-21)

- ✅ Phase 0-Impl-1 起步架构冻结
- ⏳ Phase 1 等主拍决策后启动
