# 2026-07-24 W68 第 8 批 A-2: Drive v2 PR9-11 Master Runbook 整合

> **锚点范式第 91 守恒** — 跨 W68 第 5 批 + 第 7 批 runbook 整合, master runbook 总入口收口

## 任务背景

W68 第 5 批 + 第 7 批已建多个 Drive v2 部署文档:
- **W68 第 5 批 H-1** `docs/drive-v2-pr9-deployment-runbook.md` (~446 行, PR9 SSH 12 步)
- **W68 第 3 批 H-1** `docs/drive-v2-pr9-deployment.md` (~340 行, PR9 详细迁移说明)
- **W68 第 7 批 D-2** `docs/drive-v2-pr10-deployment-runbook.md` (~227 行, PR10 协同 WS)

主指挥需要**统一索引** — 部署前查哪个文件? 多份文档散落, 主指挥运维负担大。

## 完成内容

1. **新建** `docs/drive-v2-pr9-11-deployment-master-runbook.md` (~280 行)
   - 第 0 节 总览: PR9 + PR10 + PR11 部署顺序表 (1 张)
   - 第 1 节 SSH 部署 18 步 (W68 第 5 批 + 第 7 批综合, 含 pycrdt + pywebpush 安装)
   - 第 2 节 alembic 链风险 (复用 W68 第 3 批纪律, 单链 061→062→063→064→065)
   - 第 3 节 验证脚本 4 用法 (PR9 + PR10 + WS 真连)
   - 第 4 节 6 个常见问题 FAQ 摘要 (完整 FAQ 见独立文档)
   - 第 5 节 回滚方案 (alembic downgrade -1 + docker restart)
   - 第 6 节 文档索引 (8 个文件路径表)

2. **新建** `docs/drive-v2-deployment-troubleshooting-faq.md` (~310 行)
   - Q1: alembic `Multiple head revisions` (PR9 + PR10 合并后)
   - Q2: `Can't locate revision identified by '062/063/064/065'`
   - Q3: `relation "drive_comments" already exists` (重复迁移)
   - Q4: `column ... does not exist` 500 (部署后)
   - Q5: WebSocket 超时 (WS 路由 4401/4403)
   - Q6: pycrdt import error (`ModuleNotFoundError`)
   - Q7: Push 失败 410 (订阅自动清理)
   - Q8: VAPID 密钥丢失 (deployment 提示重启后订阅失效)
   - 总结表 (8 问题 / 解决路径 / 预防措施)

3. **修改** `docs/drive-v2-pr9-deployment.md` (顶部加 1 行引用 master runbook)
   - 原顶部 1 行 → 改为 2 行: master runbook 总入口 + 单 PR runbook 12 步

4. **修改** `docs/drive-v2-pr9-deployment-runbook.md` (顶部加 1 行注明已合并)
   - 原顶部 1 行 → 改为 2 行: master runbook 整合说明 + 单 PR runbook 范围

## 3 新铁律沉淀

### 铁律 1: master runbook 索引

> **主指挥部署前必须先查 master runbook** (`docs/drive-v2-pr9-11-deployment-master-runbook.md`) — 总入口包含 PR9 + PR10 + PR11 部署顺序 + 18 步 SSH + alembic 链 + 验证脚本 + FAQ 摘要。单 PR runbook 保留作为参考但不重复 master runbook 内容。

**执行细节**:
- 任何跨多 PR 的部署任务, **必须**有 master runbook 索引
- 单 PR runbook 顶部加 1 行引用 master runbook (避免主指挥误以为散落多份)
- master runbook §6 文档索引表是**唯一**查文档路径的位置, 其他文档不维护路径表

### 铁律 2: FAQ 集中化

> **跨多 PR 的故障 FAQ 必须独立文档**, 不散落在各 PR runbook。`docs/drive-v2-deployment-troubleshooting-faq.md` 集中所有 Drive v2 PR9 + PR10 + 未来 PR11 的故障 Q&A。

**执行细节**:
- 故障 FAQ 集中避免主指挥排错时切多份文档
- 总结表 (Q + 解决路径 + 预防) 让主指挥一眼定位问题
- 单 PR runbook 仅保留 §6 "常见问题" 简短摘要, 完整 FAQ 见独立文档

