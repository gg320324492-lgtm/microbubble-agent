# W71 batch partial mid-派工 D-2 文档同步 (2026-07-24 — 锚点范式第 176 守恒预测, 派工 v6 §1.2 真验证纪律)

## 任务本质

W71 batch 已派工 (15 agents 4 路线), 但**实际真实施仅为子集**:
- 1 commit merged origin/main: W71-C-3 (claude-code notify v2 仓库模板回测 memory, `af4129925`, 锚点范式 175 → 176)
- 2 commits branch-pushed 待合并: W71-A-1 (部署收口 docs, `0e46bb7b5`) + W71-A-4 (grand closure memo 预期版, `1b08d8501`)
- 12 agents 仍 base HEAD `0ae74f477` 0 commit: A-2/A-3/B-1/B-2/B-3/B-4/B-5/C-1/C-2/D-1/D-3

派工 v6 段 5 反馈 #2 实战: D-2 沿用 W68 第 13 批 D-2 模板 (`936e1cb5d`), 但因 12 agents 未开工, **不伪造未实施 work** 内容。

## 关键铁律 (5 条)

1. **主仓库 MEMORY.md 用户级 MEMORY.md 必须区分真实施 vs 预期** — CLAUDE.md `## 当前状态` 段明确标 "W71 batch partial mid-派工", 不写"W71 grand closure 175→184"
2. **origin/main HEAD 必须真实验证** — `git rev-parse origin/main` + `git rev-parse main` + `git ls-remote origin main` 三步, 不要假设 HEAD 一致
3. **branch-pushed 与 merged 区分** — 派工 prompt 经常混淆"已派工"与"已合并", 派工本身是 worktree 创建, 合并才是 work 落地
4. **预期版 memo 必显式 defer** — commit `1b08d8501` 是 W71-A-4 预期版, 必须显式 "待 A-1 主拍补实际值" 不误读为已完成事实
5. **0 production code 改动铁律 N/15 待定不可偷** — 未开工 agents 例外清单未拍板, 不可宣称 "W71 16/15 守恒" 等具体数字

## 完成交付

- 主仓库 5 文件改动 (CLAUDE.md / ROADMAP.md / CHANGELOG.md / README.md / memory/MEMORY.md)
- 1 新增 memory (本文件, ~50 行)
- 用户级 MEMORY.md 主拍手动同步 (不在本 worktree)
- 1 commit + 1 push

## 沉淀纪律

派工 v6 段 5 反馈 #2 实战验证: **D-2 文档同步不能独立于 batch 实际进度** — 必须先 `git log --all --grep="<batch>"` 真验证, 再决定 entry 是 "grand closure" 还是 "mid-派工 partial"。
