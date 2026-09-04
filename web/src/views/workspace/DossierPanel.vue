<template>
  <div class="dossier-panel">
    <!-- 卷首档案头 (J 语言: 衬线标题 + mono 计数 + 章) -->
    <div class="phead fade-slide-up stagger-1">
      <h2>团队 · 卷为纲，人为目</h2>
      <span class="sub">{{ headCount }}</span>
      <span class="grow"></span>
      <slot name="actions"></slot>
      <span class="hstamp ok">名册挂卷下 · 单页总览</span>
    </div>

    <!-- 导览带 (总·起): 一卷一签 + 缺口签, 点击滚到对应卷 -->
    <div class="ovband fade-slide-up stagger-2">
      <a
        v-for="d in dossiers"
        :key="d.id"
        class="ovchip"
        href="javascript:void(0)"
        @click="scrollTo(`doss-${d.id}`)"
      >
        <span class="no">卷宗 NO.{{ d.no }}</span>
        <b>{{ d.name }}</b>
        <span class="st">
          <span>{{ d.persons }} 人</span>
          <span>{{ d.pct === null ? '—' : d.pct + '%' }}</span>
          <span v-if="d.lateCount" class="lt">● 逾期 {{ d.lateCount }}</span>
          <span v-else class="okt">按期</span>
        </span>
      </a>
      <a
        v-if="unfiled.length"
        class="ovchip warn"
        href="javascript:void(0)"
        @click="scrollTo('doss-unfiled')"
      >
        <span class="no">缺口</span>
        <b>未入卷 {{ unfiled.length }} 人</b>
        <span class="st"><span>{{ unfiled.map(m => m.name).join(' · ') }}</span></span>
      </a>
    </div>

    <!-- 分: 每卷一节, 节下挂成员行 -->
    <section
      v-for="(d, i) in dossiers"
      :id="`doss-${d.id}`"
      :key="d.id"
      class="doss"
      :class="`fade-slide-up stagger-${Math.min(i + 3, 6)}`"
    >
      <div class="dhead">
        <span class="dno">NO.{{ d.no }}</span>
        <div class="dt" @click="$emit('open-project', d.raw)">
          {{ d.name }}
          <div class="dsub">{{ d.period }} · MB-LAB PROJECT FILE</div>
        </div>
        <div v-if="d.pct !== null" class="druler">
          <i :style="{ width: d.pct + '%' }"></i>
          <em v-if="d.pct < 100" :style="{ left: d.pct + '%' }"></em>
          <em v-else style="left: calc(100% - 8px)"></em>
        </div>
        <span v-if="d.pct !== null" class="pct">{{ d.pct }}%</span>
        <span class="dstate" :class="d.stamp.cls">{{ d.stamp.text }}</span>
        <span class="dops" @click.stop>
          <span class="op" @click="$emit('open-project', d.raw)">开卷</span>
        </span>
      </div>
      <div class="dband">{{ d.persons }} 名成员编入此卷<template v-if="d.vpMissing"> · {{ d.vpMissing }} 人未录声纹</template></div>
      <div class="dbody">
        <div v-for="m in d.persons_list" :key="m.id" class="frow">
          <span class="av">
            <img v-if="m.avatar" :src="m.avatar" :alt="m.name">
            <template v-else>{{ m.name?.charAt(0) }}</template>
          </span>
          <div class="idw">
            <b>{{ m.name }}</b>
            <span>#{{ padId(m.id) }} · {{ m.grade || '届别未录' }}</span>
          </div>
          <div class="fa">{{ m.research_area || '研究方向未登记' }}</div>
          <div class="fs">
            <span v-for="s in (m.skills || []).slice(0, 3)" :key="s" class="sk">{{ s }}</span>
          </div>
          <div class="fv">
            <span v-if="m.voice_sample_count" class="vp">声纹 ×{{ m.voice_sample_count }}</span>
            <span v-else class="vp no">未录入</span>
          </div>
          <div class="fop" @click.stop>
            <span class="op" @click="$emit('open-member', m)">详情</span>
          </div>
        </div>
        <p v-if="!d.persons_list.length" class="empty-hint">○ 此卷未编入成员 · 名册变更后自动入卷</p>
      </div>
    </section>

    <!-- 缺口: 未入卷成员 (常驻, 管理看板) -->
    <section id="doss-unfiled" class="doss unfiled">
      <div class="dhead">
        <span class="dno warn">缺口</span>
        <div class="dt">未入卷成员
          <div class="dsub">成员名册变更后自动挂到对应卷下</div>
        </div>
        <span class="grow"></span>
      </div>
      <div class="dbody">
        <div v-for="m in unfiled" :key="m.id" class="frow dim">
          <span class="av">
            <img v-if="m.avatar" :src="m.avatar" :alt="m.name">
            <template v-else>{{ m.name?.charAt(0) }}</template>
          </span>
          <div class="idw">
            <b>{{ m.name }}</b>
            <span>#{{ padId(m.id) }} · {{ m.grade || '届别未录' }}
              <span v-if="isTeacher(m)" class="role-stamp">导师组</span>
              <span v-else-if="isAlumni(m)" class="role-stamp g">已毕业</span>
            </span>
          </div>
          <div class="fa">{{ m.research_area || '研究方向未登记' }}</div>
          <div class="fs"></div>
          <div class="fv">
            <span v-if="m.voice_sample_count" class="vp">声纹 ×{{ m.voice_sample_count }}</span>
            <span v-else class="vp no">未录入</span>
          </div>
          <div class="fop" @click.stop>
            <span class="op cta" @click="$emit('open-member', m)">详情</span>
          </div>
        </div>
        <p v-if="!unfiled.length" class="empty-hint">✓ 全员已入卷</p>
      </div>
    </section>

    <!-- 总·收: 全团卷宗账 -->
    <div class="tally">
      <span>全团卷宗账</span>
      <b>{{ linkedCount }}<i>/{{ totalMembers }} 入卷</i></b>
      <b>{{ lateTotal }}<i> 逾期未闭里程碑</i></b>
      <b class="brk">{{ dossiers.map(d => `NO.${d.no}×${d.persons}`).join(' · ') }}</b>
    </div>
  </div>
