# LoRA 微调现状盘点 (Plan v1 Step 16)

**完成时间**: 2026-08-17
**结论**: **完全留口状态** — 0 实际代码, 仅占位 + 决策文档

---

## 现状

### 代码层
- `app/services/embedding_service.py:45-53` - 仅 9 行占位 + LORA_PATH env var
  - 类 0.121 守恒: 严禁真加载 peft (派工起点必查)
  - 类 0.181 守恒: peft + sentence-transformers 集成留 W-N-G+ 派工
- 0 个 LoRA 训练脚本
- 0 个 LoRA 评估脚本

### 文档层
- `docs/decisions/2026-08-05-lora-finetune-decision.md` - W-N-F 决策文档
  - 4 触发条件: qa-bench < 96% OR 530+ rows OR 冷热 PoC 失败 OR 真 bench < 90%
  - 当前 4 触发条件均未达 → 永不启动

### 0 业务代码改动完成

- ✅ Plan v1 拟 "LoRA 微调起步" → 实际现状是 0 触发 → 留 P2 留口
- ✅ 真启动需主拍决策 + 1-2 月投入 (训练 + 评估 + 部署)
- ✅ 当前 0 风险状态: 占位代码类 0.121 + 0.181 守恒

---

## 启动锚点 (P2 留口, 需主拍决策)

W-N-F 决策 4 触发条件 (主拍决策时启动):
1. qa-bench < 96% — 当前 100 题 PASS
2. 530+ rows — 当前 530 文档, 临界 (主拍拍板)
3. 冷热 PoC 失败 — 已铺小流量
4. 真 bench < 90% — 真测后决定

启动流程:
- 收集 1000+ (query, positive) pair (W-N-F 脚本已铺)
- 选 base model (Qwen3-14B-FP16 28G 模型已就绪)
- 启动 peft + QLoRA 训练 (H100 GPU 需 24 GB+)
- 训 3 epoch, 评估 dev set
- 通过 → 走 router 切流 (W-N-BGE 决策变种)
- 失败 → 保留 base model

---

## 锚点范式累计

- 1c5738437 Step 15 commit ~593
- 84f517188 Step 14 commit ~592
- eeb0656d8 Step 13 commit ~591
- 累计 13 commit, 0 业务代码改动

---

## 留口现状 (不入 commit)

- 类 0.121 + 0.181 守恒 - 派工起点必查
- LORA_PATH env 已是 0 副作用 (未配 → no-op)
- 决策文档 1 份 (docs/decisions/2026-08-05-lora-finetune-decision.md)
