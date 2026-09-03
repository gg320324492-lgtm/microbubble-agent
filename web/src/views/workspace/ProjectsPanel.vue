<template>
  <div class="projects-panel">
    <!-- 卷首档案头 (J 稿语言: 衬线标题 + mono 计数行 + 日期章) -->
    <div class="phead fade-slide-up stagger-1">
      <h2>科研项目 · 卷宗库</h2>
      <span class="sub">{{ headCount }}</span>
      <span class="grow"></span>
      <span class="hstamp ok">数据截至 {{ todayStamp }}</span>
    </div>

    <!-- 筛选印章带 (替原 el-select 状态筛选) -->
    <div class="fband fade-slide-up stagger-2">
      <span
        v-for="c in chips"
        :key="c.key"
        class="fchip"
        :class="{ on: chip === c.key, late: c.key === 'late' && c.count > 0 }"
        @click="chip = c.key"
      >{{ c.label }}<b>{{ c.count }}</b></span>
      <button class="fadd" @click="showCreateDialog = true">＋ 建立卷宗</button>
    </div>

    <!-- 空态 -->
    <div v-if="!cards.length" class="fempty fade-slide-up stagger-3">
      <template v-if="projects.length">此筛选下暂无卷宗 · 换个印章试试</template>
      <template v-else>卷宗库是空的 · 点右上「＋ 建立卷宗」开册</template>
    </div>

    <!-- 吊篮档案卡 2×2 -->
    <div class="files">
      <div
        v-for="(c, idx) in cards"
        :key="c.id"
        class="folder"
        :class="`fade-slide-up stagger-${Math.min(idx + 2, 6)}`"
      >
        <div class="ftab">NO.{{ c.no }}</div>
        <div class="fbody" @click="$emit('open-detail', c.raw)">
          <span class="hole"></span>
          <div class="fhead">
            <div class="fno">MB-LAB · PROJECT FILE · 卷宗 NO.{{ c.no }}</div>
            <!-- 原生 div 拦冒泡 (@click.stop 挂组件标签会被当组件事件, 不阻原生冒泡 → 会误开详情) -->
            <div class="fmenu" @click.stop @mousedown.stop>
              <el-dropdown
                trigger="click"
                @command="(cmd) => handleCommand(cmd, c.raw)"
              >
                <span class="fmenu-btn" aria-label="更多操作">⋯</span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">编辑</el-dropdown-item>
                    <el-dropdown-item command="pause">暂停</el-dropdown-item>
                    <el-dropdown-item command="complete">完成</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <span class="hstamp" :class="c.stampCls">{{ c.stamp }}</span>
          </div>
          <div class="fname">{{ c.name }}</div>
          <div class="fdesc">{{ c.desc || '暂无描述 · 点击开卷补全。' }}</div>

          <div class="frow">
            <span class="k">周期</span>
            <span class="mono-date">{{ c.period }}</span>
            <span v-if="c.area" class="area-tag">{{ c.area }}</span>
          </div>

          <div class="frow">
            <span class="k">成员</span>
            <template v-if="c.memberTags.length">
              <span v-for="n in c.memberTags" :key="n" class="labtag">{{ n }}</span>
              <span v-if="c.moreMembers" class="labtag">+{{ c.moreMembers }}</span>
            </template>
            <span v-else class="labtag none">未指派</span>
          </div>

          <div class="frow">
            <span class="k">周期标尺</span>
            <div v-if="c.pct !== null" class="ruler">
              <i v-for="n in 9" :key="n" :style="{ left: n * 10 + '%' }"></i>
              <span class="fill" :style="{ width: c.pct + '%' }"></span>
              <span v-if="c.pct < 100" class="now" :style="{ left: c.pct + '%', marginLeft: '-4px' }"></span>
              <span v-else class="now" style="right: -8px"></span>
            </div>
            <div v-else class="ruler nodates"><span class="nodates-t">未录起止日期</span></div>
            <span class="pct">{{ c.pct === null ? '—' : c.pct + '%' }}</span>
          </div>

          <div class="frow msrow">
            <span class="k">里程碑</span>
            <div class="mst">
              <div v-if="!c.milestones.length" style="color: var(--pj-fog)">○ 未立里程碑</div>
              <div v-for="m in c.milestones" :key="m.id" :class="{ late: m.late }">
                <template v-if="m.done"><s>◉ {{ m.name }}</s> <span class="d">{{ m.date }} ✓</span></template>
                <template v-else-if="m.late"><span class="d late">{{ m.date }}</span><span class="late-t">▸ {{ m.name }} · 逾期未闭</span></template>
                <template v-else><span class="d">{{ m.date }}</span>▸ {{ m.name }}<span v-if="m.left"> · {{ m.left }}</span></template>
              </div>
              <div v-if="c.moreMs" style="color: var(--pj-fog)">… 另 {{ c.moreMs }} 项,点开卷宗查看</div>
            </div>
          </div>

        </div>
      </div>
    </div>

    <!-- 创建项目对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建项目" :width="isMobile ? '90vw' : '500px'" top="8vh">
      <el-form :model="projectForm" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="projectForm.name" name="projectForm-name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="研究方向">
          <el-input v-model="projectForm.research_area" name="projectForm-research_area" placeholder="如：水处理、农业应用" />
        </el-form-item>
        <el-form-item label="项目周期">
          <div style="display:flex;gap:8px;align-items:center;width:100%">
            <el-date-picker
              v-model="projectForm.startDate"
              name="project-form-start-date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
              style="flex:1"
              :clearable="true"
            />
            <span>至</span>
            <el-date-picker
              v-model="projectForm.endDate"
              name="project-form-end-date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
              style="flex:1"
              :clearable="true"
            />
          </div>
        </el-form-item>
        <el-form-item label="项目成员">
          <el-select
            v-model="projectForm.members" name="projectForm-members"
            multiple
            placeholder="选择项目成员"
          >
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="projectForm.description" name="projectForm-description"
            type="textarea"
            :rows="3"
            placeholder="请输入项目描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createProject">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑项目对话框（与创建共享 projectForm） -->
    <el-dialog v-model="showEditDialog" title="编辑项目" :width="isMobile ? '95vw' : '500px'" top="8vh">
      <el-form :model="projectForm" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="projectForm.name" name="projectForm-edit-name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="研究方向">
          <el-input v-model="projectForm.research_area" name="projectForm-edit-research-area" placeholder="如：水处理、农业应用" />
        </el-form-item>
        <el-form-item label="项目周期">
          <div style="display:flex;gap:8px;align-items:center;width:100%">
            <el-date-picker
              v-model="projectForm.startDate"
              name="project-form-edit-start-date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
              style="flex:1"
              :clearable="true"
            />
            <span>至</span>
            <el-date-picker
              v-model="projectForm.endDate"
              name="project-form-edit-end-date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
              style="flex:1"
              :clearable="true"
            />
          </div>
        </el-form-item>
        <el-form-item label="项目成员">
          <el-select
            v-model="projectForm.members"
            name="projectForm-edit-members"
            multiple
            placeholder="选择项目成员"
          >
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="projectForm.description"
            name="projectForm-edit-description"
            type="textarea"
            :rows="3"
            placeholder="请输入项目描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="updateProject">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * ProjectsPanel.vue — v78 "团队协作" 项目 tab 子组件
 *
 * 从原 web/src/views/ProjectView.vue 拆出 (2026-07-02):
 * - 保留: 项目卡片列表 + 创建/编辑 dialog + filters 状态
 * - 移除: 项目详情 dialog (由父 WorkspaceView 接管, 通过 emit 'open-detail' 触发)
 * - 详情走 WorkspaceView 顶层 el-dialog (统一位置 + 跨 tab 共享)
 *
 * 2026-07-15 修正:
 * - 加 cleanDescriptionForDisplay() 兜底防脏 description 显示
 *   (详见后端 sanitize_project_description 等价 JS 实现)
 *
 * 2026-09-04 J 稿「卷宗 · 吊篮档案卡」实装 (docs/design-proposals/projects-2026-09/J-files.html):
 * - el-select 状态筛选 → 筛选印章带 (chip), 列表一次拉全、前端按 chip 过滤
 *   (chip 计数需要全量, status 不再作为后端查询参数)
 * - 假 progress 字段 (DB 无此列, 老进度条恒 0%) → 「周期标尺」= 周期已过百分比,
 *   由 start/end 前端计算; 逾期信息上卡片 (骑缝章 + 里程碑标红), 不再只藏在详情弹窗
 * - 里程碑卡片内联: GET /projects/{id}/milestones 并发拉取 (与详情弹窗同一端点, 0 后端改动)
 * - 成员 ID 数组 → memberStore 姓名标签 (前 3 + N), memberStore 为空时补拉一次
 * - 创建/编辑/状态/删除 dialog 与逻辑全保留
 */

