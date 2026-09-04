<template>
  <div class="workspace-view">
    <!-- 2026-09-04 主拍(两轮): 团队协作页 = V 稿「卷宗」单一综合界面,
         管理入口 tab 也撤除; 详情弹窗 align-center 跟随当前浏览位置 (不再钉死视口顶) -->
    <div class="tab-panel">
      <DossierPanel
        ref="dossierRef"
        @open-project="openProjectDetail"
        @open-member="openMemberDetail"
      />
    </div>

    <!-- 项目详情 dialog (DossierPanel/卷开卷 触发) — J 稿卷宗开卷语言 -->
    <el-dialog
      v-model="projectDetailVisible"
      :width="'720px'"
      align-center
      append-to-body
      class="dossier-dialog"
    >
      <template #header>
        <div class="dlg-fhead">
          <div class="dlg-fhead-l">
            <div class="dlg-fno">MB-LAB · PROJECT FILE · 卷宗 NO.{{ padId(detailProject?.id) }}</div>
            <div class="dlg-title">{{ detailProject?.name }}</div>
          </div>
          <span class="hstamp" :class="projectStamp.cls">{{ projectStamp.text }}</span>
        </div>
      </template>
      <div v-if="detailProject" class="dossier-body">
        <div class="arow">
          <span class="ak">研究方向</span>
          <span class="av">{{ detailProject.research_area || '未登记' }}</span>
        </div>
        <div class="arow">
          <span class="ak">周期</span>
          <span class="av mono">{{ periodOf(detailProject) }}</span>
        </div>
        <div class="arow">
          <span class="ak">项目描述</span>
          <span class="av desc">{{ cleanDescriptionForDisplay(detailProject.description) || '暂无描述' }}</span>
        </div>

        <h4 class="sec-title">项目成员<span class="sec-n">{{ (detailProject.members || []).length }} PERSONS</span></h4>
        <div class="labtag-row">
          <span
            v-for="memberId in detailProject.members"
            :key="memberId"
            class="labtag"
            :class="{ ghost: !memberExists(memberId) }"
          >{{ detailMemberName(memberId) }}</span>
          <span v-if="!(detailProject.members || []).length" class="labtag ghost">未指派</span>
        </div>

        <h4 class="sec-title">里程碑<span class="sec-n">{{ detailMilestones.length }} ITEMS<template v-if="detailLateCount"> · {{ detailLateCount }} LATE</template></span></h4>
        <div v-if="detailMilestones.length" class="ms-ledger">
          <div
            v-for="m in sortedDetailMilestones"
            :key="m.id"
            class="msrow"
            :class="msState(m).cls"
          >
            <span class="msd">{{ fmtMs(m.completed_at || m.due_date) }}</span>
            <div class="msc">
              <span class="msn">{{ m.name }}</span>
              <span v-if="m.description" class="msdesc">{{ m.description }}</span>
            </div>
            <span class="mss">{{ msState(m).label }}</span>
          </div>
        </div>
        <p v-else class="empty-hint">○ 未立里程碑 · 卷内空白</p>
      </div>
    </el-dialog>

    <!-- 成员详情 dialog (DossierPanel emit 'open-member' 触发) — 成员档案开卷 -->
    <el-dialog
      v-model="memberDetailVisible"
      :width="'600px'"
      align-center
      append-to-body
      class="dossier-dialog"
    >
      <template #header>
        <div class="dlg-fhead">
          <div class="dlg-fhead-l">
            <div class="dlg-fno">MB-LAB · MEMBER FILE · 档案 NO.{{ padId(detailMember?.id) }}</div>
            <div class="dlg-title">{{ detailMember?.name }}</div>
          </div>
          <span class="hstamp" :class="roleStamp.cls">{{ roleStamp.text }}</span>
        </div>
      </template>
      <div v-if="detailMember" class="dossier-body">
        <div class="dlg-hero">
          <div class="dlg-avatar">
            <img v-if="detailMember.avatar" :src="detailMember.avatar" :alt="detailMember.name">
            <template v-else>{{ detailMember.name?.charAt(0) }}</template>
          </div>
          <div class="dlg-hero-tags">
            <span v-if="detailMember.grade" class="labtag">届别 {{ detailMember.grade }}</span>
            <span class="labtag" :class="detailMember.voice_enrolled_at ? 'ok' : 'ghost'">
              {{ detailMember.voice_enrolled_at ? '🎤 已录入声纹' : '未录入声纹' }}
            </span>
          </div>
        </div>

        <h4 class="sec-title">基本信息<span class="sec-n">PERSONAL DATA</span></h4>
        <div class="arow">
          <span class="ak">研究方向</span>
          <span class="av">{{ detailMember.research_area || '未登记' }}</span>
        </div>
        <div class="arow">
          <span class="ak">邮箱</span>
          <span class="av mono">{{ detailMember.email || '—' }}</span>
        </div>
        <div class="arow">
          <span class="ak">手机</span>
          <span class="av mono">{{ detailMember.phone || '—' }}</span>
        </div>
        <div class="arow">
          <span class="ak">个人简介</span>
          <span class="av desc">{{ detailMember.bio || '未填写' }}</span>
        </div>

        <template v-if="detailMember.skills?.length">
          <h4 class="sec-title">技能<span class="sec-n">{{ detailMember.skills.length }} TAGS</span></h4>
          <div class="labtag-row">
            <span v-for="skill in detailMember.skills" :key="skill" class="labtag">{{ skill }}</span>
          </div>
        </template>

        <template v-if="detailMember.voice_enrolled_at">
          <h4 class="sec-title">声纹<span class="sec-n">VOICEPRINT</span></h4>
          <div class="arow">
            <span class="ak">录入时间</span>
            <span class="av mono">{{ fmtMs(detailMember.voice_enrolled_at) }}</span>
          </div>
          <div class="arow">
            <span class="ak">采样次数</span>
            <span class="av mono">{{ detailMember.voice_sample_count || 1 }} 次</span>
          </div>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * WorkspaceView.vue — v78 UI redesign "团队协作" 容器
 *
 * 设计: 合并原 /projects、/members、/voiceprint 3 个独立路由为 1 个 /workspace 路由
 * - 顶部 3 个 tab: 项目 / 成员 / 声纹
 * - tab 切换同步 ?tab=xxx URL query, 刷新定位保持
 * - 项目/成员详情用 el-dialog 弹层模式 (与原桌面 ProjectView.showDetailDialog 一致)
 * - 移动端通过 resolveMobileComponent 切换到 MobileWorkspaceView
 *
 * 2026-07-03: 模板管理删除后, WorkspaceView 只剩项目 / 成员 / 声纹 3 个 tab
 *
 * 2026-09-04 J 稿「卷宗」语言收口:
 * - 两个详情 dialog 重写为档案开卷 (mono 卷宗号 + 衬线题名 + 骑缝章 + 表格行 + 里程碑台账),
 *   el-descriptions/el-tag/el-timeline 全部移除; 数据拉取逻辑零改动
 * - TabStrip 同步换标本签皮肤 (共享组件, 全站生效)
 * - 幽灵成员 id (不在成员列表) 与卡片口径统一: 显示「用户不存在」
 *
 * 2026-09-04 V 稿综合界面收口 (主拍两轮: 只保留卷宗一屏):
 * - TabStrip 三签移除, DossierPanel 为唯一主视图; 管理台抽屉/入口按钮第二轮也撤除
 *   (项目/成员/声纹信息全部由卷宗页承载; 建卷/编辑基建留在原 Panel 组件, 需要时回接)
 * - 两个详情 dialog 改 align-center: 弹窗跟随当前浏览位置 (视口垂直居中), 不再 top 5vh 钉死顶部
 * - 老 ?tab= 深链静默清 query, 不再弹任何抽屉
 */

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import dayjs from 'dayjs'
import { useMemberStore } from '@/stores/member'
import { cleanDescriptionForDisplay } from '@/utils/textSanitize'
import DossierPanel from './workspace/DossierPanel.vue'

