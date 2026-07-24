# W70-W71 Plans Backlog v2 调研：子 plan ②/③ 实施路径

> W68 第 14 批 A-3 综合调研，2026-07-24
> 范围：只做 plans/docs/memory 调研，不实施 production code。
> 基线：W68 第 13 批 B-3 `docs/w70-plans-backlog-decision-2026-07-24.md`；W69 预排 `docs/chatgpt-structured-floyd-w69-plan.md`。

## 1. 执行摘要

本次复核了复合 plan `chatgpt-structured-floyd.md` 的子 plan ②（qa-bench、自动入库、回滚、KB 闭环、Dashboard、CI smoke）和子 plan ③（NavRail、ThinkingModeSwitch、ChatBreadcrumb），并按派工纪要 v4 铁律执行仓库真验证。结论不是简单的“留待实施”：子 plan ② 的七维评分、KB 自动入库灰度/回滚、闭环 automation、Dashboard 和 smoke 已分批落地，但文件布局与原始 plan 预计路径不同，仍有缺口；子 plan ③ 三个组件已经存在并接入 ChatViewSSE，属于“已实施、需验收和收口”，不应照原计划重复创建。

主推荐：**选项 A**——W71 派 5 agents 对子 plan ② 做验收、缺口补齐和风险收口；W72 再派 3 agents 对子 plan ③ 做视觉/a11y/mobile 验收和必要的小修。这样保留计划优先基调，避免并行重写已经存在的功能，也把高风险 KB 自动入库和 CI gate 放在 UI 美化之前。

## 2. 调研输入与方法

### 2.1 读取的基准资料

- `docs/w70-plans-backlog-decision-2026-07-24.md`：W68 第 13 批五项 backlog 调研与 W70 预排。
- `docs/chatgpt-structured-floyd-w69-plan.md`：子 plan ②/③ 的原始目标、5 agents/4 agents 拆分和 DoD。
- `C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md`：原始复合 plan 全文，尤其 §3 七维评分、§5 KB 防线、W1-W6 DoD。

### 2.2 真验证纪律

以下命令在当前 worktree 执行，不把 plan Status 当作证据：

```text
grep -rn "qa-bench" --include="*.py" app/ | wc -l
grep -rn "save_to_kb\|auto_intake_rollback" --include="*.py" app/ | head -10
grep -rn "NavRail\|ThinkingModeSwitch\|ChatBreadcrumb" web/src/ | head -10
git log --oneline --all | grep -iE "save_to_kb|auto_intake" | head -10
```

实际摘要：`qa-bench` 命中 31；app 层命中的是 knowledge 监控/安全 intake 接口与 schema，原 plan 设计的 `app/services/qa_bench_tasks.py` 不存在；UI 三组件均存在且 ChatViewSSE 已导入；历史命中 `14aae9aaf feat(qa-bench): v3.1 D2 runner 集成 save_to_kb + 端到端测试`。补充 `git log --stat` 找到 `63cdac3bb`（七维评分）、`b388cc72b`（全自动入库灰度）、`64660718c`（自动入库回滚/告警闭环）、`0066087c8`（KB 闭环 automation）和 `4c7816c1e`（D7 baseline gate）。

## 3. 子 plan ② 实施清单（W71 验收对象）

### 3.1 七维评分

| 原始目标 | 真验证结果 | 判断 | W71动作 |
|---|---|---|---|
| `scoring/seven_dim.py` + 可配置权重 | `tests/qa-bench/scoring/seven_d_scoring.py` 已存在；`test_seven_d_scoring.py`、`verdict_consensus_v2.py` 已存在 | 已实施，路径改名 | 复核权重、fail-fast、报告契约，补端到端证据 |
| 7 维 intent/tool/content/rich/defense/perf/consistency | `63cdac3bb` 明确实现，D6/D7 runner 已消费 | 已实施 | 以 780 题/分层样本重跑，不重复造算法 |
| 7 维基线与矩阵报告 | phase2/phase3 runner、docs、memory 已落地 | 部分收口 | 固化 JSON schema、版本号、阈值和回归快照 |

原始 plan 的 `scoring/weights.json` 尚未按该名称出现；权重目前由评分模块/配置约定承载。W71 必须先确认“代码真实权重 = 文档权重”，再决定是否抽出配置文件。

### 3.2 `save_to_kb.py` 五道防线

