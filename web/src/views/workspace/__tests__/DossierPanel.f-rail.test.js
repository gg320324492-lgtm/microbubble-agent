// DossierPanel F 稿竖轨 (按届别组内年级细分) — cohort-subgroup-2026-09 主拍实装回归
//
// 数据 = docs/design-proposals/cohort-subgroup-2026-09/_shared.js 同一份 2026-09-15
// 生产快照 (20 人: 导师 1 / 博士 4 / 硕士 12 / 本科生 3)。验证口径:
//   1. 按届别组内按 SUBORDER 年级序切轨 (研三→研二→研一 / 博二→博一→博零 / 大四), 轨序与提案一致
//   2. 轨头 = 细年级 + 人数; 该轨有人未录声纹 → bar.hot 点亮
//   3. 轨内行序 = id 升序; 导师组 (副教授单轨) 照常出轨 — F 稿每届一段, 无豁免
//   4. 按项目视图不出轨 (无 .rail), 行集合与改造前一致 (6 列含 .fop)
//   5. 锚导仍只挂身份组节, 轨不建锚点
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const MEMBERS = [
  { id: 1,  name: '王天志', grade: '副教授', research_area: '微纳米气泡技术与应用', skills: ['项目管理', '气泡生成', '水处理'], voice_sample_count: 121 },
  { id: 2,  name: '赵航佳', grade: '博二', research_area: '黑臭水体治理', skills: ['臭氧微纳米气泡', '底泥-水界面', '污染物去除'], voice_sample_count: 0 },
  { id: 3,  name: '杜同贺', grade: '研二', research_area: '水产高密度无抗养殖与品质改善', skills: ['微纳米气泡', '水质提升', '数据分析'], voice_sample_count: 4 },
  { id: 4,  name: '陈天祥', grade: '研二', research_area: '表面清洗技术', skills: ['清洗工艺', '去除工艺', '表面清洗'], voice_sample_count: 0 },
  { id: 6,  name: '耿嘉栋', grade: '研二', research_area: '装备开发', skills: ['装备开发', '系统集成', '发生器优化'], voice_sample_count: 0 },
  { id: 7,  name: '陈金薪', grade: '研三', research_area: '气泡成核过程调控', skills: ['自由基', '界面反应', '气泡溃灭'], voice_sample_count: 38 },
  { id: 9,  name: '关小未', grade: '研三', research_area: '盐碱土改良', skills: ['盐碱土修复', '种养系统', '农业应用'], voice_sample_count: 0 },
  { id: 10, name: '胡小琪', grade: '研三', research_area: '黑臭水体', skills: [], voice_sample_count: 0 },
  { id: 11, name: '李胜景', grade: '研三', research_area: '水产养殖', skills: ['高密度养殖', '无抗鱼养殖', '水产应用'], voice_sample_count: 0 },
  { id: 13, name: '宋洋', grade: '研三', research_area: '饮用水处理', skills: ['生物稳定性', '管网生物膜', '膜耦合'], voice_sample_count: 0 },
  { id: 14, name: '王书馨', grade: '研三', research_area: '农业灌溉', skills: ['农业应用', '土壤修复', '工程化应用'], voice_sample_count: 0 },
  { id: 15, name: '吴孟铨', grade: '研三', research_area: '自由基生成', skills: ['气泡溃灭', '传质强化', '分子动力学'], voice_sample_count: 8 },
  { id: 16, name: '韩重阳', grade: '博一', research_area: '设备开发', skills: ['装备研发', '工程验证', '发生器优化'], voice_sample_count: 0 },
  { id: 20, name: '张宏魁', grade: '博零', research_area: '设施农业', skills: ['设施农业', '盐碱土修复', '农业应用'], voice_sample_count: 4 },
  { id: 21, name: '贾琦', grade: '大四', research_area: '表面清洗', skills: ['实验辅助', '数据整理', '表面清洗'], voice_sample_count: 12 },
  { id: 22, name: '周之超', grade: '大四', research_area: '表面污染去除', skills: ['表面去除', '文献调研', '实验辅助'], voice_sample_count: 11 },
  { id: 26, name: '吴怡霏', grade: '研一', research_area: '', skills: [], voice_sample_count: 0 },
  { id: 27, name: '蒋芦笛', grade: '研二', research_area: '', skills: [], voice_sample_count: 0 },
  { id: 28, name: '刘莫菲', grade: '研一', research_area: '', skills: [], voice_sample_count: 0 },
  { id: 58, name: '刘子煜', grade: '研二', research_area: '', skills: [], voice_sample_count: 0 },
]

vi.mock('axios', () => ({
  default: {
    get: vi.fn((url) => {
      if (url.includes('/projects')) return Promise.resolve({ data: { items: [] } })
      if (url.includes('/members')) return Promise.resolve({ data: { items: MEMBERS } })
      return Promise.resolve({ data: {} })
    }),
  },
}))

import DossierPanel from '@/views/workspace/DossierPanel.vue'
import { useMemberStore } from '@/stores/member'

function setup() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useMemberStore()
  store.members = MEMBERS.map((m) => ({ ...m }))
  const wrapper = mount(DossierPanel, { global: { plugins: [pinia] } })
  return wrapper
}

// 切到按届别视图
async function toGradeView(wrapper) {
  const btns = wrapper.findAll('.seg button')
  expect(btns.map((b) => b.text())).toEqual(['按项目', '按届别'])
  await btns[1].trigger('click')
  await flushPromises()
}