const route = useRoute()
const router = useRouter()
const memberStore = useMemberStore()

const dossierRef = ref(null)

// ====== 项目详情 dialog (从 ProjectsPanel 接收 open-detail) ======
const projectDetailVisible = ref(false)
const detailProject = ref(null)
const detailMilestones = ref([])

async function openProjectDetail(project) {
  detailProject.value = project
  detailMilestones.value = []
  projectDetailVisible.value = true
  try {
    const res = await axios.get(`/api/v1/projects/${project.id}/milestones`)
    detailMilestones.value = res.data || []
  } catch (e) {
    console.error('获取里程碑失败:', e)
  }
}

// ====== 成员详情 dialog (从 MembersPanel 接收 open-detail) ======
const memberDetailVisible = ref(false)
const detailMember = ref(null)

async function openMemberDetail(member) {
  // 优先从 store 拿最新数据, 避免旧缓存
  const fresh = memberStore.members.find((m) => m.id === member.id)
  detailMember.value = fresh || member
  memberDetailVisible.value = true
}

// ====== 卷宗派生 (口径与 ProjectsPanel 卡片一致) ======
const padId = (id) => (id == null ? '—' : String(id).padStart(3, '0'))
const fmtMs = (d) => (d ? dayjs(d).format('YY/MM/DD') : '未定')

