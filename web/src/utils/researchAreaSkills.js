// v77 P2.6-D 收官: 成员 skills 字段缺失时的前端 fallback
// 数据源: scripts/init_db.py 23 个真实成员的 research_area → skills 映射
// 未命中映射表时用关键词推断规则

// 23 个真实映射（直接复用 init_db.py 种子数据）
export const RESEARCH_AREA_SKILLS = {
  '微纳米气泡技术与应用': ['气泡生成', '水处理', '技术产业化'],
  '黑臭水体治理': ['臭氧微纳米气泡', '底泥-水界面', '污染物去除'],
  '污染控制与水质提升': ['微纳米气泡', '水质提升', '数据分析'],
  '表面清洗技术': ['清洗工艺', '去除工艺', '表面清洗'],
  '智能化运行': ['发生器优化', '在线监测', '过程控制'],
  '装备开发': ['装备开发', '系统集成', '发生器优化'],
  '气泡成核过程调控': ['自由基', '界面反应', '气泡溃灭'],
  '鱼菜共生': ['鱼菜共生', '水产养殖', '农业应用'],
  '臭氧微纳米气泡对黑臭水体泥/水界面微生境修复机理研究': ['消毒/抑菌', '微生物控制', '臭氧气泡'],
  '水产养殖': ['高密度养殖', '无抗鱼养殖', '水产应用'],
  '水质评价': ['过程评价', '数据分析', '水质提升'],
  '饮用水处理': ['生物稳定性', '管网生物膜', '膜耦合'],
  '农业灌溉': ['农业应用', '土壤修复', '工程化应用'],
  '自由基生成': ['气泡溃灭', '传质强化', '分子动力学'],
  '设备开发': ['装备研发', '工程验证', '发生器优化'],
  '管网水质': ['生物膜控制', '管网系统', '水质稳定'],
  '饮用水安全': ['饮用水安全', '微生物消杀', '水质监测'],
  '藻华控制': ['藻华控制', '水质净化', '小球藻抑制'],
  '设施农业': ['设施农业', '盐碱土修复', '农业应用'],
  '表面清洗': ['实验辅助', '数据整理', '表面清洗'],
  '表面污染去除': ['表面去除', '文献调研', '实验辅助'],
  '自由基研究': ['实验辅助', '数据分析', '自由基'],
  '微纳米气泡水处理': ['微纳米气泡', '水处理'],
}

// 关键词推断 fallback（用于未命中映射表的新研究方向）
// 顺序敏感：前匹配优先
const KEYWORD_RULES = [
  { kw: ['纳米气泡', '气泡'], skill: '微纳米气泡' },
  { kw: ['水体', '水质', '水处理'], skill: '水处理' },
  { kw: ['养殖', '鱼', '菜'], skill: '水产养殖' },
  { kw: ['农业', '灌溉'], skill: '农业应用' },
  { kw: ['自由基'], skill: '自由基' },
  { kw: ['清洗', '去除'], skill: '表面清洗' },
  { kw: ['管网'], skill: '管网系统' },
  { kw: ['饮用'], skill: '饮用水' },
  { kw: ['装备', '设备'], skill: '装备开发' },
  { kw: ['发生器'], skill: '发生器优化' },
  { kw: ['藻'], skill: '藻华控制' },
  { kw: ['表面'], skill: '表面处理' },
  { kw: ['土壤'], skill: '土壤修复' },
  { kw: ['膜'], skill: '膜分离' },
  { kw: ['消毒', '抑菌', '杀菌'], skill: '消毒/抑菌' },
  { kw: ['数据分析', '分析'], skill: '数据分析' },
]

export function inferSkillsFromArea(researchArea) {
  if (!researchArea || !researchArea.trim()) return ['研究方向待定']
  const area = researchArea.toLowerCase()
  const matches = []
  const seen = new Set()

  for (const rule of KEYWORD_RULES) {
    for (const kw of rule.kw) {
      if (area.includes(kw) && !seen.has(rule.skill)) {
        matches.push(rule.skill)
        seen.add(rule.skill)
        break
      }
      if (matches.length >= 3) break
    }
    if (matches.length >= 3) break
  }

  return matches.length ? matches.slice(0, 3) : [researchArea.slice(0, 6) || '研究方向待定']
}

// 综合函数：先查表 → 命中返回；不命中回退推断
// 限制最多 3 个标签（用户要求"两三个不超卡片边界"）
export function getDisplaySkills(member) {
  const real = member.skills || []
  if (real.length > 0) {
    return real.slice(0, 3)
  }
  // 没录入 skills → 查映射表
  if (member.research_area && RESEARCH_AREA_SKILLS[member.research_area]) {
    return RESEARCH_AREA_SKILLS[member.research_area].slice(0, 3)
  }
  // 都没命中 → 关键词推断
  return inferSkillsFromArea(member.research_area)
}