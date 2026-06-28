#!/usr/bin/env node
/**
 * replace-easing-literals.js — v77 P2.6-E.2
 * 批量把 .vue / .css 里的缓动字面量替换为 var(--ease-*) token
 *
 * 替换映射（CLAUDE.md v77 P2.6-D.2 铁律：PowerShell Set-Content 禁用，改用 Node.js 脚本无 BOM）：
 *   ease-out 字面                → var(--ease-out)
 *   ease-in-out 字面             → var(--ease-in-out)
 *   cubic-bezier(0.34, 1.56, 0.64, 1) → var(--ease-bounce)
 *   cubic-bezier(0.32, 0.72, 0, 1)    → var(--ease-sheet)
 *   cubic-bezier(0.4, 0, 0.2, 1)      → var(--ease-in-out)
 *   cubic-bezier(0.4, 0, 1, 1)        → var(--ease-in)
 *   cubic-bezier(0.2, 0.7, 0.2, 1)    → var(--ease-spring)
 *   cubic-bezier(0.25, 0.46, 0.45, 0.94) → var(--ease-quad)
 *
 * 用法：
 *   node scripts/replace-easing-literals.js            # 实际替换 web/src/
 *   node scripts/replace-easing-literals.js --dry-run  # 仅打印将替换数量，不写文件
 *
 * 排除文件：
 *   - variables.css（自身定义 --ease-* 不能改）
 *   - _runtime-style-tokens.scss（scss mixin 内部不需替换）
 *
 * 输出：每个文件打印 "  文件: N 处替换"，末尾总统计
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'web', 'src');

// 替换映射（顺序敏感：先 longest 防止误匹配）
const REPLACEMENTS = [
  // cubic-bezier 类（必须先于 ease-* 关键字处理，否则 var(--ease-out) 里的 cubic-bezier 不会触发）
  { from: /cubic-bezier\(0\.34,\s*1\.56,\s*0\.64,\s*1\)/g, to: 'var(--ease-bounce)' },
  { from: /cubic-bezier\(0\.32,\s*0\.72,\s*0,\s*1\)/g, to: 'var(--ease-sheet)' },
  { from: /cubic-bezier\(0\.4,\s*0,\s*0\.2,\s*1\)/g, to: 'var(--ease-in-out)' },
  { from: /cubic-bezier\(0\.4,\s*0,\s*1,\s*1\)/g, to: 'var(--ease-in)' },
  { from: /cubic-bezier\(0\.2,\s*0\.7,\s*0\.2,\s*1\)/g, to: 'var(--ease-spring)' },
  { from: /cubic-bezier\(0\.25,\s*0\.46,\s*0\.45,\s*0\.94\)/g, to: 'var(--ease-quad)' },
  // 关键字类（必须放在最后，避免先匹配子串）
  // ease-out 关键字 - 负向 lookbehind/ahead 排除已有 var() 包裹
  { from: /(?<![-a-zA-Z0-9_])ease-out(?![-a-zA-Z0-9_])/g, to: 'var(--ease-out)' },
  { from: /(?<![-a-zA-Z0-9_])ease-in-out(?![-a-zA-Z0-9_])/g, to: 'var(--ease-in-out)' },
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
  const perPattern = [];

  for (const { from, to } of REPLACEMENTS) {
    const matches = newContent.match(from);
    const count = matches ? matches.length : 0;
    if (count > 0) {
      newContent = newContent.replace(from, to);
      perPattern.push(`${from.source.slice(0, 40)}... → ${to}  ×${count}`);
      totalReplaced += count;
    }
  }

  if (totalReplaced > 0) {
    if (!dryRun) {
      // UTF-8 写不附加 BOM（CLAUDE.md v77 P2.6-D 教训）
      fs.writeFileSync(file, newContent, 'utf8');
    }
    console.log(`  ${path.relative(ROOT, file)}: ${totalReplaced} 处`);
  }
  return { totalReplaced, perPattern };
}

function main() {
  const dryRun = process.argv.includes('--dry-run');
  console.log(dryRun ? '🔍 DRY RUN (不写文件)\n' : '✏️  ACTUAL REPLACE\n');

  const files = walk(SRC);
  console.log(`扫描 ${files.length} 个 .vue/.css/.scss 文件\n`);

  let grandTotal = 0;
  const fileSummaries = [];

  for (const f of files) {
    const { totalReplaced } = processFile(f, dryRun);
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
  }
}

main();