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
      :class="{ hovered: isHovered, walking: isWalking, sleeping: isSleeping }"
      @mouseenter="onEnter"
      @mouseleave="onLeave"
      @click.stop="onClick"
      @dblclick.stop="onDblClick"
      @mousedown.stop="onDragStart"
    >
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
const position = reactive({ x: 50, y: 60 })
const target = reactive({ x: 50, y: 60 })
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
  const isRight = facing.value === 1
  return { [isRight ? 'right' : 'left']: '50%', transform: isRight ? 'translateX(0)' : 'translateX(-50%)' }
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
const WALK_SPEED = 0.015 // % per ms

function gameLoop(timestamp) {
  if (!lastTime) lastTime = timestamp
  const dt = Math.min(timestamp - lastTime, 50)
  lastTime = timestamp

  // State transitions
  stateTimer += dt
  if (!isSleeping.value && !isHovered.value) {
    if (state.value === 'idle' && stateTimer > 3000 + Math.random() * 5000) {
      pickNewTarget()
      state.value = 'walking'
      stateTimer = 0
    } else if (state.value === 'walking' && stateTimer > 1500 + Math.random() * 3000) {
      state.value = 'idle'
      stateTimer = 0
    }
  }

  // Move toward target
  if (state.value === 'walking' && !isSleeping.value) {
    const dx = target.x - position.x
    const dy = target.y - position.y
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist < 2) {
      state.value = 'idle'
      stateTimer = 0
      isWalking.value = false
    } else {
      isWalking.value = true
      const speed = WALK_SPEED * dt
      position.x += (dx / dist) * speed
      position.y += (dy / dist) * speed
      if (dx > 0) facing.value = 1
      else if (dx < 0) facing.value = -1
    }
  } else {
    isWalking.value = false
  }

  // Clamp to container bounds
  if (containerRef.value) {
    const w = containerRef.value.clientWidth
    const h = containerRef.value.clientHeight
    position.x = Math.max(5, Math.min(95, position.x))
    position.y = Math.max(10, Math.min(85, position.y))
  }

  // Sleep timer
  idleTimer += dt
  if (idleTimer > 60000 && !isSleeping.value) {
    isSleeping.value = true
    state.value = 'sleeping'
  }

  animFrame = requestAnimationFrame(gameLoop)
}

function pickNewTarget() {
  const margin = 15
  target.x = margin + Math.random() * (90 - margin * 2)
  target.y = 40 + Math.random() * 50 // stay in lower half (grass area)
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
  showBubble.value = true
  idleTimer = 0
  emitParticles('❤️', 1, 30, 20, [1, 1.5])
}

function onLeave() {
  isHovered.value = false
  isHeartEyes.value = false
  showBubble.value = false
}

function onClick() {
  emitParticles('❤️', 5, 60, 40, [0.8, 2])
  emitParticles('⭐', 2, 40, 30, [1, 2])
  addXp(1) // 1 click = 1 XP (tiny reward for interaction)
}

function onDblClick() {
  state.value = 'walking'
  pickNewTarget()
  target.x = position.x + (Math.random() - 0.5) * 40
  target.y = position.y + (Math.random() - 0.5) * 30
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
  const name = props.username || '同学'
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

  // Add random science facts
  const allFacts = [...FACTS.science, ...FACTS.team, ...FACTS.encourage, ...FACTS.fun]
  for (let i = 0; i < 3; i++) {
    msgs.push(allFacts[Math.floor(Math.random() * allFacts.length)])
  }

  messages.value = msgs
  currentMessage.value = msgs[0]
}

function showMessage(msg) {
  currentMessage.value = msg
  showBubble.value = true
  clearTimeout(bubbleTimer)
  bubbleTimer = setTimeout(() => {
    if (!isHovered.value) showBubble.value = false
  }, 5000)
}

