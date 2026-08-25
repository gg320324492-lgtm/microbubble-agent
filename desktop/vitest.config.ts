import { defineConfig } from 'vitest/config'
import { resolve } from 'node:path'
import vue from '@vitejs/plugin-vue'

/**
 * Phase 3-C2 引入 vitest (单元测试).
 *
 * Phase 4-C 扩展: 加 @shared / @ 路径别名解析 (与 electron-vite.config.ts 一致),
 * 因为测试要 import 渲染端模块 (chat.ts), 其内部使用 @shared/... 别名.
 *
 * 默认保持 node 环境；科研 UI 契约使用 happy-dom 做真实 Vue 挂载。
 *
 * R1 扩展: 加 @main 路径别名, 让迁移/打包相关测试 (例如 mbrp-archive)
 * 能直接 import '@main/migration/index' 这样的物理位置.
 */
export default defineConfig({
  plugins: [vue()],
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    environmentMatchGlobs: [
      ['tests/unit/research-os-frontend.test.ts', 'happy-dom'],
      ['tests/unit/research-os-integration.test.ts', 'happy-dom'],
      ['tests/unit/login-view.dom.test.ts', 'happy-dom']
    ],
    globals: false  // 显式 import { test, expect } from 'vitest'
  },
  resolve: {
    alias: {
      '@main': resolve(__dirname, 'src/main'),
      '@shared': resolve(__dirname, 'src/shared'),
      '@': resolve(__dirname, 'src/renderer/src')
    }
  }
})
