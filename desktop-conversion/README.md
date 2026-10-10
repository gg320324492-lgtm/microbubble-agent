# desktop-conversion — 桌面端转化指挥部

> 本文件夹是「小气 · 科研工作台」桌面端建设的**工单 / 验收 / 决策归档区**。
>
> **2026-10-10 变更**：本目录原为独立 git 仓库（`gg320324492-lgtm/microbubble-desktop-conversion`，
> 193 commits），现已按"方案 C：只搬文件、不带历史"并入主仓 `microbubble-agent`。
> 主仓不再 ignore 本目录，内容由主仓统一跟踪。下方"目录结构"与工作方式均未变。
> 桌面端 Agent 的工作区即本文件夹：工单、验收、决策、以及 Agent 的文件操作都在这里进行。

## 目录结构

```
desktop-conversion/
├─ AGENT.md                 # Agent 行为守则（工作区说明，Agent 每次任务自动注入）
├─ docs/
│  ├─ plans/                # 总体计划（骨架设计定稿、9-08 UI原生化+发布蓝本）
│  ├─ workorders/           # 执行工单（一次一张，总指挥签发）
│  ├─ acceptance/           # 验收记录（工单执行完由总指挥填写结论）
│  ├─ decisions/            # 决策记录（DECISIONS.md，只增不改）
│  └─ session-log/          # 总指挥会话简报（接续上下文用）
└─ （Agent 的工作产出也在本仓库内，按 AGENT.md 约定存放）
```

## 新窗口接手

打开本目录后，先读 `docs/session-log/` 最新简报 → `docs/decisions/DECISIONS.md` →
`docs/plans/`，即可接续总指挥工作（接手指令见会话简报末尾）。

## 与原项目的关系

- 桌面端应用代码（`apps/desktop`）位于上层 monorepo 的 `apps/desktop/`（本仓已跟踪）
- 本目录只承载**过程性文档**（工单 / 验收 / 决策 / 会话简报），不含可执行代码
- 历史提交（193 commits）留在原私有远端 `gg320324492-lgtm/microbubble-desktop-conversion` 作归档保留
