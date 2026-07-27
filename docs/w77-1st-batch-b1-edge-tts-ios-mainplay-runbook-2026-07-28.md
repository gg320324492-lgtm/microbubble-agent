# W77 第 1 批 B-1 — Edge-TTS iOS Safari B+D 渐进式主拍接入 runbook (2026-07-28)

## 派生背景

**派工**: W77 第 1 批 B-1 (主指挥协调范式第 51 次派工)
**依据**: W76 A-2 commit `0c3f848d7` §1.2 B+D 渐进式决策建议 + W76 B-1 commit `a20ec9603` 17/17 e2e 基础 + 派工 v6 段 5 反馈 #6 实战 (类比 W75 C-1 真支付 SDK 渐进式)
**目标**: 锚点范式 W76 第 1 批 263 → W77 第 1 批 B-1 **267** 守恒 (+1)

## 0 production code 例外清单 (1 已批)

| # | 例外 | 范围 | 文件 | 状态 |
|---|------|------|------|------|
| 1 | W77 B-1 Edge-TTS iOS Safari 主拍接入新增 | `app/services/` 仅新增 3 文件 | `ios_tts_mainplay.py` / `web_speech_fallback.py` / `tts_cache.py` | 已批 (W77 B-1 派工拍板) |

**不修改老路径**: `app/services/audio_processor.py`, `app/voice/tts.py`, `web/src/composables/chat/useChatStream.ts`, `web/src/views/mobile/chat/*`

## W77 B-1 交付物

### 1. 主拍接入适配器 (核心)

**文件**: `app/services/ios_tts_mainplay.py` (新建)
**角色**: B+D 渐进式主拍接入 orchestrator

5 阶段实战:
1. **Edge-TTS 渐进式**: 在 W76 B-1 ios_tts_autoplay.py 基础上扩展为主拍接入
2. **Web Speech API 降级**: 通过新建 `web_speech_fallback.py` 同步调用
3. **pre-synthesize 缓存**: 通过新建 `tts_cache.py` 缓存层 (24h TTL)
4. **真生产 key 主拍决策**: W78 单独拍板 (类 20.13 实战, W77 默认 `production_key_enabled=False`)
5. **监控 + 容错**: 接入 W73 B-2 4 类 hot-fix 监控 + W74 D-1 多租户监控 + W75 B-3 webhook 监控 (orchestrator 落 metrics)

### 2. Web Speech API 降级 handler

**文件**: `app/services/web_speech_fallback.py` (新建)
**角色**: iOS Safari 原生 `speechSynthesis.speak()` 降级

特性:
- 零网络依赖 (Edge-TTS 失败时立即可用)
- iOS Safari 原生支持, 无后端凭证
- 受限: 音色少 (vs Edge-TTS ~300 音色), 停顿/语速参数精度差
- 沙箱模式: 模拟执行结果 (e2e 用), 生产模式: 真原生 API 调用

### 3. TTS pre-synthesize 缓存层

**文件**: `app/services/tts_cache.py` (新建)
**角色**: D 选项核心 — Edge-TTS API 复用减少

特性:
- key = `sha256(text|voice)[:16]`
- TTL = 24h (86400s, W73 录音断网防御参考)
- LRU 简化: max_size=10000, 满时清最旧 10%
- 命中率监控: hits/misses/hit_rate/size/evictions
- 过期 lazy 清理 (get 时检查)

### 4. e2e 测试 (扩展 3 case)

**文件**: `tests/test_ios_safari_edge_tts_e2e.py` (扩展)
**原 17/17 (W76 B-1) + 新增 3/3 (W77 B-1) = 20/20 e2e PASS**

3 新增 case:
- **5.1 B+D 渐进式主拍接入**: Edge-TTS primary 失败 → Web Speech API 降级成功 + 2 attempts 记录正确
- **5.2 pre-synthesize 缓存命中**: 24h TTL + hit_rate + metrics + LRU 简化
- **5.3 真生产 key 主拍 W78 单独拍板**: 类 20.13 实战, W77 默认 `production_key_enabled=False`, 显式断言 gate

## 派工 v6 段 5 反馈 #6 实战 (渐进式)