### 铁律 3: 历史 runbook 保留为参考

> **单 PR runbook 不删除**, 即使已合并到 master runbook。顶部加 1 行 "已合并到 master runbook, 本文件保留作为 <PR> 单 PR 参考" — 历史文档保留, 主指挥部署 PR9 单 PR 时仍可查原版。

**执行细节**:
- 不删除历史 runbook (避免 git 历史追溯断裂)
- 顶部加 1 行 master runbook 链接 (主指挥一眼看到)
- 单 PR runbook 与 master runbook 内容可重叠 (master runbook 摘要 + 单 PR 详细)

## 0 production code 改动铁律维持

本任务**仅 docs/**:
- 新建 2 个文档 (master runbook + FAQ)
- 修改 2 个文档顶部 1 行引用 (drive-v2-pr9-deployment.md + drive-v2-pr9-deployment-runbook.md)
- 新建 1 个 memory 文件

**无 alembic / 路由 / ORM 改动**, 严格遵守 W68 第 8 批任务模式基调 (plans 优先 + 小修搭配 + 0 production code 改动铁律维持)。

## 锚点范式进度

- **W68 第 4 批**: 57 (单批 27 历史新高)
- **W68 第 5 批**: 58-72 (15 agents 派工, 含 PR9 + PR10 + 部署 runbook)
- **W68 第 7 批**: 73-90 (跨主题小修 + 部署验证脚本 + Plan 闭环 2)
- **W68 第 8 批 (本批)**: 91+ (master runbook 整合 + FAQ 集中 + 历史 runbook 索引)

## 文档交付

| 文档 | 类型 | 行数 | 范围 |
|------|------|------|------|
| `docs/drive-v2-pr9-11-deployment-master-runbook.md` | 新建 | ~280 | PR9 + PR10 + PR11 总入口 |
| `docs/drive-v2-deployment-troubleshooting-faq.md` | 新建 | ~310 | 8 故障 Q&A 集中 |
| `docs/drive-v2-pr9-deployment.md` | 顶部 +1 行 | +1 | master runbook 引用 |
| `docs/drive-v2-pr9-deployment-runbook.md` | 顶部 +1 行 | +1 | master runbook 引用 |
| `memory/w68-route-8-a2-pr9-11-master-runbook-2026-07-24.md` | 新建 | ~150 | 本文件 |

总计: 1 新建 master + 1 新建 FAQ + 2 改动 (顶部 +1 行) + 1 新增 memory = **5 文件**

## 后续任务

- **W69 PR11**: 离线缓存 + 编辑器集成 + 桌面端 review UI 优化
  - master runbook §0 总览表追加一行 (PR11 状态: 待开发)
  - master runbook §1 SSH 18 步 → 24 步 (PR11 6 步: 离线缓存安装 + 编辑器集成 + review UI)
  - FAQ Q1-Q8 视情况追加 PR11 专属问题 (如离线缓存冲突解决)
- **主指挥 merge 后**: 触发 webhook → 浏览器硬刷 → 验证 master runbook 索引链接全部可点击

## 记忆锚点

- **任务模式基调**: W68 第 8 批 A-2 是 plans 优先 + 小修搭配的代表 — 5 文档任务全是引用 / 索引类, 0 production code 改动, 严格遵守锚点范式第 91 守恒
- **跨 PR 部署索引模式**: W68 第 8 批确立的 "master runbook + FAQ 集中 + 历史 runbook 保留" 三件套, 可推广到其他大型功能 (Drive v3 / 知识库 v2 等)
- **0 production code 改动铁律**: 本任务 13/15 守恒 (W68 第 5 批 H-1 + 第 7 批 D-2 runbook 是已有文档, 不算新 production code)
- **锚点范式第 91 守恒**: 跨 W68 第 5 批 + 第 7 批文档整合, master runbook 统一入口避免主指挥运维负担

## Co-Authored-By 标记

本文档末尾已加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 标记 (memory 文件无 commit, 仅文档 commit)。

---

*W68 第 8 批 A-2 (2026-07-24). 锚点范式第 91 守恒 — master runbook 总入口 + FAQ 集中 + 历史 runbook 保留三件套, 跨 PR 部署索引模式首立.*