import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { useMemberStore } from '@/stores/member'
import { cleanDescriptionForDisplay, displayDescription } from '@/utils/textSanitize'

defineEmits(['open-detail'])

const memberStore = useMemberStore()
const members = computed(() => memberStore.members)

const isMobile = ref(window.innerWidth <= 768)
const projects = ref([])
const milestonesMap = ref({})   // { [projectId]: Milestone[] }
const chip = ref('all')         // all | active | paused | completed | late
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const editingProjectId = ref(null)

const projectForm = ref({
  name: '',
  research_area: '',
  startDate: '',
  endDate: '',
  members: [],
  description: ''
})

// ---------------------------------------------------------------- 数据拉取

// 一次拉全 (chip 计数需要全量), 状态过滤在前端 computed 做
const fetchProjects = async () => {
  try {
    const res = await axios.get('/api/v1/projects')
    projects.value = res.data.items || []
    loadAllMilestones()
  } catch (e) {
    console.error('获取项目失败:', e)
  }
}

const fetchMilestones = async (projectId) => {
  try {
    const res = await axios.get(`/api/v1/projects/${projectId}/milestones`)
    milestonesMap.value = { ...milestonesMap.value, [projectId]: res.data || [] }
  } catch (e) {
    console.error('获取里程碑失败:', e)
  }
}

