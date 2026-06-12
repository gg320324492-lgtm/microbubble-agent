/**
 * 工具→人类友好标签映射
 * 防止技术术语暴露给用户
 */

export const TOOL_LABELS: Record<string, string> = {
  // 任务
  create_task: '创建任务',
  query_tasks: '查询任务',
  query_all_member_tasks: '查询全员任务',
  update_task: '更新任务',
  get_task_stats: '统计任务',

  // 会议
  query_meetings: '查找会议',
  get_meeting_detail: '加载会议详情',
  get_meeting_transcript: '读取会议转录',
  get_recent_meeting_conclusions: '汇总近期会议结论',
  create_meeting: '创建会议',
  analyze_meeting_transcript: '分析会议转录',
  summarize_meeting_transcript: '总结会议转录',

  // 项目
  query_projects: '查询项目',
  get_project_summary: '汇总项目进度',
  generate_project_plan: '生成项目计划',

  // 成员
  query_members: '查找成员',
  get_member_profile: '加载成员资料',

  // 知识
  search_knowledge: '检索知识库',
  explore_knowledge_graph: '浏览知识图谱',
  find_knowledge_gaps: '发现知识空白',
  auto_research: '执行自主研究',
  compare_knowledge: '对比知识',
  summarize_topic: '总结主题',
  suggest_research: '推荐研究方向',
  save_conversation_knowledge: '保存到知识库',

  // 公式 / 假设
  list_formulas: '查找公式',
  list_hypotheses: '查找研究假设',

  // 联网 / 记忆
  web_search: '联网搜索',
  save_memory: '保存记忆',
  search_memory: '搜索记忆',
  forget_memory: '遗忘记忆',

  // 个性化 / 声纹
  set_custom_instructions: '保存偏好设置',
  enroll_voice: '录入声纹',
  submit_feedback: '提交反馈'
}

export function toolLabel(name: string | undefined): string {
  if (!name) return ''
  return TOOL_LABELS[name] || name
}
