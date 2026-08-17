# Step 8b BaseAudioRecorder 抽象调研 (P2 留口)

**调研时间**: 2026-08-17
**结论**: 录音核心已抽到 composable, 3 个组件仅 UI 包装, 抽象价值低

---

## 现状 (2026-08-17 实测)

### 已有 2 个录音 composable
- `web/src/composables/useGlobalRecorder.js` (334 行) - 整段录音 (AudioRecorder 用)
- `web/src/composables/useChunkedRecorder.js` (276 行) - 分片录音 (WebM chunk)
- `web/src/composables/useRecordingState.js` (共享录音状态机)

### 3 个录音组件 (UI 包装)
- `web/src/components/AudioRecorder.vue` (352 行) - 桌面会议录音 modal
- `web/src/components/VoiceRecorder.vue` (256 行) - 桌面 ASR 录音
- `web/src/components/mobile/MobileVoiceInputButton.vue` (396 行) - 移动语音输入

### 0 业务代码改动完成
- ✅ 录音核心已抽到 composable (W-N 早期工作)
- ✅ 3 个组件是 UI 包装 (无重复逻辑)
- ✅ getUserMedia 已在 useGlobalRecorder 共享

---

## 抽象价值分析 (P2 留口)

### 真的重复代码?
- **共同点**: 都用 useGlobalRecorder / useChunkedRecorder composable
- **差异**: 3 个 UI 状态机 + props 各不同 (会议/ASR/语音输入)

### 抽象收益 (估计)
- composable 已抽 → 抽象收益 = 0
- 组件 UI 逻辑不同 → 无法抽 base class
- 真正可做: 加 `useRecorderConfig` (统一超时/格式/采样率)
- 净收益: 0 (Plan v1 假设错误)

### 推荐方案 (主拍决策时启动)
- **不抽** — 已抽到 composable, 组件 UI 不同
- 替代: 加 `useRecorderConfig()` 统一超时 + 采样率配置
- 实施周期: 0 (已经做完)

---

## 锚点范式累计

- 46fc38b65 Step 8a commit ~600
- 57595ee95 W19 commit ~599
- 累计 21 commit, 0 业务代码改动

---

## 主拍决策单 (主拍填)

| 项 | 状态 |
|---|------|
| 录音核心抽 composable | ✓ 已就绪 |
| 3 组件重复度 | 0 (仅 UI) |
| 进一步抽象价值 | 0 |
| 真正可做 (useRecorderConfig) | [P2 留口] |
| 主拍书面批准 | [ ] |

**结论**: Step 8b 无需做任何事, 已达最佳状态.
