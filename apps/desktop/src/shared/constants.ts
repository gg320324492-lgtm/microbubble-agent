// 主进程常量 — 窗口尺寸/版本号（与骨架设计 §5 安全基线配套）
export const APP_NAME = '小气 · 科研工作台'
/// 发布版本 — 每版与 package.json version 同步更新（M6 可改为构建期自动注入）
export const APP_VERSION = '1.0.0'
export const WINDOW_MIN_WIDTH = 1024
export const WINDOW_MIN_HEIGHT = 640
export const SESSION_TTL_MS = 60 * 60 * 1000
/** 真机/联调用更新 feed 覆盖（设置后走 generic provider 指向本地静态服务） */
export const ENV_UPDATE_FEED = 'MNB_UPDATE_FEED'
