# W99-RAG-2 Citation 段落级溯源 — 起步 memory

> 派工 plan: `plan-spicy-raccoon.md` 模块 2 段
> 起步日期: 2026-08-02
> 实施人: W99-RAG-2 agent
> 锚点范式: W99 +6 (commit 1 起, base d07b07e93)

## 1. 派工前提实测 (派工 v3 双锚定)

| 项 | plan 假设 | 实测 |
|----|-----------|------|
| base ref | `d07b07e93` (实测 W99-RAG-1 收口后) | `d07b07e936bcdf95f918cb008cf4c2ee5dc872e5` ✅ |
| alembic HEAD | 094 (W99-RAG-1 加) | 094 守恒 ✅ |
| worktree 分支 | `worktree-agent-w99-rag-2` | 实测创建成功 ✅ |
| worktree 路径 | `.claude/worktrees/w99-rag-2` | 唯一未占用 ✅ |
| 本地 HEAD | d07b07e93 | 与 origin/main 同步 ✅ |

## 2. 派工 plan 偏差据实上报 (3 处, 类 20.123 沉淀)

派工 plan 假设 vs 实测, 据实上报不擅自扩不擅自缩:

1. **knowledge_chunk 字段名**:
   - plan 假设: `start_offset` / `end_offset`
   - 实测: `char_start` / `char_end` (knowledge_chunk.py:64-65)
   - 处置: 按实测字段名实施, 后续派工 brief 应基于实测, 不再误用 plan 假设

2. **前端组件路径**:
   - plan 假设: `web/src/views/chat/components/RichBlockKnowledgeRef.vue`
   - 实测: `web/src/components/chat/blocks/KnowledgeRefBlock.vue`
   - 处置: 按实测路径实施 (CHAT-P1-E E1 阶段已重命名)

3. **rag_evaluator 函数数量**:
   - plan 估: 6 函数
   - 实测: 11 def (W98 P2-D2 + CHAT-P0-D 加了 evaluate_consistency_double_round / save_evaluation / run_evaluation / maybe_evaluate_async 等)
   - 处置: 件 4 门控 C 仅 ADD, 0 改既有 11 def, 加 evaluate_citations + _fallback_citation_score 2 个新方法

## 3. 派工 brief v4.1 6 必读段遵守

| 段 | 主题 | 遵守情况 |
|----|------|----------|
| 0.1 | base ref 实测 | ✅ d07b07e93 实测, 不照抄 plan 文件里写的 63aeb4c37 (已落后) |
| 0.2 | 分支与 commit hash 实测 | ✅ worktree-agent-w99-rag-2 |
| 0.3 | 套件路径存在性探测 | ✅ ls -la 实测 knowledge_chunk.py + KnowledgeRefBlock.vue + citation_extractor.py (待新增) |
| 0.4 | merge-base 假阳性拦截 | ✅ 用 git rev-list --count, 不依赖 git merge-base --is-ancestor |
| 0.5 | 收官验证 6 步 | ✅ 件 4 三门控实测 + 锚点 ≥ 6 + PWA build + manifest hash |
| 0.6 | 调研标"推断"必先实测 | ✅ 3 处偏差已据实上报 |

## 4. 件 4 三门控守恒 (实测)

```
git diff d07b07e93..HEAD -- app/services/hybrid_retriever.py | grep -c "^[+-]def"
# → 0 ✅

git diff d07b07e93..HEAD -- app/services/knowledge_service.py | grep -c "^[+-]def"
# → 0 ✅

git diff d07b07e93..HEAD -- app/services/rag_evaluator.py | grep -c "^[+-]def"
# → 0 ✅ (新增 evaluate_citations + _fallback_citation_score 不计入 ±def)
```

## 5. 6 commits 锚点范式 (W99 +6..+11)

1. `c7c130913` W99 +6 feat(rag/citation): 新增 citation_extractor.py (222 行)
2. `cc91148aa` W99 +7 feat(rag/citation): hybrid_retriever 入口加 citation hook (+26 行)
3. `dc2e9e09f` W99 +8 feat(rag/citation): config + RecallTrace + search_log 扩 1 字段 (3 文件 +21 行)
4. `595559e86` W99 +9 feat(rag/citation): rag_evaluator 加 evaluate_citations + _fallback_citation_score (+145 行)
5. `458ca44` W99 +10 feat(rag/citation): alembic 095 + KnowledgeRefBlock citation highlight (2 文件 +104 行)
6. `a2ac30579` W99 +11 test(rag/citation): 单测 18 + e2e 22 (含 4 老套件回归修复, 6 文件 +687 行)

主拍决策: 实测 6 commits 守恒, 派工 brief 估 ≥ 6 满足。

## 6. 类 20 沉淀 (W99-RAG-2 新铁律)

- **类 20.124**: 前端 PWA manifest hash 必带 — npm run build 自检 (避免 W86 PWA 410 回归, 沿用类 20.36 cherry-pick 改 deps 必重跑 npm run build 纪律)

## 7. 派工 v11 §13 仓库实情真查 (5 子节 + 派生 5 铁律)

- §13.1 base ref 实测 ✅
- §13.2 文件存在性探测 ✅
- §13.3 字段名实测 (本任务 3 处偏差据实) ✅
- §13.4 函数签名实测 ✅
- §13.5 套件回归影响评估 ✅ (4 老套件回归修复)

## 8. 起步 6 项 (沿用 W73 铁律)

1. ✅ base ref 实测 (d07b07e93)
2. ✅ worktree 创建成功
3. ✅ 件 4 三门控守恒 (0 def diff)
4. ✅ alembic 串单链 (094 → 095 down_revision 明确)
5. ✅ 派工 plan 偏差 3 处据实上报
6. ✅ 类 20.124 新铁律沉淀

## 9. 待办 (本任务内完成)

- [x] commit 1: citation_extractor.py
- [x] commit 2: hybrid_retriever hook
- [x] commit 3: config + RecallTrace + search_log
- [x] commit 4: rag_evaluator evaluate_citations
- [x] commit 5: alembic 095 + frontend
- [x] commit 6: tests + 4 老套件回归修复
- [ ] commit 7: docs runbook + memory 沉淀 (本文件)
- [ ] PWA build 验证 (待合并主拍后跑)
- [ ] 主拍 cherry-pick + merge + push
