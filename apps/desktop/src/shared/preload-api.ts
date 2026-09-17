// window.api 形状声明 — renderer 侧全局类型（与 preload/index.ts 实现严格同步）
import type {
  AppInfo,
  AuthSession,
  ChatMessage,
  ChatSession,
  ChatStreamEvent,
  KnowledgeDocFull,
  KnowledgeDocMeta,
  KnowledgeImportResult,
  KnowledgeSearchHit,
  KnowledgeUpdateInput,
  ExperimentCreateInput,
  ExperimentFile,
  ExperimentFull,
  ExperimentSearchHit,
  ExperimentStatus,
  ExperimentUpdateInput,
  LocalUser,
  ManuscriptCreateInput,
  ManuscriptFile,
  ManuscriptFull,
  ManuscriptSearchHit,
  ManuscriptStatus,
  ManuscriptUpdateInput,
  ManuscriptWordStats,
  MeetingCreateInput,
  MeetingDetail,
  MeetingFile,
  MeetingListItem,
  MeetingSearchHit,
  MeetingTranscript,
  MeetingTranscriptImportInput,
  MeetingUpdateInput,
  ModelProvider,
  ModelProviderInput,
  WorkspaceAuditEntry
} from './types'

export interface PreloadApi {
  app: {
    info(): Promise<AppInfo>
    quit(): Promise<void>
  }
  auth: {
    status(): Promise<{ userCount: number }>
    registerAdmin(p: { username: string; displayName?: string; password: string }): Promise<AuthSession>
    login(p: { username: string; password: string }): Promise<AuthSession>
    restore(): Promise<AuthSession | null>
    logout(): Promise<void>
  }
  chat: {
    sessionsList(): Promise<ChatSession[]>
    sessionCreate(title?: string): Promise<ChatSession>
    sessionRename(id: string, title: string): Promise<void>
    sessionDelete(id: string): Promise<void>
    messagesList(sessionId: string): Promise<ChatMessage[]>
    send(sessionId: string, content: string): Promise<{ userMessage: ChatMessage; assistantMessage: ChatMessage }>
    abort(sessionId: string): Promise<void>
    /** 写工具确认结果回传；确认请求已过期时 reject */
    confirmResolve(sessionId: string, callId: string, approve: boolean): Promise<void>
    /** 回滚一次 write_file（从备份恢复原内容并审计留痕） */
    rollbackWrite(sessionId: string, messageId: string, callId: string): Promise<{ path: string }>
    onStreamEvent(cb: (e: ChatStreamEvent) => void): () => void
  }
  model: {
    list(): Promise<ModelProvider[]>
    save(p: ModelProviderInput): Promise<void>
    remove(id: string): Promise<void>
    setDefault(id: string): Promise<void>
    test(p: ModelProviderInput): Promise<{ ok: boolean; message: string }>
  }
  settings: {
    get(key: string): Promise<unknown>
    set(key: string, value: unknown): Promise<void>
  }
  workspace: {
    get(): Promise<{ root: string | null }>
    /** 弹系统目录选择框，确认后 setRoot；返回所选根目录，取消返回 null */
    set(): Promise<string | null>
    /** 清除工作区（回到未设置态；不删除工作区目录内任何文件） */
    clear(): Promise<void>
    auditList(limit?: number): Promise<WorkspaceAuditEntry[]>
  }
  knowledge: {
    list(): Promise<KnowledgeDocMeta[]>
    get(id: number): Promise<KnowledgeDocFull | null>
    import(files: { name: string; content: string }[]): Promise<KnowledgeImportResult>
    update(id: number, patch: KnowledgeUpdateInput): Promise<KnowledgeDocFull | null>
    delete(id: number): Promise<boolean>
    search(query: string): Promise<KnowledgeSearchHit[]>
  }
  meetings: {
    list(): Promise<MeetingListItem[]>
    get(id: number): Promise<MeetingDetail | null>
    create(input: MeetingCreateInput): Promise<{ id: number }>
    update(id: number, patch: MeetingUpdateInput): Promise<boolean>
    delete(id: number): Promise<boolean>
    importTranscript(p: MeetingTranscriptImportInput): Promise<MeetingTranscript | null>
    updateTranscript(meetingId: number, transcriptId: number, content: string): Promise<MeetingTranscript | null>
    addFile(meetingId: number, file: { name: string; data: Uint8Array }): Promise<MeetingFile | null>
    removeFile(meetingId: number, fileId: number): Promise<boolean>
    openFile(meetingId: number, fileId: number): Promise<{ path: string } | null>
    search(query: string): Promise<MeetingSearchHit[]>
  }
  manuscripts: {
    list(status?: ManuscriptStatus): Promise<ManuscriptFull[]>
    get(id: number): Promise<ManuscriptFull | null>
    create(input: ManuscriptCreateInput): Promise<{ id: number }>
    update(id: number, patch: ManuscriptUpdateInput): Promise<boolean>
    delete(id: number): Promise<boolean>
    addFile(manuscriptId: number, file: { name: string; data: Uint8Array }): Promise<ManuscriptFile | null>
    removeFile(manuscriptId: number, fileId: number): Promise<boolean>
    openFile(manuscriptId: number, fileId: number): Promise<{ path: string } | null>
    search(query: string): Promise<ManuscriptSearchHit[]>
    stats(content: string): Promise<ManuscriptWordStats>
  }
  backup: {
    create(password: string, targetDir: string): Promise<{ fileName: string; size: number }>
    restore(password: string, backupFile: string): Promise<{ needRestart: boolean }>
    list(targetDir: string): Promise<{ fileName: string; size: number; appVersion: string; createdAt: number; path: string }[]>
  }
  desktop: {
    applyShortcut(accelerator: string): Promise<{ ok: boolean; accelerator: string; error?: string }>
  }
  experiments: {
    list(status?: ExperimentStatus): Promise<ExperimentFull[]>
    get(id: number): Promise<ExperimentFull | null>
    create(input: ExperimentCreateInput): Promise<{ id: number; code: string }>
    update(id: number, patch: ExperimentUpdateInput): Promise<boolean>
    delete(id: number): Promise<boolean>
    addFile(experimentId: number, file: { name: string; data: Uint8Array }): Promise<ExperimentFile | null>
    removeFile(experimentId: number, fileId: number): Promise<boolean>
    openFile(experimentId: number, fileId: number): Promise<{ path: string } | null>
    search(query: string): Promise<ExperimentSearchHit[]>
  }
  window: {
    minimize(): Promise<void>
    toggleMaximize(): Promise<void>
    close(): Promise<void>
    isMaximized(): Promise<boolean>
    show(): Promise<void>
    focus(): Promise<void>
    onStateChange(cb: (maximized: boolean) => void): () => void
  }
}

declare global {
  interface Window {
    api: PreloadApi
  }
}

export interface WindowWithApi extends Window {
  api: PreloadApi
}

export type { LocalUser, AuthSession, AppInfo, ChatSession, ChatMessage, ChatStreamEvent, ModelProvider, ModelProviderInput, WorkspaceAuditEntry }