const loadAllMilestones = () => {
  Promise.all(projects.value.map(p => fetchMilestones(p.id)))
}

// 成员名解析: 不在成员列表 (含被 API 过滤的停用/幽灵 id) → 明说「用户不存在」
// (store.getMemberName 的 '未分配' 兜底语义是"任务无负责人", 不适用于卷宗成员标签)
const memberName = (id) => {
  if (!members.value.length) return '…'  // 成员表未到位, 不闪「用户不存在」
  const m = members.value.find(x => x.id == id)  // == 兼容 string/number
  return m?.name || '用户不存在'
}

// ---------------------------------------------------------------- 派生

const isMsDone = (m) => m.status === 'completed' || !!m.completed_at
const isMsLate = (m) => !isMsDone(m) && m.due_date && dayjs(m.due_date).isBefore(dayjs(), 'day')

const overdueCount = (projectId) =>
  (milestonesMap.value[projectId] || []).filter(isMsLate).length

const totalLate = computed(() =>
  projects.value.reduce((s, p) => s + overdueCount(p.id), 0)
)

const chips = computed(() => {
  const list = projects.value
  return [
    { key: 'all', label: '全部', count: list.length },
    { key: 'active', label: '进行中', count: list.filter(p => p.status === 'active').length },
    { key: 'paused', label: '已暂停', count: list.filter(p => p.status === 'paused').length },
    { key: 'completed', label: '已完成', count: list.filter(p => p.status === 'completed').length },
    { key: 'late', label: '逾期未闭里程碑', count: list.filter(p => overdueCount(p.id) > 0).length },
  ]
})

