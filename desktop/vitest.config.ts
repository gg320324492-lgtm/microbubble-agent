import { defineConfig } from 'vitest/config'
import { resolve } from 'node:path'

/**
 * Phase 3-C2 引入 vitest (单元测试).
 *
 * 范围: 纯函数 helpers (citation.ts 等) + 未来 store 纯逻辑.
 * 不测试 Vue component (需要 happy-dom / @vue/test-utils, Phase 4+ 加).
 *
 * Phase 4-C 扩展: 加 @shared / @ 路径别名解析 (与 electron-vite.config.ts 一致),
 * 因为测试要 import 渲染端模块 (chat.ts), 其内部使用 @shared/... 别名.
 *
 * node 环境: 不需要 DOM, 跑得快.
 */
export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    globals: false  // 显式 import { test, expect } from 'vitest'
  },
  resolve: {
    alias: {
      '@shared': resolve(__dirname, 'src/shared'),
      '@': resolve(__dirname, 'src/renderer/src')
    }
  }
})
