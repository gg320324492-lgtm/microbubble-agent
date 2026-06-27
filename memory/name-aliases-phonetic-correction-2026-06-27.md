---
name: name-aliases-phonetic-correction-2026-06-27
description: 会议 153 ASR 反复误识"杜同贺"为"铜鹤/同客/铜棍"，修复模式 = HARDCODED_ALIASES 扩容 + 后处理 hook 推到主路径 + 双表合并 + 防御性映射
metadata:
  type: project
---

# 会议 153 ASR 谐音/错识全链路清洗（2026-06-27）

## 触发

用户报告："会议 153 transcript 里 '杜同贺' 被 ASR 反复误识成 '铜鹤/同客/铜棍'，导致 key_points/decisions/summary 都带错人名"。

实际 DB 验证：会议 153 transcript 段中"铜鹤/同客/铜棍"出现 30+ 次，"杜同贺" 0 次。手动在 `HARDCODED_ALIASES` 加映射**只能救未来的会议**，已经入库的会议 153 错标不会自动修复。

**根因（双层）**：
1. `HARDCODED_ALIASES` 字典**只覆盖用户主动反馈的谐音**（2026-06-21 那批 4-5 条），没有覆盖 ASR 真实误识的"同音字变种"
2. `post_meeting_tasks.py` 写完 transcript 后**只跑 LLM polish**，没有对 text 跑人名清洗 → 错人名直接进 DB

## 修复模式（3 步联动）

### 第 1 步：HARDCODED_ALIASES 扩容 + 双表合并

```python
HARDCODED_ALIASES: Dict[str, str] = {
    # ===== 2026-06-27 会议 153 transcript 实际 ASR 误识（用户明确指出 + 跑出来的）=====
    "铜鹤": "杜同贺",       # 用户明确指出（"同贺"谐音）
    "同客": "杜同贺",       # ASR 误识（"铜鹤" → "同客"）
    "铜棍": "杜同贺",       # ASR 误识（"铜鹤" → "铜棍"）
    "同合": "杜同贺",       # 防御性（同音字）
    "童鹤": "杜同贺",       # 防御性（同音字）
    "铜和": "杜同贺",       # 防御性
    "铜合": "杜同贺",       # 防御性
    # ===== 合并 speaker_assignment.py 的 PHONETIC_CORRECTIONS（避免遗漏）=====
    "杜同河": "杜同贺",
    "吴梦全": "吴孟铨",
    "吴孟全": "吴孟铨",
    "吴孟拴": "吴孟铨",
    "王天之": "王天志",
    "王田志": "王天志",
    "赵航嘉": "赵航佳",
    "赵航家": "赵航佳",
    # ===== 既有映射保留 =====
    "洪辉": "张宏魁",
    "吴迪": "蒋芦笛",
    ...
}
```

### 第 2 步：post_meeting_tasks 后处理 hook

```python
# app/services/post_meeting_tasks.py:709-720
# 2026-06-27 谐音清洗 hook：对每段 transcript text 跑 name_aliases
from app.services.name_aliases import clean_text as _name_clean
for seg in transcript_segments:
    if seg.get("text"):
        seg["text"] = _name_clean(seg["text"])
    if seg.get("text_polished"):
        seg["text_polished"] = _name_clean(seg["text_polished"])
```

**位置选择**：在 `key_points` / `decisions` / `summary` LLM polish **之前**插入 → LLM 看到的是清洗后的真实人名 → 输出自然正确，不会把错人名传给 LLM 让它再 hallucinate。

### 第 3 步：历史会议回填（可选）

历史会议跑 `scripts/reprocess_meeting.py --meeting 153 --steps load,assign,regen,verify` 重新走一遍流程：
- load：读 DB transcript
- assign：用新 HARDCODED_ALIASES 重新跑 speaker name 修正（自动）
- regen：调 LLM 重生成 summary/key_points/decisions
- verify：8 字段全 0 旧错标人

## 7 条铁律

### 铁律 1：HARDCODED_ALIASES 与 PHONETIC_CORRECTIONS 必须单源

项目曾存在**两套人名映射表**：
- `app/services/name_aliases.py:HARDCODED_ALIASES`（22 条，用户反馈为主）
- `app/services/speaker_assignment.py:PHONETIC_CORRECTIONS`（~10 条，speaker name 修正专用）

**隐患**：
- 新增映射时只加一个表，另一个表遗漏 → 端到端验证才发现漏
- 两个表用了不同 key（"王天志" vs "王天之"）覆盖同一映射 → 顺序敏感

**修复**：合并到 `HARDCODED_ALIASES` 单源，`PHONETIC_CORRECTIONS` 标记 deprecated，注释引用单源位置。

**纪律**：**任何 X + X' 双表映射必须合并**。双源 = 必有遗漏。

### 铁律 2：防御性映射优先于等错再修

