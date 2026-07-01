/**
 * tests/visual/desktop/grade-tag-extension-2026-07-01.spec.mjs
 *
 * v78 阶段 1 验证: 成员 card chip 扩展修复 (.member-info .el-tag + .hero-tags .el-tag 主色实色升级)
 *
 * 覆盖:
 *   P0-1: 桌面 /members 成员卡 grade + role chip 是主色实色 + 白字 + font-weight 600
 *   P0-2: 移动 /members/{name} hero-tags 同样升级
 *   同时验证 6 主题 (orange/ocean/forest × light/dark) 自动切换背景色
 *
 * 不写 baseline 对比 — 用 evaluate() 拿 computed style 精确断言颜色, 比 toHaveScreenshot 更稳定
 *
 * 运行:
 *   BASE_URL=http://localhost:3000 \
 *   TEST_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
 *     -H "Content-Type: application/json" \
 *     -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
 *     | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])") \
 *     npx playwright test tests/visual/desktop/grade-tag-extension-2026-07-01.spec.mjs --project=desktop-chrome
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000'
const TEST_TOKEN = process.env.TEST_TOKEN || ''

// 6 主题 (light/dark × orange/ocean/forest) — 主题颜色预期
const THEMES = [
  { name: 'light-orange', theme: 'light', accent: 'orange', rgb: '255, 122, 92', darkRgb: '255, 122, 92' },
  { name: 'light-ocean',  theme: 'light', accent: 'ocean',  rgb: '74, 144, 226', darkRgb: '74, 144, 226' },
  { name: 'light-forest', theme: 'light', accent: 'forest', rgb: '76, 175, 80',  darkRgb: '76, 175, 80' },
  { name: 'dark-orange',  theme: 'dark',  accent: 'orange', rgb: '255, 157, 133', darkRgb: '255, 157, 133' },
  { name: 'dark-ocean',   theme: 'dark',  accent: 'ocean',  rgb: '107, 171, 255', darkRgb: '107, 171, 255' },
  { name: 'dark-forest',  theme: 'dark',  accent: 'forest', rgb: '102, 187, 106', darkRgb: '102, 187, 106' },
]

async function setupPage(page, { theme, accent }) {
  // 双注入: cookie + localStorage
  await page.context().addCookies([{
    name: 'access_token',
    value: TEST_TOKEN,
    domain: new URL(BASE_URL).hostname,
    path: '/',
  }])
  await page.addInitScript((data) => {
    localStorage.setItem('access_token', data.token)
    localStorage.setItem('theme', data.theme)
    localStorage.setItem('accent', data.accent)
  }, { token: TEST_TOKEN, theme, accent })
  // 首次访问强制设主题
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' })
  await page.evaluate(([t, a]) => {
    localStorage.setItem('theme', t)
    localStorage.setItem('accent', a)
    document.documentElement.setAttribute('data-theme', t)
    document.documentElement.setAttribute('data-accent', a)
  }, [theme, accent])
}

// 拿 .member-info 内第一个 el-tag 的 computed style (grade 或 role chip)
async function getChipStyle(page, selector) {
  return await page.evaluate((sel) => {
    const el = document.querySelector(sel)
    if (!el) return null
    const cs = getComputedStyle(el)
    return {
      bg: cs.backgroundColor,
      color: cs.color,
      fontWeight: cs.fontWeight,
      borderColor: cs.borderColor,
      text: el.textContent.trim().slice(0, 12),
    }
  }, selector)
}

// 把 "rgb(255, 122, 92)" 解析为 RGB 数组, 用于字符串匹配
function parseRgb(rgbStr) {
  const m = rgbStr.match(/rgba?\(([^)]+)\)/)
  if (!m) return null
  return m[1].split(',').map(s => parseInt(s.trim(), 10))
}

test.describe('v78 Step 1: 成员 card chip 主色实色 + 白字', () => {
  test('P0-1: 桌面 /members grade + role chip 6 主题验证', async ({ page }) => {
    const failures = []
    for (const t of THEMES) {
      await setupPage(page, { theme: t.theme, accent: t.accent })
      await page.goto(`${BASE_URL}/members`, { waitUntil: 'networkidle' })
      await page.waitForTimeout(800)

      // 断言 1: <html data-theme> data-accent 已切
      const dataset = await page.evaluate(() => ({
        theme: document.documentElement.dataset.theme,
        accent: document.documentElement.dataset.accent,
      }))
      expect(dataset.theme, `${t.name}: theme`).toBe(t.theme)
      expect(dataset.accent, `${t.name}: accent`).toBe(t.accent)

      // 断言 2: 第一张成员卡 grade chip computed style
      const gradeSel = '.member-card .member-info .el-tag.grade-tag, .member-card .member-info .el-tag'
      const gradeStyle = await getChipStyle(page, gradeSel)
      if (!gradeStyle) {
        failures.push(`${t.name}: 没找到 .member-info .el-tag`)
        continue
      }
      // light: 实色主色, dark: 半透明主色 (rgba 0.55)
      const expectedRgb = parseRgb(t.theme === 'dark' ? `rgba(${t.rgb}, 0.55)` : `rgb(${t.rgb})`)
      const actualRgb = parseRgb(gradeStyle.bg)
      const bgMatch = actualRgb && expectedRgb && actualRgb.every((v, i) => Math.abs(v - expectedRgb[i]) < 5)
      if (!bgMatch) {
        failures.push(`${t.name} grade bg: expected rgb(${t.rgb})${t.theme === 'dark' ? ' α 0.55' : ''}, got ${gradeStyle.bg} (text="${gradeStyle.text}")`)
      }

      // 断言 3: 文字白色 (rgb 255,255,255)
      if (!gradeStyle.color.includes('255, 255, 255')) {
        failures.push(`${t.name} grade color: expected rgb(255, 255, 255), got ${gradeStyle.color} (text="${gradeStyle.text}")`)
      }

      // 断言 4: font-weight 600
      if (gradeStyle.fontWeight !== '600') {
        failures.push(`${t.name} grade font-weight: expected 600, got ${gradeStyle.fontWeight}`)
      }
    }
    if (failures.length) {
      console.error('P0-1 failures:\n' + failures.map(f => ' - ' + f).join('\n'))
    }
    expect(failures, `P0-1 桌面 /members ${failures.length} 处失败:\n${failures.join('\n')}`).toHaveLength(0)
  })

  // 简化移动测试: 默认 theme/orange 已切 dark 时验证 hero-tags (mobile 路由只测一主题组合)
  test('P0-2: 移动 /members/{name} hero-tags role chip (orange/light)', async ({ page, browser }) => {
    // 模拟移动 viewport
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 3,
      isMobile: true,
      hasTouch: true,
    })
    const page2 = await ctx.newPage()
    await setupPage(page2, { theme: 'light', accent: 'orange' })
    await page2.goto(`${BASE_URL}/members`, { waitUntil: 'networkidle' })
    await page2.waitForTimeout(800)
    // 拿到第一个成员 id, 跳转详情
    const memberId = await page2.evaluate(() => {
      const link = document.querySelector('.member-card a[href*="/members/"]')
      if (link) return link.getAttribute('href')
      // 试着找任意 members/N
      const any = document.querySelector('a[href*="/members/"]')
      return any ? any.getAttribute('href') : null
    })
    if (!memberId) {
      test.skip(true, '没找到成员详情链接')
      return
    }
    await page2.goto(`${BASE_URL}${memberId}`, { waitUntil: 'networkidle' })
    await page2.waitForTimeout(800)

    // 断言 1: hero-tags 第一个 el-tag (role chip) 主色实色
    const heroStyle = await getChipStyle(page2, '.hero-tags > .el-tag:not(.voice-tag)')
    if (!heroStyle) {
      test.skip(true, 'mobile detail 页没渲染 hero-tags (可能 mock data 缺)')
      return
    }
    const expectedRgb = parseRgb('rgb(255, 122, 92)')
    const actualRgb = parseRgb(heroStyle.bg)
    const bgMatch = actualRgb && expectedRgb && actualRgb.every((v, i) => Math.abs(v - expectedRgb[i]) < 5)
    if (!bgMatch) {
      throw new Error(`mobile hero role chip bg expected rgb(255, 122, 92), got ${heroStyle.bg} (text="${heroStyle.text}")`)
    }
    if (!heroStyle.color.includes('255, 255, 255')) {
      throw new Error(`mobile hero role chip color expected white, got ${heroStyle.color}`)
    }
    if (heroStyle.fontWeight !== '600') {
      throw new Error(`mobile hero role chip font-weight expected 600, got ${heroStyle.fontWeight}`)
    }

    // 断言 2: voice-tag (如果存在) 仍走 success/warning (排除规则生效)
    const voiceStyle = await getChipStyle(page2, '.hero-tags .voice-tag')
    if (voiceStyle) {
      // voice 应该 *不是* 主色实色 — 是 EP success 绿 / warning 黄
      const voiceRgb = parseRgb(voiceStyle.bg)
      const primaryRgb = parseRgb('rgb(255, 122, 92)')
      const sameAsPrimary = voiceRgb && primaryRgb && voiceRgb.every((v, i) => Math.abs(v - primaryRgb[i]) < 5)
      if (sameAsPrimary) {
        throw new Error(`voice-tag 被强制覆盖成主色 — :not(.voice-tag) 排除规则没生效. 实际 bg=${voiceStyle.bg} (text="${voiceStyle.text}")`)
      }
      console.log(`P0-2 voice-tag 排除 OK: bg=${voiceStyle.bg} text="${voiceStyle.text}"`)
    } else {
      console.log('P0-2 voice-tag 在当前 mock 数据中不存在 (该成员 voice_enrolled_at 为空), 排除规则未实测')
    }
  })

  // Step 2 P0-3: SettingsView "角色" chip 主色实色
  test('P0-3: SettingsView 角色 chip 主色实色 (orange/light)', async ({ page }) => {
    await setupPage(page, { theme: 'light', accent: 'orange' })
    await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(800)

    const roleTagStyle = await page.evaluate(() => {
      const el = document.querySelector('.el-form .role-tag')
      if (!el) return null
      const cs = getComputedStyle(el)
      return {
        bg: cs.backgroundColor,
        color: cs.color,
        fontWeight: cs.fontWeight,
        text: el.textContent.trim().slice(0, 12),
      }
    })
    if (!roleTagStyle) {
      test.skip(true, 'SettingsView 没渲染 .role-tag (可能用户 admin role 或 form 未加载)')
      return
    }
    const expectedRgb = parseRgb('rgb(255, 122, 92)')
    const actualRgb = parseRgb(roleTagStyle.bg)
    const bgMatch = actualRgb && expectedRgb && actualRgb.every((v, i) => Math.abs(v - expectedRgb[i]) < 5)
    if (!bgMatch) {
      throw new Error(`SettingsView .role-tag bg expected rgb(255, 122, 92), got ${roleTagStyle.bg} (text="${roleTagStyle.text}")`)
    }
    if (!roleTagStyle.color.includes('255, 255, 255')) {
      throw new Error(`SettingsView .role-tag color expected white, got ${roleTagStyle.color}`)
    }
    if (roleTagStyle.fontWeight !== '600') {
      throw new Error(`SettingsView .role-tag font-weight expected 600, got ${roleTagStyle.fontWeight}`)
    }
  })

  // Step 3 P0-4: .role--member 视觉权重重齐 font-weight: 600
  // 用 Stylesheet API 直接读规则 — 不依赖 MemberCardBlock 是否真渲染
  test('P0-4: .role--member font-weight 600 (像 admin/leader 一样视觉权重重齐)', async ({ page }) => {
    await setupPage(page, { theme: 'light', accent: 'orange' })
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' })

    // 注入临时 DOM 元素测 computed style (不依赖业务组件渲染)
    await page.evaluate(() => {
      const el = document.createElement('span')
      el.className = 'role role--member'
      el.id = 'p0-4-probe'
      document.body.appendChild(el)
    })

    const fontWeight = await page.evaluate(() => {
      const el = document.getElementById('p0-4-probe')
      return getComputedStyle(el).fontWeight
    })

    // 也从 stylesheet API 拿到源规则确认
    const cssText = await page.evaluate(() => {
      const text = '.role--member{color:var(--color-text-secondary);font-weight:600}'
      // 该字符串就是 dist/css 里编译产物的关键内容, 用 specificity + selectorText 验
      for (const sheet of document.styleSheets) {
        try {
          for (const rule of sheet.cssRules) {
            if (rule.selectorText && rule.selectorText.includes('.role--member') && !rule.selectorText.includes('member-card')) {
              return rule.cssText
            }
          }
        } catch (e) {}
      }
      return null
    })
    console.log(`P0-4 stylesheet API 找到 .role--member 规则: ${cssText}`)

    if (fontWeight !== '600') {
      throw new Error(`.role--member font-weight expected 600, got ${fontWeight}. stylesheet rule: ${cssText}`)
    }
    // 编译后的 cssText 是 "font-weight: 600" (minify 后空格可能保留)
    if (!cssText || !/\bfont-weight:\s*600\b/.test(cssText)) {
      throw new Error(`stylesheet .role--member 规则没找到 / 不含 font-weight: 600. cssText: ${cssText}`)
    }
  })
})
