<template>
  <div class="workspace-view">
    <!-- 2026-09-04 主拍(两轮): 团队协作页 = 单一综合界面; 详情弹窗 align-center 跟随浏览位置 -->
    <div class="tab-panel">
      <DossierPanel
        ref="dossierRef"
        @open-member="openMemberDetail"
      />
    </div>

    <!-- 成员详情 dialog — A 稿「色带档案」(docs/design-proposals/member-dialog-2026-09/A-band.html)
         色带 = 成员哈希色 (与名录行头像同族 memberAvatarColor), 弹窗身份 = 列表身份 -->
    <el-dialog
      v-model="memberDetailVisible"
      width="640px"
      align-center
      append-to-body
      class="member-file-dialog"
      :show-close="false"
    >
      <div
        v-if="detailMember"
        class="mfd"
        :style="{ '--mfd-mem': memberColor }"
      >
        <button type="button" class="mfd-close" aria-label="关闭" @click="memberDetailVisible = false">×</button>
        <div class="mfd-band"><span class="no">档案 NO.{{ padId(detailMember.id) }}</span></div>
        <div class="mfd-idcard">
          <div class="av">
            <img v-if="detailMember.avatar" :src="resolveAvatarUrl(detailMember.avatar)" :alt="detailMember.name">
            <template v-else>{{ detailMember.name?.charAt(0) }}</template>
          </div>
          <div class="who">
            <h2>{{ detailMember.name }}</h2>
            <div class="tags">
              <span class="tag t">{{ memberTitleOf(detailMember) }} · {{ detailMember.grade || '届别未录' }}</span>
              <span v-if="detailMember.voice_sample_count" class="tag vp">声纹已录入</span>
              <span v-else class="tag vp no">声纹未录入</span>
            </div>
          </div>
        </div>
        <div class="mfd-body">
          <dl class="kv">
            <dt>研究方向</dt><dd>{{ detailMember.research_area || '未登记' }}</dd>
            <dt>邮箱</dt><dd class="mono">{{ detailMember.email || '—' }}</dd>
            <dt>手机</dt><dd class="mono">{{ detailMember.phone || '—' }}</dd>
          </dl>
          <div v-if="detailMember.bio" class="sect">
            <h3>个人简介</h3>
            <p class="bio">{{ detailMember.bio }}</p>
          </div>
          <div v-if="detailMember.skills?.length" class="sect">
            <h3>技能</h3>
            <div class="chips"><span v-for="s in detailMember.skills" :key="s" class="chip">{{ s }}</span></div>
          </div>
          <div class="vpbox" :class="{ owned: detailMember.voice_sample_count }">
            <span class="wave" aria-hidden="true"><i v-for="(h, i) in WAVE_BARS" :key="i" :style="{ height: h + 'px', opacity: .45 + (i % 4) * .18 }"></i></span>
            <span class="txt">
              <b>{{ detailMember.voice_sample_count ? `已录入 ${detailMember.voice_sample_count} 段采样` : '还没有录入声纹' }}</b>
              <span v-if="detailMember.voice_sample_count">最近采样 {{ fmtDate(detailMember.voice_enrolled_at) }} · 会议发言自动识别</span>
              <span v-else>录入后组会发言可自动标出名字</span>
            </span>
            <span v-if="detailMember.voice_sample_count" class="n">{{ detailMember.voice_sample_count }}<small> 段</small></span>
          </div>
          <div class="acts">
            <button type="button" class="btn main" @click="openEnroll">
              {{ detailMember.voice_sample_count ? '重新录入声纹' : '录入声纹' }}
            </button>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 声纹录入基建复用 (VoiceprintEnrollDialog: modelValue + member, success 后刷新名册) -->
    <VoiceprintEnrollDialog
      v-model="enrollVisible"
      :member="detailMember"
      @success="onEnrollSuccess"
    />
  </div>
</template>

<script setup>
/**
 * WorkspaceView.vue — v78 UI redesign "团队协作" 容器
 *
 * 设计: 合并原 /projects、/members、/voiceprint 3 个独立路由为 1 个 /workspace 路由
 * - 移动端通过 resolveMobileComponent 切换到 MobileWorkspaceView
 *
 * 2026-09-04 V 稿综合界面收口 (主拍两轮: 只保留卷宗一屏):
 * - TabStrip 三签移除, DossierPanel 为唯一主视图; 老 ?tab= 深链静默清 query
 *
 * 2026-09-12 项目详情 dialog (开卷) 整体移除 (open-project emit/里程碑台账/项目章);
 * 成员档案弹窗保留
 *
 * 2026-09-15 团队协作页整体换 B「名录卷宗」皮肤 (主拍, 网盘工作台设计语言);
 * 本次成员详情弹窗换 A 稿「色带档案」皮肤 (docs/design-proposals/member-dialog-2026-09/):
 * 旧「卷宗开卷」衬线题名/mono 档案号/骑缝章全退役。哈希色带与名录行头像同族
 * (memberAvatarColor 单一来源); "未录声纹"从灰字状态升级为可操作的 CTA
 * (接驳既有 VoiceprintEnrollDialog)。数据拉取逻辑零改动。
 */

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { useMemberStore } from '@/stores/member'
import DossierPanel from './workspace/DossierPanel.vue'
import VoiceprintEnrollDialog from '@/components/VoiceprintEnrollDialog.vue'
import { memberTitleOf, memberAvatarColor, resolveAvatarUrl } from '@/utils/memberIdentity'