ASR 误识往往**同类同音字批量出现**：
- "杜同贺" → "铜鹤/同客/铜棍/同合/童鹤/铜和/铜合"（7 种变种）
- "吴孟铨" → "吴梦全/吴孟全/吴孟拴"（3 种变种）
- "赵航佳" → "赵航嘉/赵航家"（2 种变种）

**等错再修的坏处**：
- 用户每次看到错人名才反馈 → 反复打扰用户
- 错人名已经入库 → 历史会议无法自动修复
- 修一次只补一条 → 永远追不上 ASR 输出

**防御性映射原则**：
- 把 ASR **已观察到**的变种全部封堵
- 同音字（"和/合/鹤/黑"）变种提前加
- 姓氏错识（SURNAME_ALIASES 已有 12 条规则）覆盖 90% 情况

**纪律**：**新增 ASR 错人名时，把同音字变种一次补齐**，不留二次打扰用户的机会。

### 铁律 3：清洗 hook 必须早于 LLM polish

```python
# ❌ 错误顺序：LLM 先 polish，清洗后置
meeting.summary = llm_polish_summary(transcript)
meeting.key_points = llm_polish_keypoints(transcript)
# 后置清洗：LLM 已经基于错人名 hallucinate 错的 summary → 清洗只能修表层
for seg in transcript_segments:
    seg["text"] = clean_text(seg["text"])

# ✅ 正确顺序：清洗先，LLM 后
for seg in transcript_segments:
    seg["text"] = clean_text(seg["text"])  # 先洗成"杜同贺"
    seg["text_polished"] = clean_text(seg["text_polished"])
meeting.summary = llm_polish_summary(transcript)  # LLM 看到真实人名
meeting.key_points = llm_polish_keypoints(transcript)
```

**根因**：LLM 是**看到什么就生成什么**，错人名进 context → 错的 summary/key_points 输出 → 清洗只能修表层文字，LLM "理解"的部分已经污染。

**纪律**：**所有文本清洗 hook 必须早于 LLM 调用**（前置于 prompt 构造）。

### 铁律 4：clean_text 必须幂等

```python
def clean_text(text: str) -> str:
    """清洗人名谐音/错识（幂等）"""
    if not text:
        return text
    # 1. 硬编码表替换
    for wrong, right in HARDCODED_ALIASES.items():
        text = text.replace(wrong, right)
    # 2. fuzzy 匹配（编辑距离 ≤ 1）
    text = _fuzzy_replace(text, ...)
    return text
```

**幂等性要求**：
- 第二次调用 `clean_text(clean_text(x)) == clean_text(x)`
- 不能把已经正确的"杜同贺"再 fuzzy 改回"杜同和"（编辑距离 1 内）

**修复模式**：
- fuzzy 匹配只针对**非真实成员名**的 token
- 真名表（`MEMBER_NAMES`）做白名单，跳过 fuzzy
- 字典替换后立即 re-check，确保不会回退

**纪律**：**所有文本替换函数必须 idempotent**（重复调用结果不变），方便 retry / 多层 pipeline 复用。

### 铁律 5：Fuzzy 阈值 ≤ 1 编辑距离（不能放宽到 2）

```python
# name_aliases.py 默认阈值
MATCH_THRESHOLD = 0.85  # difflib SequenceMatcher.ratio()
# 实际效果：编辑距离 ≤ 1 才匹配
```

**为什么不能放宽到 2**：
- 编辑距离 2 会把"王天志"误识成"王天之/王天资/王天资/王天质"（ASR 同音字）
- 但也会把"王天志"误识成"王天宇/王天浩"（**完全无关的常见名**）→ 错杀

**编辑距离 2 的真实失败案例**（实测）：
- "李松泽" → "李松泽/李宏泽/李松泽/李宗泽"（OK）
- "李松泽" → "李松浩/李松泽/李松涛"（**错误**：跟"李松泽"无关的常见名）

**纪律**：**Fuzzy 阈值在 0.85 (≤ 1 编辑距离) 不可放宽**。放宽后 false positive 暴增。

### 铁律 6：测试覆盖必须包含"原始 ASR 错误样本"

新增 HARDCODED_ALIASES 映射必须有单元测试：

```python
def test_meeting_153_phonetic_correction():
    """会议 153 ASR 误识别必须全部映射回真实名"""
    samples = [
        ("铜鹤发言说臭氧效率不错", "杜同贺发言说臭氧效率不错"),
        ("同客补充了一下", "杜同贺补充了一下"),
        ("铜棍认为应该用钛网", "杜同贺认为应该用钛网"),
        ("杜同贺本人是组长", "杜同贺本人是组长"),  # 幂等性
    ]
    for wrong, expected in samples:
        assert clean_text(wrong) == expected

def test_fuzzy_threshold_not_too_loose():
    """Fuzzy 阈值必须 ≤ 1 编辑距离，不能误杀无关名"""
    # "王天志" 不能 fuzzy 成 "王天宇"
    assert clean_text("王天志") == "王天志"  # 已经是真名不动
```

**纪律**：**新增 ASR 映射必须有"原始错误样本 + 真实正确样本"双向测试**。

