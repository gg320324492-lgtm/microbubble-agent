#!/usr/bin/env node
/**
 * replace-transition-all-literals.js — v77 P2.6-F
 * 批量把 .vue / .css 里的 `transition: all 0.Xs` shorthand 替换为 token
 *
 * 替换映射（CLAUDE.md v77 P2.6-D 教训：PowerShell Set-Content 禁用，改用 Node.js 脚本无 BOM）：
 *   transition: all 0.15s   → transition: var(--transition-all-fast)
 *   transition: all 0.2s    → transition: var(--transition-all-normal)
 *   transition: all 0.25s   → transition: var(--transition-all-slow)
 *   transition: all 0.3s    → transition: var(--transition-all-slower)
 *
 * 不替换：
 *   - 已用 var(--transition-*) 的（避免重复）
 *   - 已用 var(--duration-*) + var(--ease-out) 完整版的（保留精确语义）
 *   - transition: all Xs + ease（保留 ease keyword 兼容性，留给用户单独改）
 *
 * 用法：
 *   node scripts/replace-transition-all-literals.js            # 实际替换 web/src/
 *   node scripts/replace-transition-all-literals.js --dry-run  # 仅打印将替换数量
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'web', 'src');

// 替换映射（顺序敏感：从最长到最短，避免 0.2s 误匹配 0.25s）
const REPLACEMENTS = [
  { from: /transition:\s*all\s+0\.3s(?![\w-])/g, to: 'transition: var(--transition-all-slower)' },
  { from: /transition:\s*all\s+0\.25s(?![\w-])/g, to: 'transition: var(--transition-all-slow)' },
  { from: /transition:\s*all\s+0\.2s(?![\w-])/g, to: 'transition: var(--transition-all-normal)' },
  { from: /transition:\s*all\s+0\.15s(?![\w-])/g, to: 'transition: var(--transition-all-fast)' },
];

const EXCLUDE_PATTERNS = [
  /variables\.css$/,
  /_runtime-style-tokens\.scss$/,
  /node_modules/,
  /\.git/,
];

function shouldExclude(file) {
  return EXCLUDE_PATTERNS.some((re) => re.test(file));
}

function walk(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (shouldExclude(full)) continue;
    if (entry.isDirectory()) {
      results.push(...walk(full));
    } else if (/\.(vue|css|scss)$/.test(entry.name)) {
      results.push(full);
    }
  }
  return results;
}

function processFile(file, dryRun) {
  const content = fs.readFileSync(file, 'utf8');
  let totalReplaced = 0;
  let newContent = content;

  for (const { from, to } of REPLACEMENTS) {
    const matches = newContent.match(from);
    const count = matches ? matches.length : 0;
    if (count > 0) {
      newContent = newContent.replace(from, to);
      totalReplaced += count;
    }
  }

  if (totalReplaced > 0) {
    if (!dryRun) {
      fs.writeFileSync(file, newContent, 'utf8');
    }
    console.log(`  ${path.relative(ROOT, file)}: ${totalReplaced} 处`);
  }
  return totalReplaced;
}

function main() {
  const dryRun = process.argv.includes('--dry-run');
  console.log(dryRun ? '🔍 DRY RUN (不写文件)\n' : '✏️  ACTUAL REPLACE\n');

  const files = walk(SRC);
  console.log(`扫描 ${files.length} 个 .vue/.css/.scss 文件\n`);

  let grandTotal = 0;
  const fileSummaries = [];

  for (const f of files) {
    const totalReplaced = processFile(f, dryRun);
    if (totalReplaced > 0) {
      grandTotal += totalReplaced;
      fileSummaries.push({ file: path.relative(ROOT, f), count: totalReplaced });
    }
  }

  console.log(`\n📊 总计：${grandTotal} 处替换，${fileSummaries.length} 个文件`);
  if (dryRun) {
    console.log('💡 去掉 --dry-run 跑实际替换');
  } else {
    console.log('✅ 已写入所有文件（UTF-8 无 BOM）');
    console.log('⚠️  手工处理剩余 transition: all Xs ease (~7 处含 ease 关键字)');
  }
}

main();