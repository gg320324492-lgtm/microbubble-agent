# MicroBubble Agent - 极简风格版

这是 MicroBubble Agent 的极简主义风格重设计版本，完全独立于原项目。

## 设计理念

- **简洁清晰**：去除多余装饰，突出内容本身
- **留白充足**：呼吸感强，视觉舒适
- **层次分明**：通过间距和分割线区分区域
- **一致性**：统一的设计语言和组件规范
- **可读性**：清晰的字体层级和颜色对比

## 技术栈

- Vue 3 + Composition API
- Vite 8
- Pinia 状态管理
- Vue Router 4
- Element Plus 组件库
- Vitest 测试框架

## 快速开始

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

### 运行测试

```bash
npm run test:unit
```

## 项目结构

```
web-minimal/
├── index.html              # HTML 入口
├── package.json            # 项目配置
├── vite.config.js          # Vite 配置
├── public/                 # 静态资源
│   └── favicon.ico
└── src/
    ├── main.js             # 应用入口
    ├── App.vue             # 根组件
    ├── assets/             # 资源文件
    │   └── variables.css   # 设计系统变量
    ├── layouts/            # 布局组件
    │   └── MainLayout.vue
    ├── router/             # 路由配置
    │   └── index.js
    ├── stores/             # 状态管理
    │   ├── user.js
    │   └── member.js
    ├── utils/              # 工具函数
    │   ├── format.js
    │   └── task.js
    ├── composables/        # 组合式函数
    │   ├── useTask.js
    │   ├── useMeeting.js
    │   ├── useKnowledge.js
    │   └── useNetworkStatus.js
    ├── views/              # 页面视图
    │   ├── Dashboard.vue
    │   ├── TaskView.vue
    │   ├── MeetingView.vue
    │   ├── ChatView.vue
    │   ├── KnowledgeView.vue
    │   ├── MemberView.vue
    │   ├── SettingsView.vue
    │   └── ...
    └── components/         # 组件
        ├── AudioPlayer.vue
        ├── AudioRecorder.vue
        ├── MeetingRoom.vue
        └── ...
```

## 设计规范

### 颜色系统

- 主色调：#1a1a1a（深灰黑色）
- 强调色：#FF7A5C（珊瑚橙）
- 背景色：#fafafa（浅灰白）
- 卡片背景：#ffffff（纯白）

### 字体系统

- 主字体：-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei'
- 基础字号：14px
- 行高：1.6

### 间距系统

- 基础间距：4px
- 常用间距：8px, 12px, 16px, 24px, 32px

### 圆角系统

- 小圆角：8px
- 中圆角：12px
- 大圆角：16px
- 全圆角：9999px

## 页面列表

1. **登录页** - 简洁的登录表单
2. **仪表盘** - 统计卡片 + 快速操作 + 任务列表 + 会议列表
3. **任务管理** - 任务列表 + 筛选 + 创建任务
4. **会议管理** - 日历视图 + 会议列表 + 创建会议
5. **AI 对话** - 消息列表 + 输入框
6. **知识库** - 文档列表 + 搜索 + 上传
7. **成员管理** - 成员卡片列表
8. **项目管理** - 项目卡片列表
9. **长期记忆** - 记忆列表 + 搜索
10. **声纹库** - 声纹卡片 + 录入
11. **设置** - 个人信息 + 安全设置

## 注意事项

- 这是一个独立的前端项目，不依赖原项目的任何代码
- API 接口与原项目保持一致，可以直接连接后端
- 所有组件都使用极简主义风格设计
- 响应式设计，支持移动端、平板和桌面端

## 后续计划

- [ ] 添加暗黑模式支持
- [ ] 添加国际化支持
- [ ] 添加 PWA 支持
- [ ] 优化性能和加载速度