const headCount = computed(() => {
  const list = projects.value
  const memberVisits = list.reduce((s, p) => s + (Array.isArray(p.members) ? p.members.length : 0), 0)
  const msTotal = list.reduce((s, p) => s + (milestonesMap.value[p.id] || []).length, 0)
  return `${list.length} IN FILE · ${memberVisits} MEMBERS · ${msTotal} MILESTONES · ${totalLate.value} LATE`
})

const todayStamp = dayjs().format('MM-DD')

// 周期标尺: 周期已过百分比 (DB 无 progress 字段, 前端由起止日期计算)
const cyclePct = (p) => {
  if (!p.start_date || !p.end_date) return null
  const start = dayjs(p.start_date)
  const end = dayjs(p.end_date)
  if (!end.isAfter(start)) return null
  const pct = dayjs().diff(start, 'day') / end.diff(start, 'day') * 100
  return Math.max(0, Math.min(100, Math.round(pct)))
}

const fmtPeriod = (p) => {
  if (!p.start_date && !p.end_date) return '起止未录'
  const f = (d) => (d ? dayjs(d).format('YYYY-MM') : '?')
  return `${f(p.start_date)} → ${f(p.end_date)}`
}

const stampOf = (p) => {
  if (p.status === 'completed') return { stamp: '已结案', cls: 'ok' }
  if (p.status === 'archived') return { stamp: '已归档', cls: 'ok' }
  if (p.status === 'paused') return { stamp: '已暂停', cls: '' }
  const late = overdueCount(p.id)
  if (late > 0) return { stamp: `逾期未闭 ×${late}`, cls: '' }
  if (p.end_date && dayjs(p.end_date).isBefore(dayjs(), 'day')) return { stamp: '周期已到 · 未结题', cls: '' }
  return { stamp: '在研', cls: 'ok' }
}

const fmtMsDate = (m) => {
  const d = m.completed_at || m.due_date
  return d ? dayjs(d).format('YY/MM/DD') : '未定'
}

const cards = computed(() => {
  let list = projects.value
  if (chip.value === 'late') list = list.filter(p => overdueCount(p.id) > 0)
  else if (chip.value !== 'all') list = list.filter(p => p.status === chip.value)

  return list.map((p, i) => {
    const rawMs = [...(milestonesMap.value[p.id] || [])].sort((a, b) =>
      String(a.due_date || '9999').localeCompare(String(b.due_date || '9999')))
    const shown = rawMs.slice(0, 3).map(m => {
      const done = isMsDone(m)
      const late = isMsLate(m)
      const left = !done && !late && m.due_date
        ? `剩 ${dayjs(m.due_date).diff(dayjs(), 'day')} 天` : ''
      return { id: m.id, name: m.name, date: fmtMsDate(m), done, late, left }
    })
    const ids = Array.isArray(p.members) ? p.members : []
    const names = ids.map(memberName)
    return {
      id: p.id,
      raw: p,
      no: String(p.id).padStart(3, '0'),
      name: p.name,
      desc: displayDescription(p.description),
      area: p.research_area || '',
      period: fmtPeriod(p),
      pct: cyclePct(p),
      memberTags: names.slice(0, 3),
      moreMembers: Math.max(0, names.length - 3),
      milestones: shown,
      moreMs: Math.max(0, rawMs.length - 3),
      ...stampOf(p),
    }
  })
})

// ---------------------------------------------------------------- 操作 (逻辑未动)

