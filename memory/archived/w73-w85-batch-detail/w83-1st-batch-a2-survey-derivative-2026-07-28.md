# W83 第 1 批 A-2: W82 5 份 Survey 调研派生 + 7 agents 详细化 + W84/W85/W86 排期 (2026-07-28)

> **主基调**: "W82 5 份 Survey 派生 W83 7 agents 详细化 + 类 20.13 实战 16/17 沉淀". 0 production code.
> **锚点范式**: W82 300 → W83 第 1 批 A-2 303 守恒 (+3, 0 regression).
> **派工范式**: 主指挥协调范式第 58 次派工.
> **派工前提真验证**: base HEAD `b99eb52da` ✓ + W82 5 份 Survey 实测 ✓ + dead service 实测 0 行可删 ✓.

## 1. W82 5 份 Survey 调研结论 (派生基础)

| Survey | 实测结论 | W83 派生 |
|---|---|---|
| 1 内容状态 | 23 批累计 410+ commits / 380+ 铁律 / 487+ e2e PASS / 67+ 例外 | 锚点范式 300 → 307 (+7) 累计 25 批 |
| 2 latent bug | **P0 0 / P1 5 / P2 15+** (W82 §6.2 实测, **不复制任务 brief 膨胀 P1 13 / P2 20+**) | W83 B-1: 4 项 P1 (rate_limit + license + wechat + agentic_loop, 沿用 W82 §5 W83 batch 2) |
| 3 冗余/重复 | ~1025 行可删 (W82 §6.3 实测 app/ 500 + web/src/ 300 + ...) | W83 B-2: TTS cache 合并 + BREAKPOINTS 收敛 |
| 4 branches | 484 branches + 209 wt (W82 C-2 已清) | W83 沿用, 不重复清 |
| 5 tests/scripts | 13.6MB 已清 (W82 C-1 据实上报 5 round) | W83 C-2: 17+175+5 docs/memory 清 |

## 2. W83 第 1 批 7 agents 详细化 (本批派生)