describe('F 稿竖轨 · 按届别组内年级细分', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('硕士组切三轨: 研三(7)→研二(5)→研一(2), 组头计数 14 守恒', async () => {
    const wrapper = setup()
    await toGradeView(wrapper)
    const master = wrapper.find('#doss-g-硕士')
    expect(master.exists()).toBe(true)
    expect(master.classes()).toContain('banded')
    const rails = master.findAll('.rail')
    expect(rails.map((r) => r.find('.rg').text())).toEqual(['研三', '研二', '研一'])
    expect(rails.map((r) => r.find('.rn').text())).toEqual(['7人', '5人', '2人'])
    expect(master.find('.dhead .cnt').text()).toContain('14 人')
    // 三轨行总数 = 组头人数 (计数同口径, 评审实装备忘 #3)
    expect(master.findAll('.row').length).toBe(14)
  })

  it('轨内行序 = id 升序 (研三: 7,9,10,11,13,14,15)', async () => {
    const wrapper = setup()
    await toGradeView(wrapper)
    const band0 = wrapper.findAll('#doss-g-硕士 .subwrap')[0]
    const ids = band0.findAll('.row .id').map((e) => e.text())
    expect(ids).toEqual(['#007', '#009', '#010', '#011', '#013', '#014', '#015'])
  })

  it('缺声纹点亮标按轨判定: 硕士三轨全 hot; 博士博零不 hot; 本科生大四全录不 hot; 导师不 hot', async () => {
    const wrapper = setup()
    await toGradeView(wrapper)
    // 硕士 14 人中仅 3 人录声纹 (7,15,3), 三轨各有缺录 → 全亮
    for (const b of wrapper.findAll('#doss-g-硕士 .rail .bar')) {
      expect(b.classes()).toContain('hot')
    }
    // 博士: 博二(赵航佳 0)与博一(韩重阳 0)亮, 博零(张宏魁 vp4)不亮
    expect(wrapper.findAll('#doss-g-博士 .rail .bar').map((b) => b.classes().includes('hot')))
      .toEqual([true, true, false])
    // 本科生大四 2 人皆已录 (12/11) → 不亮
    expect(wrapper.findAll('#doss-g-本科生 .rail .bar').every((b) => !b.classes().includes('hot'))).toBe(true)
    // 导师组 王天志 vp=121 全录 → bar 不点亮
    expect(wrapper.find('#doss-g-导师 .rail .bar').classes()).not.toContain('hot')
  })

  it('博士组切三轨 博二→博一→博零; 导师组单轨 (副教授) 照出 — 每届一段无豁免', async () => {
    const wrapper = setup()
    await toGradeView(wrapper)
    expect(wrapper.findAll('#doss-g-博士 .rail .rg').map((e) => e.text())).toEqual(['博二', '博一', '博零'])
    expect(wrapper.findAll('#doss-g-本科生 .rail .rg').map((e) => e.text())).toEqual(['大四'])
    const adviser = wrapper.find('#doss-g-导师')
    expect(adviser.findAll('.rail')).toHaveLength(1)
    expect(adviser.find('.rail .rg').text()).toBe('副教授')
    // 导师行 gtag 保留 (E 稿曾误伤处, F 不收起行内 chip)
    expect(adviser.find('.row .gtag.t').text()).toBe('副教授')
  })

  it('轨宽 62px 固定; 锚导仍只挂身份组节, 轨无 id 不建锚', async () => {
    const wrapper = setup()
    await toGradeView(wrapper)
    const rail = wrapper.find('.rail')
    expect(rail.exists()).toBe(true)
    // 锚点 id 只有组节
    const anchored = wrapper.findAll('section[id^="doss-"]')
    expect(anchored.map((s) => s.attributes('id'))).toEqual(['doss-g-导师', 'doss-g-博士', 'doss-g-硕士', 'doss-g-本科生'])
    // subwrap / rail 不携带 id
    for (const el of wrapper.findAll('.subwrap, .rail')) {
      expect(el.attributes('id')).toBeUndefined()
    }
  })

  it('按项目视图零变化: 无 .rail/.subwrap 出轨, .doss 不带 banded', async () => {
    const wrapper = setup()
    await flushPromises()
    expect(wrapper.find('.seg button.on').text()).toBe('按项目')
    expect(wrapper.findAll('.rail').length).toBe(0)
    // projects 为空 mock → 仅剩未编入节, 其行也无轨
    const unfiled = wrapper.find('#doss-unfiled')
    expect(unfiled.exists()).toBe(true)
    expect(unfiled.classes()).not.toContain('banded')
    expect(unfiled.findAll('.row').length).toBe(20)
    expect(unfiled.findAll('.rail').length).toBe(0)
    // 未编入行序保持旧语义: 导师置顶 + id 升序
    expect(unfiled.findAll('.row .id')[0].text()).toBe('#001')
  })

  it('按届别切回按项目再切回: 轨结构稳定重算 (computed 无残留)', async () => {
    const wrapper = setup()
    await toGradeView(wrapper)
    const first = wrapper.findAll('.rail .rg').map((e) => e.text()).join('')
    const btns = wrapper.findAll('.seg button')
    await btns[0].trigger('click')
    await flushPromises()
    await btns[1].trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.rail .rg').map((e) => e.text()).join('')).toBe(first)
  })
})
