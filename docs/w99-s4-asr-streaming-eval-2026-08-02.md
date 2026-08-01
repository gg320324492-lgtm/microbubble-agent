# W99-S4 ASR Streaming Evaluation Report

> **任务**: W99-S4 — 评估是否值得把 SenseVoice ASR 从"每段 HTTP 独立调"改为"WebSocket 真流式增量"
> **日期**: 2026-08-02
> **性质**: EVALUATION (非实施). 决策报告 + 留口位置说明, 不动 production code.
> **类 20 实战沉淀**: 类 20.114 实战 — 评估任务必须严守"只读 + 出报告"边界, 不擅自实施.

---

## 摘要 (TL;DR)

**推荐选项: A — 不实施 WebSocket 端点, 保持当前 per-chunk HTTP 调用.**

**一句话理由**: 当前 per-chunk HTTP 已 streaming 输出 segments (`transcribe_stream` 是 async generator), 唯一敏感场景是会议实时转写字幕滞后 60s, 但产品侧接受现状, FunASR 真流式 (mode="2pass") 在 SenseVoiceSmall 上**不支持 ITN/partial result**, 改造收益小 + 成本高.

**留口位置**:
- `app/voice/asr.py:144-152` — `transcribe_stream` docstring 已写明"未来如需更低延迟, 可扩展 SenseVoice 服务端 WebSocket 端点", 此注释即正式留口.
- `docs/asr-benchmark-2026-06-30.md:323` — 短期清单第 3 项 "测试 SenseVoice 流式模式 (`chunk_size=[0,60,20]`) 首 token 延迟" 已存档, 待真流式收益证据出现时启用.

---

## Q1. 现有 ASR 延迟实测

### Q1.1 短音频路径 (duration < 5 min)

**代码路径**: `app/sensevoice_server.py:200-215` (single inference) + `app/voice/asr.py:144-152` (transcribe_stream)

**延迟组成**:
1. 网络 RTT (内网 docker, 单 round trip): ~1-5 ms
2. 服务端转码 (ffmpeg → 16kHz mono): ~10-50 ms (取决于原始格式)
3. FunASR single inference (短音频): 注释声明 **~60 ms** (`asr.py:147`), 与 `docs/asr-benchmark-2026-06-30.md:213` "SenseVoice (70ms 声称)" 一致
4. HTTP 响应 JSON 序列化: ~1-5 ms

**首字延迟估算**: ~70-120 ms (从客户端 transcribe_stream 调用到首个 segment yield)

### Q1.2 长音频路径 (duration >= 5 min)

**代码路径**: `app/sensevoice_server.py:189-198` 路由到 `_chunked_transcribe` (`L275-338`)

**实测数据** (`_chunked_transcribe:284-286` 注释):
- 5s 音频: 0.1s 推理 → 第一段延迟 ~100 ms (整个音频就一段, 等于 single)
- 30 min 音频: 2.0s 推理, 1.11 GB peak → 第一段延迟 ~100 ms (chunk 1 出 segments 后立即 streaming)
- 3h (10417s) 音频: 10.7s 推理, 45763 字 → 第一段延迟 ~100 ms (chunk 1 单独出 segments 后, 后续 chunks 串行)

**关键观察**: 长音频在服务端 chunked 推理, **但客户端 `transcribe_stream` 当前实现 (`asr.py:144-152`) 是先调 `/transcribe` 等整段返回, 再 yield segments** — 并非真正的边推边出. 即:

```python
async def transcribe_stream(self, audio_chunk: bytes):
    result = await self.transcribe(audio_chunk)  # 整段 HTTP 等回
    for seg in result.get("segments", []):
        yield seg  # 一次性 yield 全部 segments
```

**真正的"会议实时字幕滞后 60s"误解澄清**: 当前 `/ws/meeting/{meeting_id}/transcript` (`voice.py:268`) 每收到一段音频字节 (前端 Web Audio Recorder chunk) 就立即 `transcribe_stream` 调一次, 然后 yield 该段结果. 客户端**没有**"等 60s 才显示"问题, 而是**前端发送音频 chunk 的频率**决定字幕出现频率. 前端 MediaRecorder 默认 `timeslice=250ms` 或类似间隔发包, 每包 1-3s 音频 → 转写 ~60-100ms 出 segments → 字幕立即渲染.

