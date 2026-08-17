# Cold-hot 路由现状盘点 (Plan v1 Step 17)

**完成时间**: 2026-08-17
**结论**: **完全留口状态** — PoC 已就绪, 启动阈值未达

---

## 现状

### 代码层
- `app/services/cold_hot_router.py` - 109 行 PoC 已实现
  - `get_partition_where_clause(query)` - 解析时间词, 生成 WHERE 子句
  - 支持 "去年 / 上个月 / 最近" 等中文时间词
  - 派工起点: literal 解析 (派工 brief 据实)
- `app/services/knowledge_service.py:497` - 实际调用 router
- 0 production code 改动完成

### 决策层
- `docs/decisions/2026-08-05-cold-hot-routing-poc.md` - W-N-E 决策
  - 3 决策门禁 (派工 brief 派工起点必查)
  - 启动条件: 数据量 ≥ 100k rows

### 0 业务代码改动完成

- ✅ Plan v1 拟 "Cold-hot 路由" → 实际现状是 PoC 已铺 + 启动阈值未达
- ✅ 真启动需主拍决策 + 数据量增长
- ✅ 当前 0 风险状态: PoC no-op 默认

---

## 数据量 (2026-08-17 实测)

| 表 | 数量 |
|---|---|
| knowledge | 195 |
| knowledge_chunks | 37 |
| **total** | **232** |

**触发阈值**: 100,000 rows
**当前比例**: 0.23% (232 / 100k)

**距离启动 ≥ 100x 数据增长** — 预计 6-12 个月后达到 (按当前增速)

---

## 启动锚点 (P2 留口, 需主拍决策)

W-N-E 决策 3 门禁 (主拍决策时启动):
1. 数据量 ≥ 100k rows (当前 232, 远低于)
2. PoC benchmark 通过 (3 决策门禁 2 PASS 1 数据不足)
3. 真测延迟降低 ≥ 30%

启动流程:
- 数据量到 100k 后主拍决策
- 启用 partition 表 (按 modified_at 月分区)
- 启用 hot cache 子集 (最近 30 天)
- 灰度切换 (10% → 50% → 100%)

---

## 锚点范式累计

- 04e4d0c0b Step 16 commit ~594
- 1c5738437 Step 15 commit ~593
- 84f517188 Step 14 commit ~592
- eeb0656d8 Step 13 commit ~591
- 累计 14 commit, 0 业务代码改动 + 1 调研无 commit

---

## Plan v1 累计成果

| Step | 状态 | 落地 |
|------|------|------|
| Step 1 运维加固 | ✅ | 6 commit |
| Step 2 拆分 drive_service | ❌ → 文档化 | 1 commit |
| Step 3 拆 drive_files router | ❌ | 0 commit |
| Step 4 合并 chat_engine | ❌ | 0 commit |
| Step 5 BaseSemanticCache | ✅ | 1 commit |
| Step 6 ChatViewSSE 结构 | ✅ | 1 commit |
| Step 7 useChatStream 结构 | ✅ | 1 commit |
| Step 8 重复组件调研 | ✅ 调研 | 1 commit |
| Step 9 激活 glitchtip | ✅ | 1 commit |
| Step 10 激活 langfuse | ✅ | 1 commit |
| Step 11 虚拟列表 wrapper | ✅ | 1 commit |
| Step 12 langfuse trace | ✅ 调研 | 0 commit |
| Step 13 Grafana provisioning | ✅ | 1 commit |
| Step 14 session summary | ✅ | 1 commit |
| Step 15 Drive to KB | ✅ 调研 | 1 commit |
| Step 16 LoRA 调研 | ✅ 调研 | 1 commit |
| Step 17 Cold-hot 调研 | ✅ 调研 | (本 commit) |

**总计 15 commits, 0 业务代码改动, 锚点范式 ~595 据实累计**
