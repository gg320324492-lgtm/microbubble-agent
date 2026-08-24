# 科研工作区

## 概述

科研工作区 — 集成所有 Phase 8 科学模块的统一界面,涵盖科研智能体、知识库、多智能体协作、实验闭环、数字孪生、设备集成、控制中心、论文生成 8 大模块。

## 数据模型

### ResearchWorkspace

```
ResearchWorkspace
  id            工作区 ID
  projectId     关联项目 ID
  title         工作区标题
  overview      项目总览 (ProjectOverview)
  modules       模块数组 (WorkspaceModule[])
  progress      研究进度 (ResearchProgress)
  activities    活动数组 (WorkspaceActivity[])
  summary       工作区摘要 (WorkspaceSummary)
  createdAt     创建时间
  updatedAt     更新时间
```

### WorkspaceModule

```
WorkspaceModule
  id          模块 ID (agent/knowledge/multi-agent/experiment/twin/device/control/manuscript)
  name        模块名
  category    分类 (AI/Data/Lab/Model/IoT/Ops/Output)
  status      状态: ready | running | paused | completed | failed | disabled
  description 描述
  enabled     是否启用
```

### ProjectOverview

```
ProjectOverview
  projectId    项目 ID
  title        标题
  domain       领域
  description  描述
  status       状态
  createdAt    创建时间
  updatedAt    更新时间
  memberCount  成员数
  taskCount    任务数
```

### ResearchProgress

```
ResearchProgress
  totalTasks / completedTasks          任务进度
  totalExperiments / completedExperiments  实验进度
  totalManuscripts / publishedManuscripts  论文进度
  totalKnowledge / indexedKnowledge      知识进度
  percent                                总体百分比
```

### WorkspaceActivity

```
WorkspaceActivity
  id          ID
  kind        类型: agent | experiment | manuscript | device | twin | knowledge | system
  title       标题
  description 描述
  timestamp   时间戳
  actor       操作者
```

### WorkspaceSummary

```
WorkspaceSummary
  projectId          项目 ID
  totalModules       总模块数
  activeModules      活跃模块数
  recentActivities   近期活动数
  healthScore        健康度 (0..100)
  generatedAt        生成时间
```

## 核心组件

### ResearchWorkspaceService

工作区服务:

- `loadWorkspace(input)` — 加载工作区
- `getWorkspace(id)` / `getProjectSummary(projectId)` — 获取
- `getModuleStatus(workspaceId, moduleId)` — 模块状态
- `getRecentActivities(workspaceId, limit)` — 近期活动
- `appendActivity(workspaceId, activity)` — 追加活动
- DEFAULT_MODULES: 8 个默认模块定义

健康度 = 总体百分比,活跃模块数 = 启用且状态为 ready/running 的模块数。

### Pinia Store (research-workspace.store)

状态: workspace / modules / progress / activities / summary / overview / isLoading / errorMessage

Getters: moduleCount / activeModuleCount / progressPercent / title / projectId

Actions: setWorkspace / clear / updateModuleStatus / appendActivity

### UI 组件

5 个组件 (Chinese UI):

- ResearchProgressCard — 研究进度卡片 (含 4 项分指标)
- ModuleStatusCard — 模块状态卡片
- ActivityTimeline — 活动时间线 (按 kind 分色)
- ProjectSummaryPanel — 项目总览面板
- ResearchMilestonePanel — 研究里程碑面板

### 页面

`ResearchWorkspace.vue` — 集成页面,包含:

1. 项目总览 + 研究进度
2. 8 个模块状态卡片网格
3. 研究里程碑 + 活动时间线 (2 列)

## 集成示例

```ts
import { ResearchWorkspaceService } from './services/workspace/research-workspace.service'

const service = new ResearchWorkspaceService()
const ws = service.loadWorkspace({
  projectId: 'exp-1',
  title: 'O3-MNB 研究',
  domain: '环境科学',
  tasks: { total: 24, completed: 14 },
  experiments: { total: 6, completed: 4 },
  manuscripts: { total: 3, published: 1 },
  knowledge: { total: 80, indexed: 65 }
})
```

## 复用 Phase 8 类型

| 复用源 | 用途 |
|--------|------|
| Phase 8-J2 `ResearchProject` | projectId 来源 |
| Phase 8-K0 `Experiment` | experiments 总数 |
| Phase 8-C `Knowledge` | knowledge 总数 |
| Phase 8-H3 `Manuscript` | manuscripts 总数 |

工作区**仅消费**这些类型, 不修改其契约。

## 安全边界

- 所有数值字段严格有限性检查 (Number.isFinite)
- healthScore / percent 必须 >= 0
- 所有 getter 返回防御性拷贝
- 无 LLM 直连, 无后端调用, 无密钥存储