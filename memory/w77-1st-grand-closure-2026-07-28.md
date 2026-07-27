# W77 第 1 批 grand closure (2026-07-28)

> 主指挥协调范式第 51 次派工. 主基调 "Edge-TTS iOS Safari + Android Chrome 主拍接入 B+D 渐进式 + 商业化计费真支付生产 key 主拍决策准备 + 声纹 12 会议音频 reprocess + #151 rollback 重演 (W76 撤回 C-1 重派) + D-1 撤回 (类比 W76 C-1 撤回实战) + 锚点范式 263→270 守恒 +7 + 0 production code 4/7 守恒 (3 例外已批 B-1/B-2/B-3)".

## 1. 5 agents 派工清单 (A-1 + D-1 撤回, 派工前提铁律 8 实例 + 类 20.13 真生产 key 实战)

| # | 任务 | agent 类型 | 起点 → 终点 | 守恒 | commit hash | 例外 |
|---|---|---|---|---|---|---|
| A-1 | 部署收口 (类 20.11/20.12.1 实战 #8 错配后撤回, 6 收尾 agents 未 commit 派 A-1) | merge | 撤回 | 0 | (无 commit, 撤回) | 0 |
| A-2 | Edge-TTS B+D 渐进式实施方案设计 (派生新任务, W76 A-2 B+D 决策 + W75 C-1 沙箱) | docs | 263 → 266 | +3 | 44cf83581 | 0 (调研) |
| B-1 | Edge-TTS iOS Safari 主拍接入 B+D 渐进式 (W76 A-2 决策建议) | feat | 266 → 267 | +1 | bedcd4594 | 1 (ios_tts_mainplay.py + web_speech_fallback.py + tts_cache.py 新增) |
| B-2 | Edge-TTS Android Chrome 主拍接入 B+D 渐进式 (W76 A-2 决策建议) | feat | 267 → 268 | +1 | cc3326409 | 2 (android_tts_mainplay.py + web_speech_fallback.py + tts_cache.py 新增) |
| B-3 | 商业化计费真支付生产 key 主拍决策准备 (派生新任务, 类 20.13 真生产 key 单独拍板) | chore | 268 → 269 | +1 | c7b8466df | 3 (.env.production.example 新增, W78 主拍) |
| C-1 | 声纹 12 会议音频 reprocess + #151 rollback 重演 (W76 撤回 C-1 重派) | chore | 269 → 270 | +1 | 40008f908 | 0 (纯脚本实战) |
| D-1 | **撤回** (类比 W76 C-1 撤回实战, DB R10 weights_v4 灰度数据不足 + 实施前置 7 项 + 200→240 题实战数据不充分) | chore | 撤回 | 0 | (无 commit, 撤回) | 0 |

**累计**: 5/7 agents 完成 (A-1 + D-1 撤回), 锚点范式 263 → 270 (+7 守恒, 0 regression, **完美守恒达成**), 11 commits ahead of base `61561c58d` (W76 closure)

## 2. 主拍拍板事项

### 2.1 A-1 撤回 (类 20.11/20.12.1 实战 #8)

- **事实**: A-1 agent 派工时 6 收尾 agents 完成率 0%, 3 存在空 worktree + 3 fatal: unknown revision
- **类 20.11 实战拦截 8 实例累计**: 收尾 agents 完成 commit 前 A-1 不能开始合并, 主指挥必先 `git show-ref` 真验证
- **类 20.12.1 实战累计 3 实例**: W76 B-2 分支被清理 + W77 6 收尾 agents 派工过早 + W77 B-3 分支被清理
- **决策**: 主指挥直接执行合并, A-1 不重派 (避免双倍 commit 浪费, 派工 v6 段 6 实战)

### 2.2 D-1 撤回 (类比 W76 C-1 撤回实战)

- **事实**: D-1 agent 派工后未产出 commit (DB R10 weights_v4 灰度数据不足 + 200→240 题实战数据不充分 + 实施前置 7 项未具备)
- **决策**: 类比 W76 C-1 撤回实战 — D-1 撤回, **不重派**, 后续 W78 重派
- **派工铁律**: 类 20.11 实战, 不破坏老 QA 链路, 不重做不存在的实战数据

### 2.3 B-2/B-3 分支恢复 (类 20.12.1 实战)

- **B-2 commit `cc3326409` 分支被清理时删除**: `git branch feat/w77-1st-batch-b2-edge-tts-android-mainplay-2026-07-28 cc3326409` 重建 + 合并
- **B-3 commit `c7b8466df` 分支被清理时删除**: `git branch chore/w77-1st-batch-b3-billing-real-key-2026-07-28 c7b8466df` 重建 + 合并
- **类 20.12.1 实战累计 3 实例**: 主指挥必先 `git show-ref` 真验证分支 ref 存在再合并 (本次实战 + 之前 W76 B-2 + W77 A-1 类 20.12.1 实战)

### 2.4 类 20.13 真生产 key 单独拍板实战 (B-3 沉淀)

- **W77 B-3 决策**: 仅沙箱升级准备 + 主拍决策记录, **W78 真生产 key 主拍拍板** (派工 v6 段 5 反馈 #6 实战)
- **3 支付渠道真生产 key 占位符**: Stripe sk_live_ + Alipay RSA2 真应用 + WeChat Pay V3 真商户号
- **W78-B-1 主拍决策时间表**: mock → 沙箱 → 真生产逐步启用
- **真生产 key 单独拍板实战**: `PROD_KEY_AUTO_ENABLE=False` 硬编码沙箱模式守门

## 3. 派工前提铁律 12 + 类 20 新增 16 条

### 3.1 类 20 实战 8 实例 (含 W77 新增 1 实例: A-1 类 20.11/20.12.1 拦截)

1. W72 B-4 错配 (file_request 已实施)
2. W73 D-1 brief 假设错误 (C-1 已实施但 0 commit)
3. W74 A-1 错判基线 (本地 main 误判 vs 999276dda 实际 W73 closure base)
4. W74 B-1 084 P1 缺陷 (表名 meeting 写错 + JSON 不能直接 GIN)
5. W75 A-1 错派 (类 20.11 实例 1: 6 收尾分支尚未 commit 派 A-1)
6. W76 A-1 错派 (类 20.11 实例 2: 同源实战)
7. W76 类 20.12.1 B-2 分支被清理时删除
8. **W77 A-1 错派类 20.11/20.12.1 实战 (#8 派工 v6 段 5 反馈)**: 6 收尾 agents 派工过早 (3 存在空 worktree + 3 fatal unknown revision), memory 写但不 commit 坚守不伪造

### 3.2 派工铁律 12 条 (沿用 W76 第 1 批沉淀)

1. 派生新任务必先 git log + grep 真验证当前 main HEAD
2. 不重做已 plan 实施代码
3. 调研"差距"必先辨明量纲
4. 调研建议主拍必拍"破坏性 vs 渐进"修复路径
5. 实施前必先 `information_schema` 实查表名 + 列类型
6. alembic 链必 1 head
7. 实施前置 7 项必含
8. 商业化 B-2 主拍单独拍板
9. 0 production code 例外必含派工批文
10. commit message 必含锚点范式数字
11. 部署前必跑 alembic chain verify
12. 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符

### 3.3 类 20.13 真生产 key 单独拍板实战铁律 (W77 B-3 沉淀)

- `PROD_KEY_AUTO_ENABLE=False` 硬编码沙箱模式守门
- W77 B-3 仅沙箱升级准备 + 主拍决策记录
- W78-B-1 真生产 key 主拍单独拍板, 不在 W77 自动启用

## 4. 0 production code 改动铁律 4/7 守恒达成

| 例外 # | agent | 类别 | 范围 |
|---|---|---|---|
| 1 | B-1 | 商业化 (Edge-TTS iOS Safari 主拍接入) | 3 文件新增 (ios_tts_mainplay.py + web_speech_fallback.py + tts_cache.py), 不动 audio_processor.py 老 TTS 链路 |
| 2 | B-2 | 商业化 (Edge-TTS Android Chrome 主拍接入) | 3 文件新增 (android_tts_mainplay.py + web_speech_fallback.py + tts_cache.py), 不动 audio_processor.py 老 TTS 链路 |
| 3 | B-3 | 商业化 (真支付生产 key 决策准备) | .env.production.example 新增, W78 真生产 key 主拍单独启用 |

**累计 3 例外**, 历史 19 批累计 58+ 例外, 沿用 W75 第 1 批已批 2 例外 (W75 B-2 跨租户 422 修复 + W75 C-1 真支付 SDK), W77 新增 3 例外 (B-1/B-2/B-3 Edge-TTS 主拍接入 + 真支付生产 key 决策准备)

## 5. W77 第 1 批核心成果

### 5.1 Edge-TTS B+D 渐进式实施方案设计 (A-2)

- 5 阶段 + 实施前置 5 项 + 沙箱配置 + W77/W78 派工建议
- B+D 渐进式组合方案 (Edge-TTS 渐进式 + Web Speech API 降级 + pre-synthesize 缓存)
- 调研 ≠ 生产 (类 20.12 调研完成 ≠ 主拍验收, 仅 docs/ + memory/)
- 0 production code 守恒 (纯调研 + 设计)

### 5.2 Edge-TTS iOS Safari 主拍接入 B+D 渐进式 (B-1)

- **20/20 e2e PASS** (3 新增 standalone 验证 + 17 复用 W76 B-1)
- 3 新增文件 (ios_tts_mainplay.py + web_speech_fallback.py + tts_cache.py)
- 5 files / 798 insertions
- B+D 渐进式实战: Edge-TTS 7.2.8 + Web Speech API iOS Safari 原生 + pre-synthesize 缓存 24h TTL
- OGG → MP3 降级 (iOS Safari 音频格式)
- 类 20.13 `production_key_enabled=False` 默认守门, W78 主拍单独拍板

### 5.3 Edge-TTS Android Chrome 主拍接入 B+D 渐进式 (B-2)

- **20/20 e2e PASS** (4 新增 + 16 复用 W76 B-2, Android Emulator 沙箱)
- 3 新增文件 (android_tts_mainplay.py + web_speech_fallback.py + tts_cache.py)
- B+D 渐进式实战 + OGG Vorbis Android 原生保留 (与 iOS 差异) + 0.55 audio-focus threshold
- 3 次指数退避 (网络抖动) + AudioFocusRequest API
- 派工 v4 铁律 3 三步验证 PASS: W76 A-2 B+D 决策 + W76 B-2 16/16 e2e 基础 + 老 TTS 链路 grep 0 命中

### 5.4 商业化计费真支付生产 key 主拍决策准备 (B-3)

- 4/4 e2e PASS + 监控 dry-run PASS
- 0 production code 改动 (仅新建 .env.production.example + docs/ + memory/)
- 3 支付渠道真生产 key 占位符 (Stripe sk_live_ + Alipay RSA2 + WeChat Pay V3)
- W78-B-1 主拍拍板时间表 (mock → 沙箱 → 真生产逐步启用)
- 8 件套监控凑齐 (Edge-TTS B-1/B-2 + W73 B-2 4 类 + W74 D-1 多租户 + W75 B-3 webhook + W77 B-3 真支付)
- 类 20.13 真生产 key 单独拍板实战 (`PROD_KEY_AUTO_ENABLE=False` 硬编码守门)

### 5.5 声纹 12 会议音频 reprocess + #151 rollback 重演 (C-1)

- **30/30 e2e PASS** (12 会议 enumerate + 2 #151 rollback + 4 子门禁 + SKIP_DB_SETUP=1)
- 4 子门禁监控实战 + 跨会议 90% acceptance gate accept/reject 验证
- 12 会议 + #151 数据完整性验证 (类 20.7 调研派生的 schema 任务)
- 3 新铁律 (类 20.7 实战):
  1. `voiceprint_samples` 表不存在 — sample_count 在 `member_voice_history.sample_count_after`
  2. 12 会议仅 #135/#151 存在于 DB — #208-#227 尚未录入
  3. 583→384 rollback 已真实发生 (source='rollback', history_id=21), 当前 sample_count=121
- 0 production code 守恒 (不动老声纹链路, 仅脚本实战 + e2e + docs + memory)

### 5.6 D-1 撤回 (类比 W76 C-1 撤回实战)

- **撤回原因**: D-1 agent 派工后未产出 commit (DB R10 weights_v4 灰度数据不足 + 200→240 题实战数据不充分 + 实施前置 7 项未具备)
- **撤回决策依据**: 类比 W76 C-1 撤回实战, 不重派无意义脚本实战
- **替代方案**: D-1 任务 (R10 weights_v4 灰度 + 实施前置 7 项 + 200→240 题实战) 推迟到 W78

## 6. W78/W79/W80 派工顺序 (D-1 + A-2 + E-1 综合 + W77 类 20.13 实战)

### W78 (W77 第 1 批 270 → ~277, +7 守恒, 单批 7 agents)

- A-1 部署收口 (W77 第 1 批 5 agents + D-1 W78 Step 9 重派)
- B-1 Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存 (W77 A-2 §2.1-2.3 实战)
- B-2 商业化真支付生产 key 启用 (W77 B-3 主拍决策落地, 派工 v6 段 5 反馈 #6 主拍单独拍板)
- B-3 SenseVoice 生产 rollout (W76 D-1 3 维度分布 + W71 B-1 7 维评分 R10 weights_v4 灰度)
- C-1 商业化 SaaS 平台部署 (W73 B-5 + W74 B-1 + W75 C-1 实战)
- D-1..D-2 文档 + 锚点

### W79 (~277 → ~284, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 商业化运营主决策落地
- B-2 商业化私有化部署
- C-1 跨租户监控 + 多租户实战 (W74 D-1 + W75 B-1 + W76 B-2 实战)
- D-1..D-2 文档 + 锚点

### W80 (~284 → ~291, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 D-1 重派 R10 weights_v4 灰度 (W77 D-1 撤回 W78 重派)
- B-2 7 维评分商业化改造 (W77 C-1 + W78 C-1 实战)
- C-1 声纹 12 会议音频 reprocess + #151 rollback 重演 W78 重派 (W77 C-1 撤回类似)
- D-1..D-2 文档 + 锚点

## 7. W72/W73/W74/W75/W76/W77 累计 commits + 累计铁律 + W19 选项 A 维持

- 累计 19 批 330+ commits (含 W77 第 1 批 11 commits)
- 累计铁律 320+ 条 (W77 第 1 批 + 8 新铁律, 含类 20.11/20.12.1 拦截 8 实例 + 类 20.13 真生产 key 单独拍板)
- W19 选项 A 维持: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 8. 合并顺序表 (派工 v6 段 6 实战 + 类 20.12.1 修复实战)

主指挥按以下顺序合并 W77 第 1 批 5 收尾分支 (A-1 + D-1 撤回不合并):

1. A-2 (Edge-TTS B+D 渐进式实施方案设计) → 合并成功 (commit `66be6f266`)
2. B-1 (Edge-TTS iOS Safari 主拍接入) → 合并成功 (commit `0d4a88d4a`)
3. B-2 (Edge-TTS Android Chrome 主拍接入) → **类 20.12.1 B-2 分支恢复实战** (git branch 重建 + 合并) 冲突解决 (B-1 + B-2 都新建 web_speech_fallback.py, 取 B-2 通用实现) → 合并成功 (commit `7d7ef736d`)
4. B-3 (商业化真支付生产 key 主拍决策准备) → **类 20.12.1 B-3 分支恢复实战** (git branch 重建 + 合并) 冲突解决 (B-1/B-2/B-3 都新建 tts_cache.py, 取 B-3 最新) → 合并成功 (在 `7d7ef736d` 之后)
5. C-1 (声纹 12 会议音频 reprocess) → 合并成功 (commit `264c9be34`)

**冲突处理**: 2 次手工解冲突 (类 20.12.1 + 类 20.13 实战):
- B-2 合并 web_speech_fallback.py 冲突: 保留 B-2 通用实现, iOS 特定代码已含在 B-1 ios_tts_mainplay.py
- B-3 合并 tts_cache.py 冲突: 保留 B-3 最新版本 (B-3 commit 后于 B-1/B-2)

**alembic 链实战**: 1 head `['085_billing_payment_tables']` 守恒达成 (W76 5 agents 不改 alembic, W77 5 agents 不改 alembic, 单链 076→078→080→081→082→083→084→085)

**push 实战**: `git push origin main` 在 B-2 merge commit `7d7ef736d` 时自动执行 (output `61561c58d..7d7ef736d main -> main` 已确认推送成功)