const route = useRoute()
const router = useRouter()
const memberStore = useMemberStore()

const dossierRef = ref(null)

// ====== 成员详情 dialog (DossierPanel emit 'open-member' 触发) ======
const memberDetailVisible = ref(false)
const detailMember = ref(null)

async function openMemberDetail(member) {
  // 优先从 store 拿最新数据, 避免旧缓存
  const fresh = memberStore.members.find((m) => m.id === member.id)
  detailMember.value = fresh || member
  memberDetailVisible.value = true
}

// ====== 色带/头像哈希色 (与名录行同族, 单一来源 memberAvatarColor) ======
const memberColor = computed(() => memberAvatarColor(detailMember.value))

// 声纹状态块装饰波形 (静态) 与日期
const WAVE_BARS = [8, 14, 20, 11, 18, 9, 16, 22, 10, 15, 19, 8]
const fmtDate = (d) => (d ? dayjs(d).format('YYYY-MM-DD') : '—')
const padId = (id) => (id == null ? '—' : String(id).padStart(3, '0'))

// ====== 声纹录入 (复用既有基建) ======
const enrollVisible = ref(false)
function openEnroll() {
  if (!detailMember.value) return
  enrollVisible.value = true
}
async function onEnrollSuccess() {
  try {
    await memberStore.refreshMembers?.()
    // 刷新弹窗内数据 (采样数/最近采样时间)
    const fresh = memberStore.members.find((m) => m.id === detailMember.value?.id)
    if (fresh) detailMember.value = fresh
  } catch (e) {
    console.warn('声纹录入后刷新名册失败:', e)
  }
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
</style>

<!-- =====================================================================
     A 稿「色带档案」dialog 皮肤 (2026-09-15)
     el-dialog teleport (append-to-body) → 骨架规则必须非 scoped +
     class 收窄; tokens 定义在 .member-file-dialog 根上自包含,
     dark 覆盖非 scoped 块 (v60-v67 教训), 色板对齐名录 B 稿夜览态
     ===================================================================== -->
<style>
.member-file-dialog {
  --rb-primary: #0E766E; --rb-primary-dark: #0B5D56;
  --rb-primary-bg: rgba(14, 118, 110, .09); --rb-primary-border: rgba(14, 118, 110, .35);
  --rb-text: #22302C; --rb-text-2: #52615C; --rb-text-3: #8B968F; --rb-text-4: #B9BFB6;
  --rb-bg: #F2F0EB; --rb-card: #FFFFFF; --rb-line: #E5E1D8; --rb-line-2: #D5D0C3;
  --rb-r-md: 8px; --rb-r-lg: 12px; --rb-r-full: 9999px;
  --rb-grad-cta: linear-gradient(135deg, #0E766E, #12897C);
  --rb-mono: Consolas, 'JetBrains Mono', 'Courier New', monospace;
  border-radius: 16px;
  overflow: hidden;
  /* 显式声明: 全局 [data-theme=dark] .el-dialog 同特异性, 只改变量会被它压住 (J 稿教训) */
  background: var(--rb-card);
}
.member-file-dialog .el-dialog__header { display: none; }
.member-file-dialog .el-dialog__body { padding: 0; }

.mfd { position: relative; color: var(--rb-text); font-size: 13.5px; }
.mfd-close {
  position: absolute; top: 14px; right: 14px; z-index: 3;
  width: 28px; height: 28px; border-radius: 50%; border: none;
  background: rgba(255, 255, 255, .18); color: #fff; font-size: 15px; line-height: 1;
  cursor: pointer; display: grid; place-items: center;
}
.mfd-close:hover { background: rgba(255, 255, 255, .32); }
.mfd-band {
  height: 84px; position: relative;
  background: linear-gradient(120deg, var(--mfd-mem, #0E766E) 0%, color-mix(in srgb, var(--mfd-mem, #0E766E) 78%, #000) 100%);
}
.mfd-band::after { content: ''; position: absolute; inset: 0; background: radial-gradient(120px 84px at 88% 0%, rgba(255,255,255,.22), transparent 70%); }
.mfd-band .no { position: absolute; right: 18px; top: 14px; font-family: var(--rb-mono); font-size: 11px; letter-spacing: .14em; color: rgba(255,255,255,.85); }
.mfd-idcard { display: flex; gap: 16px; padding: 0 26px; margin-top: -32px; position: relative; z-index: 2; align-items: flex-end; }
.mfd-idcard .av {
  width: 76px; height: 76px; border-radius: 16px; border: 3px solid var(--rb-card);
  background: var(--mfd-mem, #0E766E); color: #fff;
  display: grid; place-items: center; font-size: 30px; font-weight: 650; flex: none;
  box-shadow: 0 6px 18px rgba(20, 40, 35, .18); overflow: hidden;
}
.mfd-idcard .av img { width: 100%; height: 100%; object-fit: cover; }
.mfd-idcard .who { padding-bottom: 8px; min-width: 0; flex: 1; }
.mfd-idcard h2 { margin: 0; font-size: 22px; font-weight: 700; letter-spacing: .01em; color: var(--rb-text); }
.mfd-idcard .tags { display: flex; gap: 7px; margin-top: 7px; flex-wrap: wrap; }
.mfd .tag { font-size: 11.5px; padding: 2.5px 10px; border-radius: var(--rb-r-full); background: var(--rb-bg); border: 1px solid var(--rb-line); color: var(--rb-text-2); }
.mfd .tag.t { background: var(--rb-primary-bg); border-color: var(--rb-primary-border); color: var(--rb-primary-dark); font-weight: 600; }
.mfd .tag.vp { font-family: var(--rb-mono); font-size: 11px; }
.mfd .tag.vp.no { color: var(--rb-text-4); border-style: dashed; background: none; }
.mfd-body { padding: 20px 26px 24px; }
.mfd .kv { display: grid; grid-template-columns: 64px 1fr; gap: 0 14px; margin: 0; }
.mfd .kv dt { font-size: 12px; color: var(--rb-text-3); padding: 9px 0; border-bottom: 1px solid var(--rb-line); }
.mfd .kv dd { font-size: 13.5px; color: var(--rb-text); padding: 9px 0; border-bottom: 1px solid var(--rb-line); min-width: 0; word-break: break-all; margin: 0; }
.mfd .kv > dt:nth-last-of-type(1), .mfd .kv > dd:nth-last-of-type(1) { border-bottom: none; }
.mfd .kv dd.mono { font-family: var(--rb-mono); font-size: 12.5px; color: var(--rb-text-2); }
.mfd .sect { margin-top: 18px; }
.mfd .sect h3 { font-size: 12px; color: var(--rb-text-3); font-weight: 500; margin: 0 0 8px; }
.mfd .bio { font-size: 13px; color: var(--rb-text-2); line-height: 1.8; margin: 0; }
.mfd .chips { display: flex; gap: 6px; flex-wrap: wrap; }
.mfd .chip { font-size: 12px; color: var(--rb-text-2); border: 1px solid var(--rb-line-2); border-radius: var(--rb-r-full); padding: 3px 12px; }
.mfd .vpbox { margin-top: 18px; border: 1px solid var(--rb-line); border-radius: var(--rb-r-lg); padding: 14px 16px; display: flex; align-items: center; gap: 14px; background: var(--rb-bg); }
.mfd .vpbox.owned { background: var(--rb-primary-bg); border-color: var(--rb-primary-border); }
.mfd .wave { display: flex; align-items: center; gap: 2.5px; height: 26px; flex: none; }
.mfd .wave i { width: 3px; border-radius: 2px; background: var(--rb-primary); }
.mfd .vpbox .txt { flex: 1; min-width: 0; }
.mfd .vpbox .txt b { display: block; font-size: 13px; font-weight: 650; color: var(--rb-text); }
.mfd .vpbox .txt span { font-size: 11.5px; color: var(--rb-text-3); }
.mfd .vpbox .n { font-family: var(--rb-mono); font-size: 20px; font-weight: 650; color: var(--rb-primary-dark); white-space: nowrap; }
.mfd .vpbox .n small { font-size: 10.5px; color: var(--rb-text-3); font-weight: 400; }
.mfd .acts { display: flex; gap: 8px; margin-top: 20px; }
.mfd .btn { font-size: 12.5px; padding: 7px 16px; border-radius: var(--rb-r-md); border: 1px solid var(--rb-line-2); background: var(--rb-card); color: var(--rb-text-2); cursor: pointer; }
.mfd .btn.main { background: var(--rb-grad-cta); border-color: transparent; color: #fff; font-weight: 600; }
.mfd .btn.main:hover { opacity: .92; color: #fff; }

/* dark: 对齐名录 B 稿夜览色板 (色带保持成员哈希色) */
[data-theme="dark"] .member-file-dialog {
  --rb-text: #E9E8E2; --rb-text-2: #B9C0B9; --rb-text-3: #8B938C; --rb-text-4: #5E665F;
  --rb-bg: #121513; --rb-card: #1A1E1B; --rb-line: #2E342F; --rb-line-2: #3A413A;
  --rb-primary: #35C2A4; --rb-primary-dark: #5AD0B5; --rb-primary-bg: rgba(53, 194, 164, .12);
  --rb-primary-border: rgba(53, 194, 164, .35);
  --rb-grad-cta: linear-gradient(135deg, #1D9C81, #35C2A4);
  background: var(--rb-card);
}
[data-theme="dark"] .mfd .vpbox { background: #171B18; }
[data-theme="dark"] .mfd .vpbox.owned { background: var(--rb-primary-bg); }
[data-theme="dark"] .mfd-idcard .av { box-shadow: 0 6px 18px rgba(0, 0, 0, .5); }
</style>
