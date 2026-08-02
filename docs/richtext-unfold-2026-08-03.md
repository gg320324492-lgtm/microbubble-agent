# RichContent 默认展开（2026-08-03）

## 问题与修复

`web/src/components/chat/RichContent.vue` 的 summary 折叠按钮会遮挡真实任务数据。现删除手动 toggle 与 summary 按钮，默认直接显示 `.rich-expanded` 内容；仅当协议显式传入 `collapsed_by_default=true` 时通过 `v-show` 隐藏，DOM 仍挂载。

## 验证

- RichContent 定向 Vitest：14/14 PASS
- PWA build：PASS（使用唯一合法 `npm run build`）
- Alembic：单 head `096_add_rag_multimodal_metrics`
- 变更边界：仅 RichContent、其测试和文档沉淀；未改后端、ORM 或 migration

## 回归风险

显式 `collapsed_by_default=true` 后不再提供用户手动展开入口，这是“删除折叠按钮”需求的直接结果。调用方若希望用户可见，应不传该字段或传 false。

## 类 20.144

生命周期/显隐测试复用 `mount(ParentComponent)`；对 `v-show` 同时断言元素 `exists()` 与 `isVisible()`，避免把 DOM 已挂载但隐藏误判成组件未渲染。
