<template>
  <div
    class="pet-world"
    ref="containerRef"
    :class="{ sleeping: isSleeping }"
    @mousemove="onWorldMouseMove"
  >
    <!-- 对话气泡 -->
    <div class="speech-bubble" v-show="showBubble" :style="bubbleStyle">
      {{ currentMessage }}
    </div>

    <!-- 睡觉 Zzz -->
    <div class="sleep-zzz" v-show="isSleeping">💤</div>

    <!-- 升级粒子 -->
    <div class="level-up-effect" v-if="showLevelUp">
      <span v-for="i in 12" :key="i" class="lu-particle" :style="luStyle(i)">⭐</span>
    </div>

    <!-- 兔子本体 -->
    <div
      class="bunny"
      ref="bunnyRef"
      :style="bunnyStyle"
      :class="{ hovered: isHovered, sleeping: isSleeping }"
      @mouseenter="onEnter"
      @mouseleave="onLeave"
      @click.stop="onClick"
      @dblclick.stop="onDblClick"
      @mousedown.stop="onDragStart"
    >
      <!-- 走路动画层 — 与定位 transform 隔离，避免互相覆盖 -->
      <div class="bunny-body" :class="{ walking: isWalking }">
        <!-- 配饰 -->
        <div class="accessory" v-if="currentAccessory">{{ currentAccessory }}</div>

        <!-- 大兔皇冠 -->
        <div class="group-crown" v-if="type === 'group' && groupLevel >= 20">👑</div>

        <!-- 耳朵 -->
        <div class="ear ear-left" :class="{ twitch: earTwitching }"></div>
        <div class="ear ear-right" :class="{ twitch: earTwitching }"></div>

        <!-- 头 -->
        <div class="head">
          <!-- 眼睛 -->
          <div class="eye eye-left" v-show="!isSleeping && !isHeartEyes">
            <div class="pupil"></div>
          </div>
          <div class="eye eye-right" v-show="!isSleeping && !isHeartEyes">
            <div class="pupil"></div>
          </div>

          <!-- 爱心眼 -->
          <div class="heart-eye heart-left" v-show="isHeartEyes">♥</div>
          <div class="heart-eye heart-right" v-show="isHeartEyes">♥</div>

          <!-- 睡觉眼 -->
          <div class="sleep-eye sleep-eye-left" v-show="isSleeping"></div>
          <div class="sleep-eye sleep-eye-right" v-show="isSleeping"></div>

          <!-- 鼻子 -->
          <div class="nose"></div>
          <!-- 嘴 -->
          <div class="mouth"></div>
          <!-- 腮红 -->
          <div class="blush blush-left"></div>
          <div class="blush blush-right"></div>
        </div>

        <!-- 身体 -->
        <div class="body"></div>

        <!-- 前腿 -->
        <div class="leg leg-front-left"></div>
        <div class="leg leg-front-right"></div>

        <!-- 尾巴 -->
        <div class="tail"></div>
      </div>
    </div>

    <!-- XP 进度条 (悬停时显示) -->
    <div class="xp-bar-wrap" v-show="isHovered">
      <div class="xp-bar">
        <div class="xp-fill" :style="{ width: levelInfo.progress + '%' }"></div>
      </div>
      <div class="xp-label">
        <span class="xp-level">Lv.{{ levelInfo.level }}</span>
        <span class="xp-hint" v-if="levelInfo.xpToNext > 0">再完成 {{ Math.ceil(levelInfo.xpToNext / 30) }} 个任务升级~</span>
      </div>
    </div>

    <!-- 爱心粒子容器 -->
    <div class="particles">
      <span
        v-for="p in particles"
        :key="p.id"
        class="particle"
        :style="{ left: p.x + 'px', '--dx': p.dx + 'px', '--dy': p.dy + 'px', animationDuration: p.dur + 's' }"
      >{{ p.emoji }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import {
  FACTS, PET_NAMES, ACCESSORIES, ACHIEVEMENTS, DAILY_QUESTS,
  PERSONAL_LEVELS, GROUP_LEVELS, XP_RULES, calcLevel, defaultPetData,
} from './DashboardPetFacts.js'

const props = defineProps({
  type: { type: String, default: 'personal' }, // 'personal' | 'group'
  username: { type: String, default: '同学' },
  overdueCount: { type: Number, default: 0 },
  inProgressCount: { type: Number, default: 0 },
  totalTasks: { type: Number, default: 0 },
  groupXp: { type: Number, default: 0 },
  groupLevel: { type: Number, default: 1 },
})

const emit = defineEmits(['xp-gained'])

// ===== Refs =====
const containerRef = ref(null)
const bunnyRef = ref(null)
const position = reactive({ x: 40 + Math.random() * 20, y: 40 + Math.random() * 40 })
const target = reactive({ x: position.x, y: position.y })
const state = ref('idle')
const facing = ref(1) // 1=right, -1=left
const isHovered = ref(false)
const isHeartEyes = ref(false)
const isSleeping = ref(false)
const isWalking = ref(false)
const showBubble = ref(false)
const earTwitching = ref(false)
const showLevelUp = ref(false)
const currentAccessory = ref('')

// ===== Pet Data =====
const petData = reactive(props.type === 'personal' ? loadPetData() : defaultPetData())
const levelInfo = computed(() => {
  const levels = props.type === 'personal' ? PERSONAL_LEVELS : GROUP_LEVELS
  const xp = props.type === 'personal' ? petData.xp : props.groupXp
  return calcLevel(xp, levels)
})

// ===== Messages =====
const messages = ref([])
const currentMessage = ref('')
const messageIndex = ref(0)
let messageTimer = null
let bubbleTimer = null
const bubbleStyle = computed(() => {
  // 个人兔气泡偏左，大兔气泡偏右，避免重叠
  if (props.type === 'group') {
    return { left: 'auto', right: '0', transform: 'translateX(10px)' }
  }
  return { left: '0', right: 'auto', transform: 'translateX(-10px)' }
})

// ===== Particles =====
const particles = ref([])
let particleId = 0

function emitParticles(emoji, count, dxRange, dyRange, durRange) {
  for (let i = 0; i < count; i++) {
    const id = ++particleId
    const dx = (Math.random() - 0.5) * dxRange
    const dy = -(Math.random() * dyRange + 20)
    const dur = Math.random() * (durRange[1] - durRange[0]) + durRange[0]
    particles.value.push({ id, emoji, x: 0, dx, dy, dur })
    setTimeout(() => {
      particles.value = particles.value.filter(p => p.id !== id)
    }, dur * 1000)
  }
}

// ===== Game Loop =====
let animFrame = null
let lastTime = 0
let stateTimer = 0
let idleTimer = 0
let pauseTimer = 0
const WALK_SPEED = 0.008 // % per ms (慢一点，更自然)

function gameLoop(timestamp) {
  if (!lastTime) lastTime = timestamp
  const dt = Math.min(timestamp - lastTime, 50)
  lastTime = timestamp

  stateTimer += dt

  if (!isSleeping.value && !isHovered.value) {
    // 走路状态：走向目标
    if (state.value === 'walking') {
      const dx = target.x - position.x
      const dy = target.y - position.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < 1.5) {
        // 到达目标，发一会儿呆
        state.value = 'idle'
        stateTimer = 0
        pauseTimer = 2000 + Math.random() * 3000 // 发呆 2-5s
        isWalking.value = false
      } else {
        isWalking.value = true
        const speed = WALK_SPEED * dt
        position.x += (dx / dist) * speed
        position.y += (dy / dist) * speed
        if (Math.abs(dx) > 1) facing.value = dx > 0 ? 1 : -1
      }
    }
    // 发呆状态：等一会儿再走
    else if (state.value === 'idle') {
      isWalking.value = false
      if (stateTimer > pauseTimer) {
        pickNearbyTarget()
        state.value = 'walking'
        stateTimer = 0
      }
    }
  } else if (isHovered.value) {
    isWalking.value = false
    state.value = 'idle'
  }

  // Clamp to container bounds (留 3% 边距)
  if (containerRef.value) {
    position.x = Math.max(3, Math.min(95, position.x))
    position.y = Math.max(3, Math.min(92, position.y))
  }

  // Sleep timer
  idleTimer += dt
  if (idleTimer > 60000 && !isSleeping.value) {
    isSleeping.value = true
    state.value = 'sleeping'
  }

  animFrame = requestAnimationFrame(gameLoop)
}