| 防线 | 真验证 | 状态 |
|---|---|---|
| dedup（embedding 相似度） | 未发现原 plan 预期的 `kb_queue/dedup.py` | 缺独立模块/需验收 |
| 长度过滤 | `save_to_kb.py` 有 `--min-content-length` 参数和候选过滤路径 | 已有，需测试边界 |
| LLM 拒答检测 | 未发现 `kb_queue/llm_refusal.py` 或等价 app 模块 | 缺口 |
| 敏感词/placeholder/filler | 现有 runner/detector 与安全 intake helper 分散覆盖；未形成五道防线清单 | 部分 |
| 人工抽检 | observer/summary/监控路径已存在，Dashboard 有数据页；未证实完整 5% admin queue | 部分/需证据 |

`tests/qa-bench/save_to_kb.py` 的灰度参数（`--grayscale`、`KB_INTAKE_GRAYSCALE`、`AUTO_KB_INTAKE_ENABLED`）和 observer/rollback 检查已存在，不能把“全自动灰度”误写成“五道防线全部完成”。W71 Agent #2 应补一张防线矩阵和负向测试；默认开关仍应保持关闭，直到证据满足门禁。

### 3.3 Celery rollback

原计划要求 `app/services/qa_bench_tasks.py:auto_intake_rollback_task`。真查显示该文件不存在；仓库存在 `scripts/auto_intake_rollback.py`，同时 `save_to_kb.py` 具备 7 天 rollback 标记/observer 调用，app API 可读取 `auto_intake_rollback_*.json`。因此功能是“脚本 + API 监控形态”，不是原计划要求的 Celery beat 任务。

判断：**部分实施，部署契约未闭环**。W71 Agent #3 应确认任务注册、幂等键、时区、7 天 review、告警阈值和 worker 运行证据；若继续保持脚本形态，必须更新 plan 和运维文档，不能标成 Celery 已完成。

### 3.4 KB 闭环

`64660718c` 与 `0066087c` 的历史记录证明自动入库回滚/告警及五步闭环已实施过；当前树同时有 `safe_minio_intake.py`、knowledge API 监控端点和 `data/auto_intake_summary.json`/rollback JSON 约定。闭环的“存在”成立，但五道防线的独立可审计证据、失败回滚、负反馈暂停和灰度开关仍需验收。

建议闭环验收顺序：候选 → 评分门禁 → 防线逐项记录 → 入库审计 → 24h/7d review → rollback/alert → dashboard 反映。任何一步只写 summary 而无 audit event，都判为 partial。

### 3.5 Dashboard MVP

原计划的 `tests/qa-bench/dashboard/index.html` 与 `data.json` 已存在，另有 W68 第 8 批/第 10 批 KB monitor 产物及 app API 监控端点。它覆盖“有数据页”的 MVP，但原计划 `/admin/qa-bench-dashboard` 四卡片、5 分钟轮询、待抽检和告警详情需要以实际路由/截图/接口响应确认。

W71 Agent #5 负责只做验收和补齐：入库数、通过率、抽检数、告警数四项；不因已有页面而重建第二套 dashboard。

### 3.6 CI smoke 200 题

`.github/workflows/qa-bench-smoke.yml`、`tests/qa-bench/questions_smoke_200.jsonl`、`scripts/ci_qa_bench_baseline.sh` 和 D7 workflow 均存在。D7 baseline gate 已有 `4c7816c1e`，但本地基线实跑为 69 passed + 7 skipped + 2 Redis 连接失败（目标文档称 71 passed + 7 skipped）。失败是本机 Redis 未启动的环境问题，不能宣布绿；W71 必须在依赖服务可用的 CI/test stack 内重跑并记录 exact output。`typing_import` baseline 为 0 错误。

## 4. 子 plan ③ UI redesign 实施清单（W72 验收对象）

### 4.1 NavRail

`web/src/components/chat/NavRail.vue` 已存在并在 ChatViewSSE 相关布局中使用。W68 第 11 批 Mobile TabBar/抽屉工作已覆盖移动端导航的一部分；原始 plan 的“统一 desktop + mobile NavRail”不能直接等同于已有 TabBar。桌面组件、移动抽屉、路由级双栈边界需分别验收。

判断：**核心组件已实施，跨栈统一目标部分覆盖**。W72 Agent #1 做导航可达性、键盘、dark mode、mobile drawer 和无重复入口验收。

### 4.2 ThinkingModeSwitch

`web/src/components/chat/ThinkingModeSwitch.vue` 已存在，且变量令牌注释标明三档推理模式；ChatViewSSE 已导入并渲染。它已解决原始“双 toggle 冲突”目标，仍需确认 fast/balanced/deep 的 store 映射、a11y 四属性和移动端是否有对应简化组件。

判断：**已实施，需测试契约收口**。若现有产品决策已不需要三档，W72 应先做产品拍板，不应为了原 plan 机械改 UI。

### 4.3 ChatBreadcrumb

