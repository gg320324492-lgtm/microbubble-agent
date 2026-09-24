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
  UpdateState,
  WorkspaceAuditEntry
} from './types'

export interface PreloadApi {
  app: {
    /** 用系统浏览器打开外链（仅允许 http/https） */
    openExternal(url: string): Promise<void>
    info(): Promise<AppInfo>
    quit(): Promise<void>
  }
  auth: {
    /** M2-3a+：以父级账号登录（成功后云端身份自动关联并认领本机历史数据） */
    cloudLogin(payload: { baseUrl?: string; username: string; password: string }): Promise<unknown>
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
    confirmResolve(sessionId: string, callId: string, approve: boolean, remember?: 'once' | 'workspace' | 'global'): Promise<void>
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
    /** M2-3b：知识库数据源状态（引导态用） */
    sourceState(): Promise<unknown>
    /** UI1-3：知识库统计（分类/实体/假设计数） */
    stats(): Promise<unknown>
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
  agent: {
    /** M8-2：上下文估算与最近裁切（设置页调试区） */
    contextGet(): Promise<unknown>
    /** M8-2：写入上下文预算配置（部分更新；主侧范围校验后立即生效） */
    contextSet(patch: Record<string, unknown>): Promise<unknown>
    /** M8-3：工具权限查看/写入（设置页） */
    permissionsGet(): Promise<unknown>
    permissionsSet(patch: Record<string, unknown>): Promise<unknown>
    /** M8-3：任务进行中补充要求（轮边界注入） */
    steer(sessionId: string, text: string): Promise<null>
  }
  cloud: {
    /** M2-3a：云端连接状态（状态 + 服务器用户名 + 最近错误） */
    statusGet(): Promise<unknown>
    /** 解绑（清令牌与绑定状态，不删本地数据） */
    unbind(): Promise<unknown>
  }
  drive: {
    /** M2-3c：网盘数据源状态（引导态，文案由集中状态机给出） */
    state(): Promise<unknown>
    /** DL-2：契约参数为 folder_id（根视图不传）；keyword 走服务端搜索 */
    list(folderId?: number | null, keyword?: string): Promise<unknown>
    /** 上传本地文件（分块/断点续传由主进程处理，进度经 drive:progress 事件推送） */
    upload(payload: { filePath: string; parentId?: number | null }): Promise<unknown>
    rename(id: number, title: string): Promise<unknown>
    remove(id: number): Promise<unknown>
    /** 未完成上传（「继续上传」入口） */
    pendingUploads(): Promise<unknown>
    /** UI1-3：文件夹列表（导航用） */
    folders(parentId?: number | null): Promise<unknown>
    /** UI1-3：新建文件夹 */
    createFolder(name: string, parentId?: number | null): Promise<unknown>
    /** 上传进度事件（返回取消订阅函数） */
    onProgress(cb: (p: unknown) => void): () => void
    /** 下载（主进程弹保存对话框后流式落盘；进度经 drive:download 事件推送） */
    download(id: number): Promise<unknown>
  }
  backup: {
    create(password: string, targetDir: string): Promise<{ fileName: string; size: number }>
    restore(password: string, backupFile: string): Promise<{ needRestart: boolean }>
    list(targetDir: string): Promise<{ fileName: string; size: number; appVersion: string; createdAt: number; path: string }[]>
    deleteLocal(fileName: string): Promise<boolean>
    /** R-9 B 每日定时备份：读取配置 + 最近结果 + 目标目录 + 密码是否已配置 */
    dailyGet(): Promise<unknown>
    /** R-9 B 写入定时备份配置（部分更新；targetDir 单独落库） */
    dailySet(patch: Record<string, unknown>): Promise<unknown>
    /** R-9 B 立即执行一次定时备份（设置页「立即备份一次」） */
    dailyRun(): Promise<unknown>
    oss: {
      saveConfig(cfg: { bucket: string; endpoint: string; prefix: string; accessKeyId: string; accessKeySecret: string }): Promise<void>
      test(): Promise<{ ok: boolean; error?: string }>
      upload(filePath: string): Promise<{ key: string; size: number }>
      listRemote(): Promise<{ key: string; size: number; lastModified: string }[]>
      download(remoteKey: string): Promise<{ localPath: string }>
      deleteRemote(remoteKey: string): Promise<void>
    }
  }
  desktop: {
    applyShortcut(accelerator: string): Promise<{ ok: boolean; accelerator: string; error?: string }>
  }
  update: {
    /** 当前更新状态快照 */
    state(): Promise<UpdateState>
    /** 手动检查更新（设置页按钮） */
    check(): Promise<UpdateState>
    /** 用户确认后开始下载 */
    download(): Promise<UpdateState>
    /** 安装并重启（仅 ready 态生效）；返回是否已触发 */
    install(): Promise<boolean>
    onStateChange(cb: (s: UpdateState) => void): () => void
    /** 更新通知被点击 → 跳转设置页 */
    onOpenSettings(cb: () => void): () => void
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