function startMessageCarousel() {
  stopMessageCarousel()
  messageTimer = setInterval(() => {
    if (!showBubble.value && !isSleeping.value) {
      messageIndex.value = (messageIndex.value + 1) % messages.value.length
      currentMessage.value = messages.value[messageIndex.value]
      showBubble.value = true
      clearTimeout(bubbleTimer)
      bubbleTimer = setTimeout(() => { showBubble.value = false }, 5000)
    }
  }, 8000)
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

// ===== Lifecycle =====
onMounted(() => {
  buildMessages()
  startMessageCarousel()
  scheduleEarTwitch()
  pickNewTarget()
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
})
</script>

<style scoped>
/* ===== 容器 ===== */
.pet-world {
  position: relative;
  width: 80px;
  height: 100px;
  flex-shrink: 0;
  cursor: default;
}

/* ===== 兔子本体 ===== */
.bunny {
  position: absolute;
  width: 45px;
  height: 55px;
  transition: transform 0.1s ease-out;
  z-index: 10;
}

.bunny.hovered { filter: brightness(1.05); }
.bunny.walking { animation: pet-walk 0.4s ease-in-out infinite; }
.bunny.sleeping { opacity: 0.85; }

@keyframes pet-walk {
  0%, 100% { margin-top: 0; }
  50% { margin-top: -4px; }
}

/* ===== 身体 ===== */
.body {
  position: absolute;
  bottom: 0;
  left: 4px;
  width: 37px;
  height: 32px;
  background: #FFF0E8;
  border-radius: 50% 50% 42% 42%;
  z-index: 2;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  animation: pet-breathe 4s ease-in-out infinite;
}

@keyframes pet-breathe {
  0%, 100% { transform: scaleY(1) scaleX(1); }
  50% { transform: scaleY(1.03) scaleX(0.97); }
}

/* ===== 头 ===== */
.head {
  position: absolute;
  bottom: 24px;
  left: 8px;
  width: 29px;
  height: 28px;
  background: #FFF0E8;
  border-radius: 50%;
  z-index: 4;
  animation: pet-breathe 4s ease-in-out infinite;
}

/* ===== 耳朵 ===== */
.ear {
  position: absolute;
  width: 10px;
  height: 24px;
  background: #FFF0E8;
  border-radius: 50% 50% 35% 35%;
  z-index: 3;
  transform-origin: bottom center;
  transition: transform 0.3s ease;
}
.ear::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 2px;
  width: 6px;
  height: 16px;
  background: #FFD4C4;
  border-radius: 50%;
}
.ear-left { bottom: 42px; left: 4px; transform: rotate(-10deg); }
.ear-right { bottom: 42px; right: 4px; transform: rotate(10deg); }
.ear.twitch { transform: rotate(15deg); }

/* ===== 眼睛 ===== */
.eye {
  position: absolute;
  top: 9px;
  width: 7px;
  height: 8px;
  background: #FFF0E8;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
}
.eye-left { left: 5px; }
.eye-right { right: 5px; }

.pupil {
  width: 4px;
  height: 4.5px;
  background: #4A3728;
  border-radius: 50%;
  transition: transform 0.1s;
}
.bunny.hovered .pupil { transform: scale(1.3); }

/* 爱心眼 */
.heart-eye {
  position: absolute;
  top: 7px;
  font-size: 11px;
  color: #FF6B6B;
  z-index: 6;
  animation: pet-heartbeat 0.6s ease-in-out infinite;
}
.heart-left { left: 3px; }
.heart-right { right: 3px; }

@keyframes pet-heartbeat {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.25); }
}

/* 睡觉眼 */
.sleep-eye {
  position: absolute;
  top: 12px;
  width: 7px;
  height: 2px;
  background: #4A3728;
  border-radius: 1px;
  z-index: 6;
}
.sleep-eye-left { left: 5px; }
.sleep-eye-right { right: 5px; }

/* ===== 鼻子 ===== */
.nose {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: 5px;
  height: 4px;
  background: #FF9D85;
  border-radius: 50%;
  z-index: 5;
}

