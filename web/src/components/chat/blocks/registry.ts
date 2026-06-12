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
import FallbackBlock from './FallbackBlock.vue'

const REGISTRY: Record<string, Component> = {
  meeting: MeetingCard,
  task_list: TaskListBlock,
  knowledge_ref: KnowledgeRefBlock,
  member: MemberCardBlock,
  fallback: FallbackBlock
}

export function resolveBlock(type: string): Component {
  return REGISTRY[type] || REGISTRY.fallback
}

export function registerBlock(type: string, component: Component) {
  REGISTRY[type] = component
}
