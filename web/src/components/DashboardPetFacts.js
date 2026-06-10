// DashboardPet 知识库 —— 科研知识、名字、配饰、成就、等级配置

// ===== 科研知识库 =====
export const FACTS = {
  science: [
    '微纳米气泡的 zeta 电位是表征气泡稳定性的重要参数哦~',
    '气泡 collapsing 时产生的羟基自由基可以高效降解有机物~',
    '微纳米气泡在水中的停留时间比普通气泡长 100 倍以上！',
    '臭氧微纳米气泡在水处理中的应用是组里的重点研究方向~',
    '微纳米气泡的粒径分布影响其传质效率和反应活性~',
    '气泡表面的电荷密度决定了气泡之间的聚并行为~',
    '纳米气泡内部压力可达数 MPa，这是它神奇特性的来源~',
    '微纳米气泡技术在水产养殖中能显著提高溶氧量~',
    '气泡的布朗运动在纳米尺度下变得非常显著~',
    'zeta 电位绝对值越高，气泡悬浮液越稳定~',
  ],
  team: [
    '最近组里有新会议记录哦，记得去会议管理页面查看~',
    '知识库又有新文献入库啦，快去看看吧~',
    '组里的小伙伴们最近很活跃呢！',
    '别忘了更新你的实验进度哦~',
    '有新的研究假设等待验证，去知识库看看~',
  ],
  encourage: [
    '每一个完成的任务，都是通向科研巅峰的一步！',
    '微纳米气泡的世界因你而更精彩~',
    '累了就摸摸我，我一直在哦~',
    '今天也是元气满满的一天呢！',
    '你做任务的样子真好看~',
    '科研需要耐心，就像气泡需要时间溶解~',
  ],
  fun: [
    '你知道吗？兔子每秒能眨 3 次眼睛！',
    '猫猫说它最喜欢看你完成任务的样子~',
    '狗狗说今天想看你创建 5 个新任务！',
    '仓鼠已经在跑滚轮了，你快去工作吧！',
  ],
}

// ===== 宠物默认名字 =====
export const PET_NAMES = ['团团', '圆圆', '胖胖', '点点', '花花', '豆豆', '球球', '毛毛', '泡泡', '咪咪', '旺财', '小白']

// ===== 配饰列表 =====
export const ACCESSORIES = [
  { id: 'ribbon', emoji: '🎀', name: '蝴蝶结', xp: 500, type: 'head' },
  { id: 'bell', emoji: '🔔', name: '小铃铛', xp: 1500, type: 'neck' },
  { id: 'hat', emoji: '🎩', name: '小礼帽', xp: 2000, type: 'head' },
  { id: 'crown', emoji: '👑', name: '小皇冠', xp: 3000, type: 'head' },
  { id: 'scarf', emoji: '🧣', name: '小围巾', xp: 4000, type: 'neck' },
  { id: 'glasses', emoji: '🕶️', name: '小墨镜', xp: 6000, type: 'eyes' },
  { id: 'flower', emoji: '🌸', name: '小花', xp: 8000, type: 'head' },
  { id: 'cape', emoji: '🦸', name: '小披风', xp: 10000, type: 'body' },
]

// ===== 成就徽章 =====
export const ACHIEVEMENTS = [
  { id: 'welcome', icon: '⭐', name: '初次见面', desc: '首次登录', check: (d) => true },
  { id: 'task_10', icon: '📝', name: '任务新手', desc: '创建 10 个任务', check: (d) => d.tasks_created >= 10 },
  { id: 'done_50', icon: '🎯', name: '效率达人', desc: '完成 50 个任务', check: (d) => d.tasks_completed >= 50 },
  { id: 'streak_7', icon: '🔥', name: '一周全勤', desc: '连续 7 天登录', check: (d) => d.login_streak >= 7 },
  { id: 'streak_30', icon: '📅', name: '月度之星', desc: '30 天登录', check: (d) => d.login_streak >= 30 },
  { id: 'done_100', icon: '💯', name: '百事通', desc: '完成 100 个任务', check: (d) => d.tasks_completed >= 100 },
  { id: 'done_500', icon: '🏆', name: '任务终结者', desc: '完成 500 个任务', check: (d) => d.tasks_completed >= 500 },
  { id: 'clear_10', icon: '🌟', name: '团队之光', desc: '清零逾期 10 次', check: (d) => d.overdue_clears >= 10 },
  { id: 'level_10', icon: '🐣', name: '猫狗双全', desc: '解锁猫猫 Lv.10', check: (d) => d.level >= 10 },
  { id: 'level_15', icon: '🐾', name: '热闹家族', desc: '解锁狗狗 Lv.15', check: (d) => d.level >= 15 },
  { id: 'level_40', icon: '👑', name: '传奇驯兽师', desc: '达到 Lv.40', check: (d) => d.level >= 40 },
]

