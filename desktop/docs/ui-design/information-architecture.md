# Scientific Research OS — Information Architecture

## Product Vision

A desktop-first scientific research operating system that unifies literature review, experimental design, data analysis, and manuscript writing into a single intelligent workspace.

## Architecture Overview

```
Scientific Research OS
├── Dashboard (首页)
│   ├── Project overview
│   ├── Progress tracking
│   ├── AI insight cards
│   └── Warning panel
│
├── Research Workspace (项目空间)
│   ├── Project list
│   ├── Session management
│   └── Cross-project search
│
├── AI Research Assistant (AI科研助手)
│   ├── Task history
│   ├── Reasoning workspace
│   ├── Citations & evidence
│   └── Tool results
│
├── Literature Intelligence (文献智能库)
│   ├── PDF library
│   ├── Paper ranking
│   ├── Credibility scoring
│   ├── Evidence extraction
│   └── Citation graph
│
├── Research Design (实验设计)
│   ├── Problem → Hypothesis
│   ├── Variables & groups
│   ├── Evaluation metrics
│   └── Model recommendations
│
├── Data Analysis (数据分析)
│   ├── Data upload
│   ├── Quality analysis
│   ├── Statistics & model fitting
│   ├── Visualization
│   └── Scientific interpretation
│
├── Manuscript Studio (论文助手)
│   ├── Outline planning
│   ├── Section writing
│   ├── Figure captions
│   ├── SCI language review
│   └── Reviewer simulation
│
├── Knowledge Graph (知识图谱)
│   ├── Entity graph
│   ├── Relation mapping
│   └── Cross-document links
│
├── Agent Center (智能体中心)
│   ├── Agent status
│   ├── Task assignment
│   └── Multi-agent orchestration
│
└── Settings (系统设置)
    ├── Model providers
    ├── API keys
    ├── Knowledge storage
    └── User profile
```

## User Workflow

1. **Create project** → Research Workspace
2. **Read literature** → Literature Intelligence → extract evidence
3. **Design experiment** → Research Design → plan variables/groups
4. **Collect data** → Data Analysis → quality + statistics + models
5. **Write paper** → Manuscript Studio → outline → sections → review
6. **Monitor progress** → Dashboard → AI insights → warnings

## Module → Phase 8 Mapping

| UI Module | Phase 8 Module | Data Flow |
|-----------|---------------|-----------|
| Dashboard | All phases | Aggregated status |
| AI Assistant | Phase 8-E/F | ResearchAgent + Memory |
| Literature | Phase 8-C/G | RAG + ScientificReasoning |
| Research Design | Phase 8-H0 | ResearchDesignResult |
| Data Analysis | Phase 8-H1/H2 | ExperimentOptimization + DataAnalysis |
| Manuscript | Phase 8-H3 | Manuscript generation |
| Knowledge Graph | Phase 8-C | Entity graph |
| Agent Center | Phase 8-E | Agent orchestration |

## Data Flow

```
Literature → Knowledge → RAG Context
                              ↓
Research Design → Experiment Plan → Observations
                                         ↓
                              Data Analysis → Statistics/Models
                                         ↓
                              Manuscript → Sections/Figures
                                         ↓
                              Dashboard ← All results
```

## Non-Functional Requirements

- **Offline-first**: All mock data works without backend
- **Chinese UI**: All labels in Chinese
- **Desktop-first**: Optimized for large screens
- **Scientific style**: Not consumer chatbot — research tool aesthetic
