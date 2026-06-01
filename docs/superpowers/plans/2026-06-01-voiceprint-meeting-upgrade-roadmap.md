# 声纹会议系统升级 — 三波总览 Roadmap

**日期**：2026-06-01
**作者**：Claude (brainstorming 阶段产物)
**范围**：声纹会议系统三波升级的总体规划
**状态**：第一波设计中，第二/第三波待细化

---

## 0. 当前痛点

1. 声纹不可靠 — 3D-Speaker 模型多版本不一致，识别准确率低（**实情**：实时场景未真正启用声纹，见探索报告）
2. 实时转录噪音 — Whisper 幻觉输出"字幕志愿者"等（**实情**：已通过反幻觉参数 + 黑名单部分解决）
3. 转录显示差 — 居中面板但字体小、不自动滚动、临时输出让人眼花
4. 分析延迟 — 挂断后用户看到空白，不知道系统在处理
5. 没有"互动" — 用户只能单向讲话，小气不能实时参与
6. 声纹录入麻烦 — 录入需要单独 API
7. 无法回溯 — 录音内容只出现在转录里，没有完整音频存档

---

## 1. 第一波（核心）— 设计与计划中

**交付物**：让用户**开会中**看到高质量分段转录（AI 润色口语为书面语，关键决策/待办自动高亮），**挂断后**清楚知道系统在做什么、做到哪一步。

**设计规格**：[2026-06-01-voiceprint-meeting-wave1-design.md](../specs/2026-06-01-voiceprint-meeting-wave1-design.md)

### 1.1 功能清单

| 功能 | 优先级 | 状态 |
|---|---|---|
| 转录 AI 润色（异步渐进覆盖） | P0 | 设计中 |
| 智能分段（静音 + LLM 动态边界） | P0 | 设计中 |
| 关键句高亮（决策/待办/风险徽章） | P0 | 设计中 |
| 挂断后处理进度（Redis + WS 推送） | P0 | 设计中 |
| 转录面板字号自适应 | P1 | 设计中 |
| 智能滚动（自动跟随 + 用户打断） | P1 | 设计中 |

### 1.2 新增/修改文件

**后端新建**：
- `app/services/meeting_ai_polish.py` — AI 润色 + 缓存 + 锁
- `app/services/prompts/meeting_polish.py` — 润色 prompt
- `app/services/progress_service.py` — 进度写入 + pub/sub
- `app/services/post_meeting_tasks.py` — Celery 任务
- `app/api/v1/meeting_progress.py` — 进度 WS + REST
- `app/voice/segmenter.py` — 轻量段满检测

**后端修改**：
- `app/api/v1/voice.py` — /live 端点接入润色
- `app/api/v1/meeting.py` — 新增 end-call 端点
- `app/main.py` — 注册新路由

**前端新建**：
- `web/src/components/ProcessingDialog.vue` — 挂断后进度弹窗
- `web/src/composables/useMeetingRoomWS.js` — /live WS 状态机
- `web/src/composables/useMeetingProgress.js` — /progress WS 封装
- `web/src/composables/useTranscript.js` — 转录条目状态机
- `web/src/composables/useAutoScroll.js` — 通用自动滚动

**前端修改**：
- `web/src/components/MeetingRoom.vue` — 全面重写
- `web/src/views/MeetingView.vue` — 拆分 + 挂断后弹窗
- `web/src/views/MeetingDetailView.vue` — 嵌入 ProcessingDialog

### 1.3 数据库

**无新字段**（transcript / speaker_mapping / summary 等 JSON 字段已存在）

**Redis 新增 Key 空间**：
- `polish:{meeting_id}:{segment_hash}` — 缓存润色结果，TTL 24h
- `polish:lock:{meeting_id}` — 防并发锁，TTL 120s
- `progress:{meeting_id}` — 进度 HASH，TTL 1h

### 1.4 验收标准

