import { defineConfig } from 'vitest/config'

/**
 * Phase 3-C2 引入 vitest (单元测试).
 *
 * 范围: 纯函数 helpers (citation.ts 等) + 未来 store 纯逻辑.
 * 不测试 Vue component (需要 happy-dom / @vue/test-utils, Phase 4+ 加).
 *
 * node 环境: 不需要 DOM, 跑得快.
 */
export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    globals: false  // 显式 import { test, expect } from 'vitest'
  }
})
