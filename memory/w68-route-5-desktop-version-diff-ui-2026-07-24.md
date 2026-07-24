# W68 第 5 批 #7: Drive 桌面端版本对比 UI

> **锚点范式第 64 守恒** — 在 W68 第 4 批 F-2+ `drive-version-diff` 后端与 `desktop-versions-ui` 桌面版本历史页之上补齐最后一段交互链路。
>
> **边界守恒** — 仅修改 desktop view，并新增 desktop components、desktop composable、e2e 与 memory；未修改后端、模型、迁移、移动端或共享 Drive store。

## 1. 背景

W68 第 4 批已经交付两个独立基础：

1. `app/services/drive_version_diff_service.py` 与 API 路由提供版本 diff；
2. `web/src/views/desktop/DesktopFileVersionsView.vue` 提供 `/drive/file/:id/versions` 桌面版本历史时间线。

两者尚未在桌面端连通。用户只能浏览、下载或恢复历史版本，不能在页面内选择两个版本并查看文本变更或二进制元数据差异。

本批将入口、版本选择、请求状态、diff 渲染和测试闭成一条链：

`版本历史页 → 版本对比 → 选择 from/to → GET diff → unified diff / metadata table`。

## 2. 交付文件

| 文件 | 类型 | 职责 |
|---|---|---|
| `web/src/views/desktop/DesktopFileVersionsView.vue` | 修改 | 顶部增加“版本对比”按钮并挂载弹窗 |
| `web/src/components/desktop/DesktopVersionDiffDialog.vue` | 新增 | 弹窗、from/to 选择、状态编排和关闭动作 |
| `web/src/components/desktop/DesktopVersionDiffViewer.vue` | 新增 | 文本 unified diff 与二进制 metadata 差异渲染 |
| `web/src/composables/useVersionDiffDesktop.ts` | 新增 | API 请求、loading/error/404、结果状态 |
| `web/tests/e2e/desktop_drive_version_diff.spec.js` | 新增 | 打开、换版本、显示 unified diff 三场景 |
| `memory/w68-route-5-desktop-version-diff-ui-2026-07-24.md` | 新增 | 本次设计、验证、风险与铁律沉淀 |

合计：**3 个新增前端实现文件 + 1 个 view 修改 + 1 个 e2e + 1 个 memory = 6 文件**。

## 3. 实现设计

### 3.1 入口与默认版本

仅当版本数不少于 2 时显示“版本对比”按钮，避免把用户带入无法完成的交互。

弹窗打开时按 `version_number` 升序排序，默认选择：

- from：当前最新版本的前一个版本；
- to：当前最新版本。

例如存在 v1/v2/v3 时，默认比较 v2 → v3。选择器互相过滤已选择版本，不允许 from 与 to 相同。

### 3.2 API composable

`useVersionDiffDesktop.ts` 调用：

```text
GET /api/v1/drive/versions/files/{file_id}/diff?from=N&to=M
```

状态分为：

- `loading`：请求中的骨架态；
- `error`：通用错误文字；
- `notFound`：HTTP 404 专属状态；
- `diffResult`：成功响应；
- `clearDiff()`：关闭或重新选择时清理旧结果；
- `requestEpoch`：用户快速切换版本时丢弃过期响应，防止旧请求覆盖新选择。

from/to 使用 `URLSearchParams` 直接拼入 URL，不使用 axios `{ params }`。这是对项目既有“生产 build 下 query 参数曾丢失”经验的复用。

鉴权同时显式携带 `Authorization: Bearer <access_token>`；即使全局 axios interceptor 已配置，独立 composable 仍能在组件测试和局部加载场景下保持契约完整。

### 3.3 文本 diff

后端返回 `unified_diff`，前端不伪造原文预览，而是按真实 unified diff 行前缀解析：

- `---` / `+++`：文件头；
- `@@`：hunk 定位；
- `+`：新增行，success token 高亮；
- `-`：删除行，danger token 高亮；
- 其余：上下文行。

弹窗顶部与主体都使用 FROM/TO 双轨：删除内容只落在 from 列，新增内容只落在 to 列，上下文同步出现在两侧。解析器还兼容后端当前 `lineterm=""` + `"".join(...)` 造成的紧凑响应（`--- v1+++ v2@@ ...`），先恢复结构边界再生成双栏行。

