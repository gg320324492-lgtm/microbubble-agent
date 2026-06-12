/**
 * Rich Block 组件注册表
 *
 * 新增 type 只需：1) import 组件 2) 加到 REGISTRY
 */

import type { Component } from 'vue'
import MeetingCard from './MeetingCard.vue'
import TaskListBlock from './TaskListBlock.vue'
import KnowledgeRefBlock from './KnowledgeRefBlock.vue'
import MemberCardBlock from './MemberCardBlock.vue'
import FormulaBlock from './FormulaBlock.vue'
import HypothesisBlock from './HypothesisBlock.vue'
import ProjectSummaryBlock from './ProjectSummaryBlock.vue'
import TranscriptBlock from './TranscriptBlock.vue'
import ChartBlock from './ChartBlock.vue'
import TableBlock from './TableBlock.vue' // PR #3 新增
import FallbackBlock from './FallbackBlock.vue'

const REGISTRY: Record<string, Component> = {
  meeting: MeetingCard,
  task_list: TaskListBlock,
  knowledge_ref: KnowledgeRefBlock,
  member: MemberCardBlock,
  formula: FormulaBlock,
  hypothesis: HypothesisBlock,
  project: ProjectSummaryBlock,
  transcript: TranscriptBlock,
  chart: ChartBlock,
  table: TableBlock, // PR #3 新增
  fallback: FallbackBlock
}

export function resolveBlock(type: string): Component {
  return REGISTRY[type] || REGISTRY.fallback
}

export function registerBlock(type: string, component: Component) {
  REGISTRY[type] = component
}
