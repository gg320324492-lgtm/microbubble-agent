// Demo Research Project Fixture — Phase 8-M0-G
// 演示模式专用 fixture 数据, 与真实业务 Store 完全隔离.
// 主题: 臭氧微纳米气泡强化四环素降解研究.

export type ResearchStage = 'planning' | 'literature' | 'experiment' | 'analysis' | 'writing' | 'submitted'

export interface DemoExperimentStep {
  id: string
  name: string
  status: 'completed' | 'in-progress' | 'planned'
  startDate: string
  endDate?: string
}

export interface DemoExperimentGroup {
  id: string
  name: string
  replicates: number
  description: string
}

export interface DemoManuscriptInfo {
  title: string
  targetJournal: string
  wordCount: number
  sectionCount: number
  figureCount: number
  stage: ResearchStage
}

export interface DemoResearchProject {
  name: string
  domain: string
  description: string
  stage: ResearchStage
  progressPercent: number
  objectives: string[]
  experiments: DemoExperimentStep[]
  groups: DemoExperimentGroup[]
  manuscript: DemoManuscriptInfo
  warningLabel: string
}

export const DEMO_PROJECT: DemoResearchProject = {
  name: 'O₃-MNBs 强化四环素降解研究',
  domain: '环境科学 · 微纳米气泡',
  description: '探索微纳米气泡臭氧技术对四环素类抗生素的降解效率与机理, 建立动力学模型与放大规律。',
  stage: 'analysis',
  progressPercent: 68,
  objectives: [
    '建立 O₃-MNBs 体系降解四环素的最优工艺参数',
    '阐明·OH 直接/间接氧化贡献占比',
    '识别关键变量 (曝气量 / pH / 初始浓度 / 气泡粒径) 的相对重要性',
    '拟合一级与零级动力学模型并比较',
    '完成 SCI 论文撰写并投递至《Chemical Engineering Journal》'
  ],
  experiments: [
    { id: 'exp-lit-review', name: '文献综述与方案设计', status: 'completed', startDate: '2026-02-01', endDate: '2026-03-15' },
    { id: 'exp-design', name: '实验方案与变量筛选', status: 'completed', startDate: '2026-03-16', endDate: '2026-04-10' },
    { id: 'exp-bench', name: '微纳米气泡装置搭建与稳定性测试', status: 'completed', startDate: '2026-04-11', endDate: '2026-05-20' },
    { id: 'exp-batch-1', name: '第一轮批量降解实验', status: 'completed', startDate: '2026-05-21', endDate: '2026-06-25' },
    { id: 'exp-batch-2', name: '第二轮验证实验与重复性', status: 'in-progress', startDate: '2026-06-26' },
    { id: 'exp-analysis', name: '数据分析与动力学拟合', status: 'planned', startDate: '2026-07-15' },
    { id: 'exp-writing', name: '论文撰写与投稿', status: 'planned', startDate: '2026-08-15' }
  ],
  groups: [
    { id: 'g-control', name: '对照组 (纯 O₃)', replicates: 3, description: '常规臭氧化对照, 验证微纳米气泡增益' },
    { id: 'g-mnb-50', name: 'MNBs 50 mg/L', replicates: 3, description: '低浓度微纳米气泡体系' },
    { id: 'g-mnb-100', name: 'MNBs 100 mg/L', replicates: 3, description: '中浓度实验组, 量产放大预研' },
    { id: 'g-mnb-200', name: 'MNBs 200 mg/L', replicates: 3, description: '高浓度极限工况测试' },
    { id: 'g-ph-7', name: 'pH 7 中性条件', replicates: 3, description: '考察 pH 中性对·OH 生成的抑制' },
    { id: 'g-ph-9', name: 'pH 9 碱性条件', replicates: 3, description: '碱性促进·OH 生成' }
  ],
  manuscript: {
    title: 'Ozone micro-nano bubble enhanced tetracycline degradation: Kinetics and mechanism',
    targetJournal: 'Chemical Engineering Journal',
    wordCount: 8420,
    sectionCount: 7,
    figureCount: 6,
    stage: 'writing'
  },
  warningLabel: '演示数据 · 非真实实验结果'
}

export const DEMO_PROJECT_ID = 'demo-o3-mnbs-tc'
