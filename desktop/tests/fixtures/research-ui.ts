export const RESEARCH_NAV = [
  ['科研驾驶舱', 'research-dashboard', 'home'],
  ['演示场景', 'research-demo', 'sparkles'],
  ['科研助手', 'research-assistant', 'assistant'],
  ['研究工作区', 'research-project', 'project'],
  ['文献研究', 'research-literature', 'literature'],
  ['实验设计', 'research-experiment', 'experiment'],
  ['数据分析', 'research-data-analysis', 'data'],
  ['SCI写作', 'research-manuscript', 'manuscript'],
  ['知识图谱', 'research-knowledge-graph', 'graph'],
  ['AI研究团队', 'research-agent-center', 'agent'],
  ['实验控制中心', 'research-experiment-control', 'experiment'],
  ['系统设置', 'research-settings', 'settings']
] as const

export const RESEARCH_STATES = [
  ['loading', 'AI 正在分析...'],
  ['empty', '暂无科研数据'],
  ['error', '分析失败，请重试']
] as const

export const RESEARCH_PAGES = [
  ['Dashboard', ['当前科研项目', 'AI 研究活动', '近期科学洞见']],
  ['Assistant', ['研究会话', '研究轨迹', '引用文献']],
  ['ProjectWorkspace', ['项目概览', '文献', '实验', '数据', '模型', '论文']],
  ['Literature', ['文献证据工作区', '相关度', '证据等级', '引用位置']],
  ['Experiment', ['研究假设', '实验变量', 'AI 实验建议']],
  ['DataAnalysis', ['数据分析工作区', '数据质量', '模型拟合', '科学解读']],
  ['Manuscript', ['SCI 论文工作台', '章节结构', '暂无 Reviewer 意见']],
  ['KnowledgeGraph', ['实体列表', '关系详情']],
  ['AgentCenter', ['AI 思考时间线', '智能体协作矩阵', '工具执行可视化']],
  ['Settings', ['模型配置', '知识库管理', '研究者信息', 'API 与密钥']]
] as const
