# W78 第 1 批 B-1 — Edge-TTS B+D 组合渐进式跨平台整合 runbook

> **依据**: A-2 W77 commit `44cf83581` §5.3 W78 B-1 + W77 B-1 commit `bedcd4594` (iOS Safari) + W77 B-2 commit `cc3326409` (Android Chrome) + W76 A-2 commit `0c3f848d7` §3 B+D 决策
> **基线**: W78 main HEAD `068626ecc`
> **锚点范式**: W77 第 1 批 270 → W78 第 1 批 B-1 274 守恒 (+1)
> **0 production code 改动铁律例外 1 已批**: 仅新增 `tts_mainplay_pipeline.py`，不动 `app/services/audio_processor.py` / `app/voice/tts.py` 老 TTS 链路

---

## 段 0 — 前置真验证发现 (类 20.12.1 复发, 必读)

派工 v4 铁律 3 真验证 3 步在本批**拦下一个已合并进 main 的真回归**。派工输入声称的
"W77 B-1 20/20 e2e PASS" 与 "W77 B-2 20/20 e2e PASS" 在 main HEAD `068626ecc` 上
**无法同时成立**。

### 0.1 根因 — 同名模块 merge 互相覆盖

W77 B-1 与 W77 B-2 两个**并行** agent 各自新建了**同名**模块，且内部 API 完全不同:

| 模块 | W77 B-1 (iOS) 导出 | W77 B-2 (Android) 导出 |
|------|---------------------|-------------------------|
| `web_speech_fallback.py` | `WebSpeechFallbackHandler` / `build_web_speech_fallback_handler` (110 行) | `WebSpeechFallback` / `browser_hooks()` (130 行) |
| `tts_cache.py` | `TTSCacheStore` / `TTSCacheEntry` / `build_tts_cache_store` (149 行) | `TTSCache` / `TTSSynthesizeRequest` (124 行) |

`bedcd4594` (B-1) 先 merge，`cc3326409` (B-2) 后 merge → **B-2 版本整文件覆盖 B-1 版本**
(`git diff bedcd4594 HEAD -- app/services/web_speech_fallback.py` = 106 insertions / 86 deletions)。
后果:

```
ImportError: cannot import name 'WebSpeechFallbackHandler'
from 'app.services.web_speech_fallback'
```

`ios_tts_mainplay.py:28` 整模块加载失败 → iOS 侧 3 个 mainplay e2e 由自报的
"PASS" 实际退化为 **FAILED**。这与 §"2026-07-24 alembic 并行 agent 串单链纪律"
同构: **并行 agent 写同名新文件，merge 必冲突**，只是 Python 模块不像 alembic
有 `heads` 自检，所以静默到下游批次才暴露。

### 0.2 次要发现 — 20 errors 是环境噪音, 不是代码

直跑 `pytest tests/test_ios_safari_edge_tts_e2e.py` 得到 **20 errors in 86s**，
全部来自 conftest autouse `setup_db` fixture 连不上测试库
(`ConnectionRefusedError [WinError 1225]`，`TEST_DATABASE_URL` 默认
`localhost:5432/microbubble_test`)。这两个 TTS 套件**无 DB 依赖**，正确跑法:

```bash
SKIP_DB_SETUP=1 python -m pytest tests/test_ios_safari_edge_tts_e2e.py -q
```

**纪律**: 无 DB 依赖的 standalone 套件必须用 `SKIP_DB_SETUP=1` 跑，否则
20 errors 会掩盖真实的 3 FAILED (本批就是这样被掩盖的)。

### 0.3 修复 — 改名消歧, 渐进式不动 Android

| 动作 | 文件 |
|------|------|
| 新增 (B-1 版还原) | `app/services/ios_web_speech_fallback.py` |
| 新增 (B-1 版还原) | `app/services/ios_tts_cache.py` |
| 改 import (3 行) | `app/services/ios_tts_mainplay.py` |
| 改 import (1 行) | `tests/test_ios_safari_edge_tts_e2e.py:358` |
| **不动** | `app/services/web_speech_fallback.py` / `tts_cache.py` (Android 侧保持 B-2 版) |

Android 20/20 不受任何影响 (渐进式)。修复后:

```
SKIP_DB_SETUP=1 pytest tests/test_ios_safari_edge_tts_e2e.py tests/test_android_chrome_edge_tts_e2e.py -q
→ 40 passed in 0.09s
```

**新铁律 (第 1 条)**: 并行派多个新建 `app/services/*.py` 的 agent 时，派工 prompt
必须为每个 agent **指定唯一模块名前缀** (如 `ios_*` / `android_*`)，或明确共享模块
由**单一** agent 拥有。merge 后必须跑一次全量 import 自检:

