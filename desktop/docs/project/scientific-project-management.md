# Scientific Project Management

## 概述

科研项目管理 — 长生命周期科研项目的统一管理。

## 数据模型

### ResearchProject（项目）

```
id           项目唯一标识
title        项目标题
description 项目描述
domain       研究领域
status       planning / active / paused / completed / archived
createdAt    创建时间
updatedAt    最后修改时间
milestones   里程碑列表
tasks        任务列表
members      参与成员
```

### ResearchMilestone（里程碑）

```
id           里程碑标识
projectId    所属项目
title        里程碑标题
description  描述
status       pending / in-progress / completed / blocked
deadline     截止时间
deliverables 交付物
```

### ProjectTask（任务）

```
id           任务标识
milestoneId  所属里程碑
agentRole    委派的智能体角色
title        任务标题
input        输入
output       输出
status       pending / running / completed / failed / blocked
dependencies 依赖的其他任务 ID
```

## 核心组件

### ProjectManager（project-manager.ts）
- createProject / getProject / updateProject
- addMilestone / addTask / updateTaskStatus
- getProgress（自动计算百分比）
- 防御性拷贝、确定性排序
- 快照支持

### Workflow Engine（workflow-engine.ts）
- 调度科学工作流
- 执行工作流步骤
- 调用 AgentCoordinator
- 返回执行结果与置信度

### Research Event Bus（research-event-bus.ts）
- 强类型事件发射器
- 12 种事件类型
- 订阅/退订
- 事件历史

### Project Templates（project-templates.ts）
- 3 个预定义模板
- 新论文研究
- 现有数据集分析
- 实验条件优化

### Project Agent Adapter（project-agent-adapter.ts）
- 桥接 ProjectManager ↔ AgentCoordinator
- 任务自动派发给智能体
- 依赖检查与执行
- 结果自动回写

## 工作流示例

### 新论文研究流程

```
LiteratureAgent → 检索文献
      ↓
MechanismAgent → 分析机理
      ↓
ExperimentAgent → 实验设计
      ↓
DataAnalysisAgent → 数据分析
      ↓
WritingAgent → 论文撰写
      ↓
ReviewerAgent → 质量审查
```

## 事件流

```
project.created → 创建项目
      ↓
task.started → 任务开始
      ↓
experiment.finished → 实验完成
      ↓
analysis.finished → 分析完成
      ↓
task.completed → 任务完成
      ↓
project.completed → 项目完成
```

## 安全边界

- 所有值使用秘密防护检查（findForbidden）
- 防御性拷贝防止外部修改
- 任务输入必须为字符串类型
- 验证器在导入时检查违规
- 无 API key/secret/token/cipher 泄漏