### 3.4 二进制 metadata diff

当 `is_text=false` 时显示三列表格：属性 / from / to。当前覆盖：

- 文件大小；
- 上传者；
- 上传时间；
- 版本备注。

变化后的 to 单元格使用 primary background 标记。若后端因文件过大回退 metadata-only，优先显示 `from_meta.warning` / `to_meta.warning`；普通 PDF、图片、压缩包则解释“不做逐行解析”。

### 3.5 视觉与可访问性

沿用项目主题令牌：

- 主色：`--color-primary` / `--color-primary-bg`；
- 新增：`--color-success` / `--color-success-bg`；
- 删除：`--color-danger` / `--color-danger-bg`；
- 背景和边框全部走 `--color-bg-*` / `--color-border-*`。

签名元素是 `Δ` 版本变化标记与 FROM → TO 版本轨道；其余结构保持克制，不给既有版本历史页增加额外装饰噪声。

为 diff 与 metadata 表设置语义 `role="table"`，错误态设置 `role="alert"`，摘要使用 `aria-live="polite"`，并保留清晰的“关闭”和“重新加载”动作。

## 4. E2E 三场景

`desktop_drive_version_diff.spec.js` 使用 Vitest + Vue Test Utils + mock axios：

1. **打开弹窗**：访问 `/drive/file/99/versions`，点击顶部“版本对比”，断言弹窗与 from/to 控件出现；
2. **选择版本**：从默认 v2→v3 切换到 v1→v3，断言精确请求 URL 与 Authorization header；
3. **显示 diff**：断言 FROM v2 / TO v3、删除行“旧实验结论”和新增行“新实验结论”均渲染并带对应 class。

定向结果：

```text
Test Files  1 passed (1)
Tests       3 passed (3)
```

## 5. 验证记录

已通过：

- `desktop_drive_version_diff.spec.js`：3/3 PASS；
- Stylelint：两个新 desktop component + 修改 view，0 报错；
- `useVersionDiffDesktop.ts` 独立 TypeScript type-check：PASS；
- 两个新 Vue SFC 的 `parse + compileScript + compileTemplate`：PASS；
- `git diff --check`：PASS。

完整 `npm run build` 被主线已有问题阻断：

```text
MobileFileCommentsView.vue: Identifier 'tabsWithCounts' has already been declared
```

该错误位于本任务未修改的 mobile view，遵守 desktop-only / 0 production code 边界未越界修复。失败构建改写的 `web/dist/sw.js` 已恢复，未纳入提交。

原 `desktop_drive_versions.spec.js` 与新测试一起执行时，其 late `vi.doMock('axios')` 在静态 import 后不生效，真实请求返回 `Not authenticated`；新增测试使用 hoisted `vi.mock`，自身 3/3 稳定通过。

## 6. 审计发现

读取必读后端 service 时发现既有阻断：

- `app/services/drive_version_diff_service.py` 导入了 `and_`；
- `compare_versions()` 调用 `select(...)`；
- 文件未导入 `select`。

真实 diff 请求会在进入版本查询时触发 `NameError: select is not defined`。本任务受“仅 desktop 前端、0 production code 改动”约束，未修改后端；已单独报告主指挥，需在部署真实 UI 前补 `from sqlalchemy import and_, select` 并跑后端测试。

## 7. 锚点范式第 64 守恒

本次继续验证“先读契约、后做薄 UI、越界问题单独报告”的协调模式：

1. 必须先读 service/schema/API，不能只根据任务描述猜响应字段；
2. 后端只给 unified diff 时，前端不能假装拥有两份完整原文；
3. desktop-only 增量应收口在 desktop view/component/composable，不污染 mobile 与共享 store；
4. 404 必须与通用错误分态，不能统一显示“加载失败”；
5. query 参数走显式 URL 编码，复用项目已知的生产稳定路径；
6. 构建被范围外基线错误阻断时要保留原始证据、恢复生成物、禁止顺手越界修改；
7. 读取中发现的后端缺陷必须上报，但不得借机突破本任务代码边界；
8. from/to 自动请求必须防过期响应回写，快速切换时以最后一次选择为准。

因此：**锚点范式第 64 守恒，desktop 版本对比链路完成，0 后端/移动端/共享 store 改动，W19 选项 A 维持。**
