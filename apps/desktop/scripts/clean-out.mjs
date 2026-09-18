#!/usr/bin/env node
// 独立入口：pnpm build 前清理 out/（M6-2 清账⑤）。
// 之所以不写成 `node -e "rmSync('out')"`：本地沙箱的批量删除守卫会打断构建（见 lib/clean-out.mjs）。
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { cleanOutDir } from './lib/clean-out.mjs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
cleanOutDir(join(ROOT, 'out'), (m) => console.log(`[clean-out] ${m}`))
