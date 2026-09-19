// 主进程常量 — 窗口尺寸/版本号（与骨架设计 §5 安全基线配套）
export const APP_NAME = '小气 · 科研工作台'
/// 发布版本 — 每版与 package.json version 同步更新（M6 可改为构建期自动注入）
export const APP_VERSION = '1.0.1'
export const WINDOW_MIN_WIDTH = 1024
export const WINDOW_MIN_HEIGHT = 640
export const SESSION_TTL_MS = 60 * 60 * 1000
/** 真机/联调用更新 feed 覆盖（设置后走 generic provider 指向本地静态服务） */
export const ENV_UPDATE_FEED = 'MNB_UPDATE_FEED'

/**
 * 更新 feed 主机（R-8）——自定义域名 releases.mnb-lab.cn 接入后**只改这一行**：
 *   'https://releases.mnb-lab.cn'
 * 即可让应用侧 feed 整体切到短域名（路径前缀不变）。
 */
export const UPDATE_FEED_HOST = 'https://mnb-workbench-releases.oss-cn-beijing.aliyuncs.com'
/** feed 稳定路径前缀：latest.yml 与安装包同目录（electron-updater generic provider） */
export const UPDATE_FEED_PREFIX = 'releases/'
/** 默认 feed 基址（generic provider，末位斜杠必需） */
export const UPDATE_FEED_BASE = `${UPDATE_FEED_HOST}/${UPDATE_FEED_PREFIX}`
/** 回退到 GitHub provider 的开关环境变量（值为 github 时启用回退） */
export const ENV_UPDATE_FEED_PROVIDER = 'MNB_UPDATE_FEED_PROVIDER'
