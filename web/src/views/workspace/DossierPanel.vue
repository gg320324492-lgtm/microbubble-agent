<template>
  <div class="dossier-panel">
    <!-- 页头: 一行说完 (标题 + mono 计数 + 分组切换) -->
    <div class="head fade-slide-up stagger-1">
      <h1>团队协作</h1>
      <span class="meta"><b>{{ totalMembers }}</b> 人 · <b>{{ sections.length }}</b> {{ viewMode === 'project' ? '卷' : '组' }} · 声纹 <b>{{ vpDone }}/{{ totalMembers }}</b></span>
      <span class="grow"></span>
      <slot name="actions"></slot>
      <div class="seg" role="tablist">
        <button type="button" :class="{ on: viewMode === 'project' }" @click="viewMode = 'project'">按项目</button>
        <button type="button" :class="{ on: viewMode === 'grade' }" @click="viewMode = 'grade'">按届别</button>
      </div>
    </div>

    <!-- 横向项目锚导 (滚动自动高亮, 点击滚到对应卷) -->
    <div class="pstrip fade-slide-up stagger-2">
      <a
        class="pill"
        :class="{ on: activeAnchor === 'all' }"
        href="javascript:void(0)"
        @click="scrollTo('all')"
      ><span class="dot all"></span>全部<span class="c">{{ totalMembers }}</span></a>
      <a
        v-for="sec in sections"
        :id="`pill-${sec.key}`"
        :key="sec.key"
        class="pill"
        :class="{ on: activeAnchor === `doss-${sec.key}` }"
        href="javascript:void(0)"
        @click="scrollTo(`doss-${sec.key}`)"
      ><span class="dot" :style="{ background: sec.color }"></span>{{ sec.name }}<span class="c">{{ sec.persons }}</span></a>
      <a
        v-if="viewMode === 'project'"
        class="pill dashed"
        :class="{ on: activeAnchor === 'doss-unfiled' }"
        href="javascript:void(0)"
        @click="scrollTo('doss-unfiled')"
      ><span class="dot warn"></span>未编入<span class="c">{{ unfiled.length }}</span></a>
    </div>

    <!-- 卷 = 项目节 (按项目) / 身份组节 (按届别), 节下挂单行紧凑成员行 -->
    <section
      v-for="sec in sections"
      :id="`doss-${sec.key}`"
      :key="sec.key"
      class="doss"
      :class="{ muted: sec.persons > 0 && sec.vpMissing === sec.persons }"
    >
      <div class="dhead">
        <span class="dot" :style="{ background: sec.color }"></span>
        <h2>{{ sec.name }}</h2>
        <span v-if="sec.period && sec.period !== '? → ?'" class="period">{{ sec.period }}</span>
        <span class="grow"></span>
        <span class="cnt"><b>{{ sec.persons }}</b> 人<template v-if="sec.vpMissing"> · {{ sec.vpMissing }} 人未录声纹</template></span>
      </div>
      <template v-if="sec.persons">
        <div v-for="m in sec.persons_list" :key="m.id" class="row">
          <span class="nm">
            <span class="av" :style="{ background: avColor(m) }">
              <img v-if="m.avatar" :src="resolveAvatarUrl(m.avatar)" :alt="m.name">
              <template v-else>{{ m.name?.charAt(0) }}</template>
            </span>
            <b>{{ m.name }}</b><span class="id">#{{ padId(m.id) }}</span>
          </span>
          <span class="gtag" :class="{ t: isTeacher(m) }">{{ m.grade || '届别未录' }}</span>
          <span class="area" :class="{ dim: !m.research_area }">{{ m.research_area || '研究方向未登记' }}</span>
          <span class="sk"><span v-for="s in (m.skills || []).slice(0, 3)" :key="s">{{ s }}</span></span>
          <span v-if="m.voice_sample_count" class="vp">声纹 × {{ m.voice_sample_count }}</span>
          <span v-else class="vp no">未录入</span>
          <span class="fop" @click.stop>
            <button type="button" class="op" @click="$emit('open-member', m)">详情</button>
          </span>
        </div>
      </template>
      <div v-else class="empty">{{ viewMode === 'project' ? '此卷暂无成员 · 编入后自动显示' : '此组暂无成员' }}</div>
    </section>

    <!-- 未编入节 (按项目视角常驻, 管理看板) -->
    <section v-if="viewMode === 'project'" id="doss-unfiled" class="doss warn">
      <div class="dhead">
        <span class="dot warn"></span>
        <h2>未编入项目</h2>
        <span class="grow"></span>
        <span class="cnt"><b>{{ unfiled.length }}</b> 人</span>
      </div>
      <template v-if="unfiled.length">
        <div v-for="m in unfiled" :key="m.id" class="row">
          <span class="nm">
            <span class="av" :style="{ background: avColor(m) }">
              <img v-if="m.avatar" :src="resolveAvatarUrl(m.avatar)" :alt="m.name">
              <template v-else>{{ m.name?.charAt(0) }}</template>
            </span>
            <b>{{ m.name }}</b><span class="id">#{{ padId(m.id) }}</span>
          </span>
          <span class="gtag" :class="{ t: isTeacher(m) }">{{ m.grade || '届别未录' }}</span>
          <span class="area" :class="{ dim: !m.research_area }">{{ m.research_area || '研究方向未登记' }}</span>
          <span class="sk"><span v-for="s in (m.skills || []).slice(0, 3)" :key="s">{{ s }}</span></span>
          <span v-if="m.voice_sample_count" class="vp">声纹 × {{ m.voice_sample_count }}</span>
          <span v-else class="vp no">未录入</span>
          <span class="fop" @click.stop>
            <button type="button" class="op cta" @click="$emit('open-member', m)">详情</button>
          </span>
        </div>
      </template>
      <div v-else class="empty">全员已编入项目 ✓</div>
    </section>
  </div>
