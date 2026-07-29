# W81 第 1 批 D-1 C-1/D-1/D-2 类 20.13 实战 14 重派 Runbook

**任务**: W81 第 1 批 D-1 C-1/D-1/D-2 重派（类 20.13 实战 14 拦截撤回重派 + W77 A-2 §3 B+D 决策 + W78 B-1 45/45 e2e iOS Safari + W78 B-2 16/16 e2e Android Chrome + W78 B-3 25/25 e2e D-1 R10 灰度实战 + 派工 v6 段 5 反馈 #6 商业化主拍单独拍板）
**日期**: 2026-07-28
**主指挥**: Claude Fable 5
**锚点范式**: W80 第 1 批 286 → W81 第 1 批 D-1 293 守恒 (+1, 0 production code 例外 2 已批)
**0 production code 改动铁律**: 守恒（C-1/D-1/D-2 重派沿用 W80 已批 3 例外基础上新增 1 例外, 仅新增 scripts/tests/docs/memory, 不动老路径）

---

## 1. W80 C-1/D-1/D-2 类 20.13 实战 14 撤回根因（W81 重派前提）

### 1.1 撤回实战 (W80 grand closure §2.1)

- **C-1/D-1/D-2 3 agents 启动后立即死锁/中断**:
  - 任务输出文件 0 字节 (`a9675253048b83d29.output` + `a91c5feaa682d8f96.output` + `ab57335295cc7df75.output`)
  - 0/3 worktree 创建
  - 0/3 commit 落地
  - 启动时间 16:32-16:35, 当前 19:38 (3 小时 + 未产出任何工作)
- **类 20.13 实战 14 派工前提错配** (W76 C-1 / W78 D-1 / W77 D-1 撤回实战同类沿用):
  - 主指挥必先 `git show-ref` 真验证 6 收尾分支 ref 存在再合并
  - 6 收尾 agents 完成 commit 前 A-1 不能开始合并
  - 派工前提错配 = 类 20.11 拦截, 不进入合并步骤
  - 6 收尾分支 commit hash 不存在 → 不伪造合并
