// 云端可用状态与引导文案（工单 M2-3c 补充约束②）— 纯函数，集中一处。
//
// ★ 为什么集中：未绑定 / 离线 / 凭据失效的**判定与文案只在此处定义**，
//   组件不得硬编码「绑定」措辞 —— 后续统一登录会把语义切为「未登录」，
//   届时只改本文件即可，无需翻遍组件。

import type { CloudError } from './api-client'

export type CloudUsableState = 'ready' | 'unbound' | 'offline' | 'expired'

export interface CloudGuidance {
  state: CloudUsableState
  /** 面向用户的中性标题（空串 = 可用，无需引导） */
  title: string
  hint: string
  /** 是否应给出「前往设置」入口 */
  canOpenSettings: boolean
  /** 动作按钮文案（由本模块统一给出，组件不硬编码） */
  actionLabel: string
}

/** 由绑定状态 + 最近错误推断可用状态（纯函数） */
export function cloudUsableState(binding: { status: string }, error?: CloudError): CloudUsableState {
  if (binding.status === 'unbound') return 'unbound'
  if (binding.status === 'expired') return 'expired'
  if (error && (error.kind === 'network' || error.kind === 'timeout')) return 'offline'
  return 'ready'
}

/**
 * 引导文案（集中定义）。
 * @param feature 功能名（如「知识库」「网盘」），仅用于拼句子，不改变语义
 */
export function cloudGuidance(state: CloudUsableState, feature = ''): CloudGuidance {
  const what = feature ? `${feature}` : '此功能'
  switch (state) {
    case 'unbound':
      return {
        state,
        title: `需连接云端才能使用${what}`,
        hint: `${what}数据保存在课题组服务器上。请到「设置 · 云端连接」登录你的课题组账号。`,
        canOpenSettings: true,
        actionLabel: '前往设置 · 云端连接'
      }
    case 'expired':
      return {
        state,
        title: '云端登录状态已失效',
        hint: '请到「设置 · 云端连接」重新登录账号。',
        canOpenSettings: true,
        actionLabel: '前往设置 · 云端连接'
      }
    case 'offline':
      return {
        state,
        title: '当前离线',
        hint: `${what}需要联网访问。请检查网络后重试。`,
        canOpenSettings: false,
        actionLabel: ''
      }
    case 'ready':
      return { state, title: '', hint: '', canOpenSettings: false, actionLabel: '' }
  }
}

/** 不可见 / 无权限的中性文案（不暴露服务端原文与资源 id） */
export function inaccessibleMessage(): string {
  return '这条内容你没有查看权限。如需访问，请联系课题组管理员。'
}

/** 统一把服务端错误转成用户可见文案（403 走不可见中性文案，其余沿用归一化文案） */
export function featureErrorMessage(error: CloudError): string {
  if (error.kind === 'auth' && /403|forbidden/i.test(error.detail ?? '')) return inaccessibleMessage()
  if (error.kind === 'client' && /403|forbidden/i.test(error.detail ?? '')) return inaccessibleMessage()
  return error.message
}