1. ✅ 实时通话中，原文立即显示，1-3s 后被润色文本覆盖
2. ✅ 关键决策/待办/风险自动高亮
3. ✅ 转录面板字号随条目数量自适应
4. ✅ 用户向上滚动后停止自动滚动
5. ✅ 挂断后 ProcessingDialog 弹出 5 个阶段
6. ✅ 处理完成后 3s 自动跳转到会议详情
7. ✅ 单元测试覆盖率 > 70%

---

## 2. 第二波（增强）— 计划中

**交付物**：让用户能"对话"小气、声纹真正可用、音频可回溯。

### 2.1 功能清单

| 类别 | 功能 | 来源 | 优先级 |
|---|---|---|---|
| **实时 AI 互动** | "请重述刚才 30 秒" | 原始方案 §二.3 | P0 |
| | "中英翻译" 按钮 | 同上 | P0 |
| | "现在总结一下"（阶段性纪要） | 同上 | P0 |
| | "AI 提问"（小气反向提问） | 同上 | P1 |
| | AI 浮窗历史记录持久化 | 同上 | P1 |
| | TTS 朗读 AI 回复（可选） | 隐含需求 | P2 |
| **声纹录入整合** | 通话中检测未录入发言人 → 弹窗"是否录入 XX 声纹？" | §二.4 | P0 |
| | 一边通话一边录入（无需切页） | 同上 | P0 |
| **声纹真正启用** | 重构 /live 端点：接入 `MeetingPipeline.process_audio()` | 技术债 | P0 |
| | 修复 VAD 单例状态污染（每条 WS 独立实例） | 探索报告 §二.5 | P0 |
| | 实时显示 `audio_level`（声波条驱动信号） | §二.1 | P0 |
| **声音质量** | 完整录音存档到 MinIO（`meetings/{id}/audio.opus`） | §四.1 | P0 |
| | 新增 `Meeting.audio_archive_url` 字段（DB 迁移） | §四 | P0 |
| | 管理员"删除录音但保留纪要"功能 | §四.2 | P1 |
| | 静音片段自动跳过（基于 RMS 阈值） | §四.3 | P1 |
| | 多设备登录同会议同步 | §四.4 | P2 |

### 2.2 关键技术决策（待 brainstorming 细化）

- **声纹识别准确度提升** — 是否引入多模型投票？或重训？
- **音频存档格式** — opus 压缩 vs wav 原始？采样率 16k vs 48k？
- **多设备同步策略** — Redis pub/sub 实时同步 vs 状态轮询？
- **AI 主动提问触发条件** — 每 5 分钟？每话题切换？用户手动？

### 2.3 新增/修改文件（预估）

**后端新建**：
- `app/services/voiceprint_live_service.py` — 通话中实时声纹识别
- `app/services/audio_archive_service.py` — MinIO 音频存档
- `app/services/meeting_ai_interactive.py` — 实时 AI 互动（总结/翻译/提问）

**后端修改**：
- `app/api/v1/voice.py` — /live 端点接入 VAD + 声纹
- `app/voice/pipeline.py` — 修复 VAD 实例化（每条 WS 独立）
- `app/models/meeting.py` — 新增 `audio_archive_url` 字段（DB 迁移）

**前端新建**：
- `web/src/components/VoiceprintEnrollDialog.vue` — 声纹录入确认弹窗
- `web/src/components/AIActionPanel.vue` — 实时 AI 互动面板
- `web/src/composables/useAudioLevel.js` — 声波条驱动

**前端修改**：
- `web/src/components/MeetingRoom.vue` — 接入声纹录入 + AI 互动
- `web/src/components/SpeakerStrip.vue`（如已拆分）— 实时声波条

### 2.4 数据库迁移

```sql
ALTER TABLE meetings ADD COLUMN audio_archive_url VARCHAR(500);
ALTER TABLE meetings ADD COLUMN audio_duration_seconds INTEGER;
ALTER TABLE meetings ADD COLUMN audio_archived_at TIMESTAMP;
ALTER TABLE meetings ADD COLUMN audio_size_bytes BIGINT;
```

### 2.5 验收标准

