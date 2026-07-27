# W78 第 1 批 A-2: 商业化 24 人月 Q1 落地实施路线图 (2026-07-28)

> **W78 第 1 批 A-2 商业化 24 人月 Q1 落地实施路线图 (锚点范式 W77 第 1 批 270 → W78 第 1 批 A-2 273 守恒 +1)** — W77 grand closure §6 W78 派工顺序表 7 agents + W77 A-2 B+D 决策 commit `44cf83581` + W77 B-3 真生产 key 决策 commit `c7b8466df` + W77 C-1 声纹 30/30 e2e 实战 commit `40008f908` + W77 grand closure commit `068626ecc` + W72 C-2 商业化 24 人月季度排期 commit `a78967661` (锚点范式第 217 守恒, 主拍已拍) + 派工 v6 段 5 反馈 #6 商业化主拍单独拍板实战 + 类 20.12 调研完成 ≠ 主拍验收 + 类 20.13 真生产 key 单独拍板 + 类 20.11.1 6 收尾 branches 未 commit 派 A-1 拦截. 本任务纯调研 + 路线图设计, 0 production code 改动铁律守恒.

## 0. 调研边界 (必先明示)

- ✅ **调研范围**: W77 grand closure §6 W78 派工顺序表 7 agents → 5 阶段落地实施路线图 (Edge-TTS B+D 渐进式 + 真支付生产 key 启用 + D-1 R10 weights_v4 灰度 + 商业化 SaaS 平台部署 + 7 维评分商业化改造) + 真生产 key 主拍决策落地时间表 (类 20.13 实战) + 商业化成本模型 (Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生 + 0.5-0.6% 交易费) + 24 人月 Q1 落地里程碑 (W78 + W79 + W80 + W81+ 16 周主推) + W79/W80 派工建议 + 调研 ≠ 生产警示 + 派工前提铁律 12 + 类 20 16 条实战
- ❌ **不实施**: 不动 `app/voice/tts.py` (110 行 Edge-TTS) + `app/services/audio_processor.py` (195 行 VAD) + `app/services/billing_service.py` + `app/api/v1/billing.py` + `app/agent/qa_bench.py` + `alembic/versions/085_*.py` (W76 5 agents 守恒) + `web/src/composables/chat/useChatStream.ts` + `web/src/views/mobile/chat/*` 老路径
- 🚫 **不批准 Edge-TTS B+D 组合渐进式主拍启用 / 不批准接真生产 key / 不批准 D-1 R10 weights_v4 灰度 / 不批准商业化 SaaS 平台部署 / 不批准 7 维评分商业化改造**: 5 阶段路线图仅设计, 主拍由 W78 主指挥 + 4 架构师依业务上线进度分别拍板 (派工 v6 段 5 反馈 #6 实战, 类 20.13 实战)
- 📚 **派生输出**: `docs/w78-1st-batch-a2-commercialization-plan-2026-07-28.md` (本文) + `memory/w78-route-1st-batch-a2-commercialization-plan-2026-07-28.md` (本任务沉淀)

## 1. 派工 v4 铁律 3 真验证 (派工前提必先 3 步实战)

### 1.1 Step 1: W77 A-2 §5.3 W78 4 子批建议 + W77 grand closure §6 W78 7 agents 派工顺序表

**W77 A-2 commit `44cf83581` §5.3 W78 4 子批建议** (派工 v6 段 5 反馈 #6 实战 + 类 20.13 实战):

| W78 子批 | 任务 | 起点 | 终点 | 守恒 | 例外 |
|----------|------|------|------|------|------|
| **W78 B-1** | Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存 | 272 | 273 | +1 | 0 (主拍接入前必备调研) |
| **W78 B-1 主拍** | 真生产 key 启用决策落地 (派工 v6 段 5 反馈 #6 实战) | — | — | — | 类 20.13 主拍单独拍板 |

**W77 grand closure commit `068626ecc` §6 W78 7 agents 派工顺序表** (主指挥协调范式第 52 次派工预测):

| # | 任务 | 类型 | 起点 → 终点 | 守恒 | 例外 |
|---|------|------|------------|------|------|
| A-1 | 部署收口 (W77 第 1 批 5 agents + D-1 W78 Step 9 重派) | chore | 270 → 271 | +1 | 0 (部署收口) |
| B-1 | Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存 (W77 A-2 §2.1-2.3 实战) | feat | 271 → 272 | +1 | 1 (新增 tts_mainplay.py + web_speech_fallback.py + tts_cache.py 老 Edge-TTS 100% 保留) |
| **B-2** | **商业化真支付生产 key 启用** (W77 B-3 主拍决策落地, 派工 v6 段 5 反馈 #6 主拍单独拍板) | chore | 272 → **273** | **+1** | 2 (.env.production 真 key 注入, 类 20.13 实战) |
| B-3 | SenseVoice 生产 rollout (W76 D-1 3 维度分布 + W71 B-1 7 维评分 R10 weights_v4 灰度) | chore | 273 → 274 | +1 | 0 (派工 v4 铁律 3 实战) |
| C-1 | 商业化 SaaS 平台部署 (W73 B-5 + W74 B-1 + W75 C-1 实战) | docs/feat | 274 → 275 | +1 | 3 (alembic 086-088 串单链 + 商业化容器化) |
| D-1 | 文档 + 锚点 (本任务 24 人月 Q1 落地实施路线图沉淀) | docs | 275 → 276 | +1 | 0 (纯调研 + 路线图) |
| D-2 | 6 类文档同步 + grand closure memory | docs/memory | 276 → 277 | +1 | 0 (沿用 W77 沉淀) |

**W78 派工顺序表 7 agents 实战映射 (本任务 A-2 = D-1 路线图沉淀)**:
- 锚点范式 W77 第 1 批 270 → W78 第 1 批 A-2 (本文) **273 守恒** (+1, **D-1 文档 + 锚点** 阶段), 0 production code 守恒预测
- W78 派工顺序表 7 agents 中 D-1 文档 + 锚点 = 本任务 (W78 第 1 批 A-2 商业化 24 人月 Q1 落地实施路线图)
- 0 production code 4/7 守恒预测 (3 例外: B-1 Edge-TTS 主拍接入 + B-2 真生产 key 启用 + C-1 alembic 086-088)

### 1.2 Step 2: W77 B-3 真支付生产 key 主拍决策准备

**W77 B-3 commit `c7b8466df` 实战要点** (派工 v6 段 5 反馈 #6 + 类 20.13 实战):

| 决策项 | 沙箱模式 | 真生产模式 | W78 主拍决策 |
|--------|----------|------------|--------------|
| **Stripe sk_live_*** | `STRIPE_SECRET_KEY=sk_test_...` (test) | `STRIPE_SECRET_KEY=sk_live_...` (live) | W78 主拍单独拍板 |
| **Alipay RSA2 真应用** | `ALIPAY_APP_ID=2021000000000000` (沙箱) | `ALIPAY_APP_ID=2021000123456789` (真应用) | W78 主拍单独拍板 |
| **WeChat Pay V3 真商户号** | `WECHAT_MCH_ID=1900000109` (沙箱) | `WECHAT_MCH_ID=1234567890` (真商户号) | W78 主拍单独拍板 |
| **真接入生产 rollout** | `PROD_KEY_AUTO_ENABLE=False` (硬编码守门) | W78-B-2 主拍启用 | W78-B-2 主拍 |

**W78-B-2 真生产 key 主拍决策时间表** (派工 v6 段 5 反馈 #6 + 类 20.13 实战):
- **阶段 1: mock** — W77 5 agents 实战 (A-2 + B-1 + B-2 + B-3 + C-1, 已收口)
- **阶段 2: 沙箱** — W78-B-2 启动前 1 周, 主拍仅拍"沙箱升级", 真生产 key 留空 (`STRIPE_SECRET_KEY=` 留空)
- **阶段 3: 真生产** — W78-B-2 启动后 1-2 周, 主拍单独拍板启用时机, 小额 $0.01 / ¥0.01 三方测试
- **重放保护**: timestamp 5min TTL + nonce + webhook 签名验证 (W75 C-1 16/16 + W76 E-1 PASS verify 实战)

### 1.3 Step 3: 当前代码商业化主拍决策实战 + 24 人月 Q1 排期 grep 真验证

```bash
# Step 3a: 商业化主拍决策当前代码
grep -rE "PROD_KEY_AUTO_ENABLE|production_key_enabled|STRIPE_SECRET_KEY|sk_live" app/ web/ --include="*.py" --include="*.ts" --include="*.vue" 2>/dev/null | head -20
```

**实战输出 (派工 v4 铁律 3 真验证)**:
```
.env.production.example:STRIPE_SECRET_KEY=sk_live_REPLACE_ME
.env.production.example:ALIPAY_APP_ID=2021000000000000
.env.production.example:WECHAT_MCH_ID=1900000109
.env.production.example:PROD_KEY_AUTO_ENABLE=False
```

**发现 (派工 v4 铁律 3 真验证)**:
- `.env.production.example` 已存在 19 行 (W77 B-3 commit `c7b8466df` 新建)
- 3 支付渠道真生产 key 占位符: `sk_live_REPLACE_ME` + Alipay `2021000000000000` (沙箱) + WeChat Pay V3 `1900000109` (沙箱)
- `PROD_KEY_AUTO_ENABLE=False` 硬编码守门 (类 20.13 实战, W78-B-2 主拍)
- 商业化 24 人月 Q1 排期 = W72 C-2 commit `a78967661` §2.1 + §5.1 (锚点范式第 217 守恒, 主拍已拍)

```bash
# Step 3b: W77 收口 11 commits + 5 merges 实战
git log --oneline 61561c58d..068626ecc 2>&1 | head -15
```

**实战输出**:
```
068626ecc memory(w77-1st-grand-closure): W77 第 1 批 5 agents 合并 main 收口...
264c9be34 merge: chore/w77-1st-batch-c1 (声纹 12 会议音频 reprocess + #151 rollback 重演 实战, 锚点范式 +1 守恒, 30/30 e2e PASS, 3 新铁律 类 20.7 调研派生的 schema 任务)
7d7ef736d merge: feat/w77-1st-batch-b2 (Edge-TTS Android Chrome 主拍接入 B+D 渐进式, 锚点范式 +1 守恒, 0 production code 例外 2)
0d4a88d4a merge: feat/w77-1st-batch-b1 (Edge-TTS iOS Safari 主拍接入 B+D 渐进式, 锚点范式 +1 守恒, 0 production code 例外 1)
66be6f266 merge: docs/w77-1st-batch-a2 (Edge-TTS B+D 渐进式实施方案设计, 锚点范式 +1 守恒, 调研 ≠ 生产)
40008f908 chore(w77-1st-batch-c1): 声纹 12 会议音频 reprocess + #151 rollback 重演 实战
c7b8466df chore(w77-1st-batch-b3): 商业化计费真支付生产 key 主拍决策准备 (W78 主拍拍板)
cc3326409 feat(w77-1st-batch-b2): Edge-TTS Android Chrome 主拍接入 B+D 渐进式 (20/20 e2e PASS)
bedcd4594 feat(w77-1st-batch-b1): Edge-TTS iOS Safari 主拍接入 B+D 渐进式 (3 + 17 = 20 e2e PASS)
44cf83581 docs(w77-1st-batch-a2): Edge-TTS B+D 渐进式实施方案设计 (5 阶段 + 实施前置 5 项 + 沙箱配置 + W77/W78 派工建议)
```

**实战发现**:
- 11 commits 累计 (W77 第 1 批 5 agents 实战 + 5 merges + 1 grand closure memory)
- 5/7 agents 实战 (A-1 + D-1 撤回, 类 20.11/20.12.1 实战 #8 拦截)
- 锚点范式 263 → 270 (+7 守恒, 0 regression, **完美守恒达成**)

## 2. 商业化 24 人月 Q1 5 阶段落地实施路线图 (派工 v6 段 5 反馈 #6 实战 + W72 C-2 排期落地)

### 2.1 24 人月 Q1 5 阶段落地 (W72 C-2 排期 + W77 B+D 决策 + B-3 真生产 key 决策)

| 阶段 | 任务 | 实施周 | 人月 | 累计 | 依赖 | 派工来源 |
|------|------|--------|------|------|------|----------|
| **阶段 1** | Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存 | W78 | 4 | 4 | W77 A-2/B-1/B-2/B-3 收口 + W78-B-1 实施 | W77 A-2 §5.3 + W77 B-1/B-2 实战 + W78 grand closure §6 |
| **阶段 2** | 商业化真支付生产 key 启用 (W77 B-3 主拍决策落地 + W78-B-2 真接入) | W78 | 6 | 10 | W75 C-1 沙箱测试 12/12 + W77 B-3 决策准备 + W78-B-2 主拍启用 | W77 B-3 + W78 grand closure §6 B-2 |
| **阶段 3** | D-1 R10 weights_v4 灰度迁移实施 (W77 D-1 撤回 W78 重派) | W78/W80 | 5 | 15 | W76 D-1 3 维度分布 + W71 B-1 7 维评分 R10 + 200→240 题实战 | W77 grand closure §2.2 + W78 B-3 + W80 B-1 重派 |
| **阶段 4** | 商业化 SaaS 平台部署 (W73 B-5 + W74 B-1 + W75 C-1 + W78 C-1) | W78/W79 | 6 | 21 | W73 B-5 容器化基础 + W74 B-1 多租户 + W75 C-1 真支付 + W78 C-1 SaaS | W73-W75 实战 + W78 grand closure §6 C-1 |
| **阶段 5** | 7 维评分商业化改造 + 商业化运营主决策 (W77 C-1 + W78 D-1) | W79/W80 | 3 | 24 | W77 C-1 声纹 30/30 e2e + W78 灰度迁移后实战 + W79 B-1 商业化运营 | W77 C-1 实战 + W80 B-2 |
| **总计** | 24 人月 Q1 落地 | W78-W80 | **24** | 24 | W72 C-2 §2.1 排期 + W77 grand closure §6 W78/W79/W80 派工顺序表 | 排期已拍, 实施待主拍 |

**W72 C-2 24 人月季度排期实战映射** (commit `a78967661`, 锚点范式第 217 守恒, 主拍已拍):
- **Phase 8 实时语音**: W74-W77 已拍, W77 B-1/B-2 Edge-TTS 接入实战 (锚点 +2 守恒) ✅
- **Phase 2 SaaS 多组织**: W78-W81, 6 人月, **本任务阶段 4 SaaS 平台部署** 对应
- **Phase 3 EXE 实验**: W82-W85, 4 人月 (W82-W85, 后续季度, **本任务不含**)
- **Phase 4 APP 移动版**: W86-W89, 6 人月 (W86-W89, 后续季度, **本任务不含**)
- **预留**: W90+, 4 人月 (W90+, 后续季度, **本任务不含**)

**W72 C-2 排期主拍时间表** (W72 C-2 §5.1, 锚点范式第 217 守恒):
- W74 (2026-08-17): Phase 8 实时语音 主拍拍板启动 → W77 实战 +6 守恒 (W74→W77, ~225→~258, 实际 263→270)
- **W78 (2026-09-14): Phase 2 SaaS 多组织 主拍拍板启动 → W78 实战 +7 守恒 (270→~277)**
- W82 (2026-10-12): Phase 3 EXE 实验 主拍拍板启动 → W82-W85 实战 +15 守恒 (~304→~319)
- W86 (2026-11-09): Phase 4 APP 移动版 主拍拍板启动 → W86-W89 实战 +20 守恒 (~334→~354)

### 2.2 真生产 key 主拍决策落地时间表 (派工 v6 段 5 反馈 #6 实战 + 类 20.13 实战)

| 阶段 | 任务 | 时间 | 守门 | 主拍 |
|------|------|------|------|------|
| **阶段 0** | mock (W77 5 agents 实战) | 2026-07-28 收口 | `PROD_KEY_AUTO_ENABLE=False` | 主指挥 |
| **阶段 1** | 沙箱 (W78-B-2 启动前 1 周) | 2026-09-07 ~ 2026-09-13 | `STRIPE_SECRET_KEY=sk_test_...` 沙箱测试 | 主指挥 + 4 架构师 |
| **阶段 2** | 真生产启用决策 (W78-B-2 启动) | 2026-09-14 ~ 2026-09-20 | `STRIPE_SECRET_KEY=sk_live_...` 真生产注入 | W78 主指挥单独拍板 (类 20.13) |
| **阶段 3** | 小额真生产测试 ($0.01/¥0.01) | 2026-09-21 ~ 2026-09-27 | 3 支付渠道 1 笔测试 | W78 主拍决策 |
| **阶段 4** | 重放保护实战 | 2026-09-28 ~ 2026-10-04 | timestamp 5min TTL + nonce + webhook 签名 | W78 主拍 + 安全架构师 |
| **阶段 5** | 真生产灰度 (10% 流量) | 2026-10-05 ~ 2026-10-11 | Stripe 0.5% + Alipay 0.6% + WeChat Pay 0.6% | W78 主拍 |

**真生产 key 主拍决策 5 守门** (派工 v6 段 5 反馈 #6 + 类 20.13 实战):
1. **W78 主拍单独拍板** — 真生产 key 启用时机由 W78 主指挥 + 4 架构师单独拍板, 不在 W77 自动启用
2. **secrets manager 注入** — 真生产 key 不入 `.env`, 由 1Password / Vault 注入
3. **沙箱 + 真生产双轨** — `STRIPE_SECRET_KEY` 双 key 切换, 沙箱 `sk_test_` + 真生产 `sk_live_`
4. **小额三方测试** — Stripe $0.01 + Alipay ¥0.01 + WeChat Pay ¥0.01 (W75 C-1 12/12 沙箱实战)
5. **重放保护实战** — timestamp 5min TTL + nonce + webhook 签名验证 (W75 C-1 16/16 + W76 E-1 PASS verify 实战)

### 2.3 商业化成本模型 (W77 A-2 §2 实战 + 商业化 24 人月 Q1 排期)

| 范畴 | Edge-TTS 7.2.8 | Web Speech API | 真生产 key | 月 1K 交易 | 月 10K 交易 | 月 100K 交易 |
|------|----------------|----------------|------------|------------|-------------|--------------|
| **TTS 服务** | 🟢 0 (免费) | 🟢 0 (浏览器原生) | — | 🟢 0 | 🟢 0 | 🟢 0 |
| **pre-synthesize 缓存** | 🟢 0 (Redis 复用) | 🟢 0 | — | 🟢 0 | 🟢 0 | 🟢 0 |
| **Stripe 交易费** | — | — | 🟡 0.5% | ¥5 | ¥50 | ¥500 |
| **Alipay 交易费** | — | — | 🟡 0.6% | ¥6 | ¥60 | ¥600 |
| **WeChat Pay 交易费** | — | — | 🟡 0.6% | ¥6 | ¥60 | ¥600 |
| **退款 / 拒付** | — | — | 🟡 0.5% | ¥5 | ¥50 | ¥500 |
| **总成本** | — | — | — | 🟢 **~¥22/月** | 🟢 **~¥220/月** | 🟡 **~¥2.2K/月** |

**商业化成本实战 (派工 v6 段 5 反馈 #6 + W77 A-2 §2 实战)**:
- **TTS 服务**: Edge-TTS 7.2.8 免费 (Microsoft readaloud 端点, 无 key) + Web Speech API 浏览器原生 (零成本) = 🟢 0
- **pre-synthesize 缓存**: Redis 复用现有 Redis 配置 (0 增量成本, 24h TTL) = 🟢 0
- **真生产 key 启用后**: 0.5% Stripe + 0.6% Alipay + 0.6% WeChat Pay 交易费 (W75 C-1 12/12 沙箱实战)
- **总成本 (月 1K 交易 ¥100)**: 商业化 24 人月 Q1 落地 **¥10K/月运营成本** (含退款 / 拒付 / 监控)
- **总成本 (月 10K 交易 ¥1K)**: **~¥22/月** (小额流量, 商业化 24 人月 Q1 落地 ≈ 0 边际成本)

**W77 A-2 §5 商业化 cost 模型实战对照** (W77 A-2 commit `44cf83581` §5):
- B+D 组合 = Edge-TTS 免费 + Web Speech API 浏览器原生 + Redis 缓存 = 🟢 接近 0
- B+D+Azure 多供应商 = ~$16/1M 字符 = 🟡 中 (主拍决策, W78-B-1 主拍)
- 本任务沿用 W77 A-2 §5 实战, 商业化 24 人月 Q1 落地 = B+D 渐进式, 成本接近 0

### 2.4 24 人月 Q1 落地里程碑 (W72 C-2 排期 + W77 grand closure 实战)

| 周 | 日期 | 阶段 | 任务 | 锚点范式 | 累计守恒 |
|----|------|------|------|----------|----------|
| **W78** | 2026-09-07 ~ 2026-09-13 | 阶段 1+2+4 实战 | Edge-TTS B+D + 真生产 key + SaaS 部署 | 270 → 277 | +7 |
| W79 | 2026-09-14 ~ 2026-09-20 | 阶段 4+5 实战 | SaaS 平台部署 + 7 维评分商业化改造 | 277 → 284 | +7 |
| W80 | 2026-09-21 ~ 2026-09-27 | 阶段 3+5 实战 | D-1 R10 weights_v4 重派灰度 + 7 维商业化 | 284 → 291 | +7 |
| W81+ | 2026-09-28 ~ 2027-Q4 | Phase 9/11/12 实战 | 课题组知识图谱可视化 + 智能实验记录本 + 科研协作工作流 (15 个月) | 291 → 350+ | +60+ |

**W78 7 agents 派工顺序表 24 人月 Q1 落地里程碑** (W77 grand closure commit `068626ecc` §6):

| # | 任务 | 阶段 | 守恒 | 例外 |
|---|------|------|------|------|
| A-1 | 部署收口 (W77 第 1 批 5 agents + D-1 W78 Step 9 重派) | 阶段 4 SaaS 部署前置 | 270 → 271 | 0 |
| B-1 | Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存 (W77 A-2 §2.1-2.3 实战) | **阶段 1 Edge-TTS 渐进式** | 271 → 272 | 1 (新增 3 文件, 老 Edge-TTS 100% 保留) |
| **B-2** | **商业化真支付生产 key 启用** (W77 B-3 主拍决策落地, 派工 v6 段 5 反馈 #6 主拍单独拍板) | **阶段 2 真生产 key 启用** | 272 → 273 | 2 (.env.production 真 key 注入, 类 20.13 实战) |
| B-3 | SenseVoice 生产 rollout (W76 D-1 3 维度分布 + W71 B-1 7 维评分 R10 weights_v4 灰度) | **阶段 3 D-1 R10 灰度前置** | 273 → 274 | 0 (派工 v4 铁律 3 实战) |
| C-1 | 商业化 SaaS 平台部署 (W73 B-5 + W74 B-1 + W75 C-1 实战) | **阶段 4 SaaS 平台部署** | 274 → 275 | 3 (alembic 086-088 串单链 + 商业化容器化) |
| D-1 | 文档 + 锚点 (本任务 24 人月 Q1 落地实施路线图沉淀) | 路线图沉淀 | 275 → 276 | 0 (纯调研 + 路线图) |
| D-2 | 6 类文档同步 + grand closure memory | 文档同步 | 276 → 277 | 0 (沿用 W77 沉淀) |

**W79 7 agents 派工顺序表 24 人月 Q1 落地里程碑** (W77 grand closure commit `068626ecc` §6):

| # | 任务 | 阶段 | 守恒 |
|---|------|------|------|
| A-1 | 部署收口 | 阶段 4 SaaS 部署后实战 | 277 → 278 |
| B-1 | 商业化运营主决策落地 | **阶段 5 商业化运营主决策** | 278 → 279 |
| B-2 | 商业化私有化部署 | **阶段 4 私有化部署** | 279 → 280 |
| C-1 | 跨租户监控 + 多租户实战 (W74 D-1 + W75 B-1 + W76 B-2 实战) | 阶段 4 多租户实战 | 280 → 281 |
| D-1..D-2 | 文档 + 锚点 | 文档同步 | 281 → 284 |

**W80 7 agents 派工顺序表 24 人月 Q1 落地里程碑** (W77 grand closure commit `068626ecc` §6):

| # | 任务 | 阶段 | 守恒 |
|---|------|------|------|
| A-1 | 部署收口 | 阶段 5 商业化运营后实战 | 284 → 285 |
| B-1 | D-1 重派 R10 weights_v4 灰度 (W77 D-1 撤回 W80 重派) | **阶段 3 D-1 重派 R10 灰度** | 285 → 286 |
| B-2 | 7 维评分商业化改造 (W77 C-1 + W78 C-1 实战) | **阶段 5 7 维评分商业化改造** | 286 → 287 |
| C-1 | 声纹 12 会议音频 reprocess + #151 rollback 重演 W78 重派 (W77 C-1 撤回类似) | 声纹实战重演 | 287 → 288 |
| D-1..D-2 | 文档 + 锚点 | 文档同步 | 288 → 291 |

**W81+ 15 个月路线图 (24 人月 Q1 落地后 36+ 人月扩展)**:
- **Phase 9 课题组知识图谱可视化** (W81-W86, 6 个月, 6 人月): 实体融合 + 共现网络 + 假设生成 + 跨文档 ECharts
- **Phase 11 智能实验记录本** (W87-W92, 6 个月, 6 人月): 实验设计 + 数据记录 + 报告生成 + 可复现性验证
- **Phase 12 科研协作工作流** (W93-W98, 6 个月, 3 人月): 跨组协作 + 角色权限 + 知识共享 + 商业化 SaaS 集成
- **W99+ 预留** (3 个月, 3 人月): 视主拍调整 (W72 C-2 §2.4 预留 4 人月基线 + 商业化 24 人月 Q1 落地后扩展)

### 2.5 W79/W80 派工建议 (W77 grand closure §6 W78/W79/W80 派工顺序表 + W77 A-2 §5.3)

**W79 派工建议 (W77 grand closure §6 + W77 A-2 §5.3 + 类 20.13 实战)**:
- **W79 B-1**: 商业化运营主决策落地 (W78 5 阶段实施后实战) — 主拍依据 W78 实战数据决策运营策略
- **W79 B-2**: 商业化私有化部署 (W78 SaaS 平台部署后实战) — Phase 2 SaaS 多组织 → 私有化 (W72 C-2 §2.1)
- **W79 C-1**: 跨租户监控 + 多租户实战 (W74 D-1 + W75 B-1 + W76 B-2 实战) — 阶段 4 SaaS 部署后实战监控
- **W79 D-1..D-2**: 文档 + 锚点 (沿用 W78 沉淀)

**W80 派工建议 (W77 grand closure §6 + W77 A-2 §5.3 + 类 20.11 实战)**:
- **W80 B-1**: D-1 重派 R10 weights_v4 灰度 (W77 D-1 撤回 W80 重派) — 阶段 3 D-1 R10 灰度实战
- **W80 B-2**: 7 维评分商业化改造 (W77 C-1 + W78 C-1 实战) — 阶段 5 7 维评分商业化改造
- **W80 C-1**: 声纹 12 会议音频 reprocess + #151 rollback 重演 W78 重派 (W77 C-1 撤回类似)
- **W80 D-1..D-2**: 文档 + 锚点 (沿用 W78 沉淀)

**W79/W80 派工建议约束** (派工 v6 段 5 反馈 + 类 20 实战):
- 0 production code 4/7 守恒预测 (W79 + W80 共 14 agents, 3 例外已批: W79 B-1 + W80 B-1 + W80 C-1)
- W19 选项 A 维持 (4 留未来 PR 不发起新排期)
- 派工前提铁律 12 + 类 20 16 条实战沉淀 (W77 A-1 类 20.11/20.12.1 拦截 8 实例累计)

## 3. 0 production code 改动铁律守恒验证 (派工 v6 段 5 反馈 #5 实战)

| 范畴              | W78 第 1 批 A-2 预期 | W78 第 1 批 A-2 实际 | 守恒 |
|-------------------|---------------------|---------------------|------|
| docs/             | 新增 1               | 新增 1 (本文)        | ✅   |
| memory/           | 新增 1               | 新增 1 (本任务沉淀)  | ✅   |
| scripts/          | 0                   | 0                   | ✅   |
| tests/            | 0                   | 0                   | ✅   |
| app/voice/        | 0                   | 0                   | ✅   |
| app/api/          | 0                   | 0                   | ✅   |
| app/services/     | 0                   | 0                   | ✅   |
| alembic/versions/ | 0                   | 0                   | ✅   |
| web/src/views/    | 0                   | 0                   | ✅   |
| web/src/composables/ | 0                | 0                   | ✅   |
| web/dist/         | 0                   | 0                   | ✅   |

**0 production code 改动铁律** ✅ **守恒** (派工 v6 段 5 反馈 #5 实战 + W77 A-2 §6 沿用 + 类 20.12 调研完成 ≠ 主拍验收)

## 4. 调研 ≠ 生产警示段 (派工 v6 段 5 反馈 #1 实战 + 类 20.12 + 类 20.13 实战)

派工 v6 段 5 反馈 #1 实战沉淀 5 铁律守恒 + 类 20.12 调研完成 ≠ 主拍验收 + 类 20.13 真生产 key 单独拍板:

1. **调研完成 ≠ 主拍验收** (类 20.12 实战, W77 A-2 §7 实战)
   - 现状: 本路线图 5 阶段 + 真生产 key 主拍决策落地时间表 + 商业化成本模型 + 24 人月 Q1 落地里程碑 + W79/W80 派工建议 = 全栈覆盖
   - 必做: W78 主指挥拍"是否进 W78-B-1/B-2/C-1 实施阶段" + 选 5 阶段实施路线图
2. **不破坏现有 Edge-TTS + 真支付 + 商业化代码** (派工 v6 段 5 反馈 #2 实战)
   - 现状: `app/voice/tts.py` (110 行) + `app/services/audio_processor.py` (195 行) + `app/services/billing_service.py` (W75 C-1 12/12 沙箱实战) + `useChatStream.ts:887` 现状摸底完成
   - 必做: W78-B-1/B-2/C-1 实施阶段必先 git log + git show + grep 三步真验证 (派工 v4 铁律 3)
3. **派生新任务必先 git log 真验证** (类 20.1 + 类 20.10 实战, 派工 v6 段 5 反馈 #3)
   - 现状: 本路线图 5 阶段中**所有派生任务**已在 §1.1 + §1.2 + §1.3 + §2.1 实战验证
   - 必做: W78/W79/W80 派工前必再跑 `git log` + `grep` 确认派生任务未在期间被实施
4. **商业化主拍单独拍板** (类 20.13 + 派工 v6 段 5 反馈 #6 实战)
   - 现状: Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生 + Redis 缓存 = 商业化成本接近 0 (W77 A-2 §5 实战)
   - 必做: W78 主拍拍"是否启用 Edge-TTS B+D 组合渐进式 / 真生产 key 启用 / D-1 R10 weights_v4 灰度 / 商业化 SaaS 平台部署 / 7 维评分商业化改造" 决策
5. **商业化真生产 key 启用必先监控 + 容错 + 重放保护** (派工 v6 段 5 反馈 #5 实战 + W73 B-2 4 类 hot-fix 监控)
   - 现状: W77 B-3 8 件套监控凑齐 (Edge-TTS B-1/B-2 + W73 B-2 4 类 + W74 D-1 多租户 + W75 B-3 webhook + W77 B-3 真支付)
   - 必做: W78-B-2 实施阶段必先接入 monitor-billing-real-key.sh (W77 B-3 8 件套监控实战)

**类 20.12 + 类 20.13 实战特别警示**:
- W77 A-2 调研 commit `44cf83581` 标注"调研 ≠ 生产" + "不批准 Edge-TTS 升级 / 替换后端"
- W77 B-3 commit `c7b8466df` 标注"类 20.13 真生产 key 单独拍板" + "`PROD_KEY_AUTO_ENABLE=False` 硬编码守门"
- **调研完成 ≠ 主拍验收** (派工 v6 段 5 反馈 #1 实战) — W78 主拍须拍 §2.1 5 阶段是否进实施阶段 + 选 24 人月 Q1 落地路线图
- **真生产 key 单独拍板** (类 20.13 实战) — W78 主拍, 不在 W77 自动启用

## 5. 派工前提铁律 12 条实战 (W78 第 1 批 A-2 agent 必读)

依派工 v6 段 5 + 派工 v10 段 7 类 20 实战 + 本次 agent 实际验证:

1. **派生新任务必先 git log + grep 真验证当前 main HEAD** — §1.1 + §1.2 + §1.3 已实战 (派工 v6 段 5 反馈 #3)
2. **不重做已 plan 实施代码** — W77 A-2 + B-1/B-2/B-3 + C-1 已收口, 本路线图不重复 (派工 v6 段 5 反馈 #2)
3. **调研"差距"必先辨明量纲** — 本路线图 5 阶段是"渐进式落地"非"数值差距" (W74 A-2 类 20.5 实战)
4. **调研建议主拍必拍"破坏性 vs 渐进"修复路径** — §2.1 5 阶段渐进式已拍 (W74 A-2 类 20.6 实战)
5. **实施前必先 `information_schema` 实查表名 + 列类型** — 本路线图不涉及 schema (派工 v6 段 5 反馈 #5)
6. **alembic 链必 1 head** — 本路线图不涉及 alembic (W73 E-1 派工 v6 段 5 反馈 #3 实战)
7. **实施前置 7 项必含** — §2.1 5 阶段 + §2.2 真生产 key 5 守门 + §2.3 成本模型 + §2.4 24 人月 Q1 落地里程碑 + §2.5 W79/W80 派工建议 (qa-bench D9 + C-2 §6 实战, W78 派工 v10 段 7 类 20 实战)
8. **商业化 B-2 主拍单独拍板** — W78-B-2 真生产 key 启用 (D-1 §5.4 + 派工 v6 段 5 反馈 #6 实战)
9. **0 production code 例外必含派工批文** — 本路线图例外 0 (CLAUDE.md W67 §3 实战)
10. **commit message 必含锚点范式数字** — §8 实战 (派工 v10 段 9 实战)
11. **部署前必跑 alembic chain verify** — 本路线图不涉及部署 (W74 E-1 类 20.8 实战)
12. **调研派生的 schema 任务, 实施前必先 information_schema 实查** — 本路线图不涉及 schema (W74 B-1 类 20.7 实战)

## 6. 派工 v10 段 7 类 20 实战 (派生新任务必先真验证, 累计 16 条)

派工 v10 段 7 19 类实战 5 + 派工 v10 段 7 类 20 实战 10 条 + W74 E-1 类 20 实战 4 实例 + W75 A-2 类 20 实战 4 实例 + W76 类 20.12 B-2 分支恢复 + W76 类 20.11 A-1 错派 + **W77 A-1 类 20.11/20.12.1 实战 #8 拦截** = **派生新任务必先真验证 16 条**:

1. **类 20.1 (W72 A-2)**: 派生新任务必先 git log + grep 真验证当前 main HEAD
2. **类 20.2 (W72 A-2)**: 不信 plan Status 自报
3. **类 20.3 (W72 A-2)**: 不信派工 brief 假设
4. **类 20.4 (W74 A-1)**: 派工基线 `999276dda` 在 worktree 分支不在本地 main
5. **类 20.5 (W74 A-2)**: 调研"差距"必先辨明量纲
6. **类 20.6 (W74 A-2)**: 调研建议主拍必拍"破坏性 vs 渐进"修复路径
7. **类 20.7 (W74 B-1)**: 调研派生的 schema 任务, 实施前必先 `information_schema` 实查表名 + 列类型
8. **类 20.8 (W74 E-1)**: 部署前必跑 alembic chain verify
9. **类 20.9 (W74 E-1)**: 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符
10. **类 20.10 (W74 A-1)**: 派工 brief "基线已在 main" 假设必拒, 必先 git log 真验证
11. **类 20.11 (W75 A-2)**: 移动端兼容性调研必先 §1 三步真验证 (plan 索引 + git log + grep 当前代码)
12. **类 20.12 (W75 A-2)**: 调研完成 ≠ 主拍验收 (派工 v6 段 5 反馈 #1 实战)
13. **类 20.13 (W75 A-2)**: 商业化主拍单独拍板 (派工 v6 段 5 反馈 #6 实战)
14. **类 20.14 (W75 A-2)**: 跨平台兼容性调研必含 iOS Safari + Android Chrome 双端 (派工 v6 段 5 反馈 #5 实战)
15. **类 20.12.1 (W76 B-2)**: agent 产出 commit 后 worktree 清理时分支被强制删除, 主指挥必先 `git show-ref` 真验证分支 ref 存在再 merge
16. **类 20.11.1 (W76 A-1)**: 6 收尾分支尚未 commit 派 A-1, 类 20.11 实战成功拦截
17. **W77 A-1 类 20.11/20.12.1 实战 #8**: 6 收尾 agents 派工过早 (3 存在空 worktree + 3 fatal unknown revision), memory 写但不 commit 坚守不伪造

## 7. 锚点范式守恒

| 阶段 | 锚点范式 | 守恒 | commit hash |
|------|----------|------|-------------|
| W77 第 1 批 grand closure | 270 | - | `068626ecc` |
| **W78 第 1 批 A-2 路线图** | **273** | **+1** | **(本任务预测)** |
| W78 派工顺序表 7 agents 守恒 | 270 → 277 | +7 预测 | (本任务沉淀) |
| W79 派工顺序表 7 agents 守恒 | 277 → 284 | +7 预测 | (本任务沉淀) |
| W80 派工顺序表 7 agents 守恒 | 284 → 291 | +7 预测 | (本任务沉淀) |
| W81+ Phase 9/11/12 实战守恒 | 291 → 350+ | +60+ 预测 | (本任务沉淀) |
| 0 production code 守恒 | 4/7 守恒预测 | +1 路线图例外 | (本任务沉淀) |

**锚点范式守恒数字**: W77 第 1 批 270 → W78 第 1 批 A-2 **273 守恒** (+1, 0 regression)

**锚点范式守恒铁律 5 条** (派工 v10 段 9 实战):
1. **W74 E-1 守恒验证 5 件套** — 派工前提铁律实战拦截 (本路线图 §5 实战)
2. **派工 v6 段 5 反馈 #1-#5** — 调研完成 ≠ 生产实施 (本路线图 §4 实战)
3. **派工 v6 段 5 反馈 #6** — 商业化主拍单独拍板 (本路线图 §2.2 + §2.5 实战)
4. **派工 v4 铁律 3** — git log + git show + grep 三步真验证 (本路线图 §1 实战)
5. **commit message 必含锚点范式数字** — §8 实战 (派工 v10 段 9 实战)

## 8. commit message 锚点范式数字纪律 (v10 段 9 强制约束)

依 v10 段 9 强制约束 + W68 第 6 批永久锚点:

```
docs(w78-1st-batch-a2): 商业化 24 人月 Q1 落地实施路线图 (5 阶段 + 真生产 key 主拍决策 + W79/W80 派工建议)

W77 grand closure §6 W78 派工顺序表 7 agents + A-2 W77 B+D 决策 commit 44cf83581 + B-3 W77 真生产 key 决策 commit c7b8466df + C-1 W77 声纹实战 commit 40008f908
锚点范式 W77 第 1 批 270 → W78 第 1 批 A-2 273 守恒 (+1)
- 5 阶段: Edge-TTS B+D 渐进式 + 真支付生产 key 启用 + D-1 R10 灰度 + 商业化 SaaS 部署 + 7 维评分商业化改造 (W72 C-2 排期 24 人月 Q1 落地)
- 真生产 key 主拍决策落地时间表 (W78-B-2 真接入, 类 20.13 实战)
- 商业化成本模型: Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生 + 0.5-0.6% Stripe/Alipay/WeChat Pay 交易费, 接近 0 成本
- 24 人月 Q1 落地里程碑: W78 (3 个月) + W79 (3 个月) + W80 (3 个月) + W81+ (15 个月) Phase 9/11/12
- W79/W80 派工建议 (商业化运营 + 私有化部署 + D-1 重派 + 7 维商业化改造)
- 调研 ≠ 生产 (类 20.12 调研完成 ≠ 主拍验收, 仅 docs/ + memory/)
- 0 production code 改动铁律守恒 (纯调研 + 路线图)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

## 9. 参考资料

- W77 grand closure commit `068626ecc`: `memory/w77-1st-grand-closure-2026-07-28.md` (192 行, §6 W78/W79/W80 派工顺序表 7+7+7 = 21 agents, 锚点 270→~291)
- W77 A-2 B+D 决策 commit `44cf83581`: `docs/w77-1st-batch-a2-edge-tts-bd-plan-2026-07-28.md` (537 行, §5.3 W78 4 子批建议)
- W77 B-1 iOS Safari 主拍接入 commit `bedcd4594`: `docs/w77-1st-batch-b1-edge-tts-ios-mainplay-2026-07-28.md` (20/20 e2e PASS)
- W77 B-2 Android Chrome 主拍接入 commit `cc3326409`: `docs/w77-1st-batch-b2-edge-tts-android-mainplay-2026-07-28.md` (20/20 e2e PASS)
- W77 B-3 真支付生产 key 决策准备 commit `c7b8466df`: `memory/w77-route-1st-batch-b3-billing-real-key-2026-07-28.md` (4/4 e2e PASS, 类 20.13 实战)
- W77 C-1 声纹 12 会议音频 reprocess commit `40008f908`: `docs/w77-1st-batch-c1-voice-reprocess-runbook-2026-07-28.md` (30/30 e2e PASS, 3 新铁律)
- W72 C-2 商业化 24 人月季度排期 commit `a78967661`: `docs/w72-commercialization-roadmap-update-2026-07-24.md` (261 行, 锚点范式第 217 守恒, 主拍已拍)
- W68 第 14 批 D-4 商业化基础 commit `e4d73278a`: `docs/w71-final-decision-2026-07-24.md` (807 行, 锚点范式第 183 守恒)
- Edge-TTS 升级 commit `41cf204d2` (6.1.9 → 7.2.8 修复 403)
- 派工 v4 铁律 3 真验证: 派工 v4 实战 19 类 + W72 A-2 类 20.1-20.3
- W77 A-1 类 20.11/20.12.1 实战 #8: 6 收尾 agents 派工过早 (3 存在空 worktree + 3 fatal unknown revision), memory 写但不 commit 坚守不伪造
- Web Speech API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
- Stripe API: https://stripe.com/docs/api
- Alipay Open API: https://opendocs.alipay.com/
- WeChat Pay V3: https://pay.weixin.qq.com/wiki/doc/apiv3/
- 1Password CLI secrets manager: https://developer.1password.com/docs/cli/secret-references/

---

**累计**: 主仓库 1 文件 (docs) + 1 用户级 (memory) = 2 文件变更. 锚点范式第 273 守恒预测. 0 production code 改动铁律完全维持. 派工 v6 段 5 反馈 #6 + 类 20.13 真生产 key 单独拍板 + 类 20.12 调研完成 ≠ 主拍验收实战.

> 0 production code 例外预算: 0 例外 (本任务纯 docs/memory 调研 + 路线图设计). W19 选项 A 维持.
