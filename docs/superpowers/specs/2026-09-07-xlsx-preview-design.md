# XLSX 预览窗口（网盘右栏详情卡）设计规格 — 方案 D「横幅 + 前 8 行速览」

- 日期: 2026-09-07
- 状态: 已获用户口头批准选型与设计，待规格审查
- 选型原型: `docs/superpowers/mockups/2026-09-07-xlsx-preview-4ui.html`（四版 A/B/C/D，用户选定 D）
- 作者: Qoder 协作会话

## 1. 背景与目标

网盘三栏工作台右栏详情卡（`web/src/components/drive/DriveDetailRail.vue`）中，`.xlsx` 目前落入 `office` 兜底分支，只显示「XLSX · 无预览图」虚线占位。本设计为 Excel 文件提供真实数据速览：深青横幅头（图标 + 统计）+ 工作表标签 + 前 8 行单元格表格，全屏可滚动查看更多行。

**非目标（v1 明确不做）**
- 单元格样式/合并单元格还原（只取值）
- `.xls` 老格式（openpyxl 不支持；requirements 无 xlrd/pandas，不为 v1 引入）
- CSV（已有 `text` 分支处理）
- 移动端独立适配（该 rail 仅存在于桌面三栏工作台）
- 编辑/导出

## 2. 选型记录

2026-09-07 出四版原型供用户选择：

| 方案 | 路径 | 结论 |
|------|------|------|
| A 真数据网格 | 前端 SheetJS 解析 | 未选 |
| B 打印分页 | LibreOffice xlsx→PDF→PNG（复用 PPT/DOCX 管线） | 未选 |
| C 深青横幅摘要 | 仅元信息无数据 | 未选 |
| **D 横幅 + 前 8 行速览** | 后端 openpyxl 抽 JSON + 前端表格渲染 | **用户选定** |

选 D 理由（用户确认）：横幅给身份、表格给内容，信息最完整；服务端截断可控大文件成本；无新增前端依赖。

## 3. 后端设计

### 3.1 端点

`GET /api/v1/drive/files/{file_id}/xlsx-preview`（`app/api/v1/drive_files.py` 新增，紧邻现有 `*-pages` 端点）

- 鉴权与权限：`get_current_user` + `DriveService.get_file`，同 `pptx-pages` 模式
- Query 参数：`max_rows`（可选，默认 8，上限 200，非法值取默认）
- 扩展名校验：仅 `.xlsx`；`.xls` 返回 400 `"暂不支持 .xls 老格式，请另存为 .xlsx"`

### 3.2 缓存与状态机

与 `pptx-pages` / `docx-pages` 完全同构：

- 缓存目录：`/app/data/xlsx_preview/{file_id}_{key}/`，`key = md5("v1:" + str(updated_at))[:12]`（文件重新上传后 updated_at 变化 → key 变化 → 自动失效）
- 状态机：`converting`（持锁）→ `ready`（`ready.json`）/ `error`（`error.txt`）
- 并发锁：模块级 `_XLSX_PREVIEW_LOCKS: dict[key, threading.Lock]`，同款释放逻辑
- 转换 worker：`threading.Thread(daemon=True)` 执行 `_xlsx_preview_worker`；MinIO 下载沿用 `await file_service.download_file(...)` 在端点内完成、落 `/tmp/xlsx_src_{file_id}.xlsx` 后传路径（同 docx 模式）

### 3.3 解析规则（worker 内）

- `openpyxl.load_workbook(path, read_only=True)`（openpyxl 3.1.2 已在 requirements.txt:71，`file_parser_service._parse_xlsx` 已验证该模式可行）
- 每个 worksheet 抽取：
  - `name`：sheet 名
  - `total_rows`：`ws.max_row`（read_only 下可能为 None → 存 `null`）
  - `rows`：前 **200 行 × 前 60 列**（`ws.iter_rows(max_row=200, max_col=6, values_only=True)`）
  - 单元格：`None → ""`，其余 `str()` 截断 **24 字符**
  - `truncated`：`total_rows` 未知（null）时一律 `true`（前端按「未读全」提示）；已知时 `total_rows > len(rows)`
- 全部 sheets 一次抽好写入 `ready.json`；**端点按 `max_rows` 参数切片返回**（缓存只有一份 200 行版本（列封顶 60，v2 起），常态 8 行与全屏 200 行共用）
- 响应体：
  - `{"status": "converting"}`
  - `{"status": "ready", "sheets": [{"name", "total_rows", "truncated", "rows": [[...]]}]}`
  - `{"status": "error", "message": "..."}`