</template>

<script setup>
/**
 * DossierPanel.vue — 方案 B「名录卷宗」实装 (docs/design-proposals/collab-2026-09/B-roster.html)
 *
 * 2026-09-15 主拍选定 B: 保留"项目为纲、成员挂卷"信息架构, 皮肤整体换成网盘 B 三栏
 * 工作台语言 (暖纸底 / 白卡细描边 / 深青 #0E766E 主行动 / 灰字层级 / mono 小数据 /
 * 大圆角) — 旧 V 稿衬线+粗描边+印章+硬阴影全部退役。后端 0 改动。
 * - 数据 0 新接口: GET /projects + memberStore (与 V 稿同源)
 * - 新增 (稿内静态控件实装化): 顶部横向锚导 + IntersectionObserver 滚动高亮;
 *   "按项目 / 按届别" 分段切换 (按届别 = memberTitleOf 身份称谓分组, 纯前端派生)
 * - 成员归属 = projects.members id 数组反向 join; 幽灵 id 不计入行 (口径不变)
 * - 批次⑩.75 守恒: 不展示进度/逾期, 不拉里程碑接口
 * - 排序: 导师→博→硕→本科→未分类→已毕业 (GORD); 按届别按身份称谓序
 * - tokens 自包含在 .dossier-panel 根 (防跨组件继承断链); dark 翻转非 scoped 块 (v60-v67 教训)
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { useMemberStore } from '@/stores/member'
import { memberTitleOf, resolveAvatarUrl } from '@/utils/memberIdentity'

defineEmits(['open-member'])

const memberStore = useMemberStore()
const projects = ref([])

async function fetchProjects() {
  // 批次⑩.75: 本页不展示进度/逾期 — 不再拉里程碑接口
  try {
    const res = await axios.get('/api/v1/projects')
    projects.value = res.data?.items || (Array.isArray(res.data) ? res.data : [])
  } catch (e) {
    console.error('DossierPanel 拉取项目失败:', e)
  }
}

onMounted(fetchProjects)
defineExpose({ fetchProjects })

// ---------------------------------------------------------------- 派生

const padId = (id) => (id == null ? '—' : String(id).padStart(3, '0'))

// B 稿 8 色档案板 (头像哈希底色, 与网盘文件夹色块同一族)
const AV_COLORS = ['#0E766E', '#2F5D8A', '#3E7A52', '#B07C24', '#7C4E96', '#A84B6F', '#B3392F', '#3E7A70']
const avColor = (m) => AV_COLORS[(m.id ?? 0) % AV_COLORS.length]
const projColor = (id) => AV_COLORS[(id ?? 0) % AV_COLORS.length]

const GORD = { '副教授': 0, '教授': 0, '老师': 0, '助教': 0, '博士后': 0, '博后': 0,
               '博零': 1, '博一': 1, '博二': 1, '博三': 1, '研三': 2, '研二': 3, '研一': 4,
               '大四': 5, '大三': 6, '大二': 6, '大一': 6, '已毕业': 9 }
const gradeRank = (m) => GORD[m.grade] ?? 7
const isTeacher = (m) => /教授|老师|助教|博后|博士后/.test(m.grade || '') && !/毕业/.test(m.grade || '')

const memberById = computed(() => {
  const map = {}
  for (const m of memberStore.members) map[m.id] = m
  return map
})

const viewMode = ref('project') // 'project' | 'grade'

const dossiers = computed(() =>
  [...projects.value]
    // 2026-09-13: 导师组固定第一 (卷纲次序: 导师组 → 研究方向卷), 其余按 id 升序
    .sort((a, b) => ((b.name === '导师组') ? 1 : 0) - ((a.name === '导师组') ? 1 : 0) || a.id - b.id)
    .map((p) => {
      const persons = (p.members || [])
        .map(id => memberById.value[id])
        .filter(Boolean)
        .sort((a, b) => gradeRank(a) - gradeRank(b) || a.id - b.id)
      const f = (d) => (d ? dayjs(d).format('YYYY-MM') : '?')
      return {
        key: `p${p.id}`,
        id: p.id,
        no: padId(p.id),
        name: p.name,
        raw: p,
        color: projColor(p.id),
        period: `${f(p.start_date)} → ${f(p.end_date)}`,
        persons: persons.length,
        persons_list: persons,
        vpMissing: persons.filter(m => !m.voice_sample_count).length,
      }
    }))

// 按届别视图: 身份称谓分组 (导师/博士后/博士/硕士/本科生/校友/… 与后端 member_identity 同口径)
const IDORD = ['导师', '博士后', '博士', '硕士', '本科生', '校友']
const gradeGroups = computed(() => {
  const map = new Map()
  for (const m of memberStore.members) {
    const t = memberTitleOf(m)
    if (!map.has(t)) map.set(t, [])
    map.get(t).push(m)
  }
  const rank = (t) => { const i = IDORD.indexOf(t); return i < 0 ? 99 : i }
  return [...map.entries()]
    .sort((a, b) => rank(a[0]) - rank(b[0]) || a[0].localeCompare(b[0], 'zh'))
    .map(([title, list]) => ({
      key: `g-${title}`,
      id: title,
      name: title,
      color: projColor(rank(title) < 99 ? rank(title) : 8),
      period: '',
      persons: list.length,
      persons_list: [...list].sort((a, b) => (isTeacher(a) ? 0 : 1) - (isTeacher(b) ? 0 : 1) || a.id - b.id),
      vpMissing: list.filter(m => !m.voice_sample_count).length,
    }))
})

const sections = computed(() => (viewMode.value === 'project' ? dossiers.value : gradeGroups.value))

const linkedIds = computed(() => new Set(dossiers.value.flatMap(d => d.persons_list.map(m => m.id))))

const unfiled = computed(() =>
  memberStore.members
    .filter(m => !linkedIds.value.has(m.id))
    .sort((a, b) => (isTeacher(b) ? 1 : 0) - (isTeacher(a) ? 1 : 0) || a.id - b.id))

const totalMembers = computed(() => memberStore.members.length)
const vpDone = computed(() => memberStore.members.filter(m => m.voice_sample_count).length)

// ---------------------------------------------------------------- 锚导滚动高亮

const activeAnchor = ref('all')
const anchorIds = computed(() => {
  const ids = sections.value.map(s => `doss-${s.key}`)
  if (viewMode.value === 'project') ids.push('doss-unfiled')
  return ids
})

function scrollTo(id) {
  if (id === 'all') {
    const root = rootEl.value
    if (root) root.scrollIntoView({ behavior: 'smooth', block: 'start' })
    activeAnchor.value = 'all'
    return
  }
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const rootEl = ref(null)
let spy = null
const visibleSet = new Set()

function recomputeActive() {
  activeAnchor.value = anchorIds.value.find((id) => visibleSet.has(id)) || 'all'
}

function observeSpy() {
  spy?.disconnect()
  visibleSet.clear()
  activeAnchor.value = 'all'
  if (typeof IntersectionObserver === 'undefined') return
  spy = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) visibleSet.add(e.target.id)
      else visibleSet.delete(e.target.id)
    }
    recomputeActive()
  }, { rootMargin: '-90px 0px -55% 0px', threshold: 0 })
  nextTick(() => {
    for (const id of anchorIds.value) {
      const el = document.getElementById(id)
      if (el) spy.observe(el)
    }
  })
}

watch(anchorIds, observeSpy)
onMounted(observeSpy)
onBeforeUnmount(() => spy?.disconnect())
</script>

<style scoped>
/* --- tokens 自包含 (B 名录 = 网盘工作台设计语言, 不依赖组件树继承) --- */
.dossier-panel {
  --rb-primary: #0e766e; --rb-primary-dark: #0b5d56;
  --rb-primary-bg: rgba(14, 118, 110, .09); --rb-primary-border: rgba(14, 118, 110, .35);
  --rb-text: #22302c; --rb-text-2: #52615c; --rb-text-3: #8b968f; --rb-text-4: #b9bfb6;
  --rb-bg: #f2f0eb; --rb-card: #ffffff; --rb-line: #e5e1d8; --rb-line-2: #d5d0c3; --rb-bg-hover: #eeebe3;
  --rb-danger: #d94f2b;
  --rb-shadow-sm: 0 2px 8px rgba(20, 40, 35, .07);
  --rb-r-md: 8px; --rb-r-lg: 12px; --rb-r-full: 9999px;
  --rb-grad-cta: linear-gradient(135deg, #0e766e, #12897c);
  --rb-dur: 180ms;
  --rb-mono: Consolas, 'JetBrains Mono', 'Courier New', monospace;

  position: relative;
  margin: calc(-1 * var(--space-4, 16px));
  padding: 26px 24px 60px;
  min-height: 100%;
  background: var(--rb-bg);
  color: var(--rb-text);
  font-size: 13.5px;
}
.dossier-panel :deep(button) { font-family: inherit; }
.dossier-panel :deep(a:focus-visible), .dossier-panel :deep(button:focus-visible) { outline: 2px solid var(--rb-primary); outline-offset: 1px; }

/* --- 页头: 一行说完 --- */
.head { display: flex; align-items: flex-end; gap: 14px; margin-bottom: 18px; }
.head h1 { margin: 0; font-size: 19px; font-weight: 650; letter-spacing: .01em; color: var(--rb-text); }
.head .meta { font-size: 12px; color: var(--rb-text-3); padding-bottom: 3px; }
.head .meta b { font-family: var(--rb-mono); color: var(--rb-text-2); font-weight: 600; }
.head .grow { flex: 1; }
.seg { display: flex; background: var(--rb-card); border: 1px solid var(--rb-line); border-radius: var(--rb-r-md); padding: 2px; }
.seg button { border: none; background: none; font-size: 12.5px; color: var(--rb-text-2); padding: 5px 13px; border-radius: 6px; cursor: pointer; }
.seg button.on { background: var(--rb-primary-bg); color: var(--rb-primary-dark); font-weight: 600; box-shadow: inset 0 0 0 1px var(--rb-primary-border); }

/* --- 横向锚导 --- */
.pstrip { display: flex; gap: 8px; overflow-x: auto; padding: 2px 0 14px; scrollbar-width: none; }
.pstrip::-webkit-scrollbar { display: none; }
.pill { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; text-decoration: none; font-size: 12.5px; color: var(--rb-text-2); background: var(--rb-card); border: 1px solid var(--rb-line); border-radius: var(--rb-r-full); padding: 6px 13px; cursor: pointer; transition: all var(--rb-dur); }
.pill .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.pill .dot.all { background: var(--rb-grad-cta); }
.pill .dot.warn { background: var(--rb-danger); }
.pill .c { font-family: var(--rb-mono); font-size: 10.5px; color: var(--rb-text-4); }
.pill:hover { border-color: var(--rb-primary-border); color: var(--rb-primary-dark); }
.pill.on { background: var(--rb-grad-cta); border-color: transparent; color: #fff; font-weight: 600; }
.pill.on .c { color: rgba(255, 255, 255, .75); }
.pill.dashed { border-style: dashed; }

/* --- 卷 (白卡节) --- */
.doss { background: var(--rb-card); border: 1px solid var(--rb-line); border-radius: var(--rb-r-lg); box-shadow: var(--rb-shadow-sm); margin-bottom: 16px; scroll-margin-top: 12px; }
.dhead { display: flex; align-items: center; gap: 12px; padding: 14px 20px; border-bottom: 1px solid var(--rb-line); }
.dhead .dot { width: 10px; height: 10px; border-radius: 3px; flex: none; }
.dhead h2 { margin: 0; font-size: 14.5px; font-weight: 650; color: var(--rb-text); }
.dhead .period { font-family: var(--rb-mono); font-size: 10.5px; color: var(--rb-text-4); margin-left: 2px; }
.dhead .grow { flex: 1; }
.dhead .cnt { font-size: 11.5px; color: var(--rb-text-3); }
.dhead .cnt b { color: var(--rb-text-2); font-family: var(--rb-mono); }

/* --- 成员行: 单行紧凑 --- */
.row { display: grid; grid-template-columns: minmax(160px, 1.2fr) 74px minmax(140px, 1.2fr) 1fr 88px 56px; gap: 14px; align-items: center; padding: 0 20px; height: 52px; border-bottom: 1px solid var(--rb-line); transition: background var(--rb-dur); }
.row:last-child { border-bottom: none; }
.row:hover { background: var(--rb-bg-hover); }
.row:hover .op { opacity: 1; }
.nm { display: flex; align-items: center; gap: 10px; min-width: 0; }
.av { width: 30px; height: 30px; border-radius: var(--rb-r-md); display: grid; place-items: center; font-size: 13px; font-weight: 600; color: #fff; flex: none; overflow: hidden; }
.av img { width: 100%; height: 100%; object-fit: cover; }
.nm b { font-weight: 600; font-size: 13.5px; color: var(--rb-text); }
.nm .id { font-family: var(--rb-mono); font-size: 10.5px; color: var(--rb-text-4); margin-left: 4px; font-weight: 400; }
.gtag { font-size: 11.5px; padding: 2px 9px; border-radius: var(--rb-r-full); background: var(--rb-bg); border: 1px solid var(--rb-line); color: var(--rb-text-2); justify-self: start; white-space: nowrap; }
.gtag.t { background: var(--rb-primary-bg); border-color: var(--rb-primary-border); color: var(--rb-primary-dark); }
.area { font-size: 12.5px; color: var(--rb-text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.area.dim { color: var(--rb-text-4); }
.sk { display: flex; gap: 5px; flex-wrap: nowrap; overflow: hidden; min-width: 0; }
.sk span { font-size: 11px; color: var(--rb-text-3); border: 1px solid var(--rb-line-2); border-radius: var(--rb-r-full); padding: 1.5px 9px; white-space: nowrap; flex: none; }
.vp { justify-self: end; font-family: var(--rb-mono); font-size: 11px; color: var(--rb-primary-dark); background: var(--rb-primary-bg); border-radius: var(--rb-r-full); padding: 2.5px 9px; white-space: nowrap; }
.vp.no { color: var(--rb-text-4); background: none; border: 1px dashed var(--rb-line-2); padding: 1.5px 8px; }
.fop { justify-self: end; }
.op { opacity: 0; transition: opacity var(--rb-dur); font-size: 11px; color: var(--rb-text-2); border: 1px solid var(--rb-line-2); border-radius: 6px; padding: 3px 9px; cursor: pointer; background: var(--rb-card); }
.op:hover { color: var(--rb-primary-dark); border-color: var(--rb-primary-border); background: var(--rb-primary-bg); }
.op.cta { color: var(--rb-danger); border-color: var(--rb-danger); border-style: dashed; }
.op.cta:hover { background: rgba(217, 79, 43, .07); }

/* 整卷全员缺声纹 → 弱示 (B 稿 muted 语义) */
.muted .row { opacity: .62; }

/* 未编入节 */
.doss.warn .dhead { border-bottom-style: dashed; }
.doss.warn .dhead .dot { background: var(--rb-danger) !important; }

.empty { padding: 16px 20px; font-size: 12.5px; color: var(--rb-text-4); }

/* --- 窄屏: 行收掉技能列 --- */
@media (max-width: 1100px) {
  .dossier-panel { margin: calc(-1 * var(--space-3, 12px)); padding: 18px 14px 40px; }
  .row { grid-template-columns: minmax(120px, 1fr) 66px 1fr 76px 48px; }
  .sk { display: none; }
}
</style>

<!-- v60-v67 教训: dark 覆盖必须非 scoped 块 (B 稿夜览态色板) -->
<style>
[data-theme="dark"] .dossier-panel {
  --rb-text: #e9e8e2; --rb-text-2: #b9c0b9; --rb-text-3: #8b938c; --rb-text-4: #5e665f;
  --rb-bg: #121513; --rb-card: #1a1e1b; --rb-line: #2e342f; --rb-line-2: #3a413a; --rb-bg-hover: #242a25;
  --rb-primary: #35c2a4; --rb-primary-dark: #5ad0b5; --rb-primary-bg: rgba(53, 194, 164, .12);
  --rb-primary-border: rgba(53, 194, 164, .35);
  --rb-grad-cta: linear-gradient(135deg, #1d9c81, #35c2a4);
  --rb-shadow-sm: 0 2px 8px rgba(0, 0, 0, .35);
}
</style>
