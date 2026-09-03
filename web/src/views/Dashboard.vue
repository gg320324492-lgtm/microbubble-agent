<template>
  <div class="dashboard dashboard-dossier">
    <!-- ═══ 卷首 · DAILY BRIEF ═══ -->
    <section class="hero slide-down-fade">
      <div class="hero-label">DAILY BRIEF · 卷首语</div>
      <div class="hero-body">
        <div class="hero-main">
          <h1 class="hero-greeting">{{ greeting }}，{{ username }}</h1>
          <div class="hero-meta">
            <span>{{ currentDate }}</span>
            <span class="hero-meta-sep">·</span>
            <span>{{ currentTime }}</span>
          </div>
          <div class="hero-tip" :class="tipKind" v-if="summary">
            <template v-if="summary.overdue_tasks > 0">
              <span class="tip-mark">!</span>
              团队共有 <b>{{ summary.overdue_tasks }}</b> 项逾期任务待处理
            </template>
            <template v-else-if="summary.in_progress_tasks > 0">
              <span class="tip-mark">→</span>
              团队共有 <b>{{ summary.in_progress_tasks }}</b> 项任务进行中
            </template>
            <template v-else>
              <span class="tip-mark">✓</span>
              今日任务已完成，继续保持
            </template>
          </div>
        </div>

        <div class="hero-side">
          <div class="hero-actions">
            <el-button class="dbtn dbtn--solid" size="large" @click="$router.push('/chat')">
              <el-icon><ChatDotRound /></el-icon>
              开始对话
            </el-button>
            <el-button class="dbtn dbtn--line" size="large" @click="showCreateTask = true">
              <el-icon><Plus /></el-icon>
              创建任务
            </el-button>
          </div>

          <!-- 🐰 兔子角: 独立纵向区间, 气泡在按钮下方留出, 不再压到操作区 -->
          <div class="hero-pets">
            <div class="pet-slot">
              <DashboardPet
                type="personal"
                :username="userStore.username"
                :overdue-count="summary?.overdue_tasks ?? 0"
                :in-progress-count="summary?.in_progress_tasks ?? 0"
                :total-tasks="summary?.total_tasks ?? 0"
                :y-min="70"
                :y-max="92"
              />
            </div>
            <div class="pet-slot">
              <DashboardPet
                type="group"
                :username="userStore.username"
                :total-tasks="summary?.done_tasks ?? 0"
                :group-xp="groupPetStats.total_xp"
                :group-level="groupPetStats.level"
                :y-min="70"
                :y-max="92"
              />
            </div>
          </div>
        </div>
      </div>
      <!-- 草地基线 -->
      <div class="hero-ground">
        <span class="grass" v-for="i in 7" :key="i" :style="{ left: (6 + i * 13) + '%' }">🌿</span>
      </div>
    </section>

    <!-- ═══ 统计三卡 ═══ -->
    <div class="stat-grid">
      <template v-if="loadingStats">
        <div class="stat-card is-skeleton" v-for="i in 3" :key="i">
          <div class="sk sk-label"></div>
          <div class="sk sk-num"></div>
          <div class="sk sk-hint"></div>
        </div>
      </template>
      <template v-else>
        <div class="stat-card fade-slide-up stagger-1">
          <div class="stat-label">IN PROGRESS</div>
          <div class="stat-name">进行中</div>
          <div class="stat-value stat-value--teal" :ref="el => animateNumber(el, summary?.in_progress_tasks || 0)">0</div>
          <div class="stat-rule"></div>
          <div class="stat-hint">任务执行中</div>
        </div>
        <div class="stat-card fade-slide-up stagger-2">
          <div class="stat-label">DONE</div>
          <div class="stat-name">已完成</div>
          <div class="stat-value stat-value--green" :ref="el => animateNumber(el, summary?.done_tasks || 0)">0</div>
          <div class="stat-rule"></div>
          <div class="stat-hint">累计完成{{ memberCount ? ' · ' + memberCount + ' 人贡献' : '' }}</div>
        </div>
        <div class="stat-card stat-card--danger fade-slide-up stagger-3 clickable"
             :class="{ 'has-danger': (summary?.overdue_tasks || 0) > 0 }"
             @click="$router.push('/tasks?overdue=true')">
          <div class="stat-label">OVERDUE</div>
          <div class="stat-name">已逾期</div>
          <div class="stat-value stat-value--coral" :ref="el => animateNumber(el, summary?.overdue_tasks || 0)">0</div>
          <div class="stat-rule"></div>
          <div class="stat-hint">点击查看逾期任务</div>
          <span v-if="(summary?.overdue_tasks || 0) > 0" class="stamp">需处理</span>
        </div>
      </template>
    </div>

    <!-- ═══ 进行中任务（按负责人分组）═══ -->
    <section class="card tasks-card fade-slide-up stagger-3">
      <header class="card-head">
        <h2 class="card-title"><span class="sec-no">§</span> 进行中任务</h2>
        <div class="card-head-right">
          <span class="card-count mono">{{ inProgressTasks.length }} TOTAL · BY ASSIGNEE</span>
          <button class="view-all" @click="$router.push('/tasks')">查看全部 →</button>
        </div>
      </header>

      <!-- 骨架屏 -->
      <div v-if="loadingTasks" class="task-groups">
        <div v-for="i in 2" :key="i" class="task-group is-skeleton">
          <div class="group-head">
            <div class="sk sk-avatar"></div>
            <div class="sk sk-line" style="width: 90px"></div>
          </div>
          <div class="group-body">
            <div v-for="j in 2" :key="j" class="task-row">
              <div class="sk sk-line" style="flex:1"></div>
              <div class="sk sk-line" style="width: 60px"></div>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="inProgressTasks.length === 0" class="empty-state">
        <el-empty description="暂无进行中任务" :image-size="60" />
      </div>
      <div v-else class="task-groups">
        <div v-for="(group, gIdx) in groupedTasks" :key="group.assignee_id"
             class="task-group fade-slide-up" :style="{ animationDelay: `${(gIdx + 3) * 60}ms` }">
          <!-- 负责人头部 -->
          <div class="group-head" :class="{ 'unassigned-group': group.assignee_id === 'unassigned' }"
               @click="toggleGroup(group.assignee_id)" role="button"
               :aria-expanded="!collapsedGroups[group.assignee_id]"
               :aria-label="`折叠展开 ${group.assignee_id === 'unassigned' ? '会议创建的任务' : memberStore.getMemberName(group.assignee_id)}`">
            <span class="monogram" aria-hidden="true">
              <img v-if="group.assignee_id !== 'unassigned' && memberStore.getMemberAvatar(group.assignee_id)"
                   :src="memberStore.getMemberAvatar(group.assignee_id)"
                   :alt="`${memberStore.getMemberName(group.assignee_id)}的头像`" />
              <template v-else>{{ group.assignee_id === 'unassigned' ? '会' : memberStore.getMemberName(group.assignee_id).charAt(0) }}</template>
            </span>
            <span class="group-name">{{ group.assignee_id === 'unassigned' ? '会议创建的任务' : memberStore.getMemberName(group.assignee_id) }}</span>
            <span class="group-count mono">{{ group.tasks.length }} 项</span>
            <el-icon class="collapse-icon" :class="{ collapsed: collapsedGroups[group.assignee_id] }" aria-hidden="true"><ArrowDown /></el-icon>
          </div>
          <!-- 任务列表 -->
          <div v-show="!collapsedGroups[group.assignee_id]" class="group-body">
            <div v-for="task in group.tasks" :key="task.id" class="task-row" :class="{ overdue: isOverdue(task.due_date) }">
              <div class="task-main">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-chips">
                  <span class="chip" :class="'chip--p-' + (task.priority || 'medium')">{{ getPriorityLabel(task.priority) }}</span>
                  <span v-if="task.status === 'in_progress'" class="chip chip--status">进行中</span>
                  <span v-if="task.source === 'meeting'" class="chip chip--meeting">会议创建</span>
                </div>
              </div>
              <div class="task-due mono" :class="{ overdue: isOverdue(task.due_date) }">
                <span v-if="isOverdue(task.due_date)" class="due-mark" aria-hidden="true">!</span>{{ formatDate(task.due_date) }}
              </div>
              <div class="task-actions">
                <button class="act act--done" @click.stop="completeTask(task)" aria-label="完成任务：{{ task.title }}">✓ 完成</button>
                <button class="act act--edit" @click.stop="openEditDialog(task)" aria-label="编辑任务：{{ task.title }}">编辑</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ 创建任务对话框 ═══ -->
    <el-dialog v-model="showCreateTask" title="创建任务" :width="isMobile ? '90vw' : '500px'" class="dossier-dialog">
      <el-form :model="newTask" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="newTask.title" name="newTask-title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="newTask.assignee_id" name="newTask-assignee_id" placeholder="选择负责人" clearable>
            <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="newTask.priority">
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="newTask.due_date"
            name="newTask-due_date"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择截止日期和时间"
            style="width: 100%"
            :clearable="true"
          />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="newTask.description" name="newTask-description" type="textarea" :rows="3" placeholder="请输入任务描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTask = false">取消</el-button>
        <el-button type="primary" @click="createTask">创建</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 编辑任务对话框 ═══ -->
    <el-dialog v-model="showEditDialog" title="编辑任务" :width="isMobile ? '90vw' : '500px'" class="dossier-dialog">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="editForm.title" name="editForm-title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="editForm.assignee_id" name="editForm-assignee_id" placeholder="选择负责人" clearable>
            <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="editForm.priority">
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" name="editForm-status">
            <el-option label="进行中" value="in_progress" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="editForm.due_date"
            name="editForm-due_date"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择截止日期和时间"
            style="width: 100%"
            :clearable="true"
          />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="editForm.description" name="editForm-description" type="textarea" :rows="3" placeholder="请输入任务描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, ChatDotRound, Plus } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatCompactDate } from '@/utils/format'
import { getPriorityLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import { useUserStore } from '@/stores/user'
import DashboardPet from '@/components/DashboardPet.vue'
import { GROUP_LEVELS, calcLevel } from '@/components/DashboardPetFacts.js'

const memberStore = useMemberStore()
const userStore = useUserStore()
const members = computed(() => memberStore.members)
const memberCount = computed(() => members.value.length)

const dashboardData = ref({})
// 2026-09-03 修复: 大兔 XP 从全组 done_tasks 推导 (此前 groupPetStats 从未赋值, 恒 Lv.1)
// XP 口径与 DashboardPetFacts XP_RULES.complete_task.group 一致: 每完成 1 任务 = 20 XP
const groupPetStats = ref({ total_xp: 0, level: 1, tasks_completed: 0 })
const summary = computed(() => dashboardData.value.summary)
const inProgressTasks = ref([])
const showCreateTask = ref(false)
const isMobile = ref(window.innerWidth <= 768)
const currentTime = ref('')
const currentDate = ref('')

const loadingStats = ref(true)
const loadingTasks = ref(true)

const collapsedGroups = ref({})
const toggleGroup = (assigneeId) => {
  collapsedGroups.value[assigneeId] = !collapsedGroups.value[assigneeId]
}

const animateNumber = (el, target) => {
  if (!el || target === undefined || target === null) return
  const targetNum = Number(target)
  if (isNaN(targetNum)) return
  // 时钟每秒 tick 触发重渲染 → :ref 回调重复执行。目标未变则跳过, 避免动画每秒从头重放。
  if (el.dataset.animTarget === String(targetNum)) return
  el.dataset.animTarget = String(targetNum)
  const from = Number(el.dataset.animValue) || 0
  const duration = 500
  const startTime = performance.now()
  const animate = (now) => {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    const val = Math.round(from + (targetNum - from) * eased)
    el.textContent = val
    el.dataset.animValue = String(val)
    if (progress < 1) requestAnimationFrame(animate)
  }
  requestAnimationFrame(animate)
}

const handleResize = () => { isMobile.value = window.innerWidth <= 768 }
const updateTime = () => {
  const now = dayjs()
  currentTime.value = now.format('HH:mm:ss')
  currentDate.value = now.format('YYYY-MM-DD ddd').toUpperCase()
}

let clockTimer = null

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (clockTimer) {
    clearInterval(clockTimer)
    clockTimer = null
  }
})

