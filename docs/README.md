# docs/ — 项目文档索引

> **2026-09-30 建立**。本目录有 380 个 md，分散在根目录（127 个散落文件）与 20 个
> 子目录中。**本索引只说明"哪一类东西去哪找"，不逐个罗列文件**——逐个列的清单会在
> 下一次新增文档时立刻过时，那正是"8 套材料"混乱的来源。
>
> **当前状态不在这里**：`CLAUDE.md` 顶部 `## 当前状态` 段是唯一的现状权威。

## 按性质找文档

| 我想知道… | 去哪找 |
|---|---|
| **现在项目什么状态** | `CLAUDE.md` 顶部 `## 当前状态` 段 |
| **现在该怎么做（规则/铁律）** | `CLAUDE.md` 中段各规范段 + `## 永久铁律`（`grep -n "类 20\." CLAUDE.md`） |
| **某次事故的完整经过** | `docs/incident/`（README 在内有分工说明） |
| **当初为什么这么定（决策链）** | `docs/decisions/`、`docs/refactor-decision/`、`docs/W-N-decisions/` |
| **怎么部署 / 部署出过什么问题** | `docs/deploy.md`（现行）+ 根目录 `deploy-*` `build-dist-runbook.md`（历史） |
| **RAG 架构与评测** | `docs/rag/`（31 个）、`docs/qa-bench/`、`docs/bench/` |
| **桌面端 / 网盘 Drive v2 的方案与部署** | 根目录 `drive-v2-*` `desktop-*` 系列 + `docs/design/` `docs/design-proposals/` |
| **会议纪要格式（硬规则）** | `CLAUDE.md` 的 `## 会议纪要标准格式` |
| **前端设计令牌** | `docs/color-tokens.md` + `web/src/assets/variables.css`（后者是真值） |
| **阶段排期与路线图** | `docs/roadmap-phases/`、`docs/phase14/`、`docs/phase15/` |
| **PWA 相关的历史教训** | `CLAUDE.md` 的 PWA 段（⚠️ 已于 2026-07-27 失效，勿照做） |

## 目录权威性对照

| 目录 | 文件数 | 性质 | 维护 |
|---|---:|---|---|
| `incident/` | 2 | **事故档案** | 只增不改（见其 README） |
| `decisions/` `refactor-decision/` `W-N-decisions/` | 16 | 决策记录 | 追加，不改旧条目 |
| `rag/` `rag-templates/` `qa-bench/` `bench/` `capability/` | 38 | RAG 专题 | 按专题维护 |
| `design/` `design-proposals/` | 2 | 设计提案 | 历史方案，多数已落地 |
| `grafana/` | 1 | 监控 | 与 `deploy/grafana/` 配置同步 |
| `history/` | 19 | 历史档案 | 只读 |
| `superpowers/` | 22 | 早期方案与审计反馈 | 只读 |
| `roadmap-phases/` `phase14/` `phase15/` `P2-leftover/` | 38 | 阶段计划与留口 | 多已完结 |
| `archived/` `_archive_2026-07-12/` | 115 | **归档** | 只读，不再更新 |
| （根目录散落 127 个） | 127 | 混合：现行 runbook + 一次性方案 + 修复记录 | 见上方查找表 |

## 写文档的纪律

1. **现状只写 CLAUDE.md**，不要在 docs/ 下另起"当前状态"文件
2. **新事故**：先提炼铁律进 `CLAUDE.md` 的 `## 永久铁律`，再把经过写进 `docs/incident/`
3. **runbook**（可复用的操作步骤）与**一次性方案**（某次派工的产物）分开：
   前者进根目录并保持更新，后者完成即归档到 `docs/archived/`
4. 文件名带日期与主题（`2026-07-24-xxx.md`），便于按时间排序检索
5. 不要新建"XX 汇总/总览"文档——那几乎总是下一份会过时的清单