</template>

<script setup>
/**
 * DossierPanel.vue — V 稿「卷领人归」实装 (docs/design-proposals/team-2026-09/V-dossier.html)
 *
 * 2026-09-04 主拍选定乙组 V: 卷为纲 · 人为目, 一个项目下方直接挂它的成员。
 * - 数据 0 新接口: GET /projects + GET /projects/{id}/milestones + memberStore (与两 Panel 同源)
 * - 成员归属 = projects.members id 数组反向 join; 幽灵 id (不在成员列表) 不计入行, 详情弹窗已有口径
 * - 逾期未闭/周期标尺 pct 口径与 ProjectsPanel 完全一致 (同一公式同判据)
 * - 排序: 导师→博→硕→本科→未分类→已毕业 (GORD)
 * - tokens 自包含在 .dossier-panel 根 (防跨组件继承断链); dark 翻转非 scoped 块 (v60-v67 教训)
 */
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { useMemberStore } from '@/stores/member'

defineEmits(['open-project', 'open-member'])

const memberStore = useMemberStore()
const projects = ref([])
const milestonesMap = ref({})   // { [projectId]: Milestone[] }

async function fetchProjects() {
  try {
    const res = await axios.get('/api/v1/projects')
    projects.value = res.data?.items || (Array.isArray(res.data) ? res.data : [])
    Promise.all(projects.value.map(p =>
      axios.get(`/api/v1/projects/${p.id}/milestones`)
        .then(r => { milestonesMap.value = { ...milestonesMap.value, [p.id]: r.data || [] } })
        .catch(() => {})))
  } catch (e) {
    console.error('DossierPanel 拉取项目失败:', e)
  }
}

onMounted(fetchProjects)
defineExpose({ fetchProjects })

// ---------------------------------------------------------------- 派生

const padId = (id) => (id == null ? '—' : String(id).padStart(3, '0'))

const GORD = { '副教授': 0, '教授': 0, '老师': 0, '助教': 0, '博士后': 0, '博后': 0,
               '博一': 1, '博二': 1, '博三': 1, '研三': 2, '研二': 3, '研一': 4,
               '大四': 5, '大三': 6, '大二': 6, '大一': 6, '已毕业': 9 }