// 趴靠点：兔子可以在文字区域附近活动
const PERCH_ZONES = [
  { y: 8, label: '问候文字旁' },
  { y: 25, label: '日期时间旁' },
  { y: 45, label: '中间区域' },
  { y: 65, label: '任务提示旁' },
  { y: 82, label: '草地上' },
]

function pickNearbyTarget() {
  const range = 10 + Math.random() * 25
  let tx = position.x + (Math.random() - 0.5) * range * 2
  let ty = position.y + (Math.random() - 0.5) * range * 2
  tx = Math.max(3, Math.min(95, tx))
  ty = Math.max(3, Math.min(90, ty))
  target.x = tx
  target.y = ty
}

function pickFarTarget() {
  target.x = 5 + Math.random() * 90
  // 偶尔走到趴靠点
  if (Math.random() < 0.3) {
    const zone = PERCH_ZONES[Math.floor(Math.random() * PERCH_ZONES.length)]
    target.y = zone.y + (Math.random() - 0.5) * 8
  } else {
    target.y = 5 + Math.random() * 85
  }
}

function pickNewTarget() {
  if (Math.random() < 0.2) {
    pickFarTarget()
  } else {
    pickNearbyTarget()
  }
}

// ===== Cursor tracking =====
function onWorldMouseMove(e) {
  idleTimer = 0
  if (isSleeping.value) {
    isSleeping.value = false
    state.value = 'idle'
    stateTimer = 0
  }
}