const createProject = async () => {
  if (!projectForm.value.name) {
    ElMessage.warning('请输入项目名称')
    return
  }

  try {
    const data = {
      name: projectForm.value.name,
      research_area: projectForm.value.research_area,
      description: projectForm.value.description,
      members: projectForm.value.members,
      start_date: projectForm.value.startDate,
      end_date: projectForm.value.endDate
    }
    await axios.post('/api/v1/projects', data)
    ElMessage.success('项目创建成功')
    showCreateDialog.value = false
    projectForm.value = { name: '', research_area: '', startDate: '', endDate: '', members: [], description: '' }
    fetchProjects()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

const handleCommand = async (cmd, project) => {
  switch (cmd) {
    case 'edit':
      editingProjectId.value = project.id
      // 把项目数据回填到 projectForm（共享 create 表单）
      // 2026-07-15: 编辑打开时把脏 description 预先清洗 (前端兜底)
      projectForm.value = {
        name: project.name || '',
        research_area: project.research_area || '',
        startDate: project.start_date || '',
        endDate: project.end_date || '',
        members: Array.isArray(project.members) ? [...project.members] : [],
        description: cleanDescriptionForDisplay(project.description) || '',
      }
      showEditDialog.value = true
      break
    case 'pause':
      await updateProjectStatus(project, 'paused')
      break
    case 'complete':
      await updateProjectStatus(project, 'completed')
      break
    case 'delete':
      await deleteProject(project)
      break
  }
}

const updateProject = async () => {
  if (!projectForm.value.name) {
    ElMessage.warning('请输入项目名称')
    return
  }
  if (!editingProjectId.value) return
  try {
    await axios.put(`/api/v1/projects/${editingProjectId.value}`, {
      name: projectForm.value.name,
      research_area: projectForm.value.research_area,
      start_date: projectForm.value.startDate,
      end_date: projectForm.value.endDate,
      members: projectForm.value.members,
      description: projectForm.value.description,
    })
    ElMessage.success('项目更新成功')
    showEditDialog.value = false
    editingProjectId.value = null
    fetchProjects()
  } catch (e) {
    ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message))
  }
}

