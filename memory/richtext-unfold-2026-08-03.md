# RichText Unfold closure（2026-08-03）

- 分支：`chore/richtext-unfold`
- 锚点：`[W100 +48]`
- 根因：RichContent wrapper 的交互式 summary 按钮可使真实 block 长期处于隐藏态，用户误以为回复无内容。
- 修复：删除 `isExpanded`、`hasUserToggled`、`toggle`、summary 自动生成、折叠按钮及相关 CSS；保留 `collapsed_by_default === true` 的 `v-show` 协议兼容。
- 测试：新增默认缺失、false、true 三个边界；定向套件 14/14 PASS。
- 构建：`npm run build` PASS。
- 数据库：Alembic 单 head `096_add_rag_multimodal_metrics`。
- 边界：未改 `app/`、`alembic/versions/` 或后端生产代码。
- 类 20.144：显隐 lifecycle 测试应通过父组件 mount，并区分 DOM 存在与视觉可见。