1. ✅ 通话中检测到未录入发言人 → 弹窗"是否录入？"
2. ✅ 一句话内即可完成声纹录入（不切页）
3. ✅ /live 端点真正走 `MeetingPipeline.process_audio()`
4. ✅ 音频存档到 MinIO，路径 `meetings/{id}/audio.opus`
5. ✅ 管理员可"删除录音但保留纪要"
6. ✅ "请重述 30 秒" 按钮 → 拉取 ASR 转录 → LLM 复述
7. ✅ "中英翻译" 按钮 → 中英互译
8. ✅ "现在总结一下" 按钮 → 阶段性纪要

---

## 3. 第三波（高级）— 计划中

**交付物**：跨会议引用、视觉炫酷、隐私/离线兜底。

### 3.1 功能清单

| 类别 | 功能 | 来源 | 优先级 |
|---|---|---|---|
| **声纹库 — 课题组声纹中心** | 每个成员彩色声纹"指纹图"（256 维嵌入可视化） | §五.1 | P0 |
| | 声纹识别置信度历史曲线 | §五.2 | P1 |
| | "声纹认领"：弹窗确认"刚才是李四吗？" | §五.3 | P1 |
| | 跨会议声纹搜索："找李四说过的内容" | §五.4 | P2 |
| | `VoiceprintCard.vue` 声纹画像组件 | §五 | P0 |
| **跨会议关联** | 纪要自动引用历史相关决策 | §三.2 | P0 |
| | 历史决议相似度匹配（pgvector） | 同上 | P0 |
| **会议预设** | 模板：组会/一对一/立项会/自由 | §一.1 | P1 |
| | 自动填充：标题/参会人/默认时长 | 同上 | P1 |
| **会议前提醒** | 钉钉/企业微信推送 5 分钟前提醒 | §一.2 | P1 |
| **通话主屏升级** | 大头像 + 实时声波（像微信通话） | §二.1 | P0 |
| | 发言统计：每人时长/句数/热度条 | 同上 | P1 |
| | 会议小目标列表（议题） | 同上 | P1 |
| | 时间轴跳转（右侧拖动条） | §二.2 | P2 |
| **UX 细节** | 状态指示：连接中/已连接/重新连接/结束 | §六.1 | P0 |
| | 静音后视觉提示 | §六.2 | P1 |
| | 离线缓冲 5s（网络抖动时本地缓冲，重连后补发） | §六.3 | P1 |
| | 移动端横屏会议模式 | §六.4 | P2 |
| **技术债清理** | 废弃 `LiveTranscript.vue` | 第一波标记 | P0 |
| | `voice.py` 拆分（454 行 → 3 文件） | 探索报告 §六.7 | P1 |
| | `MeetingView.vue` 拆分（713 行 → 列表+3 对话框） | 探索报告 §六.7 | P1 |
| | `meeting_service.py` 删除死代码 | 探索报告 §二.6 | P1 |

### 3.2 关键技术决策（待 brainstorming 细化）

- **声纹指纹图可视化** — ECharts 雷达图 / t-SNE 散点 / 自绘 canvas？
- **跨会议相似度阈值** — pgvector cosine distance 多少算"相关"？
- **离线缓冲存储** — IndexedDB？Service Worker？浏览器内存？
- **横屏模式检测** — `screen.orientation.type` 还是 `window.innerWidth > window.innerHeight`？

### 3.3 新增/修改文件（预估）

**后端新建**：
- `app/services/voiceprint_visualization_service.py` — 256 维嵌入降维 + 可视化数据
- `app/services/meeting_link_service.py` — 跨会议相似度匹配
- `app/services/meeting_template_service.py` — 会议预设模板
- `app/services/meeting_reminder_service.py` — 5 分钟前提醒（钉钉/企微）
- `webhook_routes.py` — 腾讯会议录音回调（可选）

**后端修改**：
- `app/models/meeting.py` — 新增 `template_id`、`linked_meeting_ids` 字段
- `app/services/meeting_analysis_service.py` — 输出历史关联

**前端新建**：
- `web/src/components/VoiceprintCard.vue` — 声纹画像卡片
- `web/src/components/VoiceprintGallery.vue` — 声纹库画廊
- `web/src/components/MeetingTemplateSelect.vue` — 会议模板选择
- `web/src/components/TimelineScrubber.vue` — 时间轴跳转
- `web/src/views/MeetingTemplateView.vue` — 模板管理

