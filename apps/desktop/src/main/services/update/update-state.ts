// 更新状态机（M6-1）— 纯逻辑，零 Electron 依赖，离线可单测。
//
// 状态流转表（from --event--> to）：
//   idle        --check-start-->            checking
//   checking    --check-available(v)-->     available(v)
//   checking    --check-none-->             idle（记录 checkedAt）
//   checking    --check-error(m)-->         error(m)
//   available   --check-start-->            checking
//   available   --download-start-->         downloading(0)
//   downloading --download-progress(p)-->   downloading(clamp 0..100)
//   downloading --download-done-->          ready
//   downloading --download-error(m)-->      error(m)
//   ready       --check-start-->            ready（忽略：避免丢弃已下载包）
//   ready       --download-start-->         ready（忽略）
//   error       --check-start-->            checking
//   error       --download-start-->         error（忽略：无可用包）
//   任意        --reset-->                  idle
//   任意        --set-disabled(true)-->     idle（清空版本/进度/错误）
//   disabled    --check-start-->            idle（禁用态不发起检查）
//
// 禁用态（disabled=true）来自环境不支持（非打包且无 feed 覆盖）；由服务层计算后下发。
// 设置项「自动检查更新」关闭只拦截"启动自动检查"这一次触发，不进入禁用态——否则设置页
// 的手动「检查更新」会变成死按钮。

import type { UpdateState, UpdateStatus } from '@shared/types'

// 对外状态形状以 @shared/types 为唯一事实来源（渲染进程按同一形状消费）
export type { UpdateState, UpdateStatus }

export type UpdateEvent =
  | { type: 'check-start' }
  | { type: 'check-available'; version: string }
  | { type: 'check-none' }
  | { type: 'check-error'; message: string }
  | { type: 'download-start' }
  | { type: 'download-progress'; percent: number }
  | { type: 'download-done' }
  | { type: 'download-error'; message: string }
  | { type: 'reset' }
  | { type: 'set-disabled'; disabled: boolean }

export function initialUpdateState(disabled = false): UpdateState {
  return { status: 'idle', version: null, percent: 0, error: null, disabled, checkedAt: null }
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value)))
}

/** 纯 reducer：非法事件返回原状态（引用不变，便于上层做变更判定） */
export function reduceUpdate(state: UpdateState, event: UpdateEvent, now: number = Date.now()): UpdateState {
  switch (event.type) {
    case 'set-disabled': {
      if (event.disabled) {
        // 禁用即回到 idle，并清空版本/进度/错误
        return { status: 'idle', version: null, percent: 0, error: null, disabled: true, checkedAt: state.checkedAt }
      }
      if (!state.disabled) return state
      return { ...state, disabled: false }
    }

    case 'reset':
      return { ...initialUpdateState(state.disabled), checkedAt: state.checkedAt }

    case 'check-start':
      if (state.disabled) return state
      if (state.status === 'downloading' || state.status === 'ready') return state
      return { ...state, status: 'checking', error: null }

    case 'check-available':
      if (state.disabled || state.status !== 'checking') return state
      return { status: 'available', version: event.version, percent: 0, error: null, disabled: false, checkedAt: now }

    case 'check-none':
      if (state.disabled || state.status !== 'checking') return state
      return { ...initialUpdateState(false), checkedAt: now }

    case 'check-error':
      if (state.disabled || state.status !== 'checking') return state
      return { status: 'error', version: null, percent: 0, error: event.message, disabled: false, checkedAt: now }

    case 'download-start':
      if (state.disabled || state.status !== 'available') return state
      return { ...state, status: 'downloading', percent: 0, error: null }

    case 'download-progress':
      if (state.status !== 'downloading') return state
      return { ...state, percent: clampPercent(event.percent) }

    case 'download-done':
      if (state.status !== 'downloading') return state
      return { ...state, status: 'ready', percent: 100, error: null }

    case 'download-error':
      if (state.status !== 'downloading') return state
      return { ...state, status: 'error', percent: 0, error: event.message }

    default:
      return state
  }
}

/** 是否可以点击「安装并重启」 */
export function canInstall(state: UpdateState): boolean {
  return state.status === 'ready' && !state.disabled
}

/** 是否处于进行中（用于禁用「检查更新」按钮） */
export function isBusy(state: UpdateState): boolean {
  return state.status === 'checking' || state.status === 'downloading'
}
