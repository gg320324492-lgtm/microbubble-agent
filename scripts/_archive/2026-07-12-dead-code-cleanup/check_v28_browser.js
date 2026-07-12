/**
 * v28 Regression Check — 浏览器控制台回归脚本
 *
 * 用法：
 *   1. 打开任一 PDF 详情页（如 https://agent.mnb-lab.cn/knowledge/19）
 *   2. F12 打开 DevTools → Console 标签
 *   3. 复制本文件全部内容，粘贴到 Console，回车
 *   4. 默认检测 knowledgeId=19（甲苯论文，v28 端到端验证 PDF）
 *      想测其他论文：v28RegressionCheck(14)  // 14 = δ-MnO2 中文论文
 *
 * 输出：✅ PASS / ❌ FAIL / ⚠️ WARN 三大状态 + 总览
 *
 * 检查维度：
 *   1. 后端 API: 12 个 v28 字段是否返回（vision 模型输出持久化）
 *   2. is_publisher_image 准确度（Logo/期刊封面识别）
 *   3. vision_confidence 分布（>= 0.85 为高置信度）
 *   4. figure_no 覆盖率（已知 vision 模型看不到图外 caption）
 *   5. anchor 完整性（含中文 "图 N" 修复）
 *   6. ReadingToolbar confidence 徽章（v28 step 6）
 *   7. RightImageRail 渲染（v28 step 5 currentSectionFigures）
 *   8. Sections DOM（v28 step 8 IO 监听目标）
 *   9. Hysteresis 算法 4 个 case（v28 step 8 防跳变）
 *
 * 预期：7 PASS / 0 FAIL / 1 WARN（ReadingToolbar 徽章未点 📷 按钮时 WARN）
 */