const periodOf = (p) => {
  if (!p.start_date && !p.end_date) return '起止未录'
  const f = (d) => (d ? dayjs(d).format('YYYY-MM-DD') : '?')
  return `${f(p.start_date)} → ${f(p.end_date)}`
}

const isMsDone = (m) => m.status === 'completed' || !!m.completed_at
const isMsLate = (m) => !isMsDone(m) && m.due_date && dayjs(m.due_date).isBefore(dayjs(), 'day')

function msState(m) {
  if (isMsDone(m)) return { cls: 'done', label: '✓ 已完成' }
  if (isMsLate(m)) return { cls: 'late', label: '逾期未闭' }
  if (m.due_date) return { cls: 'soon', label: `剩 ${dayjs(m.due_date).diff(dayjs(), 'day')} 天` }
  return { cls: '', label: '未定期' }
}

const sortedDetailMilestones = computed(() =>
  [...detailMilestones.value].sort((a, b) =>
    String(a.due_date || '9999').localeCompare(String(b.due_date || '9999'))))

const detailLateCount = computed(() => detailMilestones.value.filter(isMsLate).length)

const projectStamp = computed(() => {
  const s = detailProject.value?.status
  if (s === 'completed') return { text: '已结案', cls: 'ok' }
  if (s === 'archived') return { text: '已归档', cls: 'ok' }
  if (s === 'paused') return { text: '已暂停', cls: '' }
  if (detailLateCount.value > 0) return { text: `逾期未闭 ×${detailLateCount.value}`, cls: '' }
  return { text: '在研', cls: 'ok' }
})

const ROLE_LABELS = { admin: '管理员', leader: '组长', member: '成员' }
const roleStamp = computed(() => {
  const role = detailMember.value?.role || 'member'
  return { text: ROLE_LABELS[role] || role, cls: role === 'admin' ? '' : 'ok' }
})

// 幽灵成员 id (成员 API 过滤缺员) 与卡片同口径: 明说「用户不存在」
function memberExists(id) {
  return !!memberStore.members.find(m => m.id == id)  // eslint-disable-line eqeqeq
}
function detailMemberName(id) {
  const m = memberStore.members.find(x => x.id == id)  // eslint-disable-line eqeqeq
  return m?.name || '用户不存在'
}

onMounted(async () => {
  // 主动 fetch 一次成员数据 (卷宗行渲染依赖 memberStore)
  if (memberStore.members.length === 0) {
    try {
      await memberStore.fetchMembers()
    } catch (e) {
      console.warn('fetchMembers 失败:', e)
    }
  }
  // 老 ?tab= 深链: 抽屉已撤除, 静默清掉 query
  if (route.query.tab) {
    router.replace({ path: '/workspace' })
  }
})
</script>

