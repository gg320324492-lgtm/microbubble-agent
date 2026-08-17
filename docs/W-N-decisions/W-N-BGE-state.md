# W-N-BGE 真测现状盘点 (Plan v1 主拍决策 #3)

**调研时间**: 2026-08-17
**结论**: W-N-BGE 真测**已完成** (4 commit), 等 GPU 部署启动切流

---

## 现状 (2026-08-17 实测)

### Commit 历史 (4 commits, 已合并 main)
- `71b750949` - docs(memory): W-N-BGE-PRE 起步 (+0)
- `71e448595` - docs(memory): W-N-BGE-PRE 收口 (+2)
- `90c63793c` - docs(memory): W-N-BGE-REAL +0 起步真查
- `8c50c777a` - perf(rag): bge-m3 1000 题真测 encoder-only 数据 (W-N-BGE-A 收尾)

### 数据
- `results/round11-bge-m3-1000.json` (47 字段, 1000 题真测结果)
- 决策文档 `docs/decisions/2026-08-05-bge-m3-decision.md` (W-N-C +3 + W-N-BGE +2 更新)

### 0 业务代码改动完成
- ✅ 1000 题真测跑通 (BAAI/bge-m3 真加载路径)
- ✅ 5 维决策数据落档
- ✅ 决策大门禁结果 (主拍决策)
- ❌ 路由切流未启动 (需 GPU 部署 + 决策批准)

---

## 启动锚点 (主拍决策时启动, 严禁擅自)

W-N-BGE 路由切流条件:
1. **GPU 部署** (本地 RTX 5090 32G 已就绪, 部署 bge-m3 embedding 服务)
2. **路由层切流代码** (主拍决策批准后实施)
3. **回归测试通过** (W-N-BGE 1000 题真测已证 ≥ 90% baseline)

启动流程 (主拍决策时执行):
- 部署 bge-m3 embedding 服务 (Docker 容器)
- 路由切流 (10% → 50% → 100% 灰度)
- 监控 W-N-BGE-A 数据 (recall, latency, fallback rate)
- 通过 → 全量切换 (W-N-BGE-A 收口已就绪)
- 失败 → 保留 Qwen3-Embedding-0.6B

---

## 锚点范式累计

- 4c63bbc13 W-N-FILL commit ~596
- c6992927b W-N-G+ commit ~595
- 累计 16 commit, 0 业务代码改动

---

## 主拍决策单 (主拍填)

| 项 | 状态 |
|---|------|
| W-N-BGE 真测数据 | ✓ 1000 题完成 |
| 决策文档 | ✓ 5 维数据落档 |
| GPU 部署 bge-m3 服务 | [ ] |
| 路由切流实施 | [ ] |
| 主拍书面批准 | [ ] |

批准后执行: 部署 bge-m3 → 路由切流 (10% 灰度) → 监控 7 天 → 全量
