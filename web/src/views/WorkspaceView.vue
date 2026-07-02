<template>
  <div class="workspace-view">
    <!-- 铁律 31: 全项目 tab 统一用 <TabStrip> -->
    <div class="tab-strip-wrapper">
      <TabStrip v-model="activeTab" :items="tabItems" aria-label="团队协作视图切换" />
    </div>

    <div v-show="activeTab === 'projects'" role="tabpanel"
      :aria-labelledby="`tab-strip-projects`" class="tab-panel">
      <ProjectsPanel @open-detail="openProjectDetail" />
    </div>
    <div v-show="activeTab === 'members'" role="tabpanel"
      :aria-labelledby="`tab-strip-members`" class="tab-panel">
      <MembersPanel @open-detail="openMemberDetail" />
    </div>
    <div v-show="activeTab === 'voiceprint'" role="tabpanel"
      :aria-labelledby="`tab-strip-voiceprint`" class="tab-panel">
      <VoiceprintsPanel />
    </div>

    <!-- 项目详情 dialog (ProjectsPanel emit 'open-detail' 触发) -->
    <el-dialog
      v-model="projectDetailVisible"
      title="项目详情"
      :width="'700px'"
      top="5vh"
    >
      <div v-if="detailProject" class="project-detail">
        <h2>{{ detailProject.name }}</h2>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(detailProject.status)">
              {{ getStatusLabel(detailProject.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="研究方向">{{ detailProject.research_area || '-' }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ formatDate(detailProject.start_date) }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ formatDate(detailProject.end_date) }}</el-descriptions-item>
          <el-descriptions-item label="项目描述" :span="2">{{ detailProject.description || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="detail-section-title">项目成员</h4>
        <div class="member-tags">
          <el-tag
            v-for="memberId in detailProject.members"
            :key="memberId"
            class="member-tag-item"
          >
            {{ getMemberName(memberId) }}
          </el-tag>
        </div>

        <h4 class="detail-section-title">里程碑</h4>
        <el-timeline v-if="detailMilestones.length">
          <el-timeline-item
            v-for="milestone in detailMilestones"
            :key="milestone.id"
            :timestamp="formatDate(milestone.due_date)"
            placement="top"
          >
            <el-card class="milestone-item">
              <h4 class="milestone-title">{{ milestone.name }}</h4>
              <p class="milestone-desc">{{ milestone.description }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <p v-else class="empty-hint">暂无里程碑</p>
      </div>
    </el-dialog>

    <!-- 成员详情 dialog (MembersPanel emit 'open-detail' 触发) -->
    <el-dialog
      v-model="memberDetailVisible"
      :title="detailMember?.name || '成员详情'"
      :width="'600px'"
      top="5vh"
    >
      <div v-if="detailMember" class="member-detail">
        <div class="detail-hero">
          <div class="hero-avatar">
            <el-avatar :size="72" :src="detailMember.avatar">
              {{ detailMember.name?.charAt(0) }}
            </el-avatar>
          </div>
          <h2>{{ detailMember.name }}</h2>
          <div class="hero-tags">
            <el-tag size="small" :type="getRoleType(detailMember.role)">{{ getRoleLabel(detailMember.role) }}</el-tag>
            <el-tag v-if="detailMember.grade" size="small" type="info" class="grade-tag">{{ detailMember.grade }}</el-tag>
            <el-tag v-if="detailMember.voice_enrolled_at" size="small" type="success">🎤 已录入声纹</el-tag>
            <el-tag v-else size="small" type="warning">未录入声纹</el-tag>
          </div>
        </div>

        <h4 class="detail-section-title">基本信息</h4>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="研究方向">{{ detailMember.research_area || '-' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ detailMember.email || '-' }}</el-descriptions-item>
          <el-descriptions-item label="手机">{{ detailMember.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="个人简介">{{ detailMember.bio || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 v-if="detailMember.skills?.length" class="detail-section-title">技能</h4>
        <div v-if="detailMember.skills?.length" class="member-tags">
          <el-tag v-for="skill in detailMember.skills" :key="skill" size="small" type="info" class="member-tag-item">
            {{ skill }}
          </el-tag>
        </div>

        <h4 v-if="detailMember.voice_enrolled_at" class="detail-section-title">声纹</h4>
        <el-descriptions v-if="detailMember.voice_enrolled_at" :column="1" border>
          <el-descriptions-item label="录入时间">{{ formatDate(detailMember.voice_enrolled_at) }}</el-descriptions-item>
          <el-descriptions-item label="采样次数">{{ detailMember.voice_sample_count || 1 }} 次</el-descriptions-item>
        </el-descriptions>
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
 */

import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { Folder, User, Microphone } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'
import { useMemberStore } from '@/stores/member'
import TabStrip from '@/components/common/TabStrip.vue'
import ProjectsPanel from './workspace/ProjectsPanel.vue'
import MembersPanel from './workspace/MembersPanel.vue'
import VoiceprintsPanel from './workspace/VoiceprintsPanel.vue'

const route = useRoute()
const router = useRouter()
const memberStore = useMemberStore()

// 铁律 29: URL ?tab= 同步双向（VALID_TABS 白名单 + watch + replace）
const VALID_TABS = ['projects', 'members', 'voiceprint']
const activeTab = ref(
  route.query.tab && VALID_TABS.includes(String(route.query.tab))
    ? String(route.query.tab)
    : 'projects'
)

// 铁律 30: EP 图标 named import + 通过 props 传入
const tabItems = [
  { key: 'projects',   label: '项目', icon: Folder },
  { key: 'members',    label: '成员', icon: User },
  { key: 'voiceprint', label: '声纹', icon: Microphone },
]

// 铁律 29: tab → URL 同步
watch(activeTab, (tab) => {
  router.replace({ path: '/workspace', query: { ...route.query, tab } })
})

// 铁律 29: URL → tab 反向同步（已有, 强化）
watch(() => route.query.tab, (t) => {
  if (t && VALID_TABS.includes(String(t)) && String(t) !== activeTab.value) {
    activeTab.value = String(t)
  }
})

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

// ====== 辅助函数 ======
function getMemberName(id) {
  return memberStore.getMemberName?.(id) || `成员 #${id}`
}

function getStatusType(status) {
  const map = { active: 'success', paused: 'warning', completed: 'info', archived: 'info' }
  return map[status] || 'info'
}

function getStatusLabel(status) {
  const map = { active: '进行中', paused: '已暂停', completed: '已完成', archived: '已归档' }
  return map[status] || status
}

function getRoleType(role) {
  const map = { admin: 'danger', leader: 'warning', member: 'info' }
  return map[role] || 'info'
}

function getRoleLabel(role) {
  const map = { admin: '管理员', leader: '组长', member: '成员' }
  return map[role] || role || '成员'
}

onMounted(async () => {
  // 主动 fetch 一次成员数据 (避免 3 个 Panel 各自重复请求)
  if (memberStore.members.length === 0) {
    try {
      await memberStore.fetchMembers()
    } catch (e) {
      console.warn('fetchMembers 失败:', e)
    }
  }
  // 默认 tab 同步到 URL
  if (!route.query.tab) {
    router.replace({ path: '/workspace', query: { tab: 'projects' } })
  }
})
</script>

<style scoped>
.workspace-view {
  height: 100%;
  overflow-y: auto;
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

/* TabStrip 容器 + TabPanel 容器（铁律 31: 替代 el-tabs border-card） */
.tab-strip-wrapper {
  margin-bottom: var(--space-4);
}
.tab-panel {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.detail-section-title {
  margin-top: 20px;
  margin-bottom: var(--space-3);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.member-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.member-tags .el-tag {
  border-radius: var(--radius-full);
  transition: all var(--duration-fast) var(--ease-out);
}

.member-tags .el-tag:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.milestone-item {
  background: var(--color-bg-page);
  border-color: var(--color-border-base);
}

.milestone-title {
  color: var(--color-text-primary);
}

.milestone-desc {
  color: var(--color-text-secondary);
}

.empty-hint {
  color: var(--color-text-secondary);
  padding: 12px 0;
}

/* ===== 成员详情 dialog ===== */
.detail-hero {
  text-align: center;
  padding: 16px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  color: var(--el-color-white);
  margin-bottom: var(--space-4);
}

.detail-hero h2 {
  color: var(--el-color-white);
  margin: var(--space-3) 0;
}

.hero-avatar :deep(.el-avatar) {
  border: 2px solid rgba(255, 255, 255, 0.4);
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
/* 铁律 26: dark mode 覆盖必须非 scoped, scoped 块 data-v-xxx 干扰后代选择器 */
/* TabStrip 自身的 dark 模式由组件处理, 此处只覆盖 panel 内容 */
[data-theme="dark"] .tab-panel {
  background: var(--color-bg-card);
}
[data-theme="dark"] .detail-section-title {
  color: var(--color-text-primary);
}
[data-theme="dark"] .milestone-item {
  background: var(--color-bg-hover);
  border-color: var(--color-border-base);
}
</style>