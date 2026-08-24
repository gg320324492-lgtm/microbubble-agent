// Reviewer Agent — 审稿智能体（纯函数）。
import type { AgentTask } from '../../../shared/agents/agent-schema'

export interface ReviewerOutput {
  comments: Array<{ severity: 'low' | 'medium' | 'high'; location: string; comment: string; suggestion: string }>
  overallScore: number
  recommendation: 'accept' | 'minor' | 'major'
  confidence: number
}

export function executeReviewerAgent(task: AgentTask): ReviewerOutput {
  const text = task.input.toLowerCase()

  const comments: ReviewerOutput['comments'] = []

  if (text.includes('proves') || text.includes('证明')) {
    comments.push({
      severity: 'medium', location: '结论', comment: '结论使用"证明"过于绝对',
      suggestion: '建议改为"表明"或"验证"以保持科学审慎'
    })
  }

  if (text.includes('first time') || text.includes('首次')) {
    comments.push({
      severity: 'high', location: '摘要',
      comment: '"首次"表述需要充分文献调研支持',
      suggestion: '建议添加具体对比文献说明新颖性'
    })
  }

  if (text.length < 100) {
    comments.push({
      severity: 'low', location: '全文',
      comment: '内容过短，可能缺乏充分论述',
      suggestion: '建议补充实验细节和讨论深度'
    })
  }

  if (comments.length === 0) {
    comments.push({
      severity: 'low', location: '总体',
      comment: '整体写作质量良好，建议增加更多量化指标',
      suggestion: '建议补充统计数据和误差分析'
    })
  }

  const overallScore = Math.max(0.5, 1 - comments.length * 0.15)
  const highCount = comments.filter(c => c.severity === 'high').length
  const medCount = comments.filter(c => c.severity === 'medium').length
  const recommendation: ReviewerOutput['recommendation'] = highCount > 0 ? 'major' : medCount > 0 ? 'minor' : 'accept'

  return { comments, overallScore, recommendation, confidence: 0.82 }
}
