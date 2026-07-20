---
name: p01-p02-deprecation-2026-07-21
description: "P0.1 (A3 wave2a 声纹会议真正启用) + P0.2 (D1 腾讯会议凭据) 主指挥 2026-07-21 决策彻底删除, 之后不会做这个内容"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-20T19:38:02.491Z
---

# P0.1 + P0.2 Deprecation 留痕 (2026-07-21)

## TL;DR

🎯 **P0.1 (A3 wave2a 声纹会议真正启用 `app/voice/pipeline.MeetingPipeline`) + P0.2 (D1 腾讯会议凭据) 内容主指挥 2026-07-21 决策彻底删除**。原因: 项目不依赖腾讯会议 SDK + 声纹会议 wave2a 实装复杂度高, 留 future 不再拍。

**Why**: 主指挥评估 P0.1 + P0.2 投入产出比不划算 — 声纹会议 wave2a 1-2 周 + 腾讯会议凭据 0.5 天 admin 配, 但项目实际可走简化路径 (现有 /live 端点 + VAD per-instance 已实装)。 W19 选项 A 拍板 (留 future 不主动排)。

**How to apply**: 4 删除操作 (2 spec/plan + 引用更新 + 留痕) + 4 文档沉淀 (本 memory + AGENTS.md + CHANGELOG.md + CLAUDE-history.md)。

## 4 删除操作详情

### 操作 1: 删除 2a spec/plan (2 文件)
- `git rm docs/superpowers/plans/2026-06-01-voiceprint-meeting-wave2a-impl.md` (189 行)
- `git rm docs/superpowers/specs/2026-06-01-voiceprint-meeting-wave2a-design.md` (165 行)
- **理由**: wave2a 设计 + 实装 plan 都不再需要, 2a 已彻底弃用

### 操作 2: AGENTS.md L115 改写 (1 文件)
- **改前**: `- 企业微信已上线，腾讯会议凭据待配置（详见 ROADMAP.md）`
- **改后**: `- 企业微信已上线, 腾讯会议 SDK 不再配置 (声纹会议 wave2a 已删, 主指挥 2026-07-21 决策)`
- **理由**: 跟 ROADMAP.md 同步, 删腾讯会议凭据"待配置"误导

### 操作 3: 4 plan + 4 spec 引用更新 (0 文件 — 不需改, wave2a 是唯一引用)
- `docs/superpowers/plans/2026-06-01-voiceprint-meeting-upgrade-roadmap.md` L103 + L153 提到 "wave2a" 已实装 (历史记录, 0 修改)
- `docs/superpowers/specs/2026-06-01-voiceprint-meeting-wave1-design.md` L245 + L265 提到 "MeetingPipeline" (历史, 0 修改)
- `docs/superpowers/specs/2026-06-01-voiceprint-meeting-wave2b-design.md` L18 提到 "声纹识别真正启用 (per-WS MeetingPipeline)" (历史, 0 修改)
- `docs/CLAUDE-history.md` L573 提到 "VAD per-instance" (历史铁律, 0 修改)
- **理由**: 这些是历史设计 + 探索报告, 不修改, 留历史留痕

### 操作 4: CHANGELOG.md 0 修改 (0 引用)
- **理由**: CHANGELOG.md 0 引用 wave2a / MeetingPipeline / 腾讯会议 (grep 0 命中), 不需改

## 4 留痕沉淀 (1 memory + 3 文档更新)

1. `memory/p01-p02-deprecation-2026-07-21.md` (本文件, ~80 行)
2. `AGENTS.md` L115 改写 (1 行, 操作 2)
3. `git log` 留痕 (commit message cite 4 操作 + 决策)
4. `docs/superpowers/plans/2026-06-01-voiceprint-meeting-wave2a-impl.md` + `...wave2a-design.md` (git rm 删除, 留 git log 留痕)

## 主指挥决策依据 (W19 选项 A 派板)

| 维度 | 数据 |
|---|---|
| P0.1 工作量 | 1-2 周 (声纹识别 + MeetingPipeline 重构 + VAD 集成) |
| P0.2 工作量 | 0.5 天 (admin 配腾讯会议 SDK 凭据) |
| 投入产出比 | 低 (项目可走简化路径: 现有 /live 端点 + VAD per-instance 已实装) |
| 业务需求 | 0 (项目用 wechat 已经够, 腾讯会议不是核心) |
| 维护成本 | 高 (腾讯会议 SDK 升级频繁, 3rd party 依赖) |
| W1 spec 类 3 fail 发现 | `app/voice/pipeline.MeetingPipeline` 不存在 (W1 spec 类 3 fail 跟 wave2a 强相关) |
| 决策 | 留 future 不再拍, 跟 W19 选项 A 一致 |

## 4 新铁律 (本 deprecation 沉淀)

1. **deprecation 决策透明** — 4 步操作 (delete + AGENTS.md + 留痕) + 4 决策依据 (工作量 / 投入产出 / 业务 / 维护)
2. **git rm 而非 rm** — 留 git log 留痕, 未来 session 可 `git log --diff-filter=D` 找回完整 history
3. **不修改历史 design/plan/spec** — 探索报告 + 设计规格 是历史记录, 0 修改, 留 future session 理解 context
4. **跟 W19 选项 A 一致** — 留 future 不主动排, 等真实需求触发时再决策 (P0.1 / P0.2 都不再触发)

## 累计今日统计 (2026-07-21)

| 维度 | 数值 |
|---|---|
| **commit** | **70** (含本次 git rm + 改动) push origin/main |
| **memory** | **25** 沉淀 (含本 P0.1+P0.2 deprecation 留痕) |
| **任务** | **90** 完成 (含本次删除 4 步) |
| **彻底删除的 plan/spec** | 2 (wave2a spec + plan) |
| **留 future 的内容** | 0 (P0.1 + P0.2 已彻底删除, 跟 W19 选项 A 一致) |

## 相关 memory

- `multi-agent-task-orchestration-baseline.md` — 锚点范式
- `orchestrator-mode-coordination-2026-07-20.md` — 5 协调铁律 (含 4 留 future PR 拍板)
- `config-value-contract-regression-2026-07-20.md` — 8 技术铁律 (含 deprecation 决策透明原则)
- `w1-pytest-fail-classification-2026-07-21.md` — 84 fail 详细分类 (类 3 含 phantom code)
- `w7-12-baseline-closure-2026-07-21.md` — 12 次 baseline 收口
- **p01-p02-deprecation-2026-07-21.md** — 本 deprecation 留痕 (本 commit)

## 操作详情 (主指挥 4 步执行)

1. ✅ `git rm docs/superpowers/plans/2026-06-01-voiceprint-meeting-wave2a-impl.md`
2. ✅ `git rm docs/superpowers/specs/2026-06-01-voiceprint-meeting-wave2a-design.md`
3. ✅ `AGENTS.md` L115 改写 (sed -i 改写腾讯会议凭据引用)
4. ⏳ 5 文档 0 修改 (历史 design/plan/spec 留痕, AGENTS.md 1 行改写, CHANGELOG.md 0 引用, 1 memory 新增)