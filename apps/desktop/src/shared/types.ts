// 跨进程共享领域类型 — 账号/设置/应用信息
export type UserRole = 'admin' | 'researcher'

export interface LocalUser {
  id: string
  username: string
  displayName: string | null
  role: UserRole
  isActive: boolean
  createdAt: number
}

export interface AuthSession {
  user: LocalUser
  /** epoch ms — 会话过期时间（60min 滑动续期） */
  expiresAt: number
}

export interface AppInfo {
  version: string
  platform: string
  dbPath: string
  appName: string
}

/** 会话（chat_sessions 行的跨进程投影） */
export interface ChatSession {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  /** V1 用量记账：会话累计输入/输出 token（迁移 010） */
  tokensIn: number
  tokensOut: number
}

/** 消息（chat_messages 行的跨进程投影） */
export interface ChatMessage {
  id: string
  sessionId: string
  role: 'user' | 'assistant' | 'system'
  content: string
  /** Agent 结构化信息（thinking/工具轮次），仅 assistant 消息可能非空 */
  meta: MessageMeta | null
  createdAt: number
}

export type ModelProtocol = 'openai' | 'anthropic'

/** 模型服务配置（apiKey 永不明文出主进程，只回掩码） */
export interface ModelProvider {
  id: string
  name: string
  protocol: ModelProtocol
  baseUrl: string
  model: string
  apiKeyMasked: string | null
  isDefault: boolean
  /** key 在本机解密失败（DPAPI 上下文变化等）→ invalid，UI 给重填引导 */
  keyState: 'ok' | 'invalid'
}

export interface ModelProviderInput {
  id?: string
  name: string
  protocol: ModelProtocol
  baseUrl: string
  model: string
  /** 明文 key 仅在保存瞬间进入主进程，空串=保留旧 key */
  apiKey?: string
}

/** chat:stream-event 载荷 */
export type ChatStreamEvent =
  | { type: 'delta'; sessionId: string; messageId: string; delta: string }
  | { type: 'thinking'; sessionId: string; messageId: string; delta: string }
  | { type: 'tool'; sessionId: string; messageId: string; call: ToolCallRecord }
  | { type: 'round'; sessionId: string; messageId: string; round: number; label: string }
  | { type: 'done'; sessionId: string; messageId: string; content: string; meta?: MessageMeta | null }
  | { type: 'error'; sessionId: string; messageId: string; message: string }

/** 一次工具调用（工具卡片数据；status 流转 running → ok | error；写工具含确认态） */
export interface ToolCallRecord {
  id: string
  name: string
  input: unknown
  status: 'running' | 'ok' | 'error' | 'awaiting_confirm' | 'rejected'
  summary: string
  data?: unknown
}

/** 行级 diff 单行（工具卡片确认面板渲染） */
export interface DiffLine {
  kind: 'add' | 'del' | 'ctx'
  text: string
}

/** write_file 的 diff 数据（放 ToolCallRecord.data.diff；不进模型回喂） */
export interface FileDiff {
  path: string
  kind: 'create' | 'overwrite'
  lines: DiffLine[]
  truncated: boolean
}

/** assistant 消息的 Agent 结构化信息（chat_messages.meta JSON 列；工具卡片/思维链还原用） */
export interface MessageMeta {
  thinking?: string
  tools?: ToolCallRecord[]
  rounds?: number
  /** 用户中途停止（Esc/停止按钮），已产生的部分内容已保留 */
  stopped?: boolean
  /** 达到单次任务最大轮数（15）被截断 */
  hitRoundCap?: boolean
  /** false = 本次为纯对话降级（未设工作区或协议不支持工具） */
  toolsAvailable?: boolean
}

// ============ Agent 循环（主进程）与 Anthropic 协议形状 ============

