# 侧边栏项目动态组件设计

> 日期: 2026-06-09
> 状态: 已批准

## 目标

在主页面左侧边栏底部（"个人设置"下方空白区域）添加一个「项目动态」组件，展示项目从建立至今的全历程开发信息。

## 展示内容

### 1. 项目体量指标（动态，后端 API）

| 指标 | 说明 |
|------|------|
| 代码总行数 | Python + Vue + JS + CSS 等所有源码行数 |
| Git 提交总数 | 从首次 commit 至今 |
| 开发天数 | 从首次 commit 到今天的天数 |
| 文件总数 | 项目中的源码文件数量 |

### 2. 开发阶段进度（静态配置）

统一展示 Phase 1-12 全部阶段，已完成的显示 ✅ + 100%，进行中的显示进度条，规划中的显示 🔜。

| 阶段 | 名称 | 状态 |
|------|------|------|
| Phase 1 | 基础框架搭建 | ✅ 100% |
| Phase 2 | Agent 对话系统 | ✅ 100% |
| Phase 3 | 会议管理系统 | ✅ 100% |
| Phase 4 | 知识库系统 | ✅ 100% |
| Phase 5 | 声纹识别系统 | ✅ 100% |
| Phase 6 | 代码质量升级 | ✅ 100% |
| Phase 7 | 多模态识别 | 🔜 规划中 |
| Phase 8 | 实时语音对话 | 🔜 规划中 |
| Phase 9 | 文献检索解析 | 🔜 规划中 |
| Phase 10 | 实验数据管理 | 🔜 规划中 |
| Phase 11 | 论文写作辅助 | 🔜 规划中 |
| Phase 12 | AI 自主研究 | 🔜 规划中 |

### 3. 已解决痛点（静态配置）

从项目建立至今攻克的技术难题总数 + 分类标签（幻觉/部署/性能/安全等）。

### 4. 更新日志（静态 JSON）

全历程时间线，每条包含：
- 日期：如 `2026-06-09`
- 标题：如「听会后台录音 + 全局指示器」
- 分类标签：`功能` / `修复` / `优化` / `安全`
- 解决的痛点：简要描述

默认显示最近 5 条，点击「查看完整日志」展开全部（可滚动）。

## UI 设计

### 展开态（220px）

```
┌─────────────────────┐
│ 🚀 项目动态         │
│                     │
│ 12,847 行代码       │
│ 186 次提交          │
│ 开发 45 天           │
│ 230 个文件           │
│                     │
│ 开发阶段：          │
│ ✅ Phase 1-6 已完成  │
│ 🔜 Phase 7 多模态   │
│ 🔜 Phase 8 语音对话 │
│ 🔜 Phase 9 文献检索 │
│ ...                 │
│                     │
│ 已解决 12 个痛点    │
│                     │
│ 最近更新：          │
│ • 06-09 后台录音    │
│ • 06-08 Webhint优化 │
│ • 06-06 声纹识别    │
│ • 06-05 知识库升级  │
│ • 06-04 代码质量    │
│                     │
│ 查看完整日志 →      │
└─────────────────────┘
```

### 折叠态（64px）

仅显示一个小图标（🚀），hover 时 tooltip 提示"项目动态"。

## 文件结构

```
web/src/
├── components/
│   └── SidebarProjectStats.vue    # 新组件
├── data/
│   └── changelog.json             # 静态更新日志数据
└── layouts/
    └── MainLayout.vue             # 修改：在侧边栏底部引入组件

app/api/v1/
└── dashboard.py                   # 修改：新增 project-stats 端点
```

## 后端 API

### GET /api/v1/dashboard/project-stats

返回项目开发层面的客观统计数据。

**响应**:
```json
{
  "total_lines": 12847,
  "total_commits": 186,
  "dev_days": 45,
  "total_files": 230
}
```

**实现方式**:
- `total_lines`: 遍历项目源码文件，统计行数（排除 node_modules、dist、.git 等）
- `total_commits`: `git rev-list --count HEAD`
- `dev_days`: `(today - first_commit_date).days`
- `total_files`: 遍历源码文件计数

**缓存策略**: 结果缓存 1 小时（Redis），避免每次请求都执行 git 命令。

## 静态数据文件

### changelog.json

从 ROADMAP.md 提取全历程数据，结构如下：

```json
{
  "phases": [
    { "id": 1, "name": "基础框架搭建", "status": "done", "progress": 100 },
    { "id": 2, "name": "Agent 对话系统", "status": "done", "progress": 100 },
    { "id": 3, "name": "会议管理系统", "status": "done", "progress": 100 },
    { "id": 4, "name": "知识库系统", "status": "done", "progress": 100 },
    { "id": 5, "name": "声纹识别系统", "status": "done", "progress": 100 },
    { "id": 6, "name": "代码质量升级", "status": "done", "progress": 100 },
    { "id": 7, "name": "多模态识别", "status": "planned" },
    { "id": 8, "name": "实时语音对话", "status": "planned" },
    { "id": 9, "name": "文献检索解析", "status": "planned" },
    { "id": 10, "name": "实验数据管理", "status": "planned" },
    { "id": 11, "name": "论文写作辅助", "status": "planned" },
    { "id": 12, "name": "AI 自主研究", "status": "planned" }
  ],
  "pain_points": [
    { "category": "幻觉", "count": 3, "examples": ["Whisper 三层防护", "反幻觉七重过滤"] },
    { "category": "部署", "count": 4, "examples": ["Webhook SSH fallback", "Celery 任务丢失"] },
    { "category": "安全", "count": 2, "examples": ["Nginx 扫描器屏蔽", "认证限流"] },
    { "category": "性能", "count": 3, "examples": ["声纹维度修正", "VAD 精细化"] }
  ],
  "changelog": [
    {
      "date": "2026-06-09",
      "title": "听会后台录音 + 全局指示器",
      "tag": "功能",
      "pain_point": "导航离开录音中断"
    },
    {
      "date": "2026-06-09",
      "title": "Webhook 自动部署修复",
      "tag": "修复",
      "pain_point": "扫描器正则误杀 /webhook"
    }
    // ... 更多条目
  ]
}
```

## 组件交互

1. **加载**: 组件挂载时并行请求后端 API + 读取本地 JSON
2. **骨架屏**: 数据加载前显示简化骨架
3. **折叠/展开**: 跟随侧边栏折叠状态，展开态显示完整内容，折叠态仅显示图标
4. **查看完整日志**: 点击后展开/滚动显示全部 changelog 条目
5. **响应式**: 移动端不显示（侧边栏本身在移动端不渲染）

## 样式规范

遵循现有设计令牌（`variables.css`）：
- 圆角: `--radius-lg`
- 阴影: `--shadow-sm`
- 字体: `--font-size-xs` ~ `--font-size-sm`
- 颜色: `--color-text-secondary` / `--color-text-placeholder`
- 动画: `--duration-normal` + `--ease-out`
- 卡片背景: `var(--color-bg-card)`
- 与侧边栏菜单保持视觉一致性