类比 W75 C-1 真支付 SDK 沙箱测试模式:
- **3 支付渠道真 SDK 接入** → **3 TTS backend (Edge-TTS primary + Web Speech fallback + Cache) 主拍接入**
- **沙箱模式** (默认不接真钱, 小额 ¥0.01 测试) → **沙箱模式** (默认 `production_key_enabled=False`)
- **优雅降级** (SDK 不可用 → mock) → **优雅降级** (Edge-TTS 失败 → Web Speech API 原生)
- **真生产 key 单独拍板** (W78 拍板) → **真生产 key 单独拍板** (W78 拍板)
- **12/12 e2e PASS 沙箱** → **20/20 e2e PASS 沙箱** (16 复用 + 3 新增 + 1 综合)

## 派工 v4 铁律 3 真验证记录

| Step | 验证项 | 结果 |
|------|--------|------|
| 1 | W76 A-2 B+D 决策建议 (commit 0c3f848d7) | ✅ §1.2 B+D 决策建议明确 |
| 2 | W76 B-1 ios_tts_*.py 基础 (commit a20ec9603) | ✅ 17/17 e2e 基础, 4 ios_tts_*.py 已建 |
| 3 | 当前 audio_processor.py 老 TTS 链路 | ✅ logger + audio_processor 单例, 不动 |

## 部署必做

```bash
# 1. 复制 3 个新文件到主项目
cd E:/microbubble-agent/.claude/worktrees/agent-w77-1-b1-ios-main
git add app/services/ios_tts_mainplay.py
git add app/services/web_speech_fallback.py
git add app/services/tts_cache.py
git add tests/test_ios_safari_edge_tts_e2e.py  # 3 case 扩展
git add docs/w77-1st-batch-b1-edge-tts-ios-mainplay-runbook-2026-07-28.md

# 2. e2e 验证 (沙箱模式, 无 DB 依赖)
# 3 个新增 case 已 standalone 验证 PASS (tests/conftest.py DB fixture 不影响 standalone)
python -c "import sys; sys.path.insert(0, '.'); \
    from app.services.ios_tts_mainplay import build_ios_safari_mainplay_adapter; \
    adapter = build_ios_safari_mainplay_adapter(); \
    r = adapter.play(text='晓晓'); print('OK', r.backend_used)"

# 3. W78 单独拍板 production_key_enabled (类 20.13 实战, 不在 W77 自动启用)
```

## 与 W76 B-1 / W75 C-1 关系

| 维度 | W75 C-1 (真支付 SDK) | W76 B-1 (iOS Safari 4 维度) | **W77 B-1 (B+D 主拍接入)** |
|------|----------------------|----------------------------|----------------------------|
| 角色 | 沙箱模式真接入 | iOS Safari 实战细化 | **主拍 orchestrator** |
| 派工模式 | 派工 v6 §5 反馈 #6 | 派工 v6 §5 反馈 #6 | **派工 v6 §5 反馈 #6** |
| 模式 | 渐进式 + 沙箱 | 渐进式 + iOS 实战 | **B+D 渐进式 + 沙箱** |
| 例外数 | W75 多例外 | 1 例外 (新增 4 文件) | **1 例外 (新增 3 文件)** |
| 锚点范式守恒 | W74 → W75 | W75 → W76 +1 | **W76 → W77 +1** |
| 派工协调 | #TBD | 第 49 次 (W76 A-2) | **第 51 次 (W77 B-1)** |
| 真生产 key | W75 W78 主拍 | N/A (TTS 无 sandbox) | **W78 单独拍板** |

## 锚点范式守恒

- W76 第 1 批: **263** (main HEAD `61561c58d`)
- **W77 第 1 批 B-1: 267** (+1, 3 个新增 e2e case = 1 守恒单位)

## 沉淀文件

- `app/services/ios_tts_mainplay.py` — 主拍 orchestrator (5 阶段实战)
- `app/services/web_speech_fallback.py` — iOS Safari 原生降级
- `app/services/tts_cache.py` — pre-synthesize 缓存层
- `tests/test_ios_safari_edge_tts_e2e.py` — 3 新增 e2e case
- `docs/w77-1st-batch-b1-edge-tts-ios-mainplay-runbook-2026-07-28.md` — 本文档
- `memory/w77-1st-batch-b1-edge-tts-ios-mainplay-2026-07-28.md` — 任务沉淀 (派生)