function onEnter() {
  isHovered.value = true
  isHeartEyes.value = true
  // 只有没人在说话时才显示气泡
  if (!window.__petSpeaking) {
    showBubble.value = true
  }
  idleTimer = 0
  emitParticles('❤️', 1, 30, 20, [1, 1.5])
}

function onLeave() {
  isHovered.value = false
  isHeartEyes.value = false
  // 只有自己不是轮播说话者时才隐藏气泡
  if (window.__petSpeaking !== props.type) {
    showBubble.value = false
  }
}

function onClick() {
  emitParticles('❤️', 5, 60, 40, [0.8, 2])
  emitParticles('⭐', 2, 40, 30, [1, 2])
  addXp(1) // 1 click = 1 XP (tiny reward for interaction)
}

function onDblClick() {
  // 瞬移到远处（受惊逃跑）
  position.x = Math.max(8, Math.min(88, position.x + (Math.random() - 0.5) * 50))
  position.y = Math.max(20, Math.min(78, position.y + (Math.random() - 0.5) * 40))
  pickNearbyTarget()
  state.value = 'idle'
  stateTimer = 0
  pauseTimer = 1000
  emitParticles('💨', 3, 40, 20, [0.5, 1])
}

// ===== Drag =====
let dragging = false
let dragOffset = { x: 0, y: 0 }
function onDragStart(e) {
  dragging = true
  const rect = containerRef.value.getBoundingClientRect()
  dragOffset.x = e.clientX - rect.left - (position.x / 100) * rect.width
  dragOffset.y = e.clientY - rect.top - (position.y / 100) * rect.height
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}
function onDragMove(e) {
  if (!dragging || !containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  position.x = ((e.clientX - rect.left - dragOffset.x) / rect.width) * 100
  position.y = ((e.clientY - rect.top - dragOffset.y) / rect.height) * 100
}
function onDragEnd() {
  dragging = false
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  state.value = 'idle'
  stateTimer = 0
}

// ===== XP =====
function loadPetData() {
  try {
    const raw = localStorage.getItem('personal_pet')
    if (raw) return JSON.parse(raw)
  } catch (e) { /* ignore */ }
  return defaultPetData()
}

function savePetData() {
  if (props.type !== 'personal') return
  localStorage.setItem('personal_pet', JSON.stringify(petData))
}

function addXp(amount) {
  if (props.type !== 'personal') return
  const oldLevel = levelInfo.value.level
  petData.xp += amount
  const newLevel = calcLevel(petData.xp, PERSONAL_LEVELS).level
  if (newLevel > oldLevel) {
    triggerLevelUp(newLevel)
  }
  savePetData()
  emit('xp-gained', amount)
}

function triggerLevelUp(newLevel) {
  showLevelUp.value = true
  emitParticles('⭐', 8, 80, 60, [1, 2.5])
  emitParticles('🎉', 6, 70, 50, [1.5, 3])
  // Check for new pet type
  const stage = PERSONAL_LEVELS.find(l => l.level === newLevel)
  const petMsg = stage ? `，${stage.label}` : ''
  showMessage(`Lv.${newLevel}！升级啦${petMsg}！🎉`)
  setTimeout(() => { showLevelUp.value = false }, 2500)
}

// ===== Messages =====
function buildMessages() {
  const msgs = []
  const name = (props.username && props.username !== '用户') ? props.username : '同学'

  if (props.type === 'group') {
    // 课题组大兔消息
    const level = levelInfo.value
    msgs.push(`我是课题组大兔「小气」🐰👑 全组一起养大的哦~`)
    const done = Number(props.totalTasks) || 0
    msgs.push(done > 0 ? `全组已完成 ${done} 个任务啦！继续加油！💪` : '大家加油完成任务，养大我哦~ 🥕')
    msgs.push(`大兔当前 Lv.${level.level}，再攒 ${level.xpToNext} XP 就升级啦~`)
  } else {
    // 个人兔消息
    const hour = new Date().getHours()
    const greeting = hour < 9 ? '早上好' : hour < 12 ? '上午好' : hour < 18 ? '下午好' : '晚上好'
    msgs.push(`${greeting}，${name}！☀️ 新的一天一起加油~`)

    if (props.overdueCount > 0) {
      msgs.push(`${name}，你有 ${props.overdueCount} 个任务逾期了哦 😟 需要帮忙吗？`)
    } else if (props.inProgressCount > 0) {
      msgs.push(`${name}，${props.inProgressCount} 个任务进行中，稳扎稳打！💪`)
    } else {
      msgs.push('今天没有任务呢，要不要创建新的？📝')
    }
  }

  // Add random science facts
  const allFacts = [...FACTS.science, ...FACTS.team, ...FACTS.encourage, ...FACTS.fun]
  for (let i = 0; i < 3; i++) {
    msgs.push(allFacts[Math.floor(Math.random() * allFacts.length)])
  }

  messages.value = msgs
  currentMessage.value = msgs[0]
}

// 全局说话互斥：同一时间只有一只兔子说话
function trySpeak(msg) {
  if (window.__petSpeaking) return false
  window.__petSpeaking = props.type // 记录谁在说话
  currentMessage.value = msg
  showBubble.value = true
  clearTimeout(bubbleTimer)
  bubbleTimer = setTimeout(() => {
    showBubble.value = false
    window.__petSpeaking = null
  }, 5000)
  return true
}

function showMessage(msg) {
  if (window.__petSpeaking && window.__petSpeaking !== props.type) {
    clearTimeout(bubbleTimer)
    bubbleTimer = setTimeout(() => showMessage(msg), 2000)
    return
  }
  trySpeak(msg)
}

function startMessageCarousel() {
  stopMessageCarousel()
  messageTimer = setInterval(() => {
    if (!showBubble.value && !isSleeping.value && !window.__petSpeaking) {
      messageIndex.value = (messageIndex.value + 1) % messages.value.length
      trySpeak(messages.value[messageIndex.value])
    }
  }, 8000 + Math.random() * 4000)
}

function stopMessageCarousel() {
  clearInterval(messageTimer)
  clearTimeout(bubbleTimer)
}

// ===== Ear twitch =====
let earTimer = null
function scheduleEarTwitch() {
  earTimer = setTimeout(() => {
    earTwitching.value = true
    setTimeout(() => { earTwitching.value = false }, 300)
    scheduleEarTwitch()
  }, 3000 + Math.random() * 5000)
}

// ===== Bunny style =====
const bunnyStyle = computed(() => ({
  left: position.x + '%',
  top: position.y + '%',
  transform: `translate(-50%, -50%) scaleX(${facing.value})`,
}))

// ===== Level up particle style =====
function luStyle(i) {
  const angle = (i / 12) * 360
  const dist = 30 + Math.random() * 20
  const x = Math.cos((angle * Math.PI) / 180) * dist
  const y = Math.sin((angle * Math.PI) / 180) * dist
  return {
    '--lx': x + 'px',
    '--ly': y + 'px',
    animationDelay: (i * 0.05) + 's',
  }
}

// ===== Accessory =====
watch(() => petData.xp, (xp) => {
  const unlocked = ACCESSORIES.filter(a => a.xp <= xp)
  if (unlocked.length > 0) {
    currentAccessory.value = unlocked[unlocked.length - 1].emoji
  }
}, { immediate: true })

// 用户名加载后或任务数据变化时更新消息
watch(() => props.username, (name) => {
  if (name && name !== '用户') {
    buildMessages()
  }
})
watch([() => props.overdueCount, () => props.inProgressCount], () => {
  buildMessages()
})

// ===== Lifecycle =====
onMounted(() => {
  buildMessages()
  startMessageCarousel()
  scheduleEarTwitch()
  pickNearbyTarget()
  state.value = 'walking'
  animFrame = requestAnimationFrame(gameLoop)

  // Login XP
  if (props.type === 'personal') {
    const today = new Date().toISOString().slice(0, 10)
    if (petData.last_login !== today) {
      const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
      if (petData.last_login === yesterday) {
        petData.login_streak += 1
      } else {
        petData.login_streak = 1
      }
      petData.last_login = today
      addXp(XP_RULES.daily_login.personal)
      if (petData.login_streak % 7 === 0) {
        addXp(XP_RULES.streak_7_bonus.personal)
      }
      // Check achievements
      ACHIEVEMENTS.forEach(a => {
        if (!petData.achievements.includes(a.id) && a.check({ tasks_created: petData.tasks_created, tasks_completed: petData.tasks_completed, overdue_clears: petData.overdue_clears, login_streak: petData.login_streak, level: levelInfo.value.level })) {
          petData.achievements.push(a.id)
          showMessage(`${a.icon} 解锁成就：${a.name}！`)
          emitParticles('⭐', 5, 50, 40, [1, 2])
        }
      })
      savePetData()
    }
  }
})

onUnmounted(() => {
  cancelAnimationFrame(animFrame)
  stopMessageCarousel()
  clearTimeout(earTimer)
  clearTimeout(bubbleTimer)
  if (window.__petSpeaking === props.type) {
    window.__petSpeaking = null
  }
})
</script>

<style scoped>
/* ===== 容器 ===== */
.pet-world {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 120px;
  min-height: 100px;
  flex-shrink: 1;
  cursor: default;
  perspective: 300px;
}

/* ===== 兔子本体 ===== */
.bunny {
  position: absolute;
  width: 65px;
  height: 80px;
  transition: transform 0.15s ease-out;
  z-index: 10;
  filter: drop-shadow(0 6px 12px rgba(0,0,0,0.12));
  transform-style: preserve-3d;
}
.bunny-body {
  width: 100%;
  height: 100%;
}
.bunny:hover {
  filter: drop-shadow(0 8px 18px rgba(var(--color-primary-rgb),0.25)) brightness(1.05);
}
.bunny-body.walking {
  animation: pet-walk 0.35s ease-in-out infinite;
}
.bunny.sleeping {
  opacity: 0.8;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.06));
}
@keyframes pet-walk {
  0%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
  60% { transform: translateY(-2px); }
}