export interface AnthropicToolDef {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

/** 循环内部 turns 的内容块（assistant 回放用 text/tool_use，回喂用 tool_result） */
export type AgentContentBlock =
  | { type: 'text'; text: string }
  | { type: 'tool_use'; id: string; name: string; input: unknown }
  | { type: 'tool_result'; tool_use_id: string; content: string; is_error?: boolean }

/** 循环内部消息（content 可为纯文本或块数组；system 走顶层字段不进 turns） */
export interface AgentTurn {
  role: 'user' | 'assistant'
  content: string | AgentContentBlock[]
}

/** 单轮流式回调事件（主进程内部） */
export type StreamTurnEvent = { kind: 'text' | 'thinking'; delta: string }

export interface ToolUseBlock {
  id: string
  name: string
  input: Record<string, unknown>
}

export type StopReason = 'tool_use' | 'end_turn' | 'max_tokens' | 'stop_sequence' | 'aborted' | 'other'

export interface StreamTurnResult {
  stopReason: StopReason
  text: string
  thinking: string
  toolUses: ToolUseBlock[]
  /** 供下一轮回喂的 assistant content blocks（text + tool_use，thinking 不回传） */
  assistantBlocks: AgentContentBlock[]
  /**
   * V1 用量记账：本轮流式返回的 token 用量。
   * 可选 —— 协议未返回 usage 的网关/测试假实现可缺省；消费方一律按 0 处理（见 addUsage）。
   */
  usage?: TokenUsage
}

/** 用量记账（V1）— 归一化后的 token 用量；usageComplete=false 表示来源字段缺失或非法 */
export interface TokenUsage {
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
  usageComplete: boolean
}

export interface StreamTurnRequest {
  system: string
  turns: AgentTurn[]
  tools: AnthropicToolDef[]
  onEvent: (e: StreamTurnEvent) => void
}

/** Agent 循环的流式请求函数（真实实现 = 网关 streamAgentTurn；测试注入假网关） */
export type StreamTurnFn = (userId: string, sessionId: string, req: StreamTurnRequest) => Promise<StreamTurnResult>

/** 统一 IPC 返回包 — preload 解包，失败时 reject(Error) */
export type IpcResult<T> = { ok: true; data: T } | { ok: false; error: { code: string; message: string } }

/** 工作区状态（workspace:get 返回；root 为 null 表示未设置） */
export interface WorkspaceState {
  root: string | null
}

/** 工作区审计记录（workspace_audit 行的跨进程投影） */
export interface WorkspaceAuditEntry {
  id: number
  userId: string
  tool: string
  inputSummary: string
  ok: boolean
  createdAt: number
}

// ============ 本地知识库（M2-1）============

/** 知识库文档元信息（列表用，不含正文） */
export interface KnowledgeDocMeta {
  id: number
  title: string
  tags: string[]
  fileName: string | null
  fileSize: number
  source: string
  createdAt: number
  updatedAt: number
}

/** 知识库文档全文（详情/编辑用） */
export interface KnowledgeDocFull extends KnowledgeDocMeta {
  content: string
}

/** 导入输入（渲染层文件选择器读文本后传主进程） */
export interface KnowledgeImportInput {
  name: string
  content: string
}

export interface KnowledgeImportResult {
  imported: KnowledgeDocMeta[]
  skipped: { name: string; reason: string }[]
}

export interface KnowledgeUpdateInput {
  title?: string
  content?: string
  tags?: string[]
}

/** 检索命中：片段 + 高亮偏移（相对 snippet 文本），按相关度排序 */
export interface KnowledgeSearchHit {
  id: number
  title: string
  tags: string[]
  snippet: string
  highlight: { start: number; end: number } | null
  updatedAt: number
}

// ============ 本地会议档案（M2-2）============

/** 会议条目元信息（列表用） */
export interface MeetingMeta {
  id: number
  title: string
  meetingDate: number | null
  location: string
  attendees: string[]
  minutes: string
  createdAt: number
  updatedAt: number
}

/** 会议转录条目 */
export interface MeetingTranscript {
  id: number
  meetingId: number
  content: string
  source: 'paste' | 'txt' | 'srt'
  createdAt: number
  updatedAt: number
}

/** 会议附件条目（文件本体在 userData/data/files/meetings/<meetingId>/） */
export interface MeetingFile {
  id: number
  meetingId: number
  fileName: string
  fileSize: number
  createdAt: number
}

/** 会议详情（含转录与附件） */
export interface MeetingFull extends MeetingMeta {
  transcripts: MeetingTranscript[]
  files: MeetingFile[]
}

export interface MeetingCreateInput {
  title: string
  meetingDate?: number | null
  location?: string
  attendees?: string[]
  minutes?: string
}

export interface MeetingUpdateInput {
  title?: string
  meetingDate?: number | null
  location?: string
  attendees?: string[]
  minutes?: string
}

export interface MeetingTranscriptInput {
  content: string
  source: 'paste' | 'txt' | 'srt'
}

/** 会议检索命中：hitSource 标明命中所处位置（标题/纪要/转录） */
export interface MeetingSearchHit {
  id: number
  title: string
  meetingDate: number | null
  location: string
  hitSource: 'title' | 'minutes' | 'transcript'
  snippet: string
  highlight: { start: number; end: number } | null
  updatedAt: number
}

/** 会议详情的跨进程投影（转录/附件行随详情一起返回） */
export interface MeetingDetail {
  meeting: {
    id: number
    title: string
    meetingDate: number | null
    location: string
    attendees: string[]
    minutes: string
    createdAt: number
    updatedAt: number
  }
  transcripts: MeetingTranscript[]
  files: MeetingFile[]
}

export interface MeetingListItem {
  id: number
  title: string
  meetingDate: number | null
  location: string
  attendees: string[]
  minutes: string
  createdAt: number
  updatedAt: number
}

export interface OssSettings {
  bucket: string
  endpoint: string
  prefix: string
  accessKeyId: string
  /** safeStorage 加密后的 base64；渲染层永不接触明文 */
  accessKeySecretEnc: string
}

export interface OssTestResult {
  ok: boolean
  error?: string
}

export interface OssRemoteBackup {
  key: string
  size: number
  lastModified: string
}

export interface MeetingTranscriptImportInput {
  meetingId: number
  content: string
  source: 'paste' | 'txt' | 'srt'
}

// ============ 本地实验记录本（M3-1）============

export type ExperimentStatus = 'draft' | 'ongoing' | 'completed' | 'archived'

/** 实验条目元信息（列表用，不含记录正文） */
export interface ExperimentMeta {
  id: number
  title: string
  code: string
  status: ExperimentStatus
  tags: string[]
  createdAt: number
  updatedAt: number
}

export interface ExperimentFile {
  id: number
  experimentId: number
  fileName: string
  fileSize: number
  createdAt: number
}

/** 实验详情（含记录正文与附件） */
export interface ExperimentFull extends ExperimentMeta {
  content: string
  files: ExperimentFile[]
}

export interface ExperimentCreateInput {
  title: string
  code?: string
  status?: ExperimentStatus
  tags?: string[]
  content?: string
}

export interface ExperimentUpdateInput {
  title?: string
  code?: string
  status?: ExperimentStatus
  tags?: string[]
  content?: string
}

/** 检索命中：snippet 来自记录正文原文 */
export interface ExperimentSearchHit {
  id: number
  code: string
  title: string
  status: ExperimentStatus
  tags: string[]
  snippet: string
  highlight: { start: number; end: number } | null
  updatedAt: number
}

// ============ 本地稿件库（M3-2）============

export type ManuscriptStatus = 'draft' | 'revising' | 'submitted' | 'published'

/** 稿件元信息（列表用，不含正文） */
export interface ManuscriptMeta {
  id: number
  title: string
  status: ManuscriptStatus
  targetJournal: string
  tags: string[]
  createdAt: number
  updatedAt: number
}

export interface ManuscriptFile {
  id: number
  manuscriptId: number
  fileName: string
  fileSize: number
  createdAt: number
}

/** 稿件详情（含正文与附件） */
export interface ManuscriptFull extends ManuscriptMeta {
  content: string
  files: ManuscriptFile[]
}

export interface ManuscriptCreateInput {
  title: string
  status?: ManuscriptStatus
  targetJournal?: string
  tags?: string[]
  content?: string
}

export interface ManuscriptUpdateInput {
  title?: string
  status?: ManuscriptStatus
  targetJournal?: string
  tags?: string[]
  content?: string
}

/** 字数统计结果（中文字符数 + 总词数） */
export interface ManuscriptWordStats {
  cjkChars: number
  words: number
}

/** 稿件检索命中：snippet 来自正文原文 */
export interface ManuscriptSearchHit {
  id: number
  title: string
  status: ManuscriptStatus
  targetJournal: string
  snippet: string
  highlight: { start: number; end: number } | null
  updatedAt: number
}

// ---------- 自动更新（M6-1）----------

export type UpdateStatus = 'idle' | 'checking' | 'available' | 'downloading' | 'ready' | 'error'

/** 更新状态快照 — 主进程状态机的对外（渲染进程）视图 */
export interface UpdateState {
  status: UpdateStatus
  /** 目标新版本号（available / downloading / ready 时有值） */
  version: string | null
  /** 下载进度 0-100（downloading 时有值） */
  percent: number
  /** 错误原因（error 时有值） */
  error: string | null
  /** 环境不支持（非打包且无 feed 覆盖）时为 true */
  disabled: boolean
  /** 最近一次检查完成时间戳（ms） */
  checkedAt: number | null
}