(async function v28RegressionCheck(knowledgeId = 19) {
  console.log('%c🔍 v28 Regression Check v2 (kid=' + knowledgeId + ')', 'background:#FF7A5C;color:#fff;padding:4px 8px;border-radius:4px;font-weight:bold')
  console.log('')

  const results = []
  const pass = (n, d) => { results.push({n, s: '✅', d}); console.log(`%c✅ ${n}`, 'color:#10B981;font-weight:bold', '—', d) }
  const fail = (n, d) => { results.push({n, s: '❌', d}); console.log(`%c❌ ${n}`, 'color:#EF4444;font-weight:bold', '—', d) }
  const warn = (n, d) => { results.push({n, s: '⚠️', d}); console.log(`%c⚠️ ${n}`, 'color:#F59E0B;font-weight:bold', '—', d) }

  // ── Check 1: 后端 API 12 v28 字段（修复 401：用 localStorage.access_token）──
  try {
    const token = localStorage.getItem('access_token') || ''
    const resp = await fetch(`/api/v1/knowledge/${knowledgeId}/images`, {
      headers: { 'Authorization': `Bearer ${token}` },
      credentials: 'include'
    })
    if (!resp.ok) { fail('API reachable', `HTTP ${resp.status}（检查 token 是否过期）`); return summarize(results) }
    const data = await resp.json()
    if (!data.items || !data.items.length) { fail('API has images', '0 images'); return summarize(results) }

    const v28Fields = ['figure_no','figure_type','is_core_figure','is_publisher_image',
                       'is_supporting_figure','section_hint','visual_summary',
                       'anchor_paragraph_index','anchor_text','vision_confidence',
                       'vision_model_used','vision_analyzed_at']
    const missing = v28Fields.filter(f => !(f in data.items[0]))
    if (missing.length === 0) pass('API 12 v28 fields', `${data.items.length} images, 全部 12 字段 present`)
    else fail('API 12 v28 fields', `missing: ${missing.join(', ')}`)

    // publisher 准确度
    const pubs = data.items.filter(i => i.is_publisher_image === true)
    const pubsKw = pubs.filter(i => /elsevier|springer|wiley|journal of|issn/i.test(i.ocr_text || ''))
    const pubAcc = pubs.length ? (pubsKw.length / pubs.length * 100).toFixed(0) : 100
    pubAcc >= 90 ? pass('is_publisher_image 准确度', `${pubAcc}% (${pubsKw.length}/${pubs.length})`) : fail('is_publisher_image 准确度', pubAcc + '%')

    // confidence
    const confs = data.items.map(i => i.vision_confidence).filter(c => c != null)
    const minC = Math.min(...confs), maxC = Math.max(...confs)
    const meanC = confs.reduce((a,b) => a+b, 0) / confs.length
    meanC >= 0.85 ? pass('vision_confidence', `mean=${meanC.toFixed(2)} min=${minC.toFixed(2)} max=${maxC.toFixed(2)} (${confs.length})`) : fail('vision_confidence', `mean=${meanC.toFixed(2)}`)

    // figure_no
    const cov = data.items.filter(i => i.figure_no).length / data.items.length
    cov >= 0.15 ? pass('figure_no 覆盖率', `${(cov*100).toFixed(0)}%`) : warn('figure_no 覆盖率', `${(cov*100).toFixed(0)}% (<15%)`)

    // anchor
    const withNo = data.items.filter(i => i.figure_no)
    const withAnch = withNo.filter(i => i.anchor_text && i.anchor_paragraph_index != null)
    withNo.length === 0 || withAnch.length === withNo.length
      ? pass('anchor 完整性', `${withAnch.length}/${withNo.length}`)
      : fail('anchor 完整性', `${withAnch.length}/${withNo.length} 缺失`)
  } catch (e) {
    fail('API check', e.message)
  }

  // ── Check 2-3: DOM 检查 ──
  const badge = document.querySelector('.confidence-badge')
  if (badge) {
    const pct = parseInt(badge.textContent)
    pct >= 85 ? pass('ReadingToolbar 徽章', `${pct}%`) : warn('ReadingToolbar 徽章', `${pct}%`)
  } else {
    warn('ReadingToolbar 徽章', '未显示（需先点工具栏 📷 按钮开启内嵌图）')
  }

  const railItems = document.querySelectorAll('.right-image-rail .rail-item')
  railItems.length > 0
    ? pass('RightImageRail 渲染', `${railItems.length} 张图`)
    : fail('RightImageRail 渲染', '0 张图')

  // ── Check 4: Sections + scroll 工具 ──
  const sections = document.querySelectorAll('[id^="section-"]')
  if (sections.length === 0) fail('Sections 渲染', '0 sections')
  else {
    pass('Sections 渲染', `${sections.length} 个 section`)
    console.log('')
    console.log('%c💡 手动测试：', 'color:#6366F1;font-weight:bold')
    window.v28ScrollToSection = (id) => {
      const el = document.getElementById('section-' + id)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      else console.warn('Section not found:', id)
    }
    console.log('   试试: v28ScrollToSection("' + sections[0].id.replace('section-','') + '")')
    console.log('   滚到 Results/Discussion/Conclusion 看 RightImageRail 是否切换')
  }

  // ── Check 5: Hysteresis 算法（v28 step 8 防跳变）──
  console.log('')
  console.log('%c🔬 Hysteresis 算法验证', 'color:#6366F1;font-weight:bold')
  const ACT = 0.35, LOW = 0.15
  const _rec = (cur, m) => {
    if (!m.size) return cur
    const c = cur, cr = m.get(c) || 0
    if (c && cr >= LOW) {
      let bid = c, br = cr
      for (const [k,v] of m) if (v > br) { br=v; bid=k }
      return (bid !== c && br >= ACT) ? bid : c
    }
    let bid=null, br=0
    for (const [k,v] of m) if (v > br) { br=v; bid=k }
    if (bid && br >= ACT) return bid
    if (br === 0 && c) return ''
    return c
  }
  const cases = [
    ['', new Map([['s1',0.1],['s2',0.6],['s3',0]]), 's2', '初次 sec2=60%'],
    ['s2', new Map([['s1',0.05],['s2',0.30],['s3',0.20]]), 's2', '快速滚动 sec2=30/sec3=20'],
    ['s2', new Map([['s1',0],['s2',0.10],['s3',0.50]]), 's3', 'sec2<15% 让位'],
    ['s3', new Map([['s1',0],['s2',0],['s3',0]]), '', '全 0 清空'],
  ]
  cases.forEach(([cur, m, exp, desc], i) => {
    const got = _rec(cur, m)
    const ok = got === exp
    console.log(`  ${ok ? '✅' : '❌'} Case ${i+1} ${desc} → "${got}"`)
  })

  // ── 总结（修复 summarize bug）──
  function summarize(rs) {
    console.log('')
    console.log('%c═══════════════════════════════════════════════════════════', 'color:#FF7A5C')
    console.log('%c📊 总览', 'background:#FF7A5C;color:#fff;padding:4px 8px;border-radius:4px;font-weight:bold')
    rs.forEach(r => console.log(`  ${r.s} ${r.n}: ${r.d}`))
    const p = rs.filter(r => r.s === '✅').length
    const f = rs.filter(r => r.s === '❌').length
    const w = rs.filter(r => r.s === '⚠️').length
    console.log('')
    console.log(`%c总计: ${p} PASS / ${f} FAIL / ${w} WARN`, f === 0 ? 'color:#10B981;font-weight:bold;font-size:14px' : 'color:#EF4444;font-weight:bold;font-size:14px')
    return {passed: p, failed: f, warned: w, results: rs}
  }
  return summarize(results)
})()