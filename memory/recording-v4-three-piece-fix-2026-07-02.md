---
name: recording-v4-three-piece-fix
description: 2026-07-02 听会 v4 三件套修复收官 — drive_files RFC 5987 中文文件名 + useFolderDropZone native getter 静默忽略 + MeetingRoomView AudioRecorder lazy meetingId 丢失 context
metadata:
  type: project
---

# 2026-07-02 听会 v4 三件套修复收官

> **commit**: `2cde346f fix(drive): 中文文件名 RFC 5987 编码 + useFolderDropZone native getter 修复 + MeetingRoomView AudioRecorder 传 meeting-id (听会 v4 三件套)`
> **配套 commit 链**: `38487056` (v2) → `6c297703` (v3) → `7d0daadf` (chunked rate-limit) → `2cde346f` (v4 收官)
> **完整 CHANGELOG.md**: `[Unreleased] 2026-07-02` 第 2 条

## 触发场景

听会录音链路 v1/v2/v3 修复累积后, 用户实测触发 3 个新 bug:

1. **下载中文文件名 PPTX 触发 UnicodeEncodeError 500** (用户实测: "组会ppt/冯懿鑫/2025.7.2 研一 冯懿鑫.pptx")
2. **Firefox 拖拽文件夹层级丢失** (relativePath 全 undefined)
3. **chunked upload 路径录音 meeting context 丢失** (chunked_filename 拼接错误)

## 修复 1: app/api/v1/drive_files.py:build_content_disposition (RFC 5987 + RFC 6266 标准化)

### 历史 bug

```python
# 旧实现 (4 处调用点重复写)
encoded = quote(filename)  # 中文 filename 被 percent-encode
headers["Content-Disposition"] = f"{disposition}; filename=\"{filename}\"; filename*=UTF-8''{encoded}"
#                     ↑ 这部分走 latin-1 codec
#                                       ↑ Starlette/FastAPI 调 latin-1 encode(filename) → UnicodeEncodeError → 500
```

**根因**: `filename="中文.pptx"` 部分走 latin-1 codec (HTTP/1.1 早期 spec), Starlette 内部调 `latin-1 encode(filename)` 失败, 触发 `UnicodeEncodeError`, 整个 endpoint 返 500.

### 修复

```python
def build_content_disposition(disposition: str, filename: str) -> str:
    """构建 Content-Disposition 头 (RFC 5987 + RFC 6266).
    
    仅输出 `filename*=UTF-8''<encoded>` (RFC 5987 标准化形式),
    移除非 ASCII safe 的 `filename="..."` 旧 attribute.
    
    现代浏览器 (Chrome / Firefox / Safari / Edge) 全部支持 filename*,
    老 IE (≤ IE9) 不支持但本项目目标用户无 IE.
    """
    encoded = quote(filename, safe='')
    return f"{disposition}; filename*=UTF-8''{encoded}"
```

**4 处调用点统一**:
- `download_drive_file` (range + 完整)
- `batch_download_drive_files` (zip)
- `public_download_by_token` (range + 完整)

### 教训

- **`filename=` 部分是历史包袱**, 老 IE≤9 才需要, 现代浏览器全支持 `filename*=UTF-8''<encoded>` 标准化形式
- **`quote()` 默认 safe='/'**, 显式 `safe=''` 让 percent-encode 更彻底 (避免 `/` 字符不被 encode 触发路径歧义)
- **统一抽 helper 而不是 4 处 inline**, 未来加新下载端点直接调, 防再次出现 `latin-1 encode` bug

## 修复 2: web/src/composables/useFolderDropZone.js:webkitRelativePath native getter 修复

### 历史 bug

```js
// 旧实现 (Firefox 拖拽场景出错)
entry.file((file) => {
  file.webkitRelativePath = relativePath  // ❌ 错误赋值
  entries.push({ file, relativePath })
  resolve()
}, () => resolve())
```

**根因**: `File.webkitRelativePath` 是 native read-only getter (WebKit/Chrome/Firefox 浏览器实现), 赋值浏览器**静默忽略**, 不报错不警告. 只有 `<input type="file" webkitdirectory>` 选择文件时浏览器自动设置这个字段.

**症状**: Firefox 拖拽文件夹场景, `entry.relativePath` 正确但 `file.webkitRelativePath` 是空字符串, 文件夹层级丢失.

### 修复

```js
// 新实现
entry.file((file) => {
  // ⚠️ 不能给 native File 赋值 webkitRelativePath: 它是 read-only native getter
  //   File 对象的 webkitRelativePath 仅由 `<input webkitdirectory>` 自动设置,
  //   拖拽场景浏览器不会设置. 我们的相对路径直接走 entry.relativePath 字段.
  entries.push({ file, relativePath })
  resolve()
}, () => resolve())
```

