# W-N-MEM 索引扩展 起步 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N 周期 MEM 阶段 (MEMORY.md #24 段扩展)
> **Task**: 扩展 `memory/MEMORY.md` #24 段, 包含 W-N-A/B/C/D + GC + ARC + ANC + E + F + D+ 全部 12+ 份 memory + 决策文档 + capability 报告
> **基线 HEAD**: `d8e463d1c` (W-N-E 冷热分层 PoC 收口沉淀) — 守恒 ✓
> **alembic head**: `098_meetings_status_varchar_32` (单链, 1 head) — 守恒 ✓
> **Worktree**: `claude/bold-mendeleev-fdc0e8`

---

## 起点 6 项 (W73 铁律)

### 1. base head 守恒
- 派工 brief 期望: `d8e463d1c` (W-N-E 冷热分层 PoC 收口沉淀)
- 实测: `d8e463d1c` ✅ 守恒

### 2. 文件清单实测
- `memory/w-n-*.md` 共 21 份: W-N-A(2) + W-N-B(2) + W-N-C(2) + W-N-D(2) + W-N-D+(3: e2e-bench-startup + realbench-startup + realbench-closure) + W-N-E(2) + W-N-F(2) + W-N-GC(2) + W-N-ARC(2) + W-N-ANC(2)
- `docs/decisions/2026-08-05-*.md` 3 份: bge-m3-decision + cold-hot-routing-poc + lora-finetune-decision
- `docs/capability/gpu-bge-m3-2026-08-05.md` 1 份

### 3. MEMORY.md #24 段当前内容
- 现有 6 行 (W-N-A/B/C/D + GC + W-N-E startup)
- 缺: W-N-D+ e2e-bench-startup + W-N-D+ realbench-{startup,closure} + W-N-E closure + W-N-F {startup,closure} + W-N-ARC {startup,closure} + W-N-ANC {startup,closure} + 3 份决策 doc + 1 份 capability 报告

### 4. 风险表
| 风险 | 缓解 |
|---|---|
| MEMORY.md #24 段内容已存在, 误删老内容 | **Edit 追加**, 不用 Write 全替换, 锚定 line 681 后追加 |
| 派工 brief 假设 W-N-D+ 2 份 (startup+closure), 实测 3 份 (+e2e-bench-startup) | 据实上报, 写入 #24 段 |
| 派工 brief 假设 W-N-ARC 1 份 closure, 实测 2 份 (startup+closure) | 据实上报, 写入 #24 段 |
| 派工 brief 假设 W-N-ANC 不在范畴, 实测已存在 2 份 (startup+closure) | 据实上报, 写入 #24 段 (沿用 ANC 锚点补 +1 commit `650cd4ffa`) |
| 改 `app/` `web/src/` `alembic/versions/` `docker-compose.yml` | 严禁, 仅 MEMORY.md + 2 memory 范畴 |

### 5. 验证策略
- 步骤级: ls memory/w-n-*.md + ls docs/decisions/ + ls docs/capability/ 实测 → Edit MEMORY.md #24 段追加 → 读全文验证 → commit + 推 main
- 5 件套守恒: alembic 1 head + pytest 沿用基线 + 0 prod code 守恒 + 锚点范式 W-N-MEM +0..+2
- 收尾: `git show --stat` 验证仅 MEMORY.md + 2 memory 文件改动

### 6. 失败回滚
- Edit 写错 → `git checkout memory/MEMORY.md` 回退
- commit 写错 → `git reset --soft HEAD~1` + 改 message 重 commit

---

## 工作清单

- [ ] 读 MEMORY.md #24 段当前内容 (line 673-680)
- [ ] ls memory/w-n-*.md + ls docs/decisions/ + ls docs/capability/ (已实测)
- [ ] Edit MEMORY.md #24 段追加 12+ 份 memory + 3 份决策 + 1 份 capability
- [ ] git add memory/MEMORY.md + memory/w-n-mem-index-expand-{startup,closure}.md
- [ ] git commit -m "docs(memory): W-N-MEM +1 MEMORY.md #24 段扩展 (W-N-D+/E/F/ARC/ANC + 决策 + capability)"
- [ ] git push origin main
- [ ] 写 W-N-MEM +2 收口 memory (5 件套守恒实测)
