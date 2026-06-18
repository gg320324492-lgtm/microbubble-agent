<template>
  <div class="mobile-member-detail-view">
    <PageHeader :title="member?.name || '成员详情'" show-back @back="$router.back()">
      <template #right>
        <button
          v-if="member && !member.voice_enrolled_at"
          type="button"
          class="header-action"
          aria-label="录入声纹"
          title="录入声纹"
          @click="startEnroll"
        >🎤</button>
      </template>
    </PageHeader>

    <main
      class="detail-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <div v-if="loading" class="loading">
        <div class="loading-spinner" />
      </div>

      <div v-else-if="!member" class="empty-state">
        <div class="empty-icon">👤</div>
        <div class="empty-title">未找到该成员</div>
      </div>

      <div v-else class="member-content">
        <section class="hero-card">
          <div class="hero-avatar">{{ member.name?.charAt(0) }}</div>
          <h2 class="hero-name">{{ member.name }}</h2>
          <div class="hero-tags">
            <el-tag size="small" :type="getRoleType(member.role)">{{ getRoleLabel(member.role) }}</el-tag>
            <el-tag v-if="member.grade" size="small" type="info">{{ member.grade }}</el-tag>
            <el-tag
              v-if="member.voice_enrolled_at"
              size="small"
              type="success"
            >🎤 已录入声纹</el-tag>
            <el-tag v-else size="small" type="warning">未录入声纹</el-tag>
          </div>
        </section>

        <section class="info-card">
          <h3 class="info-title">基本信息</h3>
          <div class="info-row">
            <span class="info-label">研究方向</span>
            <span class="info-value">{{ member.research_area || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">邮箱</span>
            <span class="info-value">{{ member.email || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">手机</span>
            <span class="info-value">{{ member.phone || '—' }}</span>
          </div>
        </section>

        <section v-if="member.bio" class="info-card">
          <h3 class="info-title">个人简介</h3>
          <p class="bio-text">{{ member.bio }}</p>
        </section>

        <section v-if="member.skills && member.skills.length" class="info-card">
          <h3 class="info-title">技能</h3>
          <div class="skills-list">
            <el-tag
              v-for="skill in member.skills"
              :key="skill"
              size="small"
              type="info"
              style="margin: 2px"
            >{{ skill }}</el-tag>
          </div>
        </section>

        <section v-if="member.voice_enrolled_at" class="info-card">
          <h3 class="info-title">声纹</h3>
          <div class="info-row">
            <span class="info-label">录入时间</span>
            <span class="info-value">{{ formatDate(member.voice_enrolled_at) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">采样次数</span>
            <span class="info-value">{{ member.voice_sample_count || 1 }} 次</span>
          </div>
        </section>
      </div>
    </main>

    <!-- 声纹录入流程 -->
    <VoiceprintEnrollFlow
      v-if="enrollingMember"
      v-model="showEnroll"
      :member="enrollingMember"
      @success="onEnrollSuccess"
    />
  </div>
</template>

<script setup>
/**
 * MobileMemberDetailView.vue — 移动端成员详情页
 *
 * 从 MobileMemberView 卡片点击进入，显示完整成员信息 + 声纹状态
 * 顶部"🎤"按钮触发声纹录入
 */

import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import dayjs from 'dayjs'
import { ElTag } from 'element-plus'
import PageHeader from '@/components/mobile/PageHeader.vue'
import VoiceprintEnrollFlow from '@/components/mobile/VoiceprintEnrollFlow.vue'

const route = useRoute()
const router = useRouter()
const member = ref(null)
const loading = ref(true)
const showEnroll = ref(false)
const enrollingMember = ref(null)

async function fetchMember() {
  const id = route.params.id
  if (!id) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const res = await axios.get(`/api/v1/members/${id}`)
    member.value = res.data
  } catch (e) {
    console.error('获取成员详情失败:', e)
    member.value = null
  } finally {
    loading.value = false
  }
}

function startEnroll() {
  if (!member.value) return
  enrollingMember.value = member.value
  showEnroll.value = true
}

function onEnrollSuccess() {
  showEnroll.value = false
  enrollingMember.value = null
  fetchMember()
}

function getRoleType(role) {
  const map = { admin: 'danger', leader: 'warning', member: 'info' }
  return map[role] || 'info'
}

function getRoleLabel(role) {
  const map = { admin: '管理员', leader: '组长', member: '成员' }
  return map[role] || role || '成员'
}

function formatDate(t) {
  if (!t) return ''
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  fetchMember()
})
</script>

<style scoped>
.mobile-member-detail-view {
  min-height: 100vh;
  background: var(--color-bg-page);
}
.detail-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.header-action:active { background: var(--color-primary-bg); }

.loading {
  text-align: center;
  padding: 60px 20px;
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  text-align: center;
  padding: 80px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  color: var(--color-text-regular);
}

.member-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hero-card {
  text-align: center;
  padding: 24px 16px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  color: white;
}
.hero-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  border: 2px solid rgba(255, 255, 255, 0.4);
  color: white;
  font-size: 28px;
  font-weight: var(--font-weight-semibold, 600);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
}
.hero-name {
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: var(--font-weight-semibold, 600);
}
.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}
.hero-tags :deep(.el-tag) {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.info-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
}
.info-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-regular);
}
.info-row {
  display: flex;
  font-size: 13px;
  padding: 6px 0;
}
.info-label {
  flex: 0 0 80px;
  color: var(--color-text-secondary);
}
.info-value {
  flex: 1;
  color: var(--color-text-primary);
  word-break: break-word;
}
.bio-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-primary);
  white-space: pre-wrap;
}
.skills-list {
  display: flex;
  flex-wrap: wrap;
}
</style>