<style scoped>
.workspace-view {
  height: 100%;
  overflow-y: auto;
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.tab-panel {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.empty-hint {
  color: var(--ws-fog, #8ba0a0);
  padding: 12px 0;
  font-size: 12.5px;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<!-- =====================================================================
     J 稿「卷宗开卷」dialog 皮肤 (2026-09-04)
     el-dialog teleport 场景 → 骨架规则必须非 scoped + customClass 收窄;
     tokens 定义在 .dossier-dialog 根上自包含, 不依赖组件树继承
     ===================================================================== -->
<style>
.dossier-dialog {
  --ws-card: #fdfefc; --ws-ink: #16232a; --ws-steel: #5a6b6a; --ws-fog: #8ba0a0;
  --ws-hair: #c9d2ca; --ws-teal: #0e766e; --ws-teal-soft: #dcece5;
  --ws-coral: #ef7256; --ws-paper: #f4f6f4; --ws-shadow: rgba(22, 35, 42, 0.14);
  --ws-mono: Consolas, 'Courier New', monospace;
  --ws-serif: Georgia, 'Songti SC', 'SimSun', serif;
  background: var(--ws-card);
  border: 1.5px solid var(--ws-ink);
  border-radius: 10px;
  box-shadow: 4px 4px 0 var(--ws-shadow), 0 12px 40px rgba(0, 0, 0, 0.12);
}
.dossier-dialog .el-dialog__header {
  border-bottom: 1px dashed var(--ws-hair);
  padding: 18px 22px 12px;
  margin-right: 0;
}
.dossier-dialog .el-dialog__body { padding: 16px 22px 22px; max-height: 72vh; overflow-y: auto; }
/* align-center 弹窗: 内容超高时 body 内滚, 弹窗本体不顶出视口 */
.dossier-dialog.is-align-center { max-height: 92vh; display: flex; flex-direction: column; }
.dossier-dialog .el-dialog__headerbtn { top: 10px; right: 12px; }

/* --- 卷首行: mono 卷宗号 + 衬线题名 + 骑缝章 --- */
.dossier-dialog .dlg-fhead { display: flex; align-items: flex-start; gap: 14px; padding-right: 30px; }
.dossier-dialog .dlg-fhead-l { flex: 1; min-width: 0; }
.dossier-dialog .dlg-fno { font-family: var(--ws-mono); font-size: 9.5px; letter-spacing: .16em; color: var(--ws-teal); margin-bottom: 4px; }
.dossier-dialog .dlg-title { font-family: var(--ws-serif); font-size: 21px; font-weight: 600; color: var(--ws-ink); line-height: 1.3; }
.dossier-dialog .hstamp {
  font-family: var(--ws-mono); font-size: 9.5px; letter-spacing: .14em;
  color: var(--ws-coral); border: 1.5px dashed var(--ws-coral); border-radius: 6px;
  padding: 4px 9px; transform: rotate(-2deg); display: inline-block; flex-shrink: 0; margin-top: 12px; background: none;
}
.dossier-dialog .hstamp.ok { color: var(--ws-teal); border-color: var(--ws-teal); }

/* --- 表格行 (替 el-descriptions) --- */
.dossier-dialog .arow { display: flex; gap: 12px; padding: 9px 2px; border-bottom: 1px dotted var(--ws-hair); font-size: 13px; }
.dossier-dialog .arow:last-of-type { border-bottom: none; }
.dossier-dialog .ak { font-family: var(--ws-mono); font-size: 9.5px; letter-spacing: .14em; color: var(--ws-fog); width: 64px; flex-shrink: 0; padding-top: 3px; }
.dossier-dialog .av { color: var(--ws-ink); flex: 1; min-width: 0; }
.dossier-dialog .av.mono { font-family: var(--ws-mono); font-size: 12px; }
.dossier-dialog .av.desc { color: var(--ws-steel); line-height: 1.75; }

/* --- § 分节标本签 --- */
.dossier-dialog .sec-title { margin: 18px 0 10px; font-size: 14px; font-weight: 600; color: var(--ws-ink); display: flex; align-items: baseline; gap: 10px; }
.dossier-dialog .sec-title::before { content: '§ '; color: var(--ws-teal); }
.dossier-dialog .sec-n { font-family: var(--ws-mono); font-size: 9.5px; letter-spacing: .14em; color: var(--ws-fog); font-weight: 400; }

/* --- labtag 族 (替 el-tag) --- */
.dossier-dialog .labtag-row { display: flex; flex-wrap: wrap; gap: 6px; }
.dossier-dialog .labtag { font-family: var(--ws-mono); font-size: 10px; color: var(--ws-steel); background: var(--ws-paper); border: 1px solid var(--ws-hair); border-radius: 3px; padding: 3px 8px 3px 9px; }
.dossier-dialog .labtag.ok { color: var(--ws-teal); border-color: var(--ws-teal); background: var(--ws-teal-soft); }
.dossier-dialog .labtag.ghost { color: var(--ws-fog); border-style: dashed; }

/* --- 里程碑台账 (替 el-timeline) --- */
.dossier-dialog .ms-ledger { border: 1px solid var(--ws-hair); border-radius: 8px; overflow: hidden; }
.dossier-dialog .msrow { display: grid; grid-template-columns: 66px 1fr auto; gap: 12px; align-items: baseline; padding: 10px 14px; border-bottom: 1px solid var(--ws-paper); font-size: 13px; }
.dossier-dialog .msrow:last-child { border-bottom: none; }
.dossier-dialog .msrow:hover { background: var(--ws-paper); }
.dossier-dialog .msd { font-family: var(--ws-mono); font-size: 10.5px; color: var(--ws-fog); }
.dossier-dialog .msc { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.dossier-dialog .msn { color: var(--ws-ink); font-weight: 500; }
.dossier-dialog .msdesc { font-size: 11.5px; color: var(--ws-steel); }
.dossier-dialog .mss { font-family: var(--ws-mono); font-size: 10px; letter-spacing: .08em; color: var(--ws-fog); }
.dossier-dialog .msrow.done .msn { color: var(--ws-fog); text-decoration: line-through; }
.dossier-dialog .msrow.done .mss { color: var(--ws-teal); }
.dossier-dialog .msrow.late { background: rgba(239, 114, 86, 0.06); }
.dossier-dialog .msrow.late .msd { color: var(--ws-coral); font-weight: 700; }
.dossier-dialog .msrow.late .mss { color: var(--ws-coral); font-weight: 700; }

/* --- 成员档案标本牌 (替渐变 hero) --- */
.dossier-dialog .dlg-hero { display: flex; align-items: center; gap: 14px; padding: 4px 2px 12px; border-bottom: 1px dashed var(--ws-hair); margin-bottom: 4px; }
.dossier-dialog .dlg-avatar { width: 56px; height: 56px; border: 1.5px solid var(--ws-ink); border-radius: 8px; background: var(--ws-paper); display: grid; place-items: center; font-family: var(--ws-serif); font-size: 22px; color: var(--ws-ink); overflow: hidden; flex-shrink: 0; }
.dossier-dialog .dlg-avatar img { width: 100%; height: 100%; object-fit: cover; }
.dossier-dialog .dlg-hero-tags { display: flex; flex-wrap: wrap; gap: 6px; }

/* --- dark (铁律 26: 非 scoped; 对齐 J 稿 data-dark 夜览态) --- */
[data-theme="dark"] .dossier-dialog {
  --ws-card: #18232a; --ws-ink: #dfe9e6; --ws-steel: #9ab0ae; --ws-fog: #6b8286;
  --ws-hair: #27363e; --ws-teal: #35c2a4; --ws-teal-soft: #12312b;
  --ws-coral: #ef7256; --ws-paper: #10171b; --ws-shadow: rgba(0, 0, 0, 0.5);
  /* 显式重复声明: 全局 [data-theme=dark] .el-dialog 的 bg/border 同特异性, 只改变量会被它压住 */
  background: var(--ws-card);
  border-color: var(--ws-ink);
}
[data-theme="dark"] .dossier-dialog .el-dialog__headerbtn .el-dialog__close { color: var(--ws-fog); }
</style>