const gradeRank = (m) => GORD[m.grade] ?? 7
const isTeacher = (m) => /教授|老师|助教|博后|博士后/.test(m.grade || '') && !/毕业/.test(m.grade || '')
const isAlumni = (m) => /毕业/.test(m.grade || '')

const isMsDone = (m) => m.status === 'completed' || !!m.completed_at
const isMsLate = (m) => !isMsDone(m) && m.due_date && dayjs(m.due_date).isBefore(dayjs(), 'day')

function cyclePct(p) {
  if (!p.start_date || !p.end_date) return null
  const start = dayjs(p.start_date), end = dayjs(p.end_date)
  if (!end.isAfter(start)) return null
  const pct = dayjs().diff(start, 'day') / end.diff(start, 'day') * 100
  return Math.max(0, Math.min(100, Math.round(pct)))
}

function stampOf(p) {
  if (p.status === 'completed') return { text: '已结案', cls: 'ok' }
  if (p.status === 'archived') return { text: '已归档', cls: 'ok' }
  if (p.status === 'paused') return { text: '已暂停', cls: '' }
  const late = (milestonesMap.value[p.id] || []).filter(isMsLate).length
  if (late > 0) return { text: `逾期未闭 ×${late}`, cls: 'bad' }
  return { text: '在研', cls: 'ok' }
}

const memberById = computed(() => {
  const map = {}
  for (const m of memberStore.members) map[m.id] = m
  return map
})

const dossiers = computed(() =>
  [...projects.value]
    .sort((a, b) => a.id - b.id)
    .map((p) => {
      const persons = (p.members || [])
        .map(id => memberById.value[id])
        .filter(Boolean)
        .sort((a, b) => gradeRank(a) - gradeRank(b) || a.id - b.id)
      const pct = cyclePct(p)
      const f = (d) => (d ? dayjs(d).format('YYYY-MM') : '?')
      return {
        id: p.id,
        no: padId(p.id),
        name: p.name,
        raw: p,
        period: `${f(p.start_date)} → ${f(p.end_date)}`,
        pct,
        lateCount: (milestonesMap.value[p.id] || []).filter(isMsLate).length,
        persons: persons.length,
        persons_list: persons,
        vpMissing: persons.filter(m => !m.voice_sample_count).length,
        stamp: stampOf(p),
      }
    }))

const linkedIds = computed(() => new Set(dossiers.value.flatMap(d => d.persons_list.map(m => m.id))))

const unfiled = computed(() =>
  memberStore.members
    .filter(m => !linkedIds.value.has(m.id))
    .sort((a, b) => (isTeacher(b) ? 1 : 0) - (isTeacher(a) ? 1 : 0) || a.id - b.id))

const linkedCount = computed(() => linkedIds.value.size)
const totalMembers = computed(() => memberStore.members.length)
const lateTotal = computed(() => dossiers.value.reduce((s, d) => s + d.lateCount, 0))

const headCount = computed(() =>
  `${dossiers.value.length} FILES · ${linkedCount.value}/${totalMembers.value} LINKED · ${lateTotal.value} LATE`)

