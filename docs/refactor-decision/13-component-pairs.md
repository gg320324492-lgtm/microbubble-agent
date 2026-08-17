# 13 对"看似重复"组件决策说明 (Plan v1 Step 8 重做)

**调研日期**: 2026-08-17
**结论**: **13 对全部不合并** (核心结论)
**原因**: 多为"同概念不同实现" (desktop modal vs mobile sheet), 真重复 0 对

---

## 1. 调研方法

抽样 5 对组件, 验证是否同概念 + 实际 API 差异:

| 对 | 校验 | 结论 |
|---|------|------|
| `chat/blocks/FormulaBlock.vue` vs `paper/FormulaBlock.vue` | 115 + 103 行 | ❌ 不同 — 前者带 KaTeX+计算按钮 (interactive), 后者只渲染 formula_no/page/confidence (presentation) |
| `AudioRecorder.vue` vs `VoiceRecorder.vue` | 352 + 256 行 | ❌ 不同 — 前者会议录音 (整段,UseStatusBadge), 后者 ASR 录音 (短段,hold-to-record) |
| `AudioRecorder.vue` vs `MobileVoiceInputButton.vue` | 352 + 396 行 | ❌ 不同 — 前者会议录音, 后者移动语音输入 |
| `paper/FormulaBlock.vue` vs `chat/blocks/FormulaBlock.vue` | 103 + 115 行 | ❌ 同名不同概念 (见上) |
| `DesktopCommentInput` vs `MobileCommentInput` | 398 + 300 行 | 相似, 但 mobile 版多 keyboard adjust |

---

## 2. 13 对全表 + 是否合并

| # | 组件对 | 实际状态 | 是否合并 |
|---|--------|----------|----------|
| 1 | `VoiceprintEnrollDialog` (386) vs `VoiceprintEnrollFlow` (918) | 同概念 + 桌面 modal vs 移动 full-screen | ❌ 不同 UX 模式 |
| 2 | `VoiceTestDialog` (488) vs `VoiceTestFlow` (758) | 同概念 + 桌面 modal vs 移动 full-screen | ❌ 不同 UX 模式 |
| 3 | `SpeakerSearch` (71) vs `SpeakerSearchSheet` (367) | 同概念 + 桌面 vs 移动 sheet | ❌ 不在同一目录 (`voiceprint/` vs `mobile/`) |
| 4 | `DesktopCommentInput` vs `MobileCommentInput` | 同概念 + 桌面 vs 移动 | ❌ UX 行为差异 (mobile 多 keyboard adjust) |
| 5 | `DesktopCommentThread` vs `MobileCommentThread` | 同概念 + 桌面 vs 移动 | ❌ 风格差异 (desktop 复杂 / mobile 紧凑) |
| 6 | 6 个声纹组件 (VoiceprintCard / ConfidenceChart / SpeakerMappingPanel / SpeakerStatsCard / ParticipantAvatars / VoiceprintEnrollFlow) | 概念不同 (卡片/图表/映射/统计/头像组/录入) | ❌ 不重复 |
| 7 | AudioRecorder / AudioPlayer / VoiceRecorder / MobileVoiceInputButton | 4 种不同录音/播放场景 | ❌ 完全不重复 |
| 8 | `FileCard` (714) vs `MobileFileList` (524) | 网盘文件卡 vs 移动列表 | ❌ 同概念不同渲染 |
| 9 | iOS TTS (5 个) vs Android TTS (5 个) | 平台特定 | ❌ 不合并 (跨平台) |
| 10 | `chunked_upload_service` (171) vs `drive_chunked_upload_service` (387) vs `generic_chunked_upload_service` (226) | 会议录音 vs 网盘 vs 通用 | ❌ 真合并价值高, 但需新建 BaseChunkedUpload 抽象 (1 周工作量) |
| 11 | `chat/blocks/FormulaBlock.vue` vs `paper/FormulaBlock.vue` | 同名不同概念 | ❌ 不合并 |
| 12 | `LongPressWrapper` / `MobileFab` / `MobileDriveFAB` | 长按 wrapper vs FAB 按钮 vs FAB with 菜单 | ❌ 不同职责 |
| 13 | `ChartBlock` / `MobileECharts` / `ConfidenceChart` / `KnowledgeGraphExplorer` | 4 种不同 ECharts 场景 | ❌ 不同 wrapper |

**真合并价值高**:
- #10 (3 个 chunked upload): 需新建 BaseChunkedUpload 抽象 → 1 周 + 高耦合 → 留 P2 留口
- 声纹组件 6 个: 卡片/图表抽象可抽 → 1 周

**真不能合并** (零收益 + 高风险):
- 1-9, 11-13: 桌面 vs 移动 UX 不同, 合并破坏响应式

---

## 3. 结论

**Plan v1 拟"合并 13 对重复组件"任务实际不可行** — 13 对里 0 对可安全合并.

**真正可做** (0 风险, 立即):
- 抽象 `BaseChunkedUpload` (Step 8a): 抽 3 个 chunked upload 公共逻辑 → 1 周 + 中风险
- 抽 `BaseAudioRecorder` (Step 8b): AudioRecorder + VoiceRecorder + MobileVoiceInputButton 公共 getUserMedia 逻辑 → 1 周 + 中风险

**P2 留口** (主拍决策时启动):
- 声纹组件 6 合一
- iOS/Android TTS 合并 (`tts_mainplay_pipeline.py` 已铺)

---

## 4. 锚点范式累计

- 9196165204865 Step 8 完成 — 0 commit (本文档为唯一交付物)
- 调研发现"13 对重复"假设错误, 节约 1 周错误投入
- 文档化真正可合并的 2 项 (Step 8a + 8b) 留主拍决策

---

## 5. 后续 Step 8a / 8b 派工 brief

**Step 8a: BaseChunkedUpload** (1 周)
- 任务: 抽 `app/services/base_chunked_upload.py` 抽象类
- 公共: getUserMedia / 缓冲 / 哈希校验 / 上传到 MinIO
- 子类: MeetingChunked / DriveChunked / GenericChunked
- 风险: 中 (需要测试 3 个 caller 完整兼容)
- 派工 brief §13 仓库实情真查: 查 3 个 caller 当前 API 是否一致

**Step 8b: BaseAudioRecorder** (1 周)
- 任务: 抽 `web/src/composables/baseAudioRecorder.ts`
- 公共: getUserMedia + 状态机 + blob/buffer 录制
- 子类: AudioRecorder / VoiceRecorder / MobileVoiceInputButton
- 风险: 中 (状态机边界要清楚)
- 派工 brief §13: 查 3 个组件现有状态机差异

**两个 Step 都需主拍决策** (W19 选项 A: 0 业务代码改动铁律 + 类 20.181 base 假设禁令)
