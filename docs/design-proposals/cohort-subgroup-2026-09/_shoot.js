const { chromium } = require('playwright')
;(async () => {
  const dir = 'E:/microbubble-agent/docs/design-proposals/cohort-subgroup-2026-09'
  const b = await chromium.launch({ channel: 'msedge' })
  const pg = await b.newPage({ viewport: { width: 1120, height: 1050 }, deviceScaleFactor: 1.5 })
  for (const [file, letter] of [['E-subband','E'],['F-rail','F'],['G-chips','G'],['H-tone','H'],['I-fold','I']]) {
    await pg.goto('file:///' + dir + '/' + file + '.html')
    await pg.waitForTimeout(300)
    await pg.screenshot({ path: dir + '/shot-' + letter + '.png', clip: { x: 0, y: 0, width: 1120, height: 1050 } })
    console.log('shot-' + letter + '.png done')
  }
  await b.close()
})().catch(e => { console.error(e); process.exit(1) })