function scrollTo(id) {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<style scoped>
/* --- tokens 自包含 (J/V 家族, 不依赖组件树继承) --- */
.dossier-panel {
  --ws-card: #fdfefc; --ws-ink: #16232a; --ws-steel: #5a6b6a; --ws-fog: #8ba0a0;
  --ws-hair: #c9d2ca; --ws-teal: #0e766e; --ws-teal-soft: #dcece5;
  --ws-coral: #ef7256; --ws-paper: #f4f6f4; --ws-shadow: rgba(22, 35, 42, 0.12);
  --ws-mono: Consolas, 'Courier New', monospace;
  --ws-serif: Georgia, 'Songti SC', 'SimSun', serif;
}

/* --- 卷首头 --- */
.phead { display: flex; align-items: baseline; gap: 14px; margin: 2px 0 14px; }
.phead h2 { margin: 0; font-family: var(--ws-serif); font-size: 20px; color: var(--ws-ink); }
.phead .sub { font-family: var(--ws-mono); font-size: 10px; letter-spacing: .12em; color: var(--ws-fog); }
.phead .grow { flex: 1; }
.phead .hstamp { font-family: var(--ws-mono); font-size: 9.5px; letter-spacing: .14em; color: var(--ws-teal); border: 1.5px dashed var(--ws-teal); border-radius: 6px; padding: 3px 9px; transform: rotate(-1.2deg); }

/* --- 导览带 --- */
.ovband { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 18px; }
.ovchip { display: block; text-decoration: none; background: var(--ws-card); border: 1.5px solid var(--ws-ink); border-radius: 9px; padding: 9px 12px 10px; box-shadow: 3px 3px 0 var(--ws-shadow); cursor: pointer; }
.ovchip:hover { border-color: var(--ws-teal); }
.ovchip .no { font-family: var(--ws-mono); font-size: 8.5px; letter-spacing: .14em; color: var(--ws-fog); }
.ovchip b { display: block; font-family: var(--ws-serif); font-size: 13px; color: var(--ws-ink); margin: 3px 0 7px; line-height: 1.35; }
.ovchip .st { display: flex; flex-wrap: wrap; gap: 9px; font-family: var(--ws-mono); font-size: 9.5px; color: var(--ws-steel); }
.ovchip .lt { color: var(--ws-coral); }
.ovchip .okt { color: var(--ws-teal); }
.ovchip.warn { border-style: dashed; border-color: var(--ws-coral); }
.ovchip.warn b { color: var(--ws-coral); }

/* --- 卷块 --- */
.doss { background: var(--ws-card); border: 1.5px solid var(--ws-ink); border-radius: 11px; margin-bottom: 16px; box-shadow: 3px 3px 0 var(--ws-shadow); scroll-margin-top: 8px; }
.dhead { display: flex; align-items: center; gap: 14px; padding: 11px 16px; border-bottom: 1.5px solid var(--ws-hair); background: var(--ws-paper); border-radius: 10px 10px 0 0; }
.dno { font-family: var(--ws-mono); font-size: 9px; letter-spacing: .12em; color: var(--ws-teal); border: 1.5px solid var(--ws-teal); border-radius: 4px; padding: 3px 7px; flex-shrink: 0; }
.dno.warn { color: var(--ws-coral); border-color: var(--ws-coral); border-style: dashed; }
.dt { font-family: var(--ws-serif); font-size: 15.5px; font-weight: 700; color: var(--ws-ink); line-height: 1.2; cursor: pointer; min-width: 0; }
.dt:hover { color: var(--ws-teal); }
.dsub { font-family: var(--ws-mono); font-size: 8.5px; letter-spacing: .1em; color: var(--ws-fog); margin-top: 3px; font-weight: 400; }
.druler { flex: 1; max-width: 260px; height: 12px; position: relative; border-bottom: 1.5px solid var(--ws-ink); }
.druler i { position: absolute; bottom: 2px; left: 0; height: 4px; background: var(--ws-teal); border-radius: 2px; }
.druler em { position: absolute; bottom: 0; width: 0; height: 0; border: 4px solid transparent; border-bottom-color: var(--ws-coral); border-top: 0; margin-left: -4px; }
.pct { font-family: var(--ws-serif); font-size: 13px; font-weight: 700; color: var(--ws-teal); width: 36px; text-align: right; }
.dstate { font-family: var(--ws-mono); font-size: 9.5px; color: var(--ws-teal); border: 1px solid var(--ws-teal); border-radius: 5px; padding: 3px 8px; flex-shrink: 0; }
.dstate.bad { color: var(--ws-coral); border: 1.5px dashed var(--ws-coral); border-radius: 5px; transform: rotate(-1.5deg); }
.dstate.ok { color: var(--ws-teal); }
.dops { display: flex; gap: 6px; flex-shrink: 0; }
.op { font-size: 11px; color: var(--ws-steel); border: 1px solid var(--ws-hair); border-radius: 5px; padding: 3px 9px; cursor: pointer; background: var(--ws-card); }
.op:hover { color: var(--ws-teal); border-color: var(--ws-teal); }
.op.add { background: var(--ws-teal); color: #fff; border-color: var(--ws-teal); }
.op.cta { color: var(--ws-coral); border-color: var(--ws-coral); border-style: dashed; }
.grow { flex: 1; }

.dband { font-family: var(--ws-mono); font-size: 9px; letter-spacing: .1em; color: var(--ws-fog); padding: 7px 16px 0; }
.dbody { padding: 4px 16px 12px; }

/* --- 成员行 --- */
.frow { display: grid; grid-template-columns: 36px 140px minmax(120px, 165px) 1fr auto 84px 60px; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px dotted var(--ws-hair); }
.frow:last-child { border-bottom: 0; }
.frow:hover .op { opacity: 1; }
.av { width: 32px; height: 32px; border-radius: 8px; border: 1.5px solid var(--ws-ink); background: var(--ws-paper); display: grid; place-items: center; font-family: var(--ws-serif); font-size: 14px; font-weight: 600; color: var(--ws-ink); overflow: hidden; box-shadow: 2px 2px 0 var(--ws-shadow); }
.av img { width: 100%; height: 100%; object-fit: cover; }
.idw b { font-family: var(--ws-serif); font-size: 13.5px; color: var(--ws-ink); }
.idw span { display: block; font-family: var(--ws-mono); font-size: 9px; color: var(--ws-fog); margin-top: 2px; }
.fa { font-size: 12px; color: var(--ws-steel); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fs { display: flex; gap: 5px; flex-wrap: wrap; min-width: 0; }
.sk { font-family: var(--ws-mono); font-size: 9px; color: var(--ws-steel); border: 1px solid var(--ws-hair); border-radius: 4px; padding: 1px 6px; }
.vp { font-family: var(--ws-mono); font-size: 9.5px; color: var(--ws-teal); border: 1px solid var(--ws-teal); background: var(--ws-teal-soft); border-radius: 4px; padding: 2px 6px; white-space: nowrap; }
.vp.no { color: var(--ws-coral); border-color: var(--ws-coral); background: transparent; border-style: dashed; }
.fop .op { opacity: 0; transition: opacity .15s; font-family: var(--ws-mono); font-size: 10px; }
.role-stamp { font-family: var(--ws-mono); font-size: 8px; letter-spacing: .1em; color: var(--ws-coral); border: 1.2px dashed var(--ws-coral); border-radius: 4px; padding: 1px 5px; margin-left: 6px; }
.role-stamp.g { color: var(--ws-fog); border-color: var(--ws-fog); }
.frow.dim .av, .frow.dim .idw b { opacity: .6; }

.unfiled .dhead { border-bottom-style: dashed; border-bottom-color: var(--ws-coral); }
.empty-hint { color: var(--ws-fog); font-size: 12px; padding: 8px 0; margin: 0; }

/* --- 总账条 --- */
.tally { display: flex; align-items: center; gap: 22px; background: var(--ws-ink); color: var(--ws-card); border-radius: 11px; padding: 13px 20px; margin: 4px 0 6px; }
.tally > span { font-family: var(--ws-mono); font-size: 9px; letter-spacing: .18em; color: var(--ws-fog); }
.tally b { font-family: var(--ws-serif); font-size: 19px; }
.tally i { font-style: normal; font-family: var(--ws-mono); font-size: 9.5px; color: #b9c6c2; margin-left: 3px; }
.tally .brk { font-size: 12px; font-family: var(--ws-mono); font-weight: 400; }

/* --- 窄屏: 导览带 2 列, 行收掉技能列 --- */
@media (max-width: 1100px) {
  .ovband { grid-template-columns: 1fr 1fr; }
  .frow { grid-template-columns: 34px 130px minmax(90px, 1fr) auto 56px; }
  .fs { display: none; }
  .druler { display: none; }
}
</style>

<!-- v60-v67 教训: dark 覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .dossier-panel {
  --ws-card: #18232a; --ws-ink: #dfe9e6; --ws-steel: #9ab0ae; --ws-fog: #6b8286;
  --ws-hair: #27363e; --ws-teal: #35c2a4; --ws-teal-soft: #12312b;
  --ws-coral: #ef7256; --ws-paper: #10171b; --ws-shadow: rgba(0, 0, 0, 0.5);
}
[data-theme="dark"] .dossier-panel .dhead { background: #131d23; }
[data-theme="dark"] .dossier-panel .tally { background: #dfe9e6; color: #16232a; }
[data-theme="dark"] .dossier-panel .tally i { color: #4c5f63; }
[data-theme="dark"] .dossier-panel .op { background: var(--ws-card); }
</style>
