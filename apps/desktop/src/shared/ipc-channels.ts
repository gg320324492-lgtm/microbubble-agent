// IPC 通道白名单 — main / preload 唯一事实来源。
// 新增能力必须同步: 1) 这里加常量 2) main/ipc.ts 注册 handler 3) preload 暴露方法。
// tests/unit/ipc-consistency.test.ts 会校验三处一致。
export const IPC = {
  APP_INFO: 'app:info',
  AUTH_STATUS: 'auth:status',
  AUTH_REGISTER_ADMIN: 'auth:register-admin',
  AUTH_LOGIN: 'auth:login',
  AUTH_RESTORE: 'auth:restore',
  AUTH_LOGOUT: 'auth:logout',
  SETTINGS_GET: 'settings:get',
  SETTINGS_SET: 'settings:set',
  CHAT_SESSIONS_LIST: 'chat:sessions:list',
  CHAT_SESSION_CREATE: 'chat:session:create',
  CHAT_SESSION_RENAME: 'chat:session:rename',
  CHAT_SESSION_DELETE: 'chat:session:delete',
  CHAT_MESSAGES_LIST: 'chat:messages:list',
  CHAT_SEND: 'chat:send',
  CHAT_ABORT: 'chat:abort',
  /** renderer → main：写工具确认结果回传（approve=true 批准 / false 拒绝） */
  CHAT_CONFIRM_RESOLVE: 'chat:confirm-resolve',
  /** renderer → main：回滚一次 write_file（从 .agent-backups 恢复原内容并留痕） */
  CHAT_ROLLBACK_WRITE: 'chat:rollback-write',
  /** main → renderer 推送通道（流式增量 / 窗口状态），preload 以 on* 方式暴露 */
  CHAT_STREAM_EVENT: 'chat:stream-event',
  WINDOW_STATE_EVENT: 'window:state-event',
  MODEL_LIST: 'model:list',
  MODEL_SAVE: 'model:save',
  MODEL_DELETE: 'model:delete',
  MODEL_SET_DEFAULT: 'model:set-default',
  MODEL_TEST: 'model:test',
  WORKSPACE_GET: 'workspace:get',
  WORKSPACE_SET: 'workspace:set',
  WORKSPACE_CLEAR: 'workspace:clear',
  WORKSPACE_AUDIT_LIST: 'workspace:audit-list',
  KNOWLEDGE_LIST: 'knowledge:list',
  KNOWLEDGE_GET: 'knowledge:get',
  KNOWLEDGE_IMPORT: 'knowledge:import',
  KNOWLEDGE_UPDATE: 'knowledge:update',
  KNOWLEDGE_DELETE: 'knowledge:delete',
  KNOWLEDGE_SEARCH: 'knowledge:search',
  WINDOW_MINIMIZE: 'window:minimize',
  WINDOW_TOGGLE_MAXIMIZE: 'window:toggle-maximize',
  WINDOW_IS_MAXIMIZED: 'window:is-maximized',
  WINDOW_CLOSE: 'window:close'
} as const

export type IpcChannel = (typeof IPC)[keyof typeof IPC]