**前端修改**：
- `web/src/components/MeetingRoom.vue` — 大头像 + 声波 + 议题列表
- `web/src/views/MeetingView.vue` — 集成模板选择
- `web/src/composables/useOfflineBuffer.js` — 离线缓冲

### 3.4 数据库迁移

```sql
-- 会议模板
CREATE TABLE meeting_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    title_template VARCHAR(200),
    default_participants JSON,
    default_duration_minutes INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 跨会议关联
CREATE TABLE meeting_links (
    id SERIAL PRIMARY KEY,
    source_meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
    target_meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
    similarity_score FLOAT,
    link_type VARCHAR(50),  -- 'related' | 'referenced' | 'follow_up'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_meeting_id, target_meeting_id)
);

CREATE INDEX idx_meeting_links_source ON meeting_links(source_meeting_id);
CREATE INDEX idx_meeting_links_target ON meeting_links(target_meeting_id);

-- 声纹可视化（可选）
ALTER TABLE members ADD COLUMN voiceprint_color VARCHAR(7);  -- 十六进制色
ALTER TABLE members ADD COLUMN voiceprint_recognition_history JSON;
```

### 3.5 验收标准

1. ✅ 声纹库画廊展示所有成员彩色指纹图
2. ✅ 跨会议引用：纪要自动包含历史相关决策链接
3. ✅ 会议模板：组会/一对一/立项会/自由，4 种模板可创建会议
4. ✅ 钉钉/企微推送 5 分钟前提醒
5. ✅ 大头像 + 实时声波通话主屏
6. ✅ 状态指示：连接中/已连接/重新连接/结束
7. ✅ 离线缓冲 5s（重连后补发）
8. ✅ LiveTranscript.vue / voice.py / MeetingView.vue 拆分完成

---

## 4. 关键依赖关系

```
第一波（设计中）
    │
    ├──→ 第二波（声纹真正启用需要清理技术债 + DB 迁移）
    │       │
    │       └──→ 第三波（声纹搜索依赖完整音频 + 声纹录入）
    │
    └──→ 第三波（跨会议关联依赖完整 transcript）

第二波（音频存档、声纹录入）
    │
    └──→ 第三波（声纹搜索依赖完整音频）

第二波（实时 AI 互动）
    │
    └──→ 第三波（跨会议关联）
```

---

## 5. 推荐节奏

| 阶段 | 时间 | 主要交付 |
|---|---|---|
| 第一波 | 3-5 天 | AI 润色 + 智能分段 + 关键句高亮 + 进度条 |
| 第二波 | 2-3 周 | 声纹接入 + AI 互动 + 音频存档 |
| 第三波 | 2-3 周 | 声纹库 + 跨会议 + UX 收尾 + 技术债清理 |

---

## 6. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 第一波 LLM 调用增加成本/延迟 | 缓存 + 锁 + `settings.ENABLE_AI_POLISH` 开关 |
| 第二波声纹识别准确度仍低 | 提供"重说一次"按钮 + 声纹认领弹窗兜底 |
| 第二波 MinIO 存储成本 | opus 压缩 + TTL 90 天自动归档 |
| 第三波跨会议相似度匹配慢 | 增量构建 + 缓存 |
| 第三波声纹指纹图渲染性能 | 256 维 → 8 维 PCA 预计算 |

---

## 7. 待细化项

进入每波实施前需重新调用 brainstorming 技能细化：
- 第一波已完成（设计中）
- 第二波待 brainstorming 细化关键决策（声纹准确度/音频格式/多设备同步/AI 提问触发）
- 第三波待 brainstorming 细化关键决策（指纹图可视化/相似度阈值/离线缓冲/横屏检测）

---

**版本**：v1.0
**关联文档**：
- [第一波设计规格](../specs/2026-06-01-voiceprint-meeting-wave1-design.md)
- 第一波实现计划（待 writing-plans 生成）
- 第二波设计规格（待 brainstorming）
- 第三波设计规格（待 brainstorming）
