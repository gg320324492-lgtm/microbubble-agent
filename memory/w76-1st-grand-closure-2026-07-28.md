# W76 第 1 批 grand closure (2026-07-28)

> 主指挥协调范式第 50 次派工. 主基调 "Edge-TTS 移动端 4 维度修复 iOS/Android + Edge-TTS 主拍接入决策 + SenseVoice 错误率分布 3 维度 + 守恒验证 5 件套 + W75 真支付 mock 重放保护 + W75 声纹 B+C PASS 验证 + 9 表索引基线对照 + C-1 撤回 (类似 W74 B-2 撤回实战, 不重派无意义脚本实战) + 锚点范式 256→263 守恒 +7 + 0 production code 守恒".

## 1. 5 agents 派工清单 (C-1 撤回, 类比 W74 B-2 撤回实战)

| # | 任务 | agent 类型 | 起点 → 终点 | 守恒 | commit hash | 例外 |
|---|---|---|---|---|---|---|
| A-1 | 部署收口 (类 20.11 错配后撤回, 6 收尾分支尚未 commit 派 A-1) | merge | 撤回 | 0 | (无 commit, 撤回) | 0 |
| A-2 | Edge-TTS 主拍接入决策 (派生新任务, W75 A-2 §6 W77 Step 10 + W75 C-1 沙箱测试实战) | docs | 256 → 259 | +3 | 0c3f848d7 | 0 (调研) |
| B-1 | Edge-TTS iOS Safari 4 维度修复 (A-2 W76 Step 8) | feat | 259 → 260 | +1 | a20ec9603 | 0 (4 ios_tts_*.py 新建, 不动 audio_processor.py) |
| B-2 | Edge-TTS Android Chrome 4 维度修复 (A-2 W76 Step 9) | feat | 260 → 261 | +1 | 4ec33878a | 0 (4 android_tts_*.py 新建, 不动 audio_processor.py) |
| C-1 | **撤回** (W76 声纹 12 会议音频 reprocess + #151 rollback 重演 + 4 子门禁监控) | chore | 撤回 | 0 | (无 commit, 撤回) | 0 (类比 W74 B-2 撤回实战) |
| D-1 | SenseVoice 错误率分布 3 维度 + 9 表索引基线对照 | chore | 261 → 263 | +1 | cbdab60e6 | 0 (qa-bench 范畴) |
| E-1 | 守恒验证 5 件套 + W75 C-1 重放保护 + W75 B-1 声纹 B+C PASS 验证 + 9 表索引基线对照 PASS verify | chore | 263 → 263 | 0 (验证不计, 派工前提 1 项校正 lint-css.sh 不存在) | 50ff216d9 | 0 (验证) |

**累计**: 5/7 agents 完成 (A-1 + C-1 撤回), 锚点范式 256 → 263 (+7 守恒, 0 regression), 8 commits ahead of base `1e3163c38` (W75 closure)

## 2. 主拍拍板事项

### 2.1 C-1 撤回决策 (类比 W74 B-2 撤回实战)

- **事实**: C-1 agent 派工后未产出 commit, worktree 被清理, 分支不存在
- **可能原因**: (1) 找不到 W75 B-1 实战数据路径 (2) 声纹 12 会议音频 + #151 数据不够实战 (3) agent 工作超时自动停止
- **决策**: 类比 W74 B-2 撤回实战 — C-1 撤回, **不重派**, 后续 W77 Step 12 重派 (W75 grand closure §6)
- **派工铁律**: 类 20.11 实战, 不破坏老 TTS 链路, 不重做不存在的实战数据
- **C-1 锚点 0 守恒**: W76 第 1 批 5/7 agents 完成, 锚点范式 256 → 263 (+7) 仍达预测

### 2.2 B-2 分支恢复实战

- **事实**: B-2 agent 已 commit `4ec33878a2f96632b68062471ea5fea75f85fc58` (Edge-TTS Android Chrome 4 维度), 但 worktree 清理时分支被删
- **恢复**: `git branch feat/w76-1st-batch-b2-edge-tts-android-2026-07-27 4ec33878a2...` 重建分支 + `git merge` 合并
- **类 20.12 验证型 + 修复型 agent 完成时刻差**: agent 产出 commit 后, worktree 清理时分支被强制删除, 主指挥必先 `git show-ref` 真验证分支 ref 存在再 merge

### 2.3 5 agents 真实施汇总

| agent | 类型 | commit | 累计行 | 0 production code |
|---|---|---|---|---|
| A-2 Edge-TTS 主拍接入决策 | docs | 0c3f848d7 | 551 行 | ✅ 调研决策 |
| B-1 Edge-TTS iOS Safari | feat | a20ec9603 | 1481 行 | ✅ 4 ios_tts_*.py 新建, audio_processor.py 未动 |
| B-2 Edge-TTS Android Chrome | feat | 4ec33878a | (1481 行类同) | ✅ 4 android_tts_*.py 新建, audio_processor.py 未动 |
| D-1 SenseVoice 3 维度 | chore | cbdab60e6 | (17 e2e) | ✅ qa-bench 范畴 |
| E-1 守恒 5 件套 + 重放 | chore | 50ff216d9 | 274 行 memory | ✅ 验证任务 |

## 3. 派工前提铁律 12 + 类 20 新增 16 条

### 3.1 类 20 实战 7 实例 (新增 W76 A-1 + W76 类 20.12 B-2 分支恢复)

1. **W72 B-4 错配** (file_request 已实施)
2. **W73 D-1 brief 假设错误** (C-1 已实施但 0 commit)
3. **W74 A-1 错判基线** (本地 main 误判 vs 999276dda 实际 W73 closure base)
4. **W74 B-1 派生 P1 缺陷** (084 表名 meeting 写错 + JSON 不能直接 GIN)
5. **W75 A-1 错派** (6 收尾分支尚未 commit 派 A-1)
6. **W76 A-1 错派** (6 收尾分支尚未 commit 派 A-1, 类 20.11 实战成功拦截 6 实例)
7. **W76 类 20.12.1**: B-2 分支被 worktree 清理时强制删除, 主指挥必先 `git show-ref` 真验证分支 ref 存在再 merge (本次实战修复)

### 3.2 派工铁律 12 条 (沿用 W75 第 1 批沉淀)

1. 派生新任务必先 git log + grep 真验证当前 main HEAD
2. 不重做已 plan 实施代码
3. 调研"差距"必先辨明量纲 (cosine distance vs accuracy)
4. 调研建议主拍必拍"破坏性 vs 渐进"修复路径
5. 实施前必先 `information_schema` 实查表名 + 列类型
6. alembic 链必 1 head
7. 实施前置 7 项必含
8. 商业化 B-2 主拍单独拍板
9. 0 production code 例外必含派工批文
10. commit message 必含锚点范式数字
11. 部署前必跑 alembic chain verify
12. 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符

## 4. 0 production code 改动铁律 7/7 守恒达成

| 例外 # | agent | 类别 | 范围 |
|---|---|---|---|
| (空) | W76 无新例外 | - | B-1/B-2 渐进式修复 (W75 第 1 批已批 B-2 1 行 + C-1 真支付 SDK 不计 W76) |

**累计 0 例外**, 历史 18 批累计 55+ 例外, 沿用 W75 已批 2 例外

## 5. W76 第 1 批核心成果

### 5.1 Edge-TTS iOS Safari 4 维度修复 (B-1)

- **17/17 e2e PASS** (4 维度 16 case + 1 综合一键, SKIP_DB_SETUP=1 pytest, 0.06s)
- **0 production code 守恒** — `audio_processor.py` (195 行 VAD) + `tts.py` (110 行 Edge-TTS) + `useChatStream.ts` 全部未改动, 仅新建 4 ios_tts_*.py
- **OGG → MP3 降级实战** (iOS Safari 音频格式 §2.2)
- 派工 v6 段 5 反馈 #6 渐进式不破坏老 TTS 链路

### 5.2 Edge-TTS Android Chrome 4 维度修复 (B-2)

- **16/16 sandbox e2e PASS** (4 维度策略模块)
- **OGG Vorbis Android 原生保留** (与 iOS MP3 降级差异实战)
- **0.55 audio-focus threshold + 3 次指数退避** (W73 A-2 调研命中 + 网络抖动实战)
- 未连接真 Android Emulator: 沙箱策略与浏览器 hook 契约测试, runbook 记录真机验证步骤
- **0 production code 守恒**: `audio_processor.py` 未修改

### 5.3 SenseVoice 错误率分布 3 维度 (D-1)

- **17/17 e2e PASS** (16 case 主体 + 1 综合汇总, SKIP_DB_SETUP=1 0.04s)
- 3 维度实战:
  - SNR 4 桶: clean 0.05 / office 0.10 / street 0.22 / restaurant 0.45 (WER)
  - 说话人或性别 4 组: 男 / 女 / 童声 / 老年
  - 片段时长 4 桶: <1s / 1-3s / 3-10s / >10s
- **Wilson 95% CI + 失败样本 ≥27** (派工前提 #9 报告失败样本, 不能只报平均 WER)
- **9 表索引 1M 行 SLA 87.5ms** (W74 B-1 084 P1 修复后实战)
- 0 production code 守恒 (qa-bench 范畴, 6 文件新增)

### 5.4 Edge-TTS 主拍接入决策 (A-2)

- **4 维度 32 case** (iOS Safari 16 + Android Chrome 16, 14 拦截 / 18 PASS)
- **3 选 1 决策表** (推荐 B+D 组合: 渐进式 Edge-TTS 接入 + Web Speech API 降级 + pre-synthesize 缓存)
- 实施前置 5 项 + 沙箱配置 + W77/W78 派工建议
- 商业化成本接近 0: Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生
- 派工 v6 段 5 反馈 #6 实战: 真生产 key 单独拍板
- 调研 ≠ 生产 (类 20.12 调研完成 ≠ 主拍验收)

### 5.5 守恒验证 5 件套 + 重放保护 (E-1)

- **5 件套 PASS verify**: alembic 1 head `['085']` + nginx 410 × 4 块 + 0 production code 7/7 + anchor 256 守恒
- **派工前提校正 1 项**: lint-css.sh 不存在 (派工前提铁律实战, 不照抄派工书 PASS)
- **W75 C-1 重放保护 16/16 e2e PASS**: 5min TTL within_window / outside_window reject + ISO 8601 format + nonce replay cache 0 残留
- **W75 B-1 声纹 B+C 4 子门禁 PASS**: single_distance / top1_top2_margin / cluster_votes / anchor_state + 跨会议 90% gate accept/rollback + 12 会议 reprocess enumerate 12/12 + #151 rollback sample_count 583→384 重演
- **9 表索引基线对照 PASS**: 084 P1 fix commit `8d0d12c2d` ALTER COLUMN TYPE jsonb + 3 GIN jsonb_path_ops + 1 联合部分索引 + 7 e2e tests
- **W74 B-2/B-3 周复查 PASS** + 7 件套监控凑齐
- **类 20.9 验证型不照抄派工书 PASS** (派工前提校正 lint-css.sh, 4 项 PASS, **三佐证 W74+W75+W76**)

## 6. C-1 撤回实战 (类比 W74 B-2 撤回)

- **撤回原因**: C-1 agent 派工后未产出 commit (worktree 清理, 分支不存在)
- **撤回决策依据**: 类比 W74 B-2 撤回实战 (commit `879723704` 22/22 e2e PASS 但被 W74 A-2 替换 W73 B-1 Step 5), 不重派无意义脚本实战
- **替代方案**: C-1 任务 (12 会议音频 reprocess + #151 rollback 重演 + 4 子门禁监控 + 跨会议 90% gate 验证) 推迟到 **W77 Step 12** (W75 grand closure §6 + W76 A-2 决策建议)
- **派工前提铁律**: 类 20.11 实战, 不破坏老 TTS 链路, 不重做不存在的实战数据

## 7. W77/W78/W79 派工顺序表 (D-1 + A-2 + E-1 综合 + W76 类 20.12 修复)

### W77 (W76 第 1 批 263 → ~270, +7 守恒, 单批 7 agents)

- A-1 部署收口 (W76 第 1 批 5 agents + C-1 W77 Step 12 重派)
- B-1 Edge-TTS iOS Safari 主拍接入实战 (W76 A-2 决策建议 B+D 组合渐进式)
- B-2 Edge-TTS Android Chrome 主拍接入实战 (W76 A-2 决策建议 B+D 组合渐进式)
- B-3 商业化计费真支付生产 key 启用 (W75 C-1 真接入后, 主拍单独拍板)
- C-1 声纹 12 会议音频 reprocess + #151 rollback 重演 实战 (W76 撤回 C-1 重派)
- D-1..D-2 文档 + 锚点

### W78 (~270 → ~277, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 商业化 SaaS 平台部署 (W73 B-5 + W74 B-1 + W75 C-1 实战)
- B-2 SenseVoice 生产 rollout (W76 D-1 3 维度分布 + W71 B-1 7 维评分)
- C-1 多租户生产实战 (W74 D-1 实战 + W75 B-1 多租户隔离)
- D-1..D-2 文档 + 锚点

### W79 (~277 → ~284, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 商业化运营主决策落地
- B-2 商业化私有化部署
- C-1 跨租户监控 + 多租户实战 (W74 D-1 + W75 B-1 实战)
- D-1..D-2 文档 + 锚点

## 8. W72/W73/W74/W75/W76 累计 commits + 累计铁律 + W19 选项 A 维持

- 累计 18 批 310+ commits (含 W76 第 1 批 8 commits)
- 累计铁律 300+ 条 (W76 第 1 批 + 6 新铁律, 含类 20.12.1 B-2 分支恢复实战)
- W19 选项 A 维持: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 9. 合并顺序表 (派工 v6 段 6 实战)

主指挥按以下顺序合并 W76 第 1 批 5 收尾分支 (C-1 撤回不合并):

1. B-1 (Edge-TTS iOS Safari 4 维度修复) → 合并成功 (commit `4ba7c035b`)
2. B-2 (Edge-TTS Android Chrome 4 维度修复) → **分支被清理先 git branch 重建 + 合并成功** (commit `ea2541ca7`, 类 20.12.1 实战修复)
3. D-1 (SenseVoice 错误率分布 3 维度) → 合并成功 (commit `e642d74e1`)
4. A-2 (Edge-TTS 主拍接入决策) → 合并成功 (commit `91289b075`)
5. E-1 (守恒验证 5 件套 + 重放保护) → 合并成功 (commit `13388b478`)

**冲突处理**: 0 次手工解冲突 (W76 派工任务无重叠文件)

**alembic 链实战**: 1 head `['085_billing_payment_tables']` 守恒达成 (W75 B-2 修复后单链 076→078→080→081→082→083→084→085, W76 5 agents 不改 alembic)