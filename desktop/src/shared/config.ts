// 后端 URL 等配置常量（main / preload / renderer 共享）。
// 修改本文件必须同步 verify 三方 import。

export const APP_CONFIG = {
  // 生产后端（与 web 端共享，不依赖 web 是否存活）
  backendUrl: 'https://agent.mnb-lab.cn/api/v1',
  // 应用元
  appName: 'MicroBubble Desktop',
  appVersion: '0.1.0'
} as const
