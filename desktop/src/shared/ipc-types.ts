// IPC channel 名集中管理 + ping/pong 类型契约（preload / main / renderer 共享）。
// 仅跨进程的安全可序列化数据形状，不定义跨进程 API surface（见 preload-api.ts）。

export const IPC_CHANNELS = {
  PING: 'app:ping'
} as const

// IPC_CHANNELS 值的字面量类型
export type IpcChannelName = (typeof IPC_CHANNELS)[keyof typeof IPC_CHANNELS]