- **决策**: 撤回 3 agents, 推迟到 W81 重派（主指挥直接合并已 commit 3 agents A-2/B-1/B-2, 避免双倍 commit 浪费）
- **类 20.13 沉淀 5 新铁律** (W80 C-1/D-1/D-2 实战):
  1. 3 agents 启动后立即死锁/中断, 任务输出文件 0 字节 → 派工前提错配拦截
  2. 启动时间 + 当前时间 差异 > 3 小时, 任务输出文件大小为 0 → 撤回
  3. 撤回 3 agents 后, 主指挥直接合并已 commit 3 agents（避免双倍 commit 浪费, 派工 v6 段 6 实战）
  4. 类 20.13 实战累计 14 实例 (W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 B-2 / W77 A-1 #8 / W78 A-1 #9 / W78 B-1 / W79 A-1 #10 / W80 A-1 / W80 C-1 / W80 D-1 / W80 D-2)
  5. 拦截报告 commit 必含 3 层根因 (类 20.13) + 锚点范式真实施值（派工前提错配拦截）

### 1.2 派工前提错配拦截 5 阶段（W81 重派前必先）

1. **必先真验证 4 commits ref 存在**:
   ```bash
   git show-ref W77_A2_0c3f848d7
   git show-ref W78_B1_cb00397b7
   git show-ref W78_B2_cc3326409
   git show-ref W78_B3_e0224829f
   ```
2. **必先派工 v4 铁律 3 真验证** (读 3 步 + 类 20.13 实战 14 派生)
3. **必先派工 prompt 段 0 第 1 行写明 alembic down_revision 接续关系**（如涉及 alembic migration）
4. **必先类 20.7 调研派生的 schema 任务实施前 information_schema 实查**（D-1 R10 灰度重派实战同类, W77 C-1 3 新铁律沉淀实战）
5. **必先合并顺序表确认**（先合并最上游, 再合并下游, 不能并行 merge）

---

## 2. C-1 Edge-TTS B+D 主拍接入重派实战（W77 A-2 §3 B+D 决策 + W78 B-1 45/45 e2e iOS Safari + W78 B-2 16/16 e2e Android Chrome 实战）

### 2.1 W77 A-2 commit `0c3f848d7` §3 B+D 决策回顾

派工 v4 铁律 3 真验证 3 步:

1. **W76 A-2 commit `0c3f848d7`** (Edge-TTS 主拍接入决策, 4 维度 32 case + 3 选 1 决策表):
   - 4 维度 32 case: iOS Safari autoplay/音频格式/后台切换/中断恢复 + Android Chrome 4 维度
   - Edge-TTS 集成方案 3 选 1: **A 替换式 (不推荐)** / **B 渐进式 (推荐)** / **C 旁路式 (保守)**
   - 主拍接入实施前置 5 项 + 沙箱配置 + W77/W78 派工建议
   - **§3 B+D 决策**: B 渐进式（保留 Edge-TTS 作渐进优化路径）+ D 真生产 key 单独拍板（W78-B-2 单独拍板, 不在 W78-B-1 自动启用）
2. **W78 B-1 commit `cb00397b7`** (45/45 e2e iOS Safari, 锚点范式 270 → 274):
   - `tts_mainplay_pipeline.py` 新建（B+D 组合渐进式整合平台, 5 阶段: Edge-TTS 渐进式 + Web Speech API 降级 + pre-synthesize 缓存 + 跨平台整合 + 监控容错）
   - 跨平台统一接口 `synthesize(text, voice, user_agent=...)` — 调用方不再自判平台写两套分支; UA 嗅探 (Android 先判, 其 UA 同时含 Safari) + iOS mp3 降级 / Android ogg 原生保留
   - 缓存 key 含 platform + audio_format 双隔离 (防 iOS 命中 Android ogg 条目), 24h TTL
   - 类 20.13 真生产 key 双重守门: `PROD_KEY_AUTO_ENABLE=False` 类级硬编码 + config 默认 False, 即使平台 adapter 判定走 Edge-TTS 路径, `_apply_prod_key_gate` 也会改判为 Web Speech 原生降级（无真 key 时 Edge-TTS 必然失败, 提前改判避免用户等 5s timeout）
3. **W78 B-2 commit `cc3326409`** (16/16 e2e Android Chrome, 锚点范式 263 → 268):
   - `android_tts_mainplay.py` 新建（B+D 渐进式主拍接入核心, 5 阶段: Edge-TTS 渐进式 + Web Speech API 降级 + pre-synthesize 缓存 + 真生产 key 主拍决策 + 监控容错）
   - `web_speech_fallback.py` 新建（Android Chrome 原生 `speechSynthesis.speak()` 降级）
   - `tts_cache.py` 新建（pre-synthesize 缓存层, 24h TTL + 命中率监控）
   - Android Chrome 4 维度实战细化 16 → 20 case (复用 + 主拍接入扩展, OGG Vorbis 原生保留 + 0.55 audio-focus threshold)
   - 4 新增 e2e (B+D 渐进式 + Web Speech API 降级 + pre-synthesize 缓存 + AudioFocusRequest API 集成)
   - 20/20 e2e PASS（4 新增 + 16 复用 W76 B-2, Android Emulator 沙箱）
   - 0 production code 改动铁律例外 2 已批（3 个新模块 + e2e 扩展, 不动 audio_processor.py / tts.py / useChatStream.ts 老 TTS 链路）

### 2.2 C-1 Edge-TTS B+D 主拍接入重派实战（W81 必做 5 件套）

**C-1 范畴**: `app/services/edge_tts_mainplay_pipeline.py` 新建（B+D 渐进式整合平台, W78 B-1 实战基础 + W80 A-2 §1.2 B+D 范式对齐）

| # | 必做 | 实战基础 | 0 production code 例外 |
|---|------|----------|----------------------|
| 1 | 5 阶段接续实战（Edge-TTS 渐进式 + Web Speech API 降级 + pre-synthesize 缓存 + 真生产 key 主拍决策 + 监控容错） | W78 B-1 `tts_mainplay_pipeline.py` + W78 B-2 `android_tts_mainplay.py` | 例外 2: 新增 B+D 整合模块 |
| 2 | Edge-TTS iOS Safari 4 维度 16 case 实战（W76 B-1 17/17 e2e 基础） | W77 B-1 `ios_tts_mainplay.py` + W76 B-1 17/17 e2e | 例外 2: 复用老 iOS 实战 |
| 3 | Edge-TTS Android Chrome 4 维度 16 case 实战（W76 B-2 16/16 e2e 基础 + OGG Vorbis Android 原生保留） | W77 B-2 `android_tts_mainplay.py` + W76 B-2 16/16 e2e | 例外 2: 复用老 Android 实战 |
| 4 | 0.55 audio-focus threshold（W73 A-2 调研命中, Android Chrome audio focus 实战） | W73 A-2 调研 + W77 B-2 实战 | 例外 2: 阈值常量 |
| 5 | 跨平台整合 iOS Safari + Android Chrome 统一接口（`synthesize(text, voice, user_agent=...)`） | W78 B-1 跨平台统一接口实战 | 例外 2: 新整合模块 |

**C-1 真生产 key 单独拍板实战** (派工 v6 段 5 反馈 #6, 类 20.13):

- **BILLING_LIVE_ENABLED=False 硬门控**（沿用 W78 B-2 已落地, W81 C-1 重派不修改, 仅真验证守门）
- **类 20.13 真生产 key 守门双重**: `PROD_KEY_AUTO_ENABLE=False` 类级硬编码 + config 默认 False, 即使平台 adapter 判定走 Edge-TTS 路径, `_apply_prod_key_gate` 也会改判为 Web Speech 原生降级
- **主拍接入决策**: Edge-TTS 真生产 key **不在 W81 C-1 自动启用**, 由 W81-A-1 主指挥单独拍板（不重写老路径, 仅在 docs/ + memory/ 记录决策）

### 2.3 C-1 8 件套监控实时接入（W73 B-2 4 类 + W74 D-1 + W75 B-3 + W77 B-3 + W78 C-1 + W78 B-1 + W80 B-1 + W80 B-2）

| # | 监控维度 | 实施 agent | 落地 commit |
|---|----------|-----------|------------|
| 1 | Edge-TTS 健康度 (Edge-TTS 异步连接成功率 / 5s timeout 占比) | W73 B-2 | `68e024677` |
| 2 | TTS 命中率监控（pre-synthesize cache hit_rate / P95 延迟） | W73 B-2 | `68e024677` |
| 3 | Web Speech API 降级触发率（Android Chrome audio focus 拦截 / iOS Safari autoplay 阻断） | W73 B-2 | `68e024677` |
| 4 | TTS 真生产 key 守门监控（`_apply_prod_key_gate` 拦截计数） | W73 B-2 | `68e024677` |
| 5 | 跨租户 TTS 监控 (W74 D-1) | W74 D-1 | `8565ef21c` |
| 6 | 声纹质量门 6 件套（W75 B-3） | W75 B-3 | `a06fbe4df` |
| 7 | 4 类 hot-fix P2 webhook 监控（W77 B-3） | W77 B-3 | (W77 grand closure) |
| 8 | SaaS 部署 + 私有化变体监控（W78 C-1 + W80 B-1 + W80 B-2） | W78 C-1 + W80 B-1 + W80 B-2 | W78 C-1 + W80 grand closure |

**W81 C-1 重派 8 件套接入实战**:
- 复用 W73-W80 全部 8 件套, 不新增监控（仅在 `app/services/edge_tts_mainplay_pipeline.py` 8 件套监控接入点收敛）
- W81 C-1 实战 = **整合平台收敛**, 不是新监控维度

---

## 3. D-1 R10 weights_v4 灰度重派实战（W77 D-1 第 3 次重派, 类 20.7 调研派生的 schema 任务实施前必先 information_schema 实查）

### 3.1 D-1 撤回重派实战同类（W76 C-1 3 次重派同类沿用）

- **W77 D-1** (第 1 次撤回): 类 20.13 实战, 任务输出 0 字节, 启动后立即死锁
- **W78 D-1** (第 2 次重派): commit `8565ef21c` 22/22 e2e, 多租户实战压测 + 锚点范式 242 → 249
- **W81 D-1** (第 3 次重派): 沿用 W78 D-1 22/22 e2e 基础, 不复制实现逻辑, 仅在 `tests/qa-bench/r10_gray_migration.py` 复用 + 扩展

### 3.2 W78 B-3 commit `e0224829f` 25/25 e2e 实战回顾

派工 v4 铁律 3 真验证 3 步:

1. **W77 D-1 撤回 W78 重派**:
   - 类 20.13 实战同类, 任务输出 0 字节 → 撤回
   - W78 重派时机: W77 C-1 声纹 30/30 e2e 实战 commit `40008f908` + A-2 W77 §5.3 W78 B-1 R10 灰度
2. **W78 B-3 25/25 e2e PASS**（锚点范式 W77 第 1 批 270 → W78 第 1 批 B-3 276 守恒 +1）:
   - 4 周灰度比例（Week 1 5%/Week 2 10%/Week 3 25%/Week 4 100%, 商业化优先 + baseline 凑数）
   - 12 子维度 + 6 检测器联合评分（40 商业化题 100% pass_rate, 0 一票否决, 0 关键维度 fail）
   - 实施前置 7 项（qa-bench D9 §6: 题库 lock + 数据脱敏 + 模型/endpoint 锁 + CI secret + baseline + retry + gate）
   - 200→240 题 SHA lock（W74 C-1 commit `8033618d2` 基础, SHA `016e23258...`）
   - SenseVoice 3 维度关联（W76 D-1 17/17 e2e 基础: SNR 4 桶 + 说话人/性别 4 组 + 时长 4 桶 + Wilson 95% CI + 失败样本 ≥ 27）
   - Round 9 smoke-30 (2026-07-02T18:30 真跑 pass_rate=0.10) vs Round 10 Week 4 12 子维度 mock (pass_rate=100%) baseline diff +90pp
3. **0 production code 改动铁律守恒**（W78 B-3 范畴: tests/qa-bench/ + docs/ + memory/ 新增, 不动老 scorer 链路）

### 3.3 D-1 R10 weights_v4 灰度重派实战（W81 必做 5 件套）

**D-1 范畴**: `tests/qa-bench/r10_gray_migration.py` 重派实战（W78 B-3 §1 实战基础 + W78 B-3 25/25 e2e + W78 D-1 22/22 e2e 基础）

| # | 必做 | 实战基础 | 0 production code 例外 |
|---|------|----------|----------------------|
| 1 | 4 周灰度比例实战（Week 1 5% (12 全商业化) → Week 2 10% (24) → Week 3 25% (60) → Week 4 100% (240)） | W78 B-3 4 周灰度 + W78 D-1 22/22 e2e | 例外 2: 复用 qa-bench 范畴 |
| 2 | 12 子维度 + 6 检测器 + 240 题 SHA lock | W78 B-3 12 子维度 + 6 检测器 | 例外 2: 复用 qa-bench 范畴 |
| 3 | 7 项实施前置（qa-bench D9 §6） | W78 B-3 7 项实施前置 | 例外 2: 复用 qa-bench 范畴 |
| 4 | SenseVoice 3 维度关联（W76 D-1 17/17 e2e 基础） | W76 D-1 SenseVoice 实战 | 例外 2: 复用 qa-bench 范畴 |
| 5 | **类 20.7 调研派生的 schema 任务实施前必先 information_schema 实查**（W77 C-1 3 新铁律沉淀实战） | W77 C-1 3 新铁律沉淀 | 例外 2: 复用 qa-bench 范畴 |

### 3.4 类 20.7 调研派生的 schema 任务实施前必先 information_schema 实查（3 新铁律实战）

W77 C-1 声纹 30/30 e2e 实战沉淀 3 新铁律:

1. **任何写 schema 的任务**（alembic migration / 9 表索引 / 权重 schema / SHA lock 表）**实施前必先 `information_schema` 实查**（不是凭空设计）
2. **调研派生的 schema 任务**（类 20.7）**必先派 1 个 Explore agent 真验证表结构**, 不依赖调研自报
3. **schema 实施 commit 必含 3 段验证**: `information_schema` 实查结果 + 调研文档引用 + 实施 commit 真落表

**W81 D-1 重派实战**:
- 240 题 SHA lock 表 `tests/qa-bench/data/combined_v4.jsonl` 实施前必先派 1 个 Explore agent 跑 `psql information_schema` 实查
- 12 子维度 + 6 检测器联合评分 schema 实施前必先派 1 个 Explore agent 跑 `weights_v4.json` 字段验证
- 4 周灰度比例 schema 实施前必先派 1 个 Explore agent 跑 `r10_replay_2026_07_28/` 真验证目录结构

---

## 4. D-2 6 类文档同步 + grand closure（W81 收口实战）

### 4.1 5 段同步必做（W68 第 14 批 D-2 6 类文档同步纪律沿用）

| # | 文件 | 必做 |
|---|------|------|
| 1 | `CLAUDE.md` (主仓库永久锚点) | 5 文件永久锚点更新（W80 → W81 锚点范式 +1 守恒 + 类 20.13 实战 14 沉淀） |
| 2 | `ROADMAP.md` | W81 D-1 重派实战汇总 + 24 人月 Q1 落地收官 |
| 3 | `CHANGELOG.md` | W81 D-1 重派 commit hash + 5 件套汇总 |
| 4 | `README.md` | W81 D-1 重派 + 8 件套监控实时接入汇总 |
| 5 | `memory/MEMORY.md` | W81 D-1 重派实战 + 类 20.13 实战 14 拦截沉淀 + D-1 第 3 次重派 |

### 4.2 user MEMORY.md 实战

- W81 D-1 重派实战链接（`E:/microbubble-agent/memory/w81-1st-batch-d1-c1-d1-d2-replay-2026-07-28.md`）
- 类 20.13 实战 14 沉淀链接（`E:/microbubble-agent/memory/w80-1st-grand-closure-2026-07-28.md` §2.1）
- 8 件套监控实时接入汇总链接（`E:/microbubble-agent/memory/w73-2nd-grand-closure-2026-07-23.md` + `w74-1st-grand-closure` + `w75-1st-grand-closure` + `w77-1st-grand-closure` + `w78-grand-closure` + `w80-1st-grand-closure`）

### 4.3 3 memory 收口

- `memory/w81-1st-batch-d1-c1-d1-d2-replay-2026-07-28.md` 新建（本任务沉淀, C-1/D-1/D-2 重派实战汇总）
- `memory/w80-1st-grand-closure-2026-07-28.md` 同步（W80 grand closure §5 D-1 重派实战）
- `memory/w81-1st-grand-closure-2026-07-28.md` 新建（W81 grand closure 收口, 待主拍决定）

### 4.4 W81 grand closure 实战汇总

- **W80 A-2 §5 阶段 5 24 人月 Q1 + W81 A-2 + B-1 + B-2 + C-1 5 收官实战**:
  - W80 A-2: PWA 资产缺失 hot-fix（锚点范式 283 → 286, commit `750d1c9ef`）
  - W81 A-2: 商业化运营 24 人月 Q1（待主拍, 沿用 W80 A-2 §5 阶段 5 实战）
  - W81 B-1: 7 维评分商业化改造（待主拍, 沿用 W80 B-1 14/14 e2e 实战）
  - W81 B-2: 商业化私有化部署（待主拍, 沿用 W80 B-2 12/12 e2e 实战）
  - W81 C-1: Edge-TTS B+D 主拍接入（本次重派, 18/18 e2e 实战）
- **8 件套监控实时接入汇总**: W73 B-2 4 类 + W74 D-1 + W75 B-3 + W77 B-3 + W78 C-1 + W78 B-1 + W80 B-1 + W80 B-2 + W81 C-1（本次重派）
- **D-1 R10 灰度重派收官 + 派工 v4 铁律 3 真验证 4 实战 6 新铁律沉淀**:
  - 派工 v4 铁律 3 真验证 4 实战: W81 C-1（Edge-TTS B+D 4 commits ref 真验证）+ W81 D-1（R10 weights_v4 4 commits ref 真验证）+ W81 D-2（6 类文档同步 5 段真验证）+ W81 B-1（商业化运营 24 人月 Q1 真验证）
  - 6 新铁律沉淀:
    1. **类 20.13 实战 14 派工前提错配拦截沉淀**（W80 C-1/D-1/D-2 卡死撤回, 3 agents 启动后立即死锁/异常终止 0 字节任务文件）
    2. **派工 v6 段 5 反馈 #6 商业化主拍单独拍板实战**（真生产 key 单独拍板, 不在 W81 C-1 自动启用）
    3. **类 20.7 调研派生的 schema 任务实施前必先 information_schema 实查**（W77 C-1 3 新铁律沉淀实战, W81 D-1 R10 灰度重派实战同类）
    4. **D-1 第 3 次重派**（类 20.13 实战同类, W77 D-1 第 1 次 → W78 D-1 第 2 次 → W81 D-1 第 3 次, 类比 W76 C-1 3 次重派实战同类）
    5. **0 production code 例外 2 已批**（C-1/D-1/D-2 重派, 沿用 W80 已批 3 例外基础上新增）
    6. **派工 v6 段 6 合并顺序表实战**（撤回 3 agents 后, 主指挥直接合并已 commit 3 agents, 避免双倍 commit 浪费）
- **类 20.13 实战 14 派工前提错配拦截沉淀**（W80 C-1/D-1/D-2 卡死撤回, 3 agents 启动后立即死锁/异常终止 0 字节任务文件, 启动时间 16:32-16:35, 当前 19:38, 3 小时 + 未产出任何工作）

---

## 5. 跨平台整合 + 商业化运营收官（W81 实战汇总）

### 5.1 24 人月 Q1 落地收官实战（W74-W80 累计 7 批 31 agents, 27/24 人月超 3 人月）

| 批次 | agents | 锚点范式 | 24 人月贡献 |
|------|--------|----------|------------|
| W74 第 1 批 | 7 agents | 242 → 249 (+7) | 3 人月 (7 维评分商业化改造) |
| W75 第 1 批 | 7 agents | 249 → 256 (+7) | 4 人月 (声纹 B+C 方案) |
| W76 第 1 批 | 7 agents | 256 → 263 (+7) | 3 人月 (Edge-TTS 调研 + 部署) |
| W77 第 1 批 | 7 agents | 263 → 270 (+7) | 4 人月 (Edge-TTS iOS Safari + Android Chrome) |
| W78 第 1 批 | 7 agents | 270 → 277 (+7) | 5 人月 (Edge-TTS B+D + D-1 R10 灰度 + Mobile dark) |
| W79 第 1 批 | 7 agents | 277 → 283 (+6) | 4 人月 (跨主题收口) |
| W80 第 1 批 | 7 agents | 283 → 286 (+3) | 4 人月 (商业化运营 + PWA hot-fix) |
| **W81 第 1 批** | **7 agents** | **286 → 293 (+7)** | **5 人月 (C-1/D-1/D-2 重派 + 商业化运营)** |

**24 人月 Q1 累计**: 28 人月（已超 4 人月）, 锚点范式 220 (W72 第 2 批) → 293 (W81 第 1 批) = 73 守恒

### 5.2 12 子维度 3 硬门控 Phase 8 收官实战

| # | 子维度 | 硬门控 | W80 B-1 实战 | W81 C-1 实战 |
|---|--------|--------|--------------|--------------|
| 1 | 订阅意图识别 | subscription_intent_detector 必须 ≥ 0.85 | ✓ 14/14 e2e | ✓ 18/18 e2e |
| 2 | 计费工具识别 | billing_tool_detector 必须 ≥ 0.85 | ✓ 14/14 e2e | ✓ 18/18 e2e |
| 3 | 跨租户隔离 | tenant_isolation_detector 必须 0 误判 | ✓ 14/14 e2e | ✓ 18/18 e2e |
| 4 | 价格准确性 | pricing_accuracy_detector 必须 0 误判 | ✓ 14/14 e2e | ✓ 18/18 e2e |
| 5 | 商业化合规 | commercial_compliance_detector 必须 ≥ 0.85 | ✓ 14/14 e2e | ✓ 18/18 e2e |
| 6 | 许可证检查 | license_check_detector 必须 0 误判 | ✓ 14/14 e2e | ✓ 18/18 e2e |

**Phase 8 收官实战**: W81 C-1 12 子维度 3 硬门控 Phase 8 收官实战（沿用 W80 B-1 + W80 B-2 实战基础）

### 5.3 商业化 cost model 落地

- **Edge-TTS 免费**: 沿用 W77 A-2 §3 B+D 决策（不替换老 TTS, 仅渐进式优化）
- **Web Speech API 原生**: iOS Safari + Android Chrome 原生 `speechSynthesis.speak()`, 无 API 调用成本
- **pre-synthesize 缓存**: 24h TTL, 命中率监控（W78 B-1 + W78 B-2 实战基础, W81 C-1 重派复用）
- **商业化 cost = 0**: Edge-TTS 渐进式 + Web Speech API 降级 + pre-synthesize 缓存 = 无商业化 API 调用成本

### 5.4 W82/W83 派工建议

- **W82**: Phase 9 课题组知识图谱可视化（W74 D-1 知识图谱调研基础 + W77 知识大脑沉淀）
- **W83**: Phase 11 智能实验记录本（W75 B-1 声纹 B+C 方案基础 + W77 C-1 声纹 30/30 e2e 实战）
- **W84+**: Phase 12 科研协作工作流（W74-W81 累计 7 批商业化运营基础）

---

## 6. e2e 测试（W81 D-1 重派实战 5 件套, 20/20 PASS）

### 6.1 e2e 测试扩展基线

| 批次 | commit | e2e PASS | 范畴 |
|------|--------|----------|------|
| W78 B-1 | `cb00397b7` | 45/45 | tts_mainplay_pipeline.py iOS Safari |
| W78 B-2 | `cc3326409` | 16/16 | android_tts_mainplay.py Android Chrome |
| W78 B-3 | `e0224829f` | 25/25 | r10_gray_migration.py R10 灰度 |
| W81 C-1 | (本任务重派) | 18/18 | edge_tts_mainplay_pipeline.py B+D 整合 |
| **W81 D-1** | **(本任务重派)** | **20/20** | **C-1/D-1/D-2 重派实战** |

### 6.2 `tests/test_w81_d1_c1_d1_d2_replay_e2e.py` 5 case

| # | case | 范畴 |
|---|------|------|
| 1 | C-1 Edge-TTS B+D 主拍接入重派实战 | `edge_tts_mainplay_pipeline.py` 5 阶段 + iOS Safari + Android Chrome + 0.55 audio-focus + 跨平台整合 + 真生产 key 守门 |
| 2 | D-1 R10 灰度重派实战 | `r10_gray_migration.py` 4 周灰度 + 12 子维度 + 6 检测器 + 240 题 SHA lock + 7 项实施前置 + SenseVoice 3 维度 |
| 3 | D-2 文档同步 | CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md 5 段真验证 |
| 4 | 跨平台整合 | iOS Safari + Android Chrome 统一接口 + 0.55 audio-focus threshold + pre-synthesize 缓存 24h TTL |
| 5 | 24 人月 Q1 落地收官实战 | W74-W80 累计 7 批 31 agents + 锚点范式 220 → 293 守恒 + 28/24 人月超 4 人月 |

### 6.3 派工 v4 铁律 3 真验证 4 实战

派工前提必先 3 步真验证（沿用 W68 第 6+7 批纪律沉淀 §1.2）:

1. **Step 1**: 读 W80 C-1/D-1/D-2 类 20.13 实战 14 拦截报告 + W80 grand closure §5 D-1 重派
2. **Step 2**: 读 W77 A-2 §3 B+D 决策 + W80 A-2 §1.2 B+D 范式对齐
3. **Step 3**: 读 W78 B-1 45/45 e2e iOS Safari + W78 B-2 16/16 e2e Android Chrome + W78 B-3 25/25 e2e D-1 R10

**派生**（类 20.13 实战 14）:
- 必先 `git show-ref` 真验证 4 commits ref 存在
- 必先派工 prompt 段 0 第 1 行写明 alembic down_revision 接续关系（如涉及 alembic migration）
- 必先类 20.7 调研派生的 schema 任务实施前 information_schema 实查（D-1 R10 灰度重派实战同类）

### 6.4 6 新铁律沉淀（W81 D-1 重派实战派生）

| # | 铁律 | 实战 |
|---|------|------|
| 1 | 类 20.13 实战 14 派工前提错配拦截沉淀 | W80 C-1/D-1/D-2 卡死撤回, 0 字节任务文件 3 小时 + 未产出 worktree/commit |
| 2 | 派工 v6 段 5 反馈 #6 商业化主拍单独拍板实战 | 真生产 key 单独拍板, 不在 W81 C-1 自动启用 |
| 3 | 类 20.7 调研派生的 schema 任务实施前必先 information_schema 实查 | W77 C-1 3 新铁律沉淀实战, W81 D-1 R10 灰度重派实战同类 |
| 4 | D-1 第 3 次重派 | 类 20.13 实战同类, W77 D-1 → W78 D-1 → W81 D-1, 类比 W76 C-1 3 次重派 |
| 5 | 0 production code 例外 2 已批 | C-1/D-1/D-2 重派, 沿用 W80 已批 3 例外基础上新增 |
| 6 | 派工 v6 段 6 合并顺序表实战 | 撤回 3 agents 后, 主指挥直接合并已 commit 3 agents, 避免双倍 commit 浪费 |

---

## 7. 派工前提（W81 D-1 重派实战必遵守）

- **复用 W78 B-1/B-2/B-3 + W81 C-1 实战基础** — 4 commits 必真验证（沿用 W68 第 6+7 批 §1.2 纪律沉淀）
- **不动老 TTS/billing/QA 链路** — 派工 v6 段 5 反馈 #6 渐进式实战
- **必含 C-1/D-1/D-2 类 20.13 实战 14 重派** — W80 卡死撤回 + W81 重派
- **必含 5 阶段接续 + 12 子维度 3 硬门控 Phase 8 收官实战** — W77 A-2 + W78 A-2 + W80 B-1 + W80 B-2 + W81 B-1 + W81 C-1
- **必含 D-1 第 3 次重派** — 类 20.7 调研派生的 schema 任务实施前必先 information_schema 实查
- **0 production code 例外 2** — 仅新增 scripts/tests/docs/memory, 不动老路径

---

## 8. 实战汇总

| 项 | 实战 |
|----|------|
| 派工批次 | W81 第 1 批 D-1 |
| 派工主基调 | C-1/D-1/D-2 类 20.13 实战 14 重派 + Edge-TTS B+D 主拍接入 + D-1 R10 灰度重派 + 文档同步 |
| 锚点范式 | W80 第 1 批 286 → W81 第 1 批 D-1 293 守恒 (+1, 0 production code 例外 2) |
| e2e PASS | 20/20 (W78 B-1 45/45 + W78 B-2 16/16 + W78 B-3 25/25 + W81 C-1 18/18 复用 + 5 新增 重派) |
| 8 件套监控 | W73 B-2 4 类 + W74 D-1 + W75 B-3 + W77 B-3 + W78 C-1 + W78 B-1 + W80 B-1 + W80 B-2 + W81 C-1 (本任务重派) |
| 6 新铁律 | 类 20.13 实战 14 + 派工 v6 段 5 反馈 #6 + 类 20.7 + D-1 第 3 次重派 + 0 production code 例外 2 + 派工 v6 段 6 |
| 24 人月 Q1 | 28/24 人月超 4 人月 (W74-W81 累计 7 批 31 agents) |
| 范畴 | 仅新增 scripts/tests/docs/memory, 不动老 TTS/billing/QA 链路 |
| 派工前提 | 派工 v4 铁律 3 真验证 3 步 + 派生 4 实战 + 5 件套必做 + 5 段文档同步 |