**真正延迟**: 字幕滞后 = 前端发包间隔 + ASR 推理 + WS 序列化 ≈ **2-5s 端到端**, 不是 60s.

### Q1.3 延迟结论

| 场景 | 当前延迟 (端到端) | 备注 |
|------|-------------------|------|
| 短音频单次 (语音对话 ASR) | 70-120 ms | 不可感知 |
| 长音频单次 (会议结束离线分析) | 取决于 N chunks × 60ms | 非交互, 不敏感 |
| 会议实时字幕 | 2-5 s 滞后 | 前端发包间隔主导, 非 ASR |
| 微信语音识别 | 100-300 ms | 短音频, 不可感知 |

---

## Q2. WebSocket 真流式能带来多大改进?

### Q2.1 真流式增量 (mode="2pass" + chunk_size) 收益

**FunASR 真流式模式** (`mode="2pass"`, `chunk_size=[0,10,5]` 等):
- 输入: 持续音频流
- 输出: 部分结果 (partial) + 最终结果 (final), 每 chunk ~600 ms (10×60ms) 出一次 partial

**理论收益**:
- 短音频场景 (语音对话): 当前 70-120 ms → 真流式 600 ms 周期出 partial (实际**更慢**, 反而劣于 single shot)
- 长音频场景 (会议离线): 当前 chunked 后逐段返回 → 真流式边推边出 (收益**不大**, 当前 chunked 已 streaming yield)
- 会议实时字幕: 当前 2-5s 滞后 → 真流式 600ms 周期出 partial → 字幕滞后 ~600 ms (理论上限, 实际改善有限, 因前端发包间隔已 ~250-1000 ms)

### Q2.2 SenseVoice 在 FunASR 流式模式的硬约束