**调用方读取**:
```js
// 调用方改用 entries[i].relativePath 而不是 entries[i].file.webkitRelativePath
for (const { file, relativePath } of entries) {
  const path = relativePath || file.name  // 降级: Firefox 拖拽走 f.name
  // ...
}
```

### 教训

- **`File.webkitRelativePath` 只读** — 永远不要赋值, 走自己的 `relativePath` 字段
- **降级路径必须保留** — Firefox 不支持 webkitdirectory 拖拽, `file.name` 兜底 (单文件没有路径层级, 但至少能上传)
- **`entry.relativePath` (来自 webkitGetAsEntry) 才是真相** — entry API 提供的字段, 跨浏览器一致

## 修复 3: web/src/views/MeetingRoomView.vue:AudioRecorder meeting-id 传递

### 历史 bug

```vue
<!-- 旧实现: 只接 ref -->
<AudioRecorder
  ref="recorderRef"
  @recording-start="onRecordingStart"
  @recording-stop="onRecordingStop"
  @audio-ready="onAudioReady"
/>
```

**根因**: AudioRecorder 内部 `lazy meetingId` 是 computed (避免初始 undefined), 不传 prop 时 computed 读不到值. 当 chunked upload 路径触发后, `chunk_filename` 拼接错误, meeting context 丢失.

### 修复

```vue
<!-- 新实现: 显式传 :meeting-id + :meeting-title -->
<AudioRecorder
  ref="recorderRef"
  :meeting-id="meetingId"
  :meeting-title="pageTitle"
  @recording-start="onRecordingStart"
  @recording-stop="onRecordingStop"
  @audio-ready="onAudioReady"
/>
```

### 教训

- **AudioRecorder 子组件 lazy computed 必须显式 prop 触发** — 不能依赖 `ref` 调子方法获取 (太晚)
- **`chunked upload` 路径与单次 upload 路径必须行为一致** — chunk_filename 拼接逻辑必须两个路径都用同样的 meetingId/title
- **4 commit 链修复同一功能**: v1 → v2 (lazy meetingId) → v3 (MeetingRoomView 传 :meeting-id) → rate-limit tier 60/min → v4 (AudioRecorder 显式接 :meeting-title)

## 4 新铁律

1. **`filename=` 部分是 HTTP 早期包袱, 现代项目只用 `filename*=UTF-8''<encoded>`** (RFC 5987 标准化形式, 所有现代浏览器支持)
2. **`File.webkitRelativePath` 是 native read-only getter, 永远不要赋值** — 走自己的 `relativePath` 字段
3. **AudioRecorder 子组件必须显式接 `:meeting-id` + `:meeting-title`** — lazy computed 不会自动响应
4. **chunked upload 路径与单次 upload 路径必须行为一致** — chunk_filename 拼接逻辑共享同一 meetingId/title

## 端到端验证

| 验证项 | 结果 |
|---|---|
| `curl -OJ "https://agent.mnb-lab.cn/api/v1/drive/files/16/download"` 下载中文 PPTX | ✅ 文件名正确 UTF-8 |
| Firefox 拖拽文件夹到 KnowledgeCard | ✅ entries 数组含正确 relativePath |
| chunked upload 录音文件命名 | ✅ `meeting_<id>_<ts>.webm` 正确 |
| build 0 警告 + vitest 全部 PASS + Playwright 全部通过 | ✅ |

## 部署必做

```bash
# 1. 后端代码 sync (volume 挂载自动, 但建议显式)
docker cp app/api/v1/drive_files.py microbubble-agent-app-1:/app/app/api/v1/

# 2. 前端 build
cd web && npm run build

# 3. 重启后端 (CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# 4. 用户硬刷浏览器 (CLAUDE.md 2026-06-13 SW 教训: 必要时 F12 → Service Workers → Unregister)
```

## 不在本次范围 (留给未来)

- **chunked upload resume 实现** — 当前 chunked upload 中断后必须重传全部, 未来加 Range 续传
- **多文件并行上传** — 当前 useChunkedUploader 单文件串行, 未来 batch upload
- **压缩上传** — gzip / zstd 压缩后上传, 节省带宽
- **多设备录音同步** — 多设备同时录音同一会议, cloud merge 合并
- **iOS Safari MediaRecorder mp4 兜底** — 桌面 Chrome 全 webm 支持, iOS Safari 必须 audio/mp4 兜底