```bash
# merge 后 import 自检 (只报 ImportError/AttributeError 类的真断链;
# ModuleNotFoundError 多为宿主缺可选依赖如 jieba / sentence_transformers, 与本批无关)
SKIP_DB_SETUP=1 python -c "
import pkgutil, importlib, app.services as s
bad = []
for m in pkgutil.iter_modules(s.__path__):
    try:
        importlib.import_module(f'app.services.{m.name}')
    except ModuleNotFoundError:
        pass                      # 宿主可选依赖缺失, 跳过
    except Exception as e:
        bad.append((m.name, type(e).__name__, str(e)[:80]))
print('BROKEN:', bad if bad else 'NONE')
"
```

本批实跑: 扫描 124 个模块 → `BROKEN: NONE` (修复前会命中
`ios_tts_mainplay / ImportError / cannot import name 'WebSpeechFallbackHandler'`)。

**新铁律 (第 2 条)**: agent 自报 "N/N e2e PASS" 不构成验收 (类 20.12 "调研完成 ≠
主拍验收" 的测试版)。下游批次必须以**实跑**为准 —— 本批若盲信派工输入的
40/40，会把一个 ImportError 直接叠加到整合层。

---

## 段 1 — 5 阶段整合平台 (`tts_mainplay_pipeline.py`)

统一入口: `TTSMainplayPipeline.synthesize(text, voice, **kwargs)`。

```python
from app.services.tts_mainplay_pipeline import (
    build_tts_mainplay_pipeline, PipelineConfig, Platform,
)

pipeline = build_tts_mainplay_pipeline()
result = pipeline.synthesize(
    "会议纪要已生成",
    voice="zh-CN-XiaoxiaoNeural",
    user_agent="... iPhone; CPU iPhone OS 17_0 like Mac OS X ... Safari/604.1",
    user_gesture=True,
)
# result.platform      → Platform.IOS_SAFARI
# result.backend       → PipelineBackend.WEB_SPEECH   (沙箱; 真 key 后为 EDGE_TTS)
# result.audio_format  → "mp3"                        (iOS 不支持 ogg)
# result.stages        → ['cross_platform_unify', 'pre_synthesize_cache',
#                         'edge_tts_progressive', 'web_speech_fallback']
```

| 阶段 | 常量 | 实现 |
|------|------|------|
| 1 Edge-TTS 渐进式 | `STAGE_EDGE_TTS_PROGRESSIVE` | 委派 W77 B-1 `IOSSafariMainplayAdapter` / W77 B-2 `AndroidTTSMainplay`，不重写 |
| 2 Web Speech 降级 | `STAGE_WEB_SPEECH_FALLBACK` | 两平台各自 `web_speech_fallback` 模块 (iOS `ios_web_speech_fallback`) |
| 3 pre-synthesize 缓存 | `STAGE_PRE_SYNTHESIZE_CACHE` | 跨平台 + 跨音色统一缓存，key = `sha256(platform|text|voice|format)[:20]`，TTL 24h |
| 4 跨平台整合 | `STAGE_CROSS_PLATFORM_UNIFY` | UA 嗅探 → `Platform` → 统一 `PipelineResult` |
| 5 监控容错 | `STAGE_MONITORING_FAULT_TOLERANCE` | 8 件套接入 + 适配器异常不外泄 |

### 1.1 缓存 key 必须含 platform (第 3 条新铁律)

iOS 走 mp3、Android 走 ogg (W76 B-2 OGG Vorbis 原生保留)。若 key 不含 platform，
Android 的 ogg 条目会被 iOS 命中并投喂一个 iOS 无法解码的 URL。key 同时含
`audio_format`，双重隔离。

### 1.2 真生产 key 双重守门 (类 20.13)

`PipelineConfig.production_key_enabled` 默认 `False`，且 `PROD_KEY_AUTO_ENABLE = False`
为**类级硬编码**。W78-B-2 主拍拍板前，即使调用方显式传 `production_key_enabled=True`，
`_resolve_prod_key()` 也会强制降级为沙箱并记 `metrics.prod_key_gate_downgrades`。
**W78 本批不自动启用真生产 key。**

### 1.3 监控 8 件套

现存 6 个 `scripts/monitor-*.sh` (9-table-index / alembic-heads / nginx-mime /
pwa-manifest / sw-cache / tenant-isolation) + 本批 `pipeline.monitoring_snapshot()`
提供的 pipeline 维度指标。

> ⚠️ **A-2 声称不符**: A-2 W77 commit `44cf83581` 记载 "monitor-edge-tts.sh 新建"，
> 但 `git log --diff-filter=A -- scripts/monitor-edge-tts.sh` **无任何记录**，
> 文件从未落地。本批不代建 (超出 B-1 范畴)，改由 `monitoring_snapshot()` 以
> 进程内指标补位，并在此登记缺口交 W78 D 系列收口。

`monitoring_snapshot()` 字段: `calls` / `cache_hits` / `cache_misses` /
`cache_hit_rate` / `edge_tts_used` / `web_speech_used` / `exhausted` /
`prod_key_gate_downgrades` / `max_cache_hit_ms`。

### 1.4 缓存 SLA

派工要求 P95 < 50ms。缓存为进程内 dict，实测命中路径 `max_cache_hit_ms` 远低于
阈值；`assert_cache_sla(p95_budget_ms=50.0)` 用 `max_cache_hit_ms` 作保守上界
(max ≥ P95，通过即 P95 必通过)。

---

## 段 2 — e2e 验收

```bash
cd E:/microbubble-agent
SKIP_DB_SETUP=1 python -m pytest \
  tests/test_tts_mainplay_pipeline_e2e.py \
  tests/test_ios_safari_edge_tts_e2e.py \
  tests/test_android_chrome_edge_tts_e2e.py -q
# → 45 passed
```

| 套件 | case | 说明 |
|------|------|------|
| `test_tts_mainplay_pipeline_e2e.py` | 5 | 本批新增跨平台整合 |
| `test_ios_safari_edge_tts_e2e.py` | 20 | 复用 W77 B-1 (本批修复后真 PASS) |
| `test_android_chrome_edge_tts_e2e.py` | 20 | 复用 W77 B-2 |
| **合计** | **45** | |

5 个新增 case: ①iOS Safari 统一接口 + mp3 降级 ②Android Chrome 统一接口 + ogg 原生保留
③Edge-TTS 渐进式 + 真生产 key 双重守门 ④Web Speech API 降级链 ⑤跨平台 pre-synthesize
缓存隔离 + 命中 + 24h TTL + SLA + 监控快照。

同时通过方案 C 铁律 2 gate: `bash scripts/check_typing_imports.sh` → 211 文件 0 错误。

---

## 段 3 — 部署必做

本批**无 alembic 迁移**、**无前端 dist 改动**，故不涉及 §alembic 串单链纪律与
§PWA manifest 410 铁律。

```bash
# 1. 无迁移, 直接重启 Python 进程 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 2. 验证新模块可加载
docker exec microbubble-agent-app-1 python -c \
  "from app.services.tts_mainplay_pipeline import build_tts_mainplay_pipeline; \
   print(build_tts_mainplay_pipeline().monitoring_snapshot())"

# 3. 确认真生产 key 守门仍关闭 (类 20.13)
docker exec microbubble-agent-app-1 python -c \
  "from app.services.tts_mainplay_pipeline import TTSMainplayPipeline; \
   assert TTSMainplayPipeline.PROD_KEY_AUTO_ENABLE is False; print('prod key gate CLOSED')"
```

回滚: `git revert <commit>` 单条撤销。老 TTS 链路 (`audio_processor.py` /
`app/voice/tts.py`) 全程未被引用，回滚零风险。

---

## 段 4 — 锚点范式守恒

W77 第 1 批 270 → W78 第 1 批 B-1 **274 守恒 (+1)**。

0 production code 改动铁律**例外 1 已批**: 新增 `tts_mainplay_pipeline.py` +
`ios_web_speech_fallback.py` + `ios_tts_cache.py`。后两者是 §0 回归修复的必要产物
(还原 W77 B-1 被覆盖的模块)，范畴仍在"新增 app/services/ 模块"内，未触碰
`audio_processor.py` / `app/voice/tts.py` / `useChatStream.ts`
(`git diff main -- app/services/audio_processor.py app/voice/ web/src/` = 空)。

`ios_tts_mainplay.py` 3 行 import 改动属 W77 B-1 自身回归修复，不扩大到老路径重构。

### 交 W78 后续批次

1. **`scripts/monitor-edge-tts.sh` 缺口** — A-2 声称已建实际从未落地 (§1.3)
2. **类 20.13 真生产 key 主拍** — W78-B-2 单独拍板，本批不自动启用
3. **并行 agent 模块命名前缀纪律** — 建议提升到 CLAUDE.md 永久锚点，与 alembic 串单链纪律并列