// ===== 每日任务模板 =====
export const DAILY_QUESTS = [
  { id: 'create_2', icon: '📝', name: '规划日', desc: '创建 2 个任务', xp: 15, goal: 2, type: 'create' },
  { id: 'done_3', icon: '✅', name: '效率日', desc: '完成 3 个任务', xp: 25, goal: 3, type: 'complete' },
  { id: 'knowledge', icon: '🔍', name: '学习日', desc: '查看知识库', xp: 5, goal: 1, type: 'knowledge' },
  { id: 'meeting', icon: '📅', name: '交流日', desc: '创建或参加会议', xp: 10, goal: 1, type: 'meeting' },
  { id: 'chat', icon: '💬', name: '聊天日', desc: '使用 AI 对话', xp: 10, goal: 1, type: 'chat' },
  { id: 'clear', icon: '🎯', name: '清零日', desc: '清零逾期任务', xp: 40, goal: 1, type: 'clear' },
]

// ===== 个人兔等级配置 =====
export const PERSONAL_LEVELS = [
  { level: 1, xp: 0, pets: 1, stage: 'baby', label: '兔宝' },
  { level: 5, xp: 300, pets: 2, stage: 'growing', label: '小兔' },
  { level: 10, xp: 1200, pets: 3, stage: 'cat', label: '兔+猫' },
  { level: 15, xp: 2500, pets: 4, stage: 'dog', label: '兔+猫+狗' },
  { level: 20, xp: 4500, pets: 5, stage: 'chick', label: '+小鸡' },
  { level: 30, xp: 7000, pets: 6, stage: 'hamster', label: '+仓鼠' },
  { level: 40, xp: 9000, pets: 7, stage: 'legend', label: '传奇' },
]

// ===== 大兔等级配置 =====
export const GROUP_LEVELS = [
  { level: 1, xp: 0, size: 1.5, title: '大兔宝' },
  { level: 10, xp: 8000, size: 1.8, title: '成年大兔' },
  { level: 20, xp: 25000, size: 2.2, title: '精英大兔' },
  { level: 30, xp: 50000, size: 2.6, title: '传奇大兔' },
  { level: 40, xp: 100000, size: 3.0, title: '神话大兔' },
]

// ===== XP 规则 =====
export const XP_RULES = {
  create_task: { personal: 10, group: 5 },
  complete_task: { personal: 30, group: 20 },
  clear_overdue: { personal: 50, group: 100 },
  daily_login: { personal: 5, group: 0 },
  streak_7_bonus: { personal: 20, group: 0 },
}

// ===== 等级计算工具 =====
export function calcLevel(xp, levels) {
  let current = levels[0]
  let next = levels[1] || levels[0]
  for (let i = levels.length - 1; i >= 0; i--) {
    if (xp >= levels[i].xp) {
      current = levels[i]
      next = levels[i + 1] || levels[i]
      break
    }
  }
  const xpInLevel = xp - current.xp
  const xpNeeded = next.xp - current.xp || 1
  return { ...current, progress: Math.min(100, Math.round((xpInLevel / xpNeeded) * 100)), xpToNext: xpNeeded - xpInLevel }
}

// ===== 默认 localStorage 数据 =====
export function defaultPetData() {
  return {
    xp: 0,
    level: 1,
    name: PET_NAMES[Math.floor(Math.random() * PET_NAMES.length)],
    tasks_created: 0,
    tasks_completed: 0,
    overdue_clears: 0,
    login_streak: 1,
    last_login: new Date().toISOString().slice(0, 10),
    accessories: [],
    achievements: [],
    daily_quests: { date: new Date().toISOString().slice(0, 10), completed: [] },
  }
}
