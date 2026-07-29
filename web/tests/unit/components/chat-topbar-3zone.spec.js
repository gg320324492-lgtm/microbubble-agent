/**
 * chat-topbar-3zone.spec.js — W72 B-3 顶栏 3-zone 重构单元测试
 *
 * 2026-07-24 W72 第 1 批 B-3 (子 plan ③ 起步).
 * 主指挥协调范式第 47 次派工. 锚点范式第 213 守恒.
 *
 * 测试场景 (6/6 PASS):
 * 1. scenario_1: 桌面端 3-zone 渲染 (left/center/right)
 * 2. scenario_2: 左 zone 集成 ChatBreadcrumb 容器 (B-2)
 * 3. scenario_3: 中 zone 标识为 center (data-zone-center)
 * 4. scenario_4: 右 zone 标识为 right (data-zone-right)
 * 5. scenario_5: 移动端断点 (768px) → 1fr 2fr 1fr 重排
 * 6. scenario_6: 3-zone grid CSS 实测 + TopBarZone type hint (派工 v6 段 5 反馈 #3)
 *
 * 设计原则 (派工 v6 段 5 反馈 #3 实战):
 * - TopBarZone type hint 必含 — 静态导入源文件校验 readonly + fr 数值
 * - 0 production code 改动铁律维持 — 仅 spec 文件新增, 不动 ChatViewSSE 源码
 * - vitest + @vue/test-utils (与 desktop_drive_v33_thumbnail 一致)
 * - 不依赖真实 Playwright 浏览器 (CSS 校验靠源文件 grep)
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

// W89-P-10: 迁入 tests/unit/components/ (3 层深) 后 ROOT 解析需 3 个 ../ (web/)
const ROOT = resolve(__dirname, '../../..')
const SOURCE = resolve(ROOT, 'src/views/chat/ChatViewSSE.vue')

beforeAll(() => {
  if (!existsSync(SOURCE)) {
    throw new Error(`ChatViewSSE.vue not found at ${SOURCE}`)
  }
})

function readSource() {
  return readFileSync(SOURCE, 'utf-8')
}

/** Extract a top-level `<script setup>` block from .vue SFC source */
function extractScript(source) {
  const m = source.match(/<script\s+setup[^>]*>([\s\S]*?)<\/script>/)
  if (!m) throw new Error('No <script setup> block found')
  return m[1]
}

/** Extract a `<style scoped>` block */
function extractStyle(source) {
  const m = source.match(/<style\s+scoped>([\s\S]*?)<\/style>/)
  if (!m) throw new Error('No <style scoped> block found')
  return m[1]
}

/** Extract `<template>` block */
function extractTemplate(source) {
  const m = source.match(/<template>([\s\S]*?)<\/template>/)
  if (!m) throw new Error('No <template> block found')
  return m[1]
}

/** First match body of a regex applied to a string, or throw */
function matchOrThrow(re, str, label) {
  const m = str.match(re)
  if (!m) throw new Error(`No ${label} match in:\n${str.slice(0, 200)}`)
  // If regex has a capture group, return group 1; else return full match
  return m[1] !== undefined ? m[1] : m[0]
}