### 3.4 错误处理

- 非 xlsx / 无 MinIO 对象 → 400/404（同现有端点行为）
- openpyxl 解析异常（损坏/加密文件）→ `error.txt` → `status: error`
- 前端对以上一律静默回落到现有占位块，不弹错误打断详情卡

## 4. 前端设计（DriveDetailRail.vue 单文件内改动）

### 4.1 类型与舞台

- `previewKind`：在 `office` 判断之前加 `if (e === 'xlsx') return 'excel'`；`xls` 保持 `office` 占位
- `stageHeight`：`excel: 268`
- `coverUrl` watch 的跳过名单 `['doc','docx','pdf']` 扩为 `['doc','docx','pdf','xlsx']`

### 4.2 模板分支（置于 docx/pdf 分支之后、兜底占位之前）

按 mockup 方案 D 结构，类名 `rf-xlsx-*`：

1. 横幅头（深青渐变 `linear-gradient(135deg, #0E766E, #0B655E)`，与音频 C1 同族）：白色表格图标 + `实验数据.xlsx` + 元信息行「N 个工作表 · M 行 · 45.2 KB」
2. 工作表标签行：三个 pill，active 用 `--color-file-excel` 10% 底 + 绿字（超 3 个横向滚动）
3. 表格：**缓存首行作表头**（表头浅灰底加粗），数据行斑马纹、等宽数字、底部 30px 渐隐 mask；常态渲染表头 + 前 8 行数据（与原型 D 一致，共 9 行）
4. 脚注：`仅预览前 8 行 · 全屏查看全部 M 行`（`total_rows` 未知时显示「全屏查看更多」）
5. error 态：分支内渲染现有 `rail-cover-ph` 同款占位（XLSX + 无预览图）

### 4.3 数据流与状态

- 状态：`xlsxStatus('idle'|'loading'|'ready'|'error')`、`xlsxSheets`、`xlsxActive(0)`、`xlsxError`
- 拉取：`startXlsxPoll(fid)` 2s 轮询状态端点（模式同 `startDocxPoll`），发起轮询时即带 `max_rows=200`，ready 后存**完整 200 行** sheets 数据；此后**零二次请求**——常态渲染前 8 行切片、全屏渲染缓存全部行（≤200），由前端切片完成
- 切工作表：`xlsxActive` 切换，表格重新切片渲染（零请求）
- 换文件：watch `file.id + previewKind` 重置全部状态并停轮询（同 docx watch 模式）
- `onBeforeUnmount`：停轮询
- 全屏：复用 `togglePptFull`（`rfStageRef.requestFullscreen`）；全屏 CSS 下表格容器 `overflow-y: auto` 渲染全部行、横幅头保留

### 4.4 样式纪律

- 新增 scoped 样式全部落在 DriveDetailRail.vue `<style scoped>`，前缀 `rf-xlsx-`
- 色值：深青 #0E766E 系与现有 `.rf-audio` 硬编码一致；绿用 `var(--color-file-excel)`；灰阶/圆角/字号全 token
- 不动 `drive-view.css`，不影响其他 previewKind

## 5. 测试计划

**后端 pytest**（`tests/test_xlsx_preview.py`，构造真实 xlsx 字节流 + monkeypatch `file_service.download_file`）：
1. 正常 .xlsx → ready，sheets/rows 内容正确
2. .xls → 400
3. 截断：30 行文件 rows 长度 30 且 `truncated=false`；260 行文件 rows 长度 200 且 `truncated=true`；单元格 >24 字符被截
4. `max_rows=8` 切片正确、默认值 8、上限 200、非法值回默认
5. 缓存命中：同 key 第二次请求不再触发 worker（mock worker 计数）
6. updated_at 变化 → 新 key → 重新解析

**前端**（`npm run dev` + 浏览器实测，按 verification-before-completion 执行）：
1. 点 xlsx 文件 → 横幅 + 表格出现，切换工作表内容联动
2. 全屏 → 长表滚动可见全部缓存行，退出恢复 8 行
3. 上传一个损坏 xlsx（改后缀）→ 回落占位
4. 切换到其他类型文件 → 状态重置无残留请求
5. `npm run build` 通过

## 6. 影响面

- `requirements.txt`：无新增（openpyxl 已有）
- Docker：`/app/data` 挂载与 `pptx_pages` 同目录策略，无需改动
- 其他文件类型预览（image/video/audio/ppt/docx/pdf）：零改动
- 知识库 RAG 入库流程：不触碰
