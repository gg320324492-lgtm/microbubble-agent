// 后端 URL 等配置常量。
// Phase 0 仅占位；Phase 1 起消费实际后端 + 鉴权。

export const APP_CONFIG = {
  // Phase 1 起使用：'https://agent.mnb-lab.cn/api/v1'
  // Phase 0 阶段不连真后端，Renderer 显示 demo 即可。
  backendUrl: '',
  appName: 'MicroBubble Desktop',
  appVersion: '0.1.0'
} as const
