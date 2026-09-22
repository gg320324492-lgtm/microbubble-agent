// 云端可用状态与引导文案（工单 M2-3c 补充约束②）— 纯函数，集中一处。
//
// ★ 为什么集中：未绑定 / 离线 / 凭据失效的**判定与文案只在此处定义**，
//   组件不得硬编码「绑定」措辞 —— 后续统一登录会把语义切为「未登录」，
//   届时只改本文件即可，无需翻遍组件。

import type { CloudError } from './api-client'

export type CloudUsableState = 'ready' | 'unbound' | 'offline' | 'expired'

/**
 * 云端可用性快照（DL-1 修复核心）。
 *
 * ★ **以认证状态为唯一事实源**：不再维护独立的「绑定状态」存储。
 *   此前 M2-3a 的绑定状态只在「绑定 IPC」里置位，统一登录路径没联动 → 登录了仍显示「未绑定」。
 *   现在由认证态（本地会话 + 该身份是否为云端身份 + 云端令牌是否在）**推导**，无第二份状态。
 *
 * 提供者模式：调用方每次用时取快照，禁止构造期缓存。
 */
export interface CloudAuthSnapshot {
  /** 本地会话有效（含离线宽容：令牌未过期即可） */
  loggedIn: boolean
  /** 当前身份是云端身份（users 行有 cloud_user_id 映射） */
  isCloudIdentity: boolean
  /** 云端 access/refresh 令牌可读（加密存储可解密） */
  hasCloudTokens: boolean
}

/** 由认证快照推导数据源可用状态（纯函数） */
export function cloudUsableStateFromAuth(snap: CloudAuthSnapshot, error?: CloudError): CloudUsableState {
  if (!snap.loggedIn || !snap.isCloudIdentity) return 'unbound'
  // 已登录但云端令牌不可读 → 需重新登录（旧绑定/换机/系统凭据变更）
  if (!snap.hasCloudTokens) return 'expired'
  if (error && (error.kind === 'network' || error.kind === 'timeout')) return 'offline'
  return 'ready'
}

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

/**
 * @deprecated DL-1：改为 cloudUsableStateFromAuth（以认证态为唯一事实源）。
 * 保留仅为兼容既有调用点，新代码不要再用。
 */
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
      // M2-3a+：统一登录后语义为「未登录」（不再有「绑定」这一动作）
      return {
        state,
        title: `需登录课题组账号才能使用${what}`,
        hint: `${what}数据保存在课题组服务器上。请到「设置 · 账号」登录你的课题组账号。`,
        canOpenSettings: true,
        actionLabel: '前往设置 · 账号'
      }
    case 'expired':
      return {
        state,
        title: '登录状态已失效',
        hint: '请到「设置 · 账号」重新登录。',
        canOpenSettings: true,
        actionLabel: '前往设置 · 账号'
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
