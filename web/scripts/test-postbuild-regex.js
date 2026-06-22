#!/usr/bin/env node
/**
 * postbuild regex 测试
 *
 * 验证 /manifest(?:\.[a-zA-Z0-9]+)?\.webmanifest/ 能同时匹配：
 *   - manifest.webmanifest（旧 URL）
 *   - manifest.{8charHash}.webmanifest（新 URL）
 */

const re = /manifest(?:\.[a-zA-Z0-9]+)?\.webmanifest/g

const cases = [
  // [input, expected matches]
  ['"url":"manifest.webmanifest"}])', ['manifest.webmanifest']],
  ['"url":"manifest.4f8d6b64.webmanifest"}])', ['manifest.4f8d6b64.webmanifest']],
  ['"manifest.webmanifest",', ['manifest.webmanifest']],
  ['"manifest.4f8d6b64.webmanifest",', ['manifest.4f8d6b64.webmanifest']],
  ['href="/manifest.webmanifest"', ['manifest.webmanifest']],
  ['href="/manifest.abc12345.webmanifest"', ['manifest.abc12345.webmanifest']],
  // 不应匹配
  ['no manifest here', null],
  ['some.other.path.webmanifest', null],
]

let pass = 0
let fail = 0
for (const [input, expected] of cases) {
  const actual = input.match(re)
  const actualStr = actual ? JSON.stringify(actual) : 'null'
  const expectedStr = expected ? JSON.stringify(expected) : 'null'
  const isMatch = JSON.stringify(actual) === expectedStr
  if (isMatch) {
    console.log(`✓ ${JSON.stringify(input).slice(0, 60)} → ${actualStr}`)
    pass++
  } else {
    console.log(`✗ ${JSON.stringify(input).slice(0, 60)}`)
    console.log(`    expected: ${expectedStr}`)
    console.log(`    actual:   ${actualStr}`)
    fail++
  }
}

console.log(`\n${pass}/${pass + fail} passed`)
process.exit(fail > 0 ? 1 : 0)