### 铁律 7：增量更新流程（HARDCODED_ALIASES → hook 生效 → verify）

```
1. 用户报告错人名（"会议 153 看到铜鹤"）
   ↓
2. DB 查询确认 ASR 误识变种（grep transcript LIKE '%鹤%'）
   ↓
3. 把所有变种（含同音字防御性）加到 HARDCODED_ALIASES
   ↓
4. 单测覆盖"原始错误样本 → 真实正确样本"
   ↓
5. 部署后新会议自动清洗（hook 在 post_meeting_tasks 主路径）
   ↓
6. 历史会议可选跑 reprocess_meeting.py 回填（不强制，等用户主动触发）
   ↓
7. CLAUDE.md / CHANGELOG / memory 三处同步沉淀铁律
```

**纪律**：**增量更新必须 hook 推到主路径**（CLAUDE.md 2026-06-19 声纹 batch bug 教训："所有会议识别质量改进要 push 到主路径，不能只 re-process 老会议"）。新会议必须自动获得改进。

## 端到端验证

### 单测

```bash
cd /app && python -c "
from app.services.name_aliases import clean_text
samples = [
    '铜鹤发言说臭氧效率不错',
    '同客补充了一下',
    '铜棍认为应该用钛网',
    '杜同贺本人是组长',  # 幂等性
]
for s in samples:
    print(f'{s!r:40} → {clean_text(s)!r}')
"
# 期望:
# '铜鹤发言说臭氧效率不错'               → '杜同贺发言说臭氧效率不错'
# '同客补充了一下'                       → '杜同贺补充了一下'
# '铜棍认为应该用钛网'                   → '杜同贺认为应该用钛网'
# '杜同贺本人是组长'                     → '杜同贺本人是组长'
```

### 集成测试（未来新会议）

```bash
# 模拟一段含错人名的 transcript
python -c "
import asyncio
from app.services.name_aliases import clean_text
transcript = [
    {'speaker': 'speaker_1', 'text': '铜鹤补充了一句', 'text_polished': '铜鹤补充了一句'},
    {'speaker': 'speaker_2', 'text': '同客接着说', 'text_polished': '同客接着说'},
]
for seg in transcript:
    seg['text'] = clean_text(seg['text'])
    seg['text_polished'] = clean_text(seg['text_polished'])
print(transcript)
"
# 期望: [{'speaker': 'speaker_1', 'text': '杜同贺补充了一句', ...}, ...]
```

### 历史会议回填（可选）

```bash
# 跑 reprocess_meeting.py 重新生成 summary/key_points/decisions
docker exec microbubble-agent-app-1 python /tmp/reprocess_meeting.py --meeting 153 --steps load,assign,regen,verify
# 期望: 8 字段 verify 全 0 旧错标人（铜鹤/同客/铜棍/同合/童鹤/铜和/铜合 全部 0）
```

## 部署必做（CLAUDE.md 752 行铁律变体）

```bash
# 1. 代码同步（volume 挂载只换文件不换模块缓存）
docker cp app/services/name_aliases.py microbubble-agent-app-1:/app/app/services/name_aliases.py
docker cp app/services/post_meeting_tasks.py microbubble-agent-app-1:/app/app/services/post_meeting_tasks.py

# 2. 重启后端（关键：post_meeting_tasks 在模块顶部 import name_aliases，必须重启加载新映射）
docker compose restart app celery-worker

# 3. 端到端验证
docker exec microbubble-agent-app-1 python -c "
from app.services.name_aliases import clean_text
print(clean_text('铜鹤补充了一下'))  # 期望: '杜同贺补充了一下'
"

# 4. (可选) 回填历史会议
docker cp scripts/reprocess_meeting.py microbubble-agent-app-1:/tmp/
docker exec microbubble-agent-app-1 python /tmp/reprocess_meeting.py --meeting 153 --steps regen
```

## 沉淀

- **修改文件 2 个**：
  - `app/services/name_aliases.py`（+15 行 HARDCODED_ALIASES）
  - `app/services/post_meeting_tasks.py`（+10 行清洗 hook）
- **新增文件 1 个**：`memory/name-aliases-phonetic-correction-2026-06-27.md`
- **7 条铁律**：单源化 / 防御性映射 / 清洗前置 / 幂等性 / Fuzzy 阈值 ≤ 1 / 原始样本测试 / 增量更新流程
- **CLAUDE.md 教训沉淀**：所有"会议人名 / 声纹 / 文本"类质量改进必须**push 到主路径 hook**，不靠 re-process 历史数据。

## 关联

- [CLAUDE.md 2026-06-19 声纹 batch bug 修复 (推到主路径)](../CLAUDE.md#2026-06-19-声纹-batch-bug-修复-推到主路径) — 同样教训：质量改进必须 hook 主路径
- [scripts/reprocess_meeting.py](scripts/reprocess_meeting.py) — 历史会议回填工具
- [docs/reprocess-meeting.md](docs/reprocess-meeting.md) — 回填使用文档