const newTask = ref({ title: '', assignee_id: null, priority: 'medium', due_date: null, description: '' })

const editingTask = ref(null)
const showEditDialog = ref(false)
const editForm = ref({ title: '', assignee_id: null, priority: 'medium', status: 'in_progress', due_date: null, description: '', reminders: [] })

const openEditDialog = (task) => {
  editingTask.value = task
  editForm.value = { ...task, reminders: task.reminders ? [...task.reminders] : [] }
  showEditDialog.value = true
}

const saveEdit = async () => {
  if (!editForm.value.title) { ElMessage.warning('请输入任务标题'); return }
  try {
    await axios.put(`/api/v1/tasks/${editingTask.value.id}`, editForm.value)
    ElMessage.success('任务更新成功')
    showEditDialog.value = false
    editingTask.value = null
    fetchInProgressTasks()
    fetchDashboardStats()
  } catch (e) { ElMessage.error('更新任务失败') }
}

const completeTask = async (task) => {
  try {
    await axios.put(`/api/v1/tasks/${task.id}`, { status: 'done' })
    ElMessage.success('任务已完成')
    fetchInProgressTasks()
    fetchDashboardStats()
  } catch (e) { ElMessage.error('操作失败') }
}

const username = computed(() => userStore.username || '用户')

const greeting = computed(() => {
  const hour = dayjs().hour()
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const tipKind = computed(() => {
  const s = summary.value
  if (!s) return ''
  if (s.overdue_tasks > 0) return 'tip--danger'
  if (s.in_progress_tasks > 0) return 'tip--ok'
  return 'tip--quiet'
})

const fetchDashboardStats = async () => {
  try {
    // 2026-09-03 修复: /api/v1/dashboard/summary 返回【平铺】三字段,
    //   而模板一直读 dashboardData.summary.* (嵌套) → 恒 undefined, 统计卡全 0.
    //   (8/28 那次 stats→summary 只改了 URL, 没对齐数据形状)
    const res = await axios.get('/api/v1/dashboard/summary')
    const s = res.data || {}
    dashboardData.value = { summary: s }
    const done = Number(s.done_tasks) || 0
    const xp = done * 20
    groupPetStats.value = { total_xp: xp, level: calcLevel(xp, GROUP_LEVELS).level, tasks_completed: done }
  } catch (e) { console.error('获取仪表盘数据失败:', e) }
  loadingStats.value = false
}

const fetchInProgressTasks = async () => {
  try {
    const res = await axios.get('/api/v1/tasks', { params: { page_size: 100 } })
    const allTasks = (res.data.items || []).filter(t => t.status !== 'done')
    allTasks.sort((a, b) => {
      const aUnassigned = !a.assignee_id ? 0 : 1
      const bUnassigned = !b.assignee_id ? 0 : 1
      if (aUnassigned !== bUnassigned) return aUnassigned - bUnassigned
      const priorityOrder = { high: 3, medium: 2, low: 1 }
      const pDiff = (priorityOrder[b.priority] || 0) - (priorityOrder[a.priority] || 0)
      if (pDiff !== 0) return pDiff
      if (!a.due_date && !b.due_date) return 0
      if (!a.due_date) return 1
      if (!b.due_date) return -1
      return dayjs(a.due_date).diff(dayjs(b.due_date))
    })
    inProgressTasks.value = allTasks
  } catch (e) { console.error('获取进行中任务失败:', e) }
  loadingTasks.value = false
}

const groupedTasks = computed(() => {
  const groups = {}
  for (const task of inProgressTasks.value) {
    const id = task.assignee_id || 'unassigned'
    if (!groups[id]) {
      groups[id] = { assignee_id: id, tasks: [] }
    }
    groups[id].tasks.push(task)
  }
  return Object.values(groups).sort((a, b) => {
    if (a.assignee_id === 'unassigned' && b.assignee_id !== 'unassigned') return -1
    if (b.assignee_id === 'unassigned' && a.assignee_id !== 'unassigned') return 1
    const aHasOverdue = a.tasks.some(t => isOverdue(t.due_date))
    const bHasOverdue = b.tasks.some(t => isOverdue(t.due_date))
    if (aHasOverdue && !bHasOverdue) return -1
    if (!aHasOverdue && bHasOverdue) return 1
    return b.tasks.length - a.tasks.length
  })
})

const createTask = async () => {
  if (!newTask.value.title) { ElMessage.warning('请输入任务标题'); return }
  try {
    await axios.post('/api/v1/tasks', newTask.value)
    ElMessage.success('任务创建成功')
    showCreateTask.value = false
    newTask.value = { title: '', assignee_id: null, priority: 'medium', due_date: null, description: '' }
    fetchInProgressTasks()
    fetchDashboardStats()
  } catch (e) { ElMessage.error('创建任务失败') }
}

const formatDate = (date) => formatCompactDate(date, '无截止')
const isOverdue = (date) => date && dayjs(date).isBefore(dayjs())

onMounted(() => {
  updateTime()
  clockTimer = setInterval(updateTime, 1000)
  fetchDashboardStats()
  fetchInProgressTasks()
  memberStore.refreshMembers()
  window.addEventListener('resize', handleResize)
})
</script>

<style scoped>
/* ═══ A · 档案页首 DASHBOARD DOSSIER — 与设置页/对话页同族 (2026-09) ═══ */
.dashboard-dossier {
  --paper: #f4f6f4;
  --card: #fdfefc;
  --ink: #16232a;
  --teal: #0e766e;
  --teal-soft: #198e83;
  --coral: #ef7256;
  --line: #cdd8d4;
  --line-dash: #b9c9c5;
  --muted: #5f6f6b;
  --shadow-ink: rgba(22, 35, 42, 0.12);
  --font-serif: 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
  --font-mono: Consolas, 'SFMono-Regular', 'Courier New', monospace;

  min-height: 100%;
  background: var(--paper);
  color: var(--ink);
  font-size: 14px;
  line-height: 1.6;
  max-width: 1400px;
  padding: 8px 4px 60px;
}

.mono { font-family: var(--font-mono); }

/* ── 卷首卡 ─────────────────────────────── */
.hero {
  position: relative;
  background: var(--card);
  border: 1.5px solid var(--ink);
  border-radius: 6px;
  box-shadow: 5px 5px 0 var(--shadow-ink);
  padding: 30px 34px 34px;
  margin-bottom: 26px;
  overflow: visible;
}
.hero-label {
  position: absolute; top: -10px; left: 26px;
  background: var(--paper); padding: 0 10px;
  font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.3em;
  color: var(--teal);
}
.hero-body { display: flex; justify-content: space-between; align-items: flex-start; gap: 28px; }
.hero-main { max-width: 580px; }
.hero-greeting {
  font-family: var(--font-serif);
  font-size: clamp(26px, 2.8vw, 34px); font-weight: 900;
  letter-spacing: 0.02em; margin: 0 0 6px;
}
.hero-meta {
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.12em;
  color: var(--muted); margin-bottom: 14px;
}
.hero-meta-sep { margin: 0 8px; color: var(--line-dash); }
.hero-tip {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--muted);
  border: 1px dashed var(--line-dash); border-radius: 3px;
  padding: 5px 12px; background: transparent;
}
.hero-tip b { font-family: var(--font-mono); font-size: 14px; }
.tip-mark {
  display: inline-grid; place-items: center;
  width: 16px; height: 16px; border-radius: 50%;
  font-family: var(--font-mono); font-size: 10px; font-weight: 700;
}
.tip--danger { color: var(--coral); border-color: var(--coral); }
.tip--danger b { color: var(--coral); }
.tip--danger .tip-mark { background: var(--coral); color: var(--card); }
.tip--ok { color: var(--teal); border-color: rgba(14, 118, 110, 0.5); }
.tip--ok b { color: var(--teal); }
.tip--ok .tip-mark { background: var(--teal); color: var(--card); }
.tip--quiet .tip-mark { background: var(--muted); color: var(--card); }

.hero-side { display: flex; flex-direction: column; align-items: flex-end; gap: 0; flex-shrink: 0; }
.hero-actions { display: flex; gap: 12px; z-index: 5; position: relative; }

/* ── 兔子角 ─────────────────────────────── */
.hero-pets {
  position: relative;
  display: flex; justify-content: flex-end;
  width: 100%;
  margin-top: 40px;      /* 预留气泡上升空间, 气泡不撞按钮 */
  min-height: 112px;
}
.pet-slot { position: relative; width: 128px; height: 112px; transform: scale(0.82); transform-origin: bottom center; }
.hero-ground {
  position: absolute; left: 0; right: 0; bottom: 0; height: 20px;
  background: linear-gradient(to top, rgba(129, 199, 132, 0.28), transparent);
  border-radius: 0 0 5px 5px;
  pointer-events: none; overflow: hidden;
}
.grass { position: absolute; bottom: 2px; font-size: 11px; opacity: 0.75; animation: pet-grass-sway 3s var(--ease-in-out) infinite; }

@media (max-width: 900px) {
  .hero { padding: 24px 20px 30px; }
  .hero-body { flex-direction: column; align-items: stretch; }
  .hero-side { align-items: flex-start; }
  .hero-pets { justify-content: center; min-height: 130px; }
  .pet-slot { width: 110px; height: 130px; }
}

/* ── 统计三卡 ───────────────────────────── */
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-bottom: 26px; }
@media (max-width: 720px) { .stat-grid { grid-template-columns: 1fr; } }