| agent | 起点 → 终点 | 锚点 | 详细任务 |
|---|---|---|---|
| **A-1** | 300 → 300 | 0 | 部署收口 (W82 6 merges + push + 拦截 #16 沉淀) |
| **A-2 (本批)** | 300 → 303 | +3 | **调研派生 (W82 5 份 Survey → W83 7 agents + W84/W85/W86 排期)** |
| **B-1** | 303 → 304 | +1 | P1 latent bug 修 batch 2 (4 项, 沿用 §1) |
| **B-2** | 304 → 305 | +1 | P1 冗余重构 (TTS cache + BREAKPOINTS, 沿用 §1) |
| **C-1** | 305 → 306 | +1 | P1 dead service 清 (实测 9 service 0 行可删, 改**收敛 drive_comments_path_backfill 296 行**) |
| **C-2** | 306 → 307 | +1 | P2 docs/scripts 清 (17+175+5, 沿用 §1) |
| **D-1** | 307 → 307 验证不计 + 1 实战 | 0 + 1 | 6 类文档同步 + grand closure |
| **D-2** | 307 收口 | 0 | 锚点范式收口 + W84/W85/W86 排期 + 类 20.13 实战 17 沉淀 |

**累计**: W82 300 → W83 307 (+7 守恒, 0 regression), 0 production code (1 例外预留给 B-1).

## 3. W84/W85/W86 派工顺序 (派工 v6 §6 实战)

### W84 (307 → ~314, +7)
- B-1 P1 latent bug 修 batch 3 (剩余 1 项 Edge-TTS B+D/Web Speech API + 商业化 license + 跨租户监控实战)
- B-2 P1 冗余重构 batch 2 (chunked upload 3+ 套合并 + useFileComments 桌面/移动收敛)
- C-1 P1 dead service 清 batch 2 (drive_cleanup_tasks + drive_chunked_upload_tasks 收敛)
- C-2 P2 docs/scripts 清 batch 2 (175 transient memory + 跨主题 docs 合并)

### W85 (~314 → ~321, +7)
- B-1 Phase 9 课题组知识图谱可视化 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营收官 + 客户支持
- C-1 跨租户监控 + 多租户实战收官

### W86 (~321 → ~328, +7)
- B-1 Phase 11 智能实验记录本 启动 (阶段 6 后)
- B-2 商业化运营 + 客户支持 + 监控实战
- C-1 Phase 12 科研协作工作流 启动 (阶段 7 后)

## 4. 类 20 实战 17 实例沉淀 (本批 #17 新增)

**17. W83 A-2 类 20.13 实战 17 (本批派生)**: 派工 brief "P1 13 项 latent bug + P2 20+ 项 dead service" 与 W82 §6.2 实测 5 项 + W82 §5 W83 batch 2 4 项不一致; 任务 brief 中 9 dead service 实测**全部有 live caller** (0 行可删). 派生严格按 W82 实测, 不复制膨胀数字. **5 新铁律**:

1. 派工 brief 数字必须实测二次 grep 真验证 (P1 13/P2 20+ 不能信 brief)
2. dead service 判定必须 3 路径 import 调用图 (app/ + tests/ + web/, 不漏 e2e 顶层 import)
3. 派工 brief 派工顺序表必须 align with grand closure §5 (W82 §5 W83 batch 2 是权威)
4. 派生任务实测出现差异时立即报主指挥 (派工 v6 §1.2 "Status 段必真验证" 沿用)
5. 派工 brief 引用历史 W82 调研报告必须对齐版本 (§5 派工顺序 + §6 Survey 实测, 两处分别引用)

## 5. dead service 实测否决 (本批 §1.6 派生基础, 类 20.13 实战 17)

| service | 行数 | 实测 live caller | 处置 |
|---|---|---|---|
| billing/payment_service.py | 199 | tests/test_billing_payment_mock_e2e.py × 5 (W75 B-2 真支付 mock) | **保留** |
| billing/subscription_service.py | 177 | tests/test_billing_payment_mock_e2e.py × 1 | **保留** |
| billing/webhook_signature_real.py | 268 | wechat_pay_sdk + 2 e2e (W78 真生产 key 启用) | **保留** |
| drive_upload_service.py | 77 | tests/e2e/test_drive_v2_pr9_versions.py × 1 | **保留** |
| tts_mainplay_pipeline.py | 510 | tests/test_tts_mainplay_pipeline_e2e.py × 1 | **保留** |
| bm25_service.py | 141 | hybrid_retriever + knowledge_service + graph_retriever + e2e (W73-W75 知识图谱) | **保留** |
| low_occupancy_filter.py | 178 | post_meeting_tasks + e2e (W68 第 14 批 voiceprint) | **保留** |
| mention_parser.py | 189 | drive_comment_service × 2 (W68 第 13 批 PR9 评论 + emoji) | **保留** |
| dynamic_taxonomy_service.py | 196 | api/v1/knowledge.py × 1 (W68 第 6 批 dynamic taxonomy) | **保留** |

**实测结论**: 9 service 共 1935 行, **0 行可删**. 仅 `drive_comments_path_backfill_service.py` 296 行可**收敛** (简化入口, 不删).

## 6. 派工前提铁律 12 + W19 选项 A 维持

- **派工前提铁律 12 条**: 沿用 W82 A-2 沉淀 (本批 #1 派生新任务必先 git log + grep 真验证 + #6 SW BUMP + #10 拦截报告 commit 必含 6 路穷尽搜证)
- **累计铁律 400+ 条**: W82 第 1 批 +20 铁律 + W83 第 1 批 +5 派生铁律 = 405+
- **累计 commits 24 批 410+**: W82 第 1 批 +9 ahead of W81 closure `2ce014c8f`
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 7. 风险评估

- **高**: B-1 rate_limit/license 安全策略 (主拍签字, 16/16 跨租户 PASS 守恒) + B-2 TTS 缓存跨 iOS/Android (~85 case 回归)
- **中**: C-1 真支付路径 (0 行可删, 必须 0 调用验证) + B-2 BREAKPOINTS 影响 73 composable (分步走)
- **低**: C-2 docs/memory 范畴 + A-1/A-2/D-1/D-2 纯 docs/memory

## 8. 交付物

- 2 文件: `docs/w83-1st-batch-a2-survey-derivative-2026-07-28.md` + `memory/w83-1st-batch-a2-survey-derivative-2026-07-28.md` (本文件)
- 1 commit: anchored 300 → 303 +3
- 推送 origin: 预期成功
- 0 production code 守恒: 沿用 W72-W82 例外清单 (67+ 累计 + W82 +1 已批)

---

**维护者**: Agent 6 (W83 第 1 批 A-2) · **创建时间**: 2026-07-28 · **锚点范式**: W82 300 → W83 第 1 批 A-2 303 守恒 (+3, 0 regression)