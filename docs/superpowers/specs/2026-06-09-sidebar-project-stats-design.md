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

### 2. 已解决痛点（静态配置）

从项目建立至今攻克的技术难题，按分类展示：

| 分类 | 痛点 |
|------|------|
| 幻觉 | Whisper 三层防护、反幻觉七重过滤、低置信度短文本过滤 |
| 部署 | Webhook SSH fallback、Celery 任务丢失修复、ThreadingHTTPServer |
| 安全 | Nginx 扫描器屏蔽（88% 恶意流量）、认证限流、sessionStorage 残留修复 |
| 性能 | 声纹维度 256→192 修正、VAD 精细化、silero-vad 本地缓存 |
| 架构 | 全局录音器单例、WebSocket 闪烁根因定位、async session lazy load |

### 3. 待做事项（静态配置）

未来发展方向：

| Phase | 名称 | 周期 | 优先级 |
|-------|------|------|--------|
| Phase 7 | 多模态知识库 | 4-6 周 | 🔴 高 |
| Phase 8 | 实时语音科研助手 | 6-8 周 | 🟡 中 |
| Phase 9 | 自动化文献综述 | 6-8 周 | 🟡 中 |
| Phase 10 | 智能实验方案生成 | 6-8 周 | 🟡 中 |
| Phase 11 | 深度论文理解 | 4-6 周 | 🔴 高 |
| Phase 12 | 课题组专属 AI 研究员 | 8-12 周 | 🟢 低 |

### 4. 更新日志（静态 JSON）

全历程时间线，每条包含：
- 日期：如 `2026-06-09`
- 标题：如「听会后台录音 + 全局指示器」
- 分类标签：`功能` / `修复` / `优化` / `安全`
- 解决的痛点：简要描述

默认显示最近 5 条，点击「查看完整日志」展开全部（可滚动）。

## UI 设计

### 展开态（220px）— 时间线风格

用时间线的形式展示项目历程，从下往上（最新在上），每个节点是一个里程碑：

```
┌─────────────────────┐
│ 🚀 项目动态         │
│                     │
│ ┌─────────────────┐ │
│ │ 📊 项目体量     │ │
│ │                 │ │
│ │ 📝 20,644 行代码│ │
│ │ 🔀 813 次提交   │ │
│ │ ⏱️ 开发 24 天    │ │
│ │ 📁 440 个文件    │ │
│ └─────────────────┘ │
│                     │
│ ┌─────────────────┐ │
│ │ 🔧 已解决痛点   │ │
│ │                 │ │
│ │ 🎯 幻觉         │ │
│ │   Whisper防护   │ │
│ │   七重过滤      │ │
│ │                 │ │
│ │ 🚀 部署         │ │
│ │   SSH fallback  │ │
│ │   Celery修复    │ │
│ │                 │ │
│ │ 🔒 安全         │ │
│ │   Nginx屏蔽     │ │
│ │   认证限流      │ │
│ │                 │ │
│ │ ⚡ 性能         │ │
│ │   声纹修正      │ │
│ │   VAD精细化     │ │
│ │                 │ │
│ │ 🏗️ 架构         │ │
│ │   录音器单例    │ │
│ │   WS闪烁修复    │ │
│ └─────────────────┘ │
│                     │
│ ┌─────────────────┐ │
│ │ 🔜 待做事项     │ │
│ │                 │ │
│ │ Phase 7  多模态 │ │
│ │ Phase 8  语音   │ │
│ │ Phase 9  文献   │ │
│ │ Phase 10 实验   │ │
│ │ Phase 11 论文   │ │
│ │ Phase 12 AI研究员│ │
│ └─────────────────┘ │
│                     │
│ ┌─────────────────┐ │
│ │ 📅 更新日志     │ │
│ │                 │ │
│ │ 06-09 后台录音  │ │
│ │ 06-08 Webhint   │ │
│ │ 06-06 声纹识别  │ │
│ │ 06-05 知识库    │ │
│ │ 06-04 代码质量  │ │
│ │                 │ │
│ │ 查看全部 →      │ │
│ └─────────────────┘ │
└─────────────────────┘
```

每个卡片用圆角边框 + 浅色背景，图标用 emoji，文字用小号字体。整体风格简洁、有层次感。

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
  "pain_points": [
    { "category": "幻觉", "icon": "🎯", "items": ["Whisper 三层防护", "反幻觉七重过滤", "低置信度短文本过滤"] },
    { "category": "部署", "icon": "🚀", "items": ["Webhook SSH fallback", "Celery 任务丢失修复", "ThreadingHTTPServer"] },
    { "category": "安全", "icon": "🔒", "items": ["Nginx 扫描器屏蔽（88% 恶意流量）", "认证限流", "sessionStorage 残留修复"] },
    { "category": "性能", "icon": "⚡", "items": ["声纹维度 256→192 修正", "VAD 精细化", "silero-vad 本地缓存"] },
    { "category": "架构", "icon": "🏗️", "items": ["全局录音器单例", "WebSocket 闪烁根因定位", "async session lazy load"] }
  ],
  "todos": [
    { "id": 7, "name": "多模态知识库", "cycle": "4-6 周", "priority": "高" },
    { "id": 8, "name": "实时语音科研助手", "cycle": "6-8 周", "priority": "中" },
    { "id": 9, "name": "自动化文献综述", "cycle": "6-8 周", "priority": "中" },
    { "id": 10, "name": "智能实验方案生成", "cycle": "6-8 周", "priority": "中" },
    { "id": 11, "name": "深度论文理解", "cycle": "4-6 周", "priority": "高" },
    { "id": 12, "name": "课题组专属 AI 研究员", "cycle": "8-12 周", "priority": "低" }
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
