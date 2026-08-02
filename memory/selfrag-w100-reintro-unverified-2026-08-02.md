---
name: selfrag-w100-reintro-unverified-2026-08-02
metadata:
  node_type: memory
  type: project
---

# Self-RAG W100 重新引入未 benchmark 验证（2026-08-02 plans 审计发现）

## 事实链

1. **2026-06-30**：用户主动要的功能（#009）"检索质量差时 AI 编造答案 -> 加 Self-RAG gate"。MVP 完整交付。
2. **2026-07-14**：6 轮 benchmark 终极证伪（R1-R6，100 题 × ON/OFF × legacy/balanced/deep）。R5=R6 98%=98%，gate **0/100 触发**，R2 触发的 15 次 100% parse-fail 0 真实重检索。结论"无论 flag 还是 deep mode，Self-RAG 都不提供价值"。详见 `memory/archived/self-rag-r5r6-deep-mode-benchmark-2026-07-14.md` + `self-rag-three-mode-r3r4-benchmark-2026-07-14.md`。
3. **2026-07-20**：执行删除（老 `app/services/self_rag.py` + 13 文件 ~600 行）。
4. **W100 P1（2026-08-01）**：重新引入 - 全新 `app/services/self_rag_service.py`（3 维度 assess_answer: top-1 score + 实体匹配率 + 长度异常, should_retry = not reliable and top1 < SCORE_THRESHOLD, retry_with_reformulation 2 次上限）。4 commits `0f21bdf05`/`daec6f596`/`de6884678`/`628bd7aea` + merge `f5acce882`，8/8 PASS。接入 `app/agent/chat_engine.py:310-378`，**无 flag 守卫**（不可靠答案自动 retry）。

## 风险

- ✅ 重新引入是**有意正式派工**（非无意复活），全新实现非恢复老代码，`docs/w101-p2-autorag-2026-08-01.md` 把它当活跃基线引用。
- ⚠️ **未跑 benchmark 验证效果**。老版证伪核心 = "gate 0 触发 + 触发后 100% parse-fail 0 真实重检索"。W100 新版 8/8 PASS 是**功能单测**，非 100 题 ON/OFF 效果对照。新版 should_retry 改用 top1 < SCORE_THRESHOLD 触发条件，理论上比老版更易触发，但无数据证明。
- ⚠️ 若新版仍 0 触发或无质量提升，则是**第三次反复**（建 -> 证伪删 -> 重建），应避免。

## 待办

跑 R7/R8 benchmark 验证（沿用 R1-R6 范式：100 题 × Self-RAG ON/OFF × balanced/deep，指标 Pass rate + Gate triggers + latency first/last 20 切片）。派工 plan 详见 `C:\Users\pc\.claude\plans\selfrag-r7-r8-benchmark-verify-2026-08-02.md`。若 R7/R8 仍 0 触发或无提升 -> 按2026-07-14 决策再次删除，不第三次反复。

## 关联

- `memory/archived/self-rag-r5r6-deep-mode-benchmark-2026-07-14.md`（6 轮证伪原文）
- `memory/archived/self-rag-2026-06-30.md`（原始 #009 建设）
- `app/services/self_rag_service.py`（W100 新实现）
- `app/agent/chat_engine.py:310-378`（活跃调用点）
- plan Status 已纠正：`selfrag-cross-encoder-reranking-self-ra-wild-wozniak.md` 标 REINTRODUCED