const updateProjectStatus = async (project, status) => {
  try {
    await axios.put(`/api/v1/projects/${project.id}`, { status })
    ElMessage.success('状态更新成功')
    fetchProjects()
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

const deleteProject = async (project) => {
  try {
    await ElMessageBox.confirm('确定要删除这个项目吗？', '确认删除', { type: 'warning' })
    await axios.delete(`/api/v1/projects/${project.id}`)
    ElMessage.success('项目删除成功')
    fetchProjects()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  if (!members.value.length) memberStore.fetchMembers()
  fetchProjects()
})
</script>

<style scoped>
/* =====================================================================
   J 稿「卷宗 · 吊篮档案卡」皮肤 (2026-09-04)
   视觉源 docs/design-proposals/projects-2026-09/J-files.html;
   tokens 命名沿用 TaskView G 稿 --dg-* 先例 (本层用 --pj-*)
   ===================================================================== */
.projects-panel {
  --pj-card: #fdfefc; --pj-ink: #16232a; --pj-steel: #5a6b6a; --pj-fog: #8ba0a0;
  --pj-hair: #c9d2ca; --pj-teal: #0e766e; --pj-teal-soft: #dcece5;
  --pj-coral: #ef7256; --pj-green: #3d7a3d; --pj-amber: #c07f2e;
  --pj-chrome: #eaece7; --pj-paper: #f4f6f4; --pj-shadow: rgba(22, 35, 42, 0.14);
  --pj-mono: Consolas, 'Courier New', monospace;
  --pj-serif: Georgia, 'Songti SC', 'SimSun', serif;
  display: flex;
  flex-direction: column;
  padding: 16px 0;
}

/* --- 卷首档案头 --- */
.phead { display: flex; align-items: flex-end; gap: 16px; margin-bottom: 20px; }
.phead h2 { font-family: var(--pj-serif); font-size: 24px; color: var(--pj-ink); margin: 0; }
.phead .sub { font-family: var(--pj-mono); font-size: 10.5px; color: var(--pj-fog); letter-spacing: .12em; padding-bottom: 4px; }
.phead .grow { flex: 1; }

/* --- 骑缝日期章 / 状态章 --- */
.hstamp { font-family: var(--pj-mono); font-size: 9.5px; letter-spacing: .14em; color: var(--pj-coral); border: 1.5px dashed var(--pj-coral); border-radius: 6px; padding: 4px 9px; transform: rotate(-2deg); display: inline-block; background: none; }
.hstamp.ok { color: var(--pj-teal); border-color: var(--pj-teal); }

/* --- 筛选印章带 --- */
.fband { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.fchip { font-size: 12px; color: var(--pj-steel); border: 1px solid var(--pj-hair); background: var(--pj-card); border-radius: 7px; padding: 5px 11px; cursor: pointer; user-select: none; }
.fchip b { font-family: var(--pj-mono); font-size: 10.5px; color: var(--pj-fog); margin-left: 5px; font-weight: 400; }
.fchip.on { border-color: var(--pj-ink); color: var(--pj-ink); font-weight: 600; box-shadow: 2px 2px 0 rgba(22, 35, 42, .12); }
.fchip.on b { color: var(--pj-teal); }
.fchip.late b { color: var(--pj-coral); }
.fadd { margin-left: auto; background: var(--pj-ink); color: var(--pj-paper); border: 0; border-radius: 7px; padding: 7px 14px; font-size: 12.5px; cursor: pointer; box-shadow: 2px 2px 0 rgba(22, 35, 42, .25); }
.fadd:hover { background: var(--pj-teal); }

/* --- 空态 --- */
.fempty { border: 1.5px dashed var(--pj-hair); border-radius: 10px; padding: 42px 20px; text-align: center; font-size: 13px; color: var(--pj-fog); }

/* --- 吊篮档案卡 --- */
.files { display: grid; grid-template-columns: 1fr 1fr; gap: 30px 22px; }
.folder { position: relative; min-width: 0; }
.ftab { width: 170px; height: 24px; background: var(--pj-chrome); border: 1.5px solid var(--pj-ink); border-bottom: 0; border-radius: 7px 7px 0 0; margin-left: 14px; display: flex; align-items: center; justify-content: center; font-family: var(--pj-mono); font-size: 9px; letter-spacing: .2em; color: var(--pj-steel); position: relative; z-index: 0; }
.folder:nth-child(even) .ftab { background: var(--pj-teal-soft); }
.fbody { position: relative; z-index: 1; background: var(--pj-card); border: 1.5px solid var(--pj-ink); border-radius: 0 9px 9px 9px; box-shadow: 3px 3px 0 var(--pj-shadow); padding: 16px 18px 14px; cursor: pointer; transition: transform var(--duration-normal, 200ms) ease; }
.fbody:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--pj-shadow); }
/* 卷首行: fno 左, 菜单+印章右 (flex 让位, 杜绝与后续行相撞) */
.fhead { display: flex; align-items: flex-start; gap: 10px; }
.fno { font-family: var(--pj-mono); font-size: 9.5px; letter-spacing: .16em; color: var(--pj-teal); margin-bottom: 5px; flex: 1; min-width: 0; padding-top: 4px; }
.fhead .hstamp { flex-shrink: 0; }
.fname { font-family: var(--pj-serif); font-size: 18.5px; font-weight: 600; line-height: 1.35; color: var(--pj-ink); }
.fdesc { font-size: 12px; color: var(--pj-steel); line-height: 1.75; margin: 8px 0 10px; border-top: 1px dashed var(--pj-hair); padding-top: 9px; min-height: 62px; }
.frow { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: var(--pj-steel); border-top: 1px dotted var(--pj-hair); padding: 7px 0 0; margin-top: 7px; }
.frow .k { font-family: var(--pj-mono); font-size: 9px; letter-spacing: .14em; color: var(--pj-fog); width: 56px; flex-shrink: 0; }
.mono-date { font-family: var(--pj-mono); font-size: 11px; color: var(--pj-steel); }
.area-tag { margin-left: auto; font-family: var(--pj-mono); font-size: 9.5px; color: var(--pj-fog); border: 1px solid var(--pj-hair); border-radius: 3px; padding: 1px 6px; }
.labtag { font-family: var(--pj-mono); font-size: 9.5px; color: var(--pj-steel); background: var(--pj-paper); border: 1px solid var(--pj-hair); border-radius: 3px; padding: 2px 6px 2px 8px; }
.labtag.none { color: var(--pj-fog); }

/* --- 周期标尺 (替假进度条) --- */
.ruler { flex: 1; height: 14px; position: relative; border-bottom: 1.5px solid var(--pj-ink); }
.ruler i { position: absolute; bottom: 0; height: 14px; width: 1.5px; background: var(--pj-hair); }
.ruler .fill { position: absolute; bottom: 2px; left: 0; height: 4px; background: var(--pj-teal); border-radius: 2px; max-width: 100%; }
.ruler .now { position: absolute; bottom: 0; width: 0; height: 0; border: 5px solid transparent; border-bottom-color: var(--pj-coral); border-top: 0; }
.ruler.nodates { border-bottom-style: dashed; border-bottom-color: var(--pj-fog); }
.nodates-t { font-family: var(--pj-mono); font-size: 9px; color: var(--pj-fog); letter-spacing: .1em; position: absolute; left: 0; bottom: 3px; }
.pct { font-family: var(--pj-mono); font-size: 11px; color: var(--pj-ink); font-weight: 700; width: 34px; text-align: right; }

/* --- 里程碑 (逾期标红上卡片) --- */
.frow.msrow { align-items: flex-start; }
.mst { font-size: 11.5px; color: var(--pj-steel); line-height: 1.9; flex: 1; min-width: 0; }
.mst .d { font-family: var(--pj-mono); font-size: 10px; color: var(--pj-fog); margin-right: 6px; }
.mst .late .d { color: var(--pj-coral); font-weight: 700; }
.mst .late-t { color: var(--pj-coral); }
.mst s { color: var(--pj-fog); }

/* --- 装订孔 --- */
.hole { position: absolute; left: -11px; top: 64px; width: 14px; height: 56px; border: 1.5px solid var(--pj-ink); border-right: 0; border-radius: 8px 0 0 8px; background: var(--pj-paper); }

/* --- 操作菜单 (卷首行内, 印章左) --- */
.fmenu { flex-shrink: 0; }
.fmenu-btn { display: grid; place-items: center; width: 26px; height: 22px; border-radius: 5px; font-family: var(--pj-mono); font-size: 14px; color: var(--pj-fog); background: none; border: 1px solid transparent; }
.fmenu-btn:hover { color: var(--pj-teal); border-color: var(--pj-hair); background: var(--pj-paper); }

/* --- 窄屏单列 --- */
@media (max-width: 900px) {
  .files { grid-template-columns: 1fr; }
  .phead { flex-wrap: wrap; }
}

.projects-panel > .fband .fadd:focus-visible,
.projects-panel > .fband .fchip:focus-visible {
  outline: 2px solid var(--pj-teal);
  outline-offset: 1px;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
/* === J 稿卷宗皮肤 dark (2026-09-04, 对齐 J-files.html data-dark 夜览态) === */
[data-theme="dark"] .projects-panel {
  --pj-card: #18232a; --pj-ink: #dfe9e6; --pj-steel: #9ab0ae; --pj-fog: #6b8286;
  --pj-hair: #27363e; --pj-teal: #35c2a4; --pj-teal-soft: #12312b;
  --pj-coral: #ef7256; --pj-green: #6fbf6f; --pj-amber: #d9a257;
  --pj-chrome: #0c1215; --pj-paper: #10171b; --pj-shadow: rgba(0, 0, 0, 0.5);
}
[data-theme="dark"] .projects-panel .fadd {
  background: var(--pj-card); color: var(--pj-ink);
  box-shadow: 2px 2px 0 rgba(0, 0, 0, .4);
}
[data-theme="dark"] .projects-panel .fadd:hover { background: var(--pj-teal); color: #0c1215; }
[data-theme="dark"] .projects-panel .fchip.on { box-shadow: 2px 2px 0 rgba(0, 0, 0, .4); }
</style>