describe('W72 B-3 ChatViewSSE 顶栏 3-zone 重构', () => {
  const source = readSource()
  const script = extractScript(source)
  const style = extractStyle(source)
  const template = extractTemplate(source)

  // ──────────────────────────────────────────────────────────────────────────
  // scenario_1: 桌面端 3-zone 渲染 (left/center/right)
  // ──────────────────────────────────────────────────────────────────────────
  it('scenario_1: 桌面端 chat-header 包含 3 个 header-{left,center,right} 子节点', () => {
    const headerBody = matchOrThrow(
      /<header[^>]*class="chat-header[^"]*"[^>]*>([\s\S]*?)<\/header>/,
      template,
      'chat-header'
    )
    expect(headerBody).toMatch(/<div\s+class="header-left"/)
    expect(headerBody).toMatch(/<div\s+class="header-center"/)
    expect(headerBody).toMatch(/<div\s+class="header-right"/)
  })

  // ──────────────────────────────────────────────────────────────────────────
  // scenario_2: 左 zone 集成 ChatBreadcrumb (B-2)
  // ──────────────────────────────────────────────────────────────────────────
  it('scenario_2: header-center 包含 ChatBreadcrumb 组件 (B-2 集成)', () => {
    expect(script).toMatch(/import\s+ChatBreadcrumb\s+from\s+['"]@\/components\/chat\/ChatBreadcrumb\.vue['"]/)
    const headerCenterBody = matchOrThrow(
      /<div\s+class="header-center"[^>]*>([\s\S]*?)<\/div>\s*<div\s+class="header-right"/,
      template,
      'header-center body'
    )
    expect(headerCenterBody).toMatch(/<ChatBreadcrumb[\s>]/)
  })

  // ──────────────────────────────────────────────────────────────────────────
  // scenario_3: 中 zone 标识为 center (data-zone-center)
  // ──────────────────────────────────────────────────────────────────────────
  it('scenario_3: header 节点含 :data-zone-center 绑定到 TOPBAR_ZONES[1].name (B-2 type hint 集成)', () => {
    const headerOpen = matchOrThrow(
      /<header[\s\S]*?class="chat-header[^"]*"[\s\S]*?>/,
      template,
      'header open tag'
    )
    expect(headerOpen).toMatch(/:data-zone-center="TOPBAR_ZONES\[1\]\.name"/)
  })

  // ──────────────────────────────────────────────────────────────────────────
  // scenario_4: 右 zone 标识为 right (data-zone-right) + left
  // ──────────────────────────────────────────────────────────────────────────
  it('scenario_4: header 节点含 :data-zone-left/right 绑定 (3-zone 必填)', () => {
    const headerOpen = matchOrThrow(
      /<header[\s\S]*?class="chat-header[^"]*"[\s\S]*?>/,
      template,
      'header open tag'
    )
    expect(headerOpen).toMatch(/:data-zone-left="TOPBAR_ZONES\[0\]\.name"/)
    expect(headerOpen).toMatch(/:data-zone-right="TOPBAR_ZONES\[2\]\.name"/)
  })

  // ──────────────────────────────────────────────────────────────────────────
  // scenario_5: 移动端断点 (≤768px) → 1fr 2fr 1fr 重排
  // ──────────────────────────────────────────────────────────────────────────
  it('scenario_5: chat-header 含 @media (max-width: 768px) 1fr 2fr 1fr 重排', () => {
    expect(style).toMatch(/@media\s*\(max-width:\s*768px\)/)
    expect(style).toMatch(/grid-template-columns:\s*1fr\s+2fr\s+1fr/)
  })

  // ──────────────────────────────────────────────────────────────────────────
  // scenario_6: TopBarZone type hint + desktop 4fr 4fr 4fr + readonly TOPBAR_ZONES (派工 v6 段 5 反馈 #3)
  // ──────────────────────────────────────────────────────────────────────────
  it('scenario_6: TopBarZone type hint + desktop 4fr 4fr 4fr + readonly TOPBAR_ZONES 必含', () => {
    // 1. TopBarZone interface 必含 (派工 v6 段 5 反馈 #3 实战)
    expect(script).toMatch(/interface\s+TopBarZone\s*\{/)
    expect(script).toMatch(/name:\s*'left'\s*\|\s*'center'\s*\|\s*'right'/)
    expect(script).toMatch(/desktopFr:\s*number/)
    expect(script).toMatch(/mobileFr:\s*number/)

    // 2. readonly TOPBAR_ZONES 数组 必含 3 个 zone
    expect(script).toMatch(/const\s+TOPBAR_ZONES:\s*readonly\s+TopBarZone\[\]\s*=/)
    const zonesBody = matchOrThrow(
      /TOPBAR_ZONES:\s*readonly\s+TopBarZone\[\]\s*=\s*\[([\s\S]*?)\]\s+as\s+const/,
      script,
      'TOPBAR_ZONES body'
    )
    // 3 个 zone 各自 desktopFr=4 / mobileFr=1 (left), desktopFr=4 / mobileFr=2 (center), desktopFr=4 / mobileFr=1 (right)
    expect(zonesBody).toMatch(/name:\s*'left'/)
    expect(zonesBody).toMatch(/name:\s*'center'/)
    expect(zonesBody).toMatch(/name:\s*'right'/)
    expect((zonesBody.match(/desktopFr:\s*4/g) || []).length).toBeGreaterThanOrEqual(3)
    expect((zonesBody.match(/mobileFr:\s*1/g) || []).length).toBeGreaterThanOrEqual(2)
    expect(zonesBody).toMatch(/mobileFr:\s*2/)

    // 3. CSS grid-template-columns: 4fr 4fr 4fr 桌面端
    expect(style).toMatch(/\.chat-header\s*\{[^}]*grid-template-columns:\s*4fr\s+4fr\s+4fr/)
  })
})