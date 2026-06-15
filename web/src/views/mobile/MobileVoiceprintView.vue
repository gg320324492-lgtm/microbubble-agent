<template>
  <div class="mobile-voiceprint-view">
    <PageHeader title="声纹中心" show-back @back="$router.back()">
      <template #right>
        <button
          id="voiceprint-header-test"
          type="button"
          name="voiceprint-header-test"
          class="header-action"
          aria-label="声纹识别测试"
          title="声纹识别测试"
          @click="showTest = true"
        >🎤</button>
      </template>
    </PageHeader>

    <main
      class="voiceprint-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 统计概览 -->
      <section class="stats-overview">
        <div class="overview-num">{{ members.length }}</div>
        <div class="overview-label">已录入声纹成员</div>
      </section>

      <!-- 成员列表 -->
      <section v-if="loading" class="loading">
        <div class="loading-spinner" />
      </section>

      <section v-else-if="members.length === 0" class="empty-state">
        <div class="empty-icon">🎤</div>
        <div class="empty-title">暂无录入声纹的成员</div>
        <div class="empty-hint">前往「我的 → 成员管理」录入</div>
        <button
          type="button"
          class="action-btn"
          @click="$router.push('/members')"
        >去录入</button>
      </section>

      <section v-else class="members-grid">
        <button
          v-for="m in members"
          :key="m.id"
          type="button"
          class="member-card"
          @click="openMember(m)"
        >
          <div class="member-avatar">
            {{ m.name?.charAt(0) }}
            <span v-if="m.voice_enrolled_at" class="enrolled-dot" />
          </div>
          <div class="member-info">
            <div class="member-name">{{ m.name }}</div>
            <div class="member-meta">
              <span class="sample-count">{{ m.voice_sample_count || 1 }} 次采样</span>
            </div>
          </div>
          <span class="card-arrow">›</span>
        </button>
      </section>
    </main>

    <!-- 成员详情 Bottom Sheet -->
    <Teleport to="body">
      <Transition name="member-sheet">
        <div v-if="showMemberDetail" class="sheet-overlay" @click.self="closeMember">
          <div class="sheet-panel" :style="{ paddingBottom: 'calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))' }">
            <div class="sheet-handle" />
            <div v-if="selectedMember" class="member-detail">
              <div class="detail-header">
                <div class="detail-avatar">{{ selectedMember.name?.charAt(0) }}</div>
                <div>
                  <h3>{{ selectedMember.name }}</h3>
                  <p class="detail-role">{{ selectedMember.role || '成员' }}</p>
                </div>
              </div>

              <div class="detail-info">
                <div class="info-row">
                  <span class="info-label">采样次数</span>
                  <span class="info-value">{{ selectedMember.voice_sample_count || 1 }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">录入时间</span>
                  <span class="info-value">{{ formatDate(selectedMember.voice_enrolled_at) }}</span>
                </div>
              </div>

              <div class="detail-actions">
                <button
                  type="button"
                  class="action-btn primary"
                  @click="reEnroll(selectedMember)"
                >🎤 重新录入</button>
                <button
                  type="button"
                  class="action-btn"
                  @click="showSpeakerSearch = true"
                >🔍 说话记录</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 麦克风测试全屏 -->
    <VoiceTestFlow v-model:show="showTest" />

    <!-- 声纹录入全屏 -->
    <VoiceprintEnrollFlow
      v-if="enrollingMember"
      v-model:show="showEnroll"
      :member="enrollingMember"
      @success="onEnrollSuccess"
    />
  </div>
</template>

<script setup>
/**
 * MobileVoiceprintView.vue — 移动端声纹中心
 *
 * PR #8b: CardList 风格 + 集成 PR #5 VoiceTestFlow + VoiceprintEnrollFlow
 */

import { ref, onMounted } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import PageHeader from '@/components/mobile/PageHeader.vue'
import VoiceTestFlow from '@/components/mobile/VoiceTestFlow.vue'
import VoiceprintEnrollFlow from '@/components/mobile/VoiceprintEnrollFlow.vue'

const members = ref([])
const loading = ref(true)
const showTest = ref(false)
const showMemberDetail = ref(false)
const showEnroll = ref(false)
const showSpeakerSearch = ref(false)
const selectedMember = ref(null)
const enrollingMember = ref(null)

async function fetchMembers() {
  loading.value = true
  try {
    const res = await axios.get('/api/v1/members', {
      params: { voice_enrolled: true, page_size: 100 },
    })
    members.value = res.data?.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function openMember(m) {
  selectedMember.value = m
  showMemberDetail.value = true
}

function closeMember() {
  showMemberDetail.value = false
  selectedMember.value = null
}

function reEnroll(m) {
  closeMember()
  enrollingMember.value = m
  showEnroll.value = true
}

function onEnrollSuccess() {
  showEnroll.value = false
  enrollingMember.value = null
  fetchMembers()
}

function formatDate(t) {
  if (!t) return ''
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  fetchMembers()
})
</script>

<style scoped>
.mobile-voiceprint-view {
  min-height: 100vh;
  background: var(--color-bg-page);
}

.voiceprint-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 概览 */
.stats-overview {
  text-align: center;
  padding: 24px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  color: white;
}
.overview-num {
  font-size: 48px;
  font-weight: var(--font-weight-bold, 700);
  font-variant-numeric: tabular-nums;
  line-height: 1;
  margin-bottom: 4px;
}
.overview-label {
  font-size: 13px;
  opacity: 0.9;
}

/* 成员网格 */
.members-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.member-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 8px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.member-card:active { background: var(--color-bg-hover); }

.member-avatar {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  font-size: 22px;
  font-weight: var(--font-weight-semibold, 600);
  display: flex;
  align-items: center;
  justify-content: center;
}
.enrolled-dot {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  background: var(--color-success, #67C23A);
  border: 2px solid var(--color-bg-card);
  border-radius: 50%;
}
.member-info { text-align: center; }
.member-name {
  font-size: 13px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  margin-bottom: 2px;
}
.sample-count {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.card-arrow {
  font-size: 18px;
  color: var(--color-text-placeholder);
  align-self: flex-end;
}

/* 加载 / 空 */
.loading {
  text-align: center;
  padding: 40px 20px;
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
  padding: 60px 20px;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 15px;
  color: var(--color-text-regular);
  margin-bottom: 4px;
}
.empty-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 16px;
}
.action-btn {
  padding: 10px 24px;
  background: var(--color-bg-page);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-text-primary);
  cursor: pointer;
}
.action-btn.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
  border: none;
}

/* Header */
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-action:active { background: var(--color-primary-bg); }

/* 成员详情 Sheet */
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 20px;
  max-height: 70vh;
}
[data-theme="dark"] .sheet-panel { background: var(--color-bg-card); }
.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 16px;
}
.member-detail { padding: 0 0 16px; }
.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 16px;
}
.detail-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  color: white;
  font-size: 28px;
  font-weight: var(--font-weight-semibold, 600);
  display: flex;
  align-items: center;
  justify-content: center;
}
.detail-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}
.detail-role {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.detail-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}
.info-row {
  display: flex;
  font-size: 13px;
}
.info-label {
  flex: 0 0 80px;
  color: var(--color-text-secondary);
}
.info-value {
  flex: 1;
  color: var(--color-text-primary);
}
.detail-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.detail-actions .action-btn {
  width: 100%;
  padding: 14px;
}

.member-sheet-enter-active, .member-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.member-sheet-enter-active .sheet-panel, .member-sheet-leave-active .sheet-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.member-sheet-enter-from, .member-sheet-leave-to { opacity: 0; }
.member-sheet-enter-from .sheet-panel, .member-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>