/* ===== 嘴 ===== */
.mouth {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 8px;
  height: 4px;
  border-bottom: 1.2px solid #E8C4B0;
  border-radius: 0 0 50% 50%;
  z-index: 5;
}

/* ===== 腮红 ===== */
.blush {
  position: absolute;
  top: 14px;
  width: 6px;
  height: 5px;
  background: rgba(255, 180, 160, 0.5);
  border-radius: 50%;
  z-index: 4;
}
.blush-left { left: 1px; }
.blush-right { right: 1px; }

/* ===== 腿 ===== */
.leg {
  position: absolute;
  bottom: 2px;
  width: 10px;
  height: 8px;
  background: #FFF0E8;
  border-radius: 50%;
  z-index: 1;
}
.leg-front-left { left: 6px; }
.leg-front-right { right: 6px; }
.bunny.walking .leg-front-left { animation: pet-leg 0.4s ease-in-out infinite; }
.bunny.walking .leg-front-right { animation: pet-leg 0.4s ease-in-out infinite 0.2s; }

@keyframes pet-leg {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}

/* ===== 尾巴 ===== */
.tail {
  position: absolute;
  bottom: 24px;
  left: -2px;
  width: 8px;
  height: 8px;
  background: #FFF0E8;
  border-radius: 50%;
  z-index: 3;
}

/* ===== 配饰 ===== */
.accessory {
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 12px;
  z-index: 10;
}
.group-crown {
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 14px;
  z-index: 11;
  animation: pet-float 2s ease-in-out infinite;
}

@keyframes pet-float {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-3px); }
}

/* ===== 对话气泡 ===== */
.speech-bubble {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  color: #333;
  border-radius: 10px;
  padding: 4px 10px;
  font-size: 11px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  z-index: 20;
  pointer-events: none;
  animation: pet-bubble-in 0.3s ease-out;
}
.speech-bubble::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 5px solid #fff;
}

@keyframes pet-bubble-in {
  from { opacity: 0; transform: translateX(-50%) translateY(4px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* ===== 睡觉 Zzz ===== */
.sleep-zzz {
  position: absolute;
  top: -5px;
  right: 0;
  font-size: 14px;
  z-index: 15;
  pointer-events: none;
  animation: pet-zzz 2s ease-out infinite;
}

@keyframes pet-zzz {
  0% { opacity: 1; transform: translateY(0) translateX(0); }
  100% { opacity: 0; transform: translateY(-16px) translateX(6px); }
}

/* ===== XP 进度条 ===== */
.xp-bar-wrap {
  position: absolute;
  bottom: -2px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 15;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.xp-bar {
  width: 40px;
  height: 5px;
  background: rgba(255,255,255,0.3);
  border-radius: 3px;
  overflow: hidden;
}
.xp-fill {
  height: 100%;
  background: #67C23A;
  border-radius: 3px;
  transition: width 0.5s ease-out;
}
.xp-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  color: rgba(255,255,255,0.9);
  white-space: nowrap;
}
.xp-level {
  font-weight: 700;
}
.xp-hint {
  opacity: 0.7;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 升级特效 ===== */
.level-up-effect {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 25;
  pointer-events: none;
}
.lu-particle {
  position: absolute;
  font-size: 12px;
  animation: pet-lu-burst 2s ease-out forwards;
}

@keyframes pet-lu-burst {
  0% { transform: translate(0, 0) scale(1); opacity: 1; }
  100% { transform: translate(var(--lx), var(--ly)) scale(1.5); opacity: 0; }
}

/* ===== 爱心粒子 ===== */
.particles {
  position: absolute;
  top: 40%;
  left: 40%;
  z-index: 30;
  pointer-events: none;
}
.particle {
  position: absolute;
  font-size: 10px;
  animation: pet-particle-up ease-out forwards;
}

@keyframes pet-particle-up {
  0% { transform: translate(0, 0); opacity: 1; }
  100% { transform: translate(var(--dx), var(--dy)); opacity: 0; }
}
</style>