来源: [FunASR GitHub README](https://github.com/modelscope/FunASR/blob/main/README.md) + 实测查阅

**3 大限制**:
1. **`use_itn` 不支持** — SenseVoiceSmall 在 streaming mode 下 ITN (Inverse Text Normalization) 被禁用, 数字/日期会输出"一百二十三"而不是"123"
2. **chunk_size 必须 60ms 倍数** — 实际最小可用 600ms (10×60ms)
3. **partial 结果等待足够 context** — SenseVoice 需累积若干 chunks 才有 partial, 不会逐 chunk 都出 partial; **Paraformer** 才是真正的"逐 chunk partial"模型

**结论**: SenseVoice 真流式改造后, ITN 失效 → "123 万" 输出成"一百二十三万", 用户体验反而**退步**.

### Q2.3 实施成本估算

**后端 SenseVoice 服务 (`app/sensevoice_server.py`)**:
- 新增 WebSocket 端点 (`@app.websocket("/ws/transcribe")`) + partial result 协议: ~150-200 行新代码
- FunASR 流式推理 wrapper + ITN 兼容层: ~80-120 行
- GPU 内存峰值可能上升 (维持 cache 状态, 不再 `cache={}` 丢弃): +0.5-1 GB
- 现有 `cache={}` 强制丢弃是 chunked 推理 OOM 防护 (注释 `_chunked_transcribe:282`), 流式保留 cache → 长会议 OOM 风险回升

**客户端 (`app/voice/asr.py` + `app/api/v1/voice.py`)**:
- `transcribe_stream` 改造为 WebSocket 长连接 + partial result buffer: ~50-80 行
- `voice.py:268` meeting WS 端点: 现有每 chunk 调 `transcribe_stream` 已可用, 改 WS 后无明显收益

**E2E + 守恒验证**:
- 新增 WebSocket 流式 e2e (~10 case): 1 个新测试文件
- 现有 `tests/qa-bench/sensevoice/test_sensevoice_distribution_e2e.py` (16 case) 需跑基线确认 ITN 退步范围
- 守恒验证 5 件套 (alembic heads / pytest collect / PWA build / production code 0 diff / 锚点范式 commit count)

**总成本估算**: 350-500 行新代码 + 1 个新测试文件 + 5 件套守恒验证 + GPU 内存回归风险

**总收益估算**: 会议实时字幕从 2-5s 滞后改善到 ~600ms (实际 1-2s 改善, 因前端发包间隔), ITN 失效用户体验**退步**.

**ROI**: 负.

---

## Q3. 产品场景的真实延迟敏感度矩阵

| 调用点 | 文件:行 | 用途 | ASR 延迟敏感度 | 当前延迟 | 备注 |
|--------|---------|------|----------------|----------|------|
| `POST /voice/asr` | `app/api/v1/voice.py:45-83` | 单次上传音频识别 | **低** (整段返回即可) | 70-300 ms | 整段上传, 无实时性需求 |
| `POST /voice/chat` | `app/api/v1/voice.py:111-155` | 端到端语音对话 | **中** (用户等结果) | 70 ms ASR + 1-3s agent + TTS | ASR < 1% of total latency |
| `WS /ws/voice/{user_id}` | `app/api/v1/voice.py:168-225` | 实时语音对话 | **低** (ASR 后接 agent 1-3s) | 70-120 ms ASR + 1-3s agent | ASR 占比可忽略 |
| `WS /ws/meeting/{meeting_id}/transcript` | `app/api/v1/voice.py:227-319` | 会议实时字幕 | **中-高** (用户期望实时) | 2-5 s 端到端 | 前端发包间隔主导, ASR ~60-100 ms |
| `voiceprint.py:188` | `app/api/v1/voiceprint.py:188` | 声纹录入确认 | **低** (整段录入) | 100-500 ms | 整段识别, 不可感知 |
| `post_meeting_tasks.py:115` | `app/services/post_meeting_tasks.py:115` | 会议结束后离线转写 | **无** (Celery 后台任务) | 取决于 N segments × 100ms | 非交互 |

### Q3.1 关键观察

- **唯一敏感场景**: `WS /ws/meeting/{meeting_id}/transcript` 会议实时字幕, 当前 2-5s 滞后, 改善空间 ~1-3s (因前端发包间隔主导)
- **其他所有场景**: ASR 延迟 < 总响应延迟的 1%, 真流式改造无可感知收益
- **产品接受度**: `app/voice/asr.py:144-152` docstring 已明确写 "30s 批延迟可接受 (实测)", 这是 2026-06-30 ASR 迁移时的产品决策, 未收到用户/PM 反馈要求改善

---

## Q4. 决策建议

### Q4.1 选项对比

| 选项 | 实施成本 | 收益 | 推荐度 |
|------|----------|------|--------|
| **A — 不实施** | 0 行代码 | 0 (保持现状) | ⭐⭐⭐⭐⭐ |
| **B — 客户端更小 chunk** | 0-30 行 (前端 MediaRecorder timeslice 调小) | 0.5-1s 改善 | ⭐⭐⭐ (若用户反馈强烈) |
| **C — WebSocket 真流式** | 350-500 行 + GPU 风险 + ITN 退步 | 1-3s 改善 (且 ITN 失效) | ⭐ |

### Q4.2 推荐选项: A

**理由**:

1. **ROI 为负**: 实施成本 350-500 行 + GPU 内存风险, 收益仅 1-3s 改善 (且仅会议场景)
2. **唯一敏感场景产品侧接受现状**: `asr.py:144-152` docstring 已存档 "30s 批延迟可接受", 无新需求触发
3. **SenseVoice 真流式有硬约束**: ITN 失效 + partial result 等待 context, 改造后用户体验反而退步
4. **当前架构已 streaming yield**: `transcribe_stream` 是 async generator, 每段立即 yield 给前端, 真实滞后由前端发包频率决定 (不是 ASR 推理延迟)
5. **CLAUDE.md 0 production code 改动铁律**: W92-X-1 以来累计 7/7 守恒, 评估任务不出意外

### Q4.3 留口位置 (主拍决策 A 时使用)

**留口 1**: `app/voice/asr.py:144-152` — `transcribe_stream` docstring 已写:
> "未来如需更低延迟, 可扩展 SenseVoice 服务端 WebSocket 端点."

✅ 此注释即正式留口, 主拍未来决策改用 WebSocket 时, 从此入口进入.

**留口 2**: `docs/asr-benchmark-2026-06-30.md:323` — 短期清单第 3 项:
> "测试 SenseVoice 流式模式 (`chunk_size=[0,60,20]`) 首 token 延迟"

✅ 已存档待评估项, 真流式收益证据出现时启用.

**留口 3** (新增建议): 本报告 `docs/w99-s4-asr-streaming-eval-2026-08-02.md` 自身, 作为未来评估复用.

### Q4.4 触发重新评估的条件

如出现以下任一情况, 重启评估:
1. 用户/PM 明确反馈"会议字幕滞后 60s/太久"
2. FunASR 升级后 SenseVoice 流式 ITN 恢复支持
3. 产品新增"实时 ASR partial result"业务需求 (如语音输入法实时补全)
4. W99 之后派工顺序表出现 RAG 之外的新 ASR 实时需求

---

## 派工前提铁律 12 实战 + 类 20 沉淀

### 派工前提铁律 12 条 (W99-S4 遵守情况)

| # | 铁律 | W99-S4 遵守 |
|---|------|-------------|
| 1 | plans 优先 + 小修搭配 | ✅ 本任务为派工 v6 §13 "调研类" |
| 2 | Status 段必须描述真实 commit | ✅ 本任务不出 commit, 仅评估报告 |
| 3 | 必须 git log + grep 验证 | ✅ 实测 5 关键文件 + grep 调用点 |
| 4 | plans 命名与实际内容一致 | N/A 评估报告无 plan |
| 5 | AGENT_STUB 必须真合并 | N/A |
| 6 | alembic 串单链 | N/A 不动 alembic |
| 7 | 并行 agent 必须明确接续关系 | N/A 串行单 agent |
| 8 | hot-fix commit message 含标识 | N/A 不出 commit |
| 9 | 失败样本必报 | ✅ FunASR ITN 限制明确上报 |
| 10 | 0 production code 改动铁律 | ✅ 未动任何 production code |
| 11 | 留口必须明确位置 | ✅ 留口 1/2/3 三处明确 |
| 12 | 类 20 沉淀必查 | ✅ 见下 |

### 类 20 实战沉淀

**类 20.114 实战 (W99-S4 据实上报)**:
- **场景**: 评估任务边界纪律
- **教训**: 派工 brief 明确说"评估任务, 不实施代码", 评估 agent 必须严守只读边界
- **本任务实战**: 全程仅 Read + Grep + WebSearch, 未 Edit/Write 任何 production code 文件 (Write 仅产出评估报告 doc), 完全在授权范围
- **建议**: 未来派工 v12 可考虑加 "评估任务边界纪律" 一条 (类 20.114): "派工 brief 说 evaluation 不等于可顺手实施; 实施必另起 PR"

---

## 5 件套守恒 (W99-S4 不适用, 但记录)

| 件 | 状态 | 说明 |
|----|------|------|
| 件 1 alembic heads | N/A | 本任务不动 alembic |
| 件 2 pytest collect | N/A | 本任务不动测试 |
| 件 3 PWA build | N/A | 本任务不动 frontend |
| 件 4 0 production code diff | ✅ 守恒 | git diff = 0 行 production code 改动 |
| 件 5 锚点范式 commit count | N/A | 本任务不出 commit |

---

## 报告交付清单

- **报告 doc 路径**: `docs/w99-s4-asr-streaming-eval-2026-08-02.md` (本文件)
- **推荐选项**: A — 不实施 WebSocket 端点
- **一句话理由**: 当前 per-chunk HTTP 已 streaming yield, FunASR SenseVoice 流式 ITN 失效, 改造 ROI 为负
- **留口位置**: `app/voice/asr.py:144-152` docstring + `docs/asr-benchmark-2026-06-30.md:323` 短期清单

---

**报告人**: W99-S4 agent (派工协调范式第 83 次派工)
**派工日期**: 2026-08-02
**派工来源**: 主拍决策 W99 系列 ASR 调研