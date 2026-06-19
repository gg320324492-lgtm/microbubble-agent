# 会议发言人重处理流程（reprocess_meeting.py）

> 沉淀时间：2026-06-19
> 触发场景：会议处理完后，发现某发言人当时没录入声纹 → 全部未识别 (例如 97% 显示"发言人?") → 后续录入了新声纹 → 重跑识别流程

## 适用场景

- 某次会议的 ASR 转录正常，但声纹识别阶段因为某发言人还没录入声纹，导致 90%+ 段落被标"发言人?"
- 后来新录入了几个成员的声纹，希望用最新的声纹库重新识别整场会议
- 老的 key_points / decisions 包含错标的"发言人A/B/C/D"等占位符，需要用真实名字重生成

## 主机端 wrapper（推荐，无需手动 docker cp）

`scripts/run-reprocess.ps1` (PowerShell) 和 `scripts/run-reprocess.bat` (cmd.exe) 封装了所有 docker 编排。

```powershell
# 完整流程（声纹 + DB + 纪要 + verify）
powershell scripts/run-reprocess.ps1 -Meeting 120 -AudioPath "C:\Users\pc\Desktop\实验相关工作安排.m4a"

# 单独 verify（任何时候可跑）
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps verify

# 只重生成纪要（复用 result.json）
powershell scripts/run-reprocess.ps1 -Meeting 120 -Steps regen
```

```cmd
REM cmd.exe 版本
scripts\run-reprocess.bat 120 verify
scripts\run-reprocess.bat 120 regen
scripts\run-reprocess.bat 120 apply "C:\path\to\audio.m4a"
```

## 手动 docker 命令（不推荐，wrapper 已覆盖）

```bash
# 0. 准备：把音频文件复制到容器
docker cp <audio> microbubble-agent-app-1:/tmp/meeting_<id>.m4a

# 1. 一键跑全流程
docker exec -i microbubble-agent-app-1 python /tmp/reprocess_meeting.py --meeting <id> --audio /tmp/meeting_<id>.m4a

# 2. 单步
docker exec -i microbubble-agent-app-1 python /tmp/reprocess_meeting.py --meeting <id> --steps verify
docker exec -i microbubble-agent-app-1 python /tmp/reprocess_meeting.py --meeting <id> --steps regen
```

## 9 步流程

| 步骤 | 作用 | 输入 | 输出 |
|------|------|------|------|
| 1. load | 从 DB 读 transcript | meeting_id | transcript 列表 |
| 2. extract | **并行**提取每段声纹 embedding | transcript + 音频 | 2830/2830 段 embedding |
| 3. cluster | KMeans 自动选 K（silhouette） | embeddings | K 个聚类 |
| 4. vote | 每聚类对已录入成员投票 | embeddings + 已录入声纹 | 聚类→名字映射 |
| 5. assign | 重新分配 transcript.speaker | 聚类 + 名字 | new_speaker[] |
| 6. backup | **文件**备份 8 字段 | 当前 DB 状态 | `/tmp/meeting_<id>_backup_*.json` |
| 7. apply | 写回 DB（5 字段） | new_speaker | transcript/transcript_polished/speaker_mapping/speaker_stats/participants |
| 8. regen | 重生成 summary/key_points/decisions | transcript | LLM 输出 |
| 9. verify | 8 字段全 0 旧错标人 | DB | ✅/❌ 列表 |

## 关键 Bug 修复（沉淀铁律）

### Bug 1: ERes2Net 不支持 batch

`modelscope ERes2Net_aug.py:__extract_feature` 强制 `unsqueeze(0)`，把整个 batch 折叠为单样本。

**症状**：原 `batch_extract_embeddings(batch_size=32)` 把 32 段塞给模型，模型只处理第 1 段 → 89/2830 段有效（其余 31 段返回零向量）

**修法**：ThreadPoolExecutor(8) 并行单条 + 显式 `_load_pipeline()` 预热 + threading.Lock 保护 `pipeline.model` 并发访问

### Bug 2: SQLAlchemy 静默忽略未映射属性

`Meeting` model 没有 `transcript_polished_old_v1` 等列，但旧脚本给 `m.transcript_polished_old_v1 = old_polished` 赋值，SQLAlchemy **静默**忽略，commit 不报错，让"已备份"成为谎言。

**修法**：用**文件**备份到 `/tmp/meeting_<id>_backup_*.json`（时间戳命名，不覆盖）

### Bug 3: verify 误报"人名提及"为"speaker 错标"

key_points/decisions 里 `【王天志】洪辉需在实验后期多帮助他人` —— "洪辉" 是人名提及不是 speaker，但旧 verify 用 `kp ~ '洪辉'` 太宽，会误报。

**修法**：text 字段只看 `【(错标名)】` 前缀，不看正文：

```sql
-- 旧 (误报)
kp ~ '洪辉|赵航佳|^发言人[ABCDE]'

-- 新 (精确)
kp ~ '^【(洪辉|赵航佳|test_\\w+|发言人[ABCDE])】'
```

**纪律**：人名可能在会议正文中被提及（如"通知王天志"），但只有写在【】括号内才算 speaker。

## 关键设计

- **主机端 wrapper**：避免手动 `docker cp` + `docker exec` 两步
- **幂等**：`regen` 复用已有的 `/tmp/reprocess_<id>_result.json`（避免重跑声纹提取）；备份文件含时间戳不覆盖
- **自动依赖**：`--steps apply` 自动加 `load,extract,cluster,vote,assign` 前置；`--steps regen` 只加 `load`
- **可重入**：`--steps verify` 可随时跑，0 旧错标人即通过

## 端到端验证

```bash
# 必跑：8 字段全 0 旧错标人验证
python /tmp/reprocess_meeting.py --meeting <id> --steps verify
# 期望：8 字段全部 ✅
```

## 输出文件

- `/tmp/reprocess_<id>_result.json` — 中间结果（new_speaker、cluster_names、speaker_label_to_name）
- `/tmp/reprocess_<id>_new_transcript.json` — 重建的 transcript
- `/tmp/meeting_<id>_backup_<ts>.json` — apply 前的全量备份
- `/tmp/meeting_<id>_summary_backup_<ts>.json` — regen 前的 summary/key_points/decisions 备份

## 已知限制

- 短段（< 0.6s）无法提 embedding，标"发言人?"是合法状态
- LLM 调用可能 1-2 分钟，需保证 ANTHROPIC_API_KEY 可用
- GPU 推荐（CPU 串行 2830 段要 84 分钟，GPU batch=8 并行 ~30 秒）