/* ===== 3D 身体 ===== */
.body {
  position: absolute;
  bottom: 0;
  left: 6px;
  width: 50px;
  height: 42px;
  background: radial-gradient(ellipse at 40% 30%, #FFF8F4 0%, #F5E0D0 60%, #E8D0BC 100%);
  border-radius: 52% 48% 48% 52% / 55% 55% 45% 45%;
  z-index: 2;
  box-shadow:
    inset 0 -6px 12px rgba(180,140,120,0.2),
    inset 0 4px 8px rgba(255,255,255,0.6),
    0 4px 8px rgba(0,0,0,0.06);
  animation: pet-breathe 4s ease-in-out infinite;
}
@keyframes pet-breathe {
  0%, 100% { transform: scaleY(1) scaleX(1); }
  50% { transform: scaleY(1.04) scaleX(0.97); }
}

/* ===== 3D 头（chibi大脸） ===== */
.head {
  position: absolute;
  bottom: 34px;
  left: 4px;
  width: 54px;
  height: 50px;
  background: radial-gradient(ellipse at 42% 35%, #FFFCFA 0%, #F8E8DA 55%, #EDD5C0 100%);
  border-radius: 50% 50% 48% 52%;
  z-index: 4;
  box-shadow:
    inset 0 -5px 10px rgba(180,140,120,0.15),
    inset 0 6px 8px rgba(255,255,255,0.5),
    0 3px 6px rgba(0,0,0,0.05);
  animation: pet-breathe 4s ease-in-out infinite 0.5s;
}

/* ===== 3D 耳朵（更立体） ===== */
.ear {
  position: absolute;
  width: 16px;
  height: 38px;
  background: radial-gradient(ellipse at 50% 30%, #FFF8F2 0%, #F2DDCB 50%, #E0C8B0 100%);
  border-radius: 45% 45% 30% 30%;
  z-index: 3;
  transform-origin: bottom center;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow:
    inset 0 3px 6px rgba(255,255,255,0.4),
    inset 0 -4px 8px rgba(180,130,100,0.15),
    0 2px 4px rgba(0,0,0,0.04);
}
.ear::after {
  content: '';
  position: absolute;
  top: 4px;
  left: 4px;
  width: 8px;
  height: 26px;
  background: radial-gradient(ellipse at 50% 30%, #FFD8C8 0%, #F0C0A8 100%);
  border-radius: 50%;
}
.ear-left {
  bottom: 64px;
  left: 8px;
  transform: rotate(-15deg);
}
.ear-right {
  bottom: 64px;
  right: 8px;
  transform: rotate(15deg);
}
.ear.twitch {
  transform: rotate(22deg) scaleX(1.05);
}

/* ===== Kawaii 大眼睛 ===== */
.eye {
  position: absolute;
  top: 14px;
  width: 14px;
  height: 16px;
  background: radial-gradient(circle at 50% 45%, #fff 0%, #fafafa 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
}
.eye-left { left: 8px; }
.eye-right { right: 8px; }

.pupil {
  width: 8px;
  height: 10px;
  background: radial-gradient(circle at 50% 40%, #5A4535 0%, #3A2518 100%);
  border-radius: 50%;
  position: relative;
  transition: transform 0.15s ease;
}
/* 眼睛高光 */
.pupil::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 3px;
  height: 3px;
  background: var(--color-bg-card);
  border-radius: 50%;
  opacity: 0.9;
}
.bunny.hovered .pupil {
  transform: scale(1.2);
}

/* 爱心眼 */
.heart-eye {
  position: absolute;
  top: 12px;
  font-size: 14px;
  color: var(--color-danger);
  z-index: 6;
  animation: pet-heartbeat 0.5s ease-in-out infinite;
  filter: drop-shadow(0 1px 2px rgba(255,60,60,0.3));
}
.heart-left { left: 6px; }
.heart-right { right: 6px; }
@keyframes pet-heartbeat {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.3); }
}

/* 睡觉眼 */
.sleep-eye {
  position: absolute;
  top: 21px;
  width: 14px;
  height: 3px;
  background: var(--color-bg-warm);
  border-radius: 2px;
  z-index: 6;
  opacity: 0.8;
}
.sleep-eye-left { left: 8px; }
.sleep-eye-right { right: 8px; }

/* ===== 小鼻子 ===== */
.nose {
  position: absolute;
  top: 29px;
  left: 50%;
  transform: translateX(-50%);
  width: 7px;
  height: 5px;
  background: radial-gradient(circle at 50% 30%, #FFB8A8 0%, #F09080 100%);
  border-radius: 50%;
  z-index: 5;
}

/* ===== 3D Y型小嘴 ===== */
.mouth {
  position: absolute;
  top: 33px;
  left: 50%;
  transform: translateX(-50%);
  width: 14px;
  height: 8px;
  z-index: 5;
}
.mouth::before,
.mouth::after {
  content: '';
  position: absolute;
  top: 0;
  width: 7px;
  height: 8px;
  border-bottom: 1.5px solid #D0B8A8;
  border-radius: 0 0 50% 50%;
}
.mouth::before { left: 0; border-right: 1.5px solid #D0B8A8; border-radius: 0 0 50% 50%; }
.mouth::after { right: 0; border-left: 1.5px solid #D0B8A8; border-radius: 0 0 50% 50%; }

/* ===== 软萌腮红 ===== */
.blush {
  position: absolute;
  top: 19px;
  width: 9px;
  height: 7px;
  background: radial-gradient(ellipse, rgba(255,160,140,0.5) 0%, transparent 70%);
  border-radius: 50%;
  z-index: 4;
}
.blush-left { left: 1px; }
.blush-right { right: 1px; }

/* ===== 圆润小腿 ===== */
.leg {
  position: absolute;
  bottom: 0;
  width: 16px;
  height: 11px;
  background: radial-gradient(ellipse at 50% 40%, #FFF6F0 0%, #F0DCC8 100%);
  border-radius: 50%;
  z-index: 1;
  box-shadow: 0 2px 3px rgba(0,0,0,0.04);
}
.leg-front-left { left: 8px; }
.leg-front-right { right: 8px; }
.bunny.walking .leg-front-left { animation: pet-leg 0.35s ease-in-out infinite; }
.bunny.walking .leg-front-right { animation: pet-leg 0.35s ease-in-out infinite 0.17s; }
@keyframes pet-leg {
  0%, 100% { transform: translateY(0) scaleY(1); }
  50% { transform: translateY(-4px) scaleY(0.85); }
}

/* ===== 毛茸茸圆尾巴 ===== */
.tail {
  position: absolute;
  bottom: 32px;
  left: -6px;
  width: 14px;
  height: 14px;
  background: radial-gradient(circle at 40% 35%, #FFFCFA 0%, #F2E0D0 100%);
  border-radius: 50%;
  z-index: 3;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

/* ===== 配饰 ===== */
.accessory {
  position: absolute;
  top: -8px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 14px;
  z-index: 10;
  filter: drop-shadow(0 2px 2px rgba(0,0,0,0.1));
}
.group-crown {
  position: absolute;
  top: -14px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 16px;
  z-index: 11;
  animation: pet-float 2s ease-in-out infinite;
  filter: drop-shadow(0 2px 4px rgba(255,180,0,0.4));
}
@keyframes pet-float {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-4px); }
}

/* ===== 对话气泡 ===== */
.speech-bubble {
  position: absolute;
  bottom: calc(100% + 8px);
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border-radius: 12px;
  padding: 6px 14px;
  font-size: 12px;
  line-height: 1.5;
  box-shadow: var(--shadow-md);
  z-index: 100;
  pointer-events: none;
  animation: pet-bubble-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  max-width: 240px;
  min-width: 60px;
  overflow-wrap: anywhere;
  white-space: normal;
  text-align: left;
}
.pet-world:first-child .speech-bubble::after,
.speech-bubble::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 14px;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid #fff;
}
.pet-world:nth-child(2) .speech-bubble::after {
  left: auto;
  right: 14px;
}
@keyframes pet-bubble-in {
  from { opacity: 0; transform: translateY(6px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* ===== 睡觉 Zzz ===== */
.sleep-zzz {
  position: absolute;
  top: -8px;
  right: -4px;
  font-size: 14px;
  z-index: 15;
  pointer-events: none;
  animation: pet-zzz 2.5s ease-out infinite;
}
@keyframes pet-zzz {
  0% { opacity: 1; transform: translate(0, 0) scale(0.8); }
  100% { opacity: 0; transform: translate(8px, -20px) scale(1.2); }
}

/* ===== XP 进度条 ===== */
.xp-bar-wrap {
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 15;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.xp-bar {
  width: 44px;
  height: 6px;
  background: rgba(255,255,255,0.25);
  border-radius: 3px;
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
}
.xp-fill {
  height: 100%;
  background: linear-gradient(90deg, #81C784, #66BB6A);
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.xp-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--color-bg-card);
  white-space: nowrap;
  background: rgba(0,0,0,0.45);
  border-radius: 10px;
  padding: 2px 8px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}
.xp-level { font-weight: 700; }
.xp-hint { opacity: 0.9; max-width: 100px; overflow: hidden; text-overflow: ellipsis; }

/* ===== 升级特效 ===== */
.level-up-effect { position: absolute; top: 50%; left: 50%; z-index: 25; pointer-events: none; }
.lu-particle {
  position: absolute; font-size: 13px;
  animation: pet-lu-burst 2.2s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
}
@keyframes pet-lu-burst {
  0% { transform: translate(0, 0) scale(0); opacity: 1; }
  50% { opacity: 1; }
  100% { transform: translate(var(--lx), var(--ly)) scale(1.8); opacity: 0; }
}

/* ===== 爱心粒子 ===== */
.particles { position: absolute; top: 35%; left: 35%; z-index: 30; pointer-events: none; }
.particle {
  position: absolute; font-size: 11px;
  animation: pet-particle-up ease-out forwards;
}
@keyframes pet-particle-up {
  0% { transform: translate(0, 0) scale(0.5); opacity: 1; }
  100% { transform: translate(var(--dx), var(--dy)) scale(1.3); opacity: 0; }
}
</style>

<!-- v69 P0: DashboardPet dark mode 覆盖（v60-v67 教训：dark 跨组件规则必须非 scoped） -->
<style>
  /* 气泡（之前硬编码 #fff 白底在 dark 上戳一坨纯白） */
  [data-theme="dark"] .speech-bubble {
    background: var(--color-bg-card);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border-base);
    box-shadow: var(--shadow-md);
  }
  [data-theme="dark"] .pet-world:first-child .speech-bubble::after,
  [data-theme="dark"] .speech-bubble::after {
    border-top-color: var(--color-bg-card);
  }
  [data-theme="dark"] .pet-world:nth-child(2) .speech-bubble::after {
    border-bottom-color: var(--color-bg-card);
  }
  [data-theme="dark"] .speech-text { color: var(--color-text-primary); }

  /* XP 条（在 hero 上保持半透明白底） */
  [data-theme="dark"] .xp-bar-bg { background: rgba(255, 255, 255, 0.15) !important; }
  [data-theme="dark"] .xp-bar-fill { background: linear-gradient(90deg, #81C784, #66BB6A); }
  [data-theme="dark"] .xp-label { color: rgba(255, 255, 255, 0.95); }
  [data-theme="dark"] .xp-name { background: rgba(0, 0, 0, 0.55); color: var(--color-bg-card); }
  [data-theme="dark"] .xp-name-divider { background: rgba(255, 255, 255, 0.3); }
</style>