`web/src/components/chat/ChatBreadcrumb.vue` 已存在，ChatViewSSE 在顶栏使用，并传递生成状态。原始 `parentPath`、session title、移动端显示策略和截断/可访问名称仍需确认。

判断：**已实施，需验收**。W72 Agent #2 只补缺失 props/测试和视觉回归，不重建组件。

### 4.4 UI agent 拆分调整

原始 4 agents 适合从零开发，但当前应调整为 3 agents：Agent #1 NavRail + 双栈；Agent #2 ThinkingModeSwitch/ChatBreadcrumb + a11y；Agent #3 ChatViewSSE 视觉回归、移动端 smoke、baseline 和 memory。这样符合题设 W70 派 3 agents，也避免重复实现。

## 5. W71 主拍四选项矩阵

| 选项 | 派工范围 | 节奏 | 优点 | 风险 | 建议 |
|---|---|---|---|---|---|
| **A（推荐）** | W71 派 5 agents：①评分验收；②五防线矩阵/负测；③Celery rollback 契约；④KB 闭环 E2E；⑤Dashboard+CI smoke。W72 派 3 agents 收 UI | 先质量门禁，后 UI | 消除 Status/代码路径错位；高风险 intake 先闭环 | 需要 Redis/test stack | **主推荐** |
| B | W71 8 agents 并行，5 个子 plan② + 3 个子 plan③ | 质量与 UI 同波 | 总周期短 | CI、KB、视觉 baseline 争抢资源；重复改动概率高 | 不推荐 |
| C | W71 4 agents，跳过 KB 闭环，仅评分、rollback、Dashboard、CI；W72 续 | 缩小范围 | 快速获得可测基线 | 自动入库仍无端到端安全门，风险被推迟 | 仅在 intake 持续关闭时可选 |
| D | W71 不派 plans，商业化优先，W72+ 再排 | 直接进入长期路线 | 零短期并行成本 | 现有 partial/环境红灯继续积累，计划状态再次漂移 | 不推荐 |

**拍板建议**：选择 A。前提是主指挥确认 `AUTO_KB_INTAKE_ENABLED` 继续默认关闭，且 W71 第一天先准备 Redis/DB 测试依赖；若依赖无法提供，降级为 C 但不得开放自动入库。

## 6. W71/W72 DoD 与回滚

### W71 DoD

- 七维评分实现与文档权重一致，至少一轮 780 题抽样报告可复现。
- 五道防线逐项有代码路径、审计字段、正负测试；缺失项明确列为 partial。
- rollback 是可发现、可幂等、可告警的 worker/脚本契约，并有运行日志。
- KB 闭环至少完成 pass/reject/rollback/negative-feedback 四条路径。
- Dashboard 四卡片接口响应可读；smoke 200 在依赖完整环境通过。
- 不改变子 plan① chat history；不写 alembic，不修改老业务路径。

### W72 DoD

- desktop/mobile 导航无重复入口，NavRail 与 MobileSessionDrawer 边界清楚。
- 三档模式映射、键盘操作、a11y 四属性和 dark mode 通过测试。
- ChatBreadcrumb session/title/path/status 在长标题、空 session、移动视口下稳定。
- Playwright 视觉 baseline 更新有审查记录；必须使用 `npm run build`。

回滚原则：W71 任一 intake gate 失败，保持 feature flag 关闭并停止自动入库；W72 视觉回归失败只回滚 UI commit，不触碰 qa-bench/KB 路径。

## 7. 最终结论

原始 W69/W70 plan 的“留待实施”状态已被后续 W68 commits 部分超前实现。真正剩余的是验收、契约统一、五防线证据和依赖环境闭环，不是从零开发。主指挥应把 backlog 状态从简单 `❌` 改成“已实施/部分实施/待验收”三态，并采用 A 方案：W71 先收紧质量与自动入库风险，W72 再完成 UI 双栈验收。此次调研不修改原始 B-3 文档、不实施 production code。

## 8. 证据索引

- `63cdac3bb`：7-dim scoring + verdict v2 + phase3 matrix。
- `b388cc72b`：save_to_kb v3.1 全自动入库灰度。
- `64660718c`：自动入库回滚/重试/告警闭环。
- `0066087c8`：KB 闭环 automation。
- `4c7816c1e`：D7 baseline conservation gate。
- `14aae9aaf`：save_to_kb runner 集成历史。
- `tests/qa-bench/scoring/seven_d_scoring.py`、`tests/qa-bench/save_to_kb.py`、`scripts/auto_intake_rollback.py`。
- `web/src/components/chat/NavRail.vue`、`ThinkingModeSwitch.vue`、`ChatBreadcrumb.vue`。

> W68 第 14 批 A-3：docs-only 调研；目标锚点范式第 171 守恒。
