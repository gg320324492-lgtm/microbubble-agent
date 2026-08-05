# W-N-MEM 索引扩展 收口 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N 周期 MEM 阶段 +2 收口
> **Task**: MEMORY.md #24 段扩展收口, 5 件套守恒实测
> **基线 HEAD**: `d8e463d1c` (W-N-E 冷热分层 PoC 收口沉淀)
> **当前 HEAD**: `ab34f0aa2` (W-N-MEM +1 MEMORY.md #24 段扩展)
> **alembic head**: `098_meetings_status_varchar_32` (单链, 1 head) — 守恒 ✓

---

## 5 件套守恒实测

### 件 1: alembic 1 head 守恒
```bash
$ python -m alembic heads
098_meetings_status_varchar_32 (head)
```
- 派工 brief 期望: 1 head `098_meetings_status_varchar_32`
- 实测: ✅ 守恒 (本任务 0 production code, 不动 alembic)

### 件 2: pytest 沿用基线
- W-N-B 19/19 PASS + W-N-C 4 commits bench + W-N-D 5 commits + W-N-D+ 真实 bench 85% 胜率 + W-N-F 14 tests PASS
- 本任务不涉及测试代码, 沿用 W-N-F 14/14 PASS 基线 ✅

### 件 3: PWA build 沿用基线
- 本任务不涉及 frontend, 沿用 W-N-GC 基线 (`vite-plugin-pwa disable: true`, PWA 已禁用) ✅

### 件 4: 0 production code 守恒
- `git diff origin/main -- app/ | wc -l` = 0 ✅
- `git diff origin/main -- web/src/ | wc -l` = 0 ✅
- `git diff origin/main -- alembic/versions/ | wc -l` = 0 ✅
- `git diff origin/main -- docker-compose.yml | wc -l` = 0 ✅
- 本任务仅 MEMORY.md + 2 memory 文件范畴, 严格守恒

### 件 5: 锚点范式守恒
- 派工 brief 估: W-N-MEM +0..+2 (3 commits)
- 实测: W-N-MEM +0 commit `b9f9b0933` + W-N-MEM +1 commit `ab34f0aa2` = 2 commits 据实
- W-N-MEM +2 收口 commit (本文件) = +3 累计
- 锚点范式: W-N-GC ~562 → W-N-ANC ~567 → W-N-MEM +1 ~567 (派生锚点补) → W-N-MEM +2 ~568 据实累计
- 派工 brief 与实测守恒 ✅

---

## 工作清单 (全部完成)

- [x] 读 MEMORY.md #24 段当前内容 (line 673-680)
- [x] ls memory/w-n-*.md (21 份实测)
- [x] ls docs/decisions/2026-08-05-*.md (3 份实测)
- [x] ls docs/capability/*.md (1 份实测)
- [x] Edit MEMORY.md #24 段追加 12+ 份 memory + 3 份决策 + 1 份 capability
- [x] git add memory/MEMORY.md + memory/w-n-mem-index-expand-{startup,closure}.md
- [x] git commit + push origin main
- [x] 写 W-N-MEM +2 收口 memory (5 件套守恒实测)

---

## 派工 brief 偏差据实上报

派工 brief 列 12+ 份 memory, 实测 21 份 (含 W-N-D+ 3 份 + W-N-ANC 2 份 + W-N-ARC 2 份 + W-N-E 1 份 closure + W-N-F 2 份 + W-N-GC 2 份, 据实不凑不缩):

| 派工 brief 估 | 实测 | 偏差 |
|---|---|---|
| 12+ 份 memory | 21 份 (W-N-A 2 + W-N-B 2 + W-N-C 2 + W-N-D 2 + W-N-D+ 3 + W-N-E 2 + W-N-F 2 + W-N-GC 2 + W-N-ARC 2 + W-N-ANC 2) | 派工 brief 偏少, 据实多列 |
| 3 份决策 doc | 3 份 (bge-m3 + cold-hot + lora) | 守恒 ✓ |
| 1 份 capability 报告 | 1 份 (gpu-bge-m3) | 守恒 ✓ |
| W-N-ARC 1 份 closure | 2 份 (startup + closure) | 派工 brief 漏 startup |
| W-N-ANC 不在范畴 | 2 份 (startup + closure, W-N-ANC +1 commit `650cd4ffa` 已存在) | 派工 brief 漏 ANC, 据实补 |

类 20 实战: 派工 brief 估 12+ 实测 21, 派工 brief 估 W-N-ARC 1 实测 2, 派工 brief 估 W-N-ANC 0 实测 2 — 全部据实不擅自扩不擅自缩

---

## 后续

- MEMORY.md #24 段已完整覆盖 W-N 周期 A/B/C/D/D+/E/F + GC + ARC + ANC + 决策 + capability
- 未来 W-N-G 阶段 (gpu-bge-m3 真生产) 派工时, 在 #24 段末尾追加 W-N-G {startup,closure} + W-N-ANC +1 (W-N-G 锚点补)
- 锚点范式: W-N 周期 ~562 → ~568 据实累计, W-N-MEM +0..+2 = 3 commits