.stat-card {
  position: relative;
  background: var(--card);
  border: 1.5px solid var(--ink);
  border-radius: 6px;
  box-shadow: 4px 4px 0 var(--shadow-ink);
  padding: 20px 22px 16px;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.stat-card.clickable { cursor: pointer; }
.stat-card:hover { transform: translate(-1px, -2px); box-shadow: 6px 6px 0 var(--shadow-ink); }
.stat-label {
  position: absolute; top: -9px; left: 18px;
  background: var(--paper); padding: 0 8px;
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 0.28em; color: var(--muted);
}
.stat-name { font-family: var(--font-serif); font-size: 14px; font-weight: 700; color: var(--muted); margin-bottom: 2px; }
.stat-value {
  font-family: var(--font-mono); font-size: 46px; font-weight: 700; line-height: 1.15;
  font-variant-numeric: tabular-nums;
}
.stat-value--teal { color: var(--teal); }
.stat-value--green { color: #3d7a3d; }
.stat-value--coral { color: var(--coral); }
.stat-rule { border-top: 1px dashed var(--line-dash); margin: 10px 0 8px; }
.stat-hint { font-size: 12px; color: var(--muted); }
.stat-card--danger { border-style: dashed; }
.stat-card--danger.has-danger { border: 1.5px solid var(--coral); }
.stamp {
  position: absolute; right: 16px; top: 34px;
  border: 2px solid var(--coral); color: var(--coral);
  font-family: var(--font-serif); font-weight: 900; font-size: 13px; letter-spacing: 0.14em;
  padding: 4px 10px; border-radius: 3px;
  transform: rotate(8deg);
  opacity: 0.85;
}

/* 骨架 */
.stat-card.is-skeleton { border-style: dashed; box-shadow: none; }
.sk { background: linear-gradient(90deg, var(--line) 25%, var(--paper) 50%, var(--line) 75%); background-size: 200% 100%; animation: dossier-shimmer 1.2s infinite; border-radius: 3px; }
.sk-label { width: 46%; height: 14px; margin-bottom: 16px; }
.sk-num { width: 40%; height: 40px; }
.sk-hint { width: 60%; height: 10px; margin-top: 16px; }
.sk-avatar { width: 30px; height: 30px; border-radius: 50%; }
.sk-line { height: 14px; }
@keyframes dossier-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* ── 任务卡 ─────────────────────────────── */
.card {
  background: var(--card);
  border: 1.5px solid var(--ink);
  border-radius: 6px;
  box-shadow: 5px 5px 0 var(--shadow-ink);
  padding: 0 0 14px;
}
.card-head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 14px;
  padding: 18px 24px 12px;
  border-bottom: 1.5px solid var(--ink);
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.card-title { font-family: var(--font-serif); font-size: 17px; font-weight: 900; letter-spacing: 0.04em; margin: 0; }
.sec-no { color: var(--teal); font-weight: 900; margin-right: 4px; }
.card-head-right { display: flex; align-items: baseline; gap: 14px; }
.card-count { font-size: 10px; letter-spacing: 0.16em; color: var(--muted); }
.view-all {
  background: none; border: none; cursor: pointer; padding: 0;
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.06em;
  color: var(--teal);
  border-bottom: 1px dashed transparent;
  transition: border-color 0.15s ease;
}
.view-all:hover { border-bottom-color: var(--teal); }

.task-groups { display: flex; flex-direction: column; gap: 14px; padding: 8px 24px 8px; }

.task-group { border: 1px solid var(--line); border-radius: 4px; background: transparent; overflow: hidden; }
.group-head {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px;
  background: linear-gradient(to right, rgba(14, 118, 110, 0.05), transparent 70%);
  border-bottom: 1px dashed var(--line-dash);
  cursor: pointer; user-select: none;
}
.group-head:hover { background: rgba(14, 118, 110, 0.09); }
.monogram {
  display: inline-grid; place-items: center; flex-shrink: 0;
  width: 30px; height: 30px; border-radius: 50%;
  background: var(--teal); color: var(--card);
  font-family: var(--font-serif); font-size: 13px; font-weight: 900;
  overflow: hidden;
}
.monogram img { width: 100%; height: 100%; object-fit: cover; }
.group-name { font-weight: 600; font-size: 14px; }
.group-count { font-size: 10.5px; letter-spacing: 0.12em; color: var(--muted); margin-left: 2px; }
.collapse-icon { margin-left: auto; transition: transform 0.2s ease; color: var(--muted); }
.collapse-icon.collapsed { transform: rotate(-90deg); }
.unassigned-group .monogram { background: var(--coral); }

.group-body { display: flex; flex-direction: column; }
.task-row {
  display: flex; align-items: center; gap: 14px;
  padding: 11px 14px;
  border-bottom: 1px dashed var(--line);
  transition: background 0.12s ease;
}
.task-row:last-child { border-bottom: none; }
.task-row:hover { background: rgba(14, 118, 110, 0.04); }
.task-row.overdue { background: rgba(239, 114, 86, 0.05); }
.task-main { flex: 1; min-width: 0; }
.task-title {
  font-size: 14px; color: var(--ink); margin-bottom: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.task-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.08em;
  border: 1px solid var(--line-dash); border-radius: 2px;
  padding: 1px 7px; color: var(--muted); background: transparent;
}
.chip--p-high { border-color: var(--coral); color: var(--coral); }
.chip--p-medium { border-color: var(--teal); color: var(--teal); }
.chip--p-low { color: var(--muted); }
.chip--status { border-color: var(--teal-soft); color: var(--teal-soft); }
.chip--meeting { border-style: dashed; border-color: var(--coral); color: var(--coral); }

.task-due {
  font-size: 11.5px; color: var(--muted); letter-spacing: 0.04em;
  flex-shrink: 0; min-width: 78px; text-align: right;
  display: flex; align-items: center; justify-content: flex-end; gap: 4px;
}
.task-due.overdue { color: var(--coral); font-weight: 700; }
.due-mark {
  display: inline-grid; place-items: center; width: 14px; height: 14px;
  border-radius: 50%; background: var(--coral); color: var(--card); font-size: 9px;
}
.task-actions { display: flex; gap: 8px; flex-shrink: 0; align-items: center; }
.act {
  cursor: pointer; font-size: 12px; letter-spacing: 0.05em;
  border-radius: 12px; padding: 4px 12px;
  transition: background 0.14s ease, color 0.14s ease;
}
.act--done {
  background: transparent; border: 1.5px solid var(--teal); color: var(--teal);
  font-weight: 600;
}
.act--done:hover { background: var(--teal); color: var(--card); }
.act--edit { background: none; border: none; color: var(--muted); font-family: var(--font-mono); font-size: 11px; }
.act--edit:hover { color: var(--ink); }

.empty-state { display: flex; justify-content: center; align-items: center; padding: 40px 0; }
.task-group.is-skeleton { border: 1px dashed var(--line-dash); box-shadow: none; }
.task-group.is-skeleton .group-head { display: flex; }

/* 对话框: 档案风按钮覆盖 (对齐全站 :root 按钮覆盖优先级) */
.dashboard.dashboard-dossier .dossier-dialog .el-button--primary,
.dashboard.dashboard-dossier .hero-actions .el-button--primary.dbtn--solid {
  background: var(--teal) !important;
  border-color: var(--teal) !important;
  color: var(--card) !important;
  font-family: var(--font-serif);
  letter-spacing: 0.06em;
  box-shadow: 3px 3px 0 var(--shadow-ink);
}
.dashboard.dashboard-dossier .hero-actions .dbtn--solid:hover { background: var(--teal-soft) !important; border-color: var(--teal-soft) !important; }
.dashboard.dashboard-dossier .hero-actions .dbtn--line {
  background: transparent !important;
  border: 1.5px dashed var(--ink) !important;
  color: var(--ink) !important;
  font-family: var(--font-serif);
  letter-spacing: 0.06em;
}
.dashboard.dashboard-dossier .hero-actions .dbtn--line:hover { border-style: solid !important; background: rgba(14, 118, 110, 0.06) !important; }
.dashboard.dashboard-dossier .hero-actions .dbtn { border-radius: 3px; height: 44px; }
</style>

<!-- dark 换墨盘 (与 SettingsView 同变量族) -->
<style>
[data-theme="dark"] .dashboard-dossier {
  --paper: #12191d;
  --card: #172126;
  --ink: #e2ecea;
  --teal: #35c2a4;
  --teal-soft: #4ad0b4;
  --coral: #ff8a6b;
  --line: #263740;
  --line-dash: #31454f;
  --muted: #8ba4a0;
  --shadow-ink: rgba(0, 0, 0, 0.45);
}
[data-theme="dark"] .dashboard-dossier .stat-value--green { color: #7ac07a; }
[data-theme="dark"] .dashboard-dossier .hero-ground { background: linear-gradient(to top, rgba(53, 194, 164, 0.12), transparent); }
[data-theme="dark"] .dashboard-dossier .group-head { background: linear-gradient(to right, rgba(53, 194, 164, 0.06), transparent 70%); }
[data-theme="dark"] .dashboard-dossier .group-head:hover { background: rgba(53, 194, 164, 0.1); }
[data-theme="dark"] .dashboard-dossier .task-row.overdue { background: rgba(255, 138, 107, 0.06); }
[data-theme="dark"] .dashboard-dossier .monogram { color: #101a16; }
[data-theme="dark"] .dashboard-dossier .tip--ok .tip-mark,
[data-theme="dark"] .dashboard-dossier .tip--danger .tip-mark { color: #101a16; }
[data-theme="dark"] .dashboard-dossier .stamp { color: var(--coral); border-color: var(--coral); }
[data-theme="dark"] .dashboard.dashboard-dossier .el-button--primary { background: var(--teal) !important; border-color: var(--teal) !important; color: #101a16 !important; }
</style>
