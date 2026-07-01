<template>
  <div class="mobile-voiceprints-panel">
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
      <div class="empty-hint">前往「成员」tab 录入</div>
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
                <button type="button" class="action-btn primary" @click="goToMemberTab">前往录入</button>
                <button type="button" class="action-btn" @click="showSpeakerSearch = true">说话记录</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 说话记录底部弹层 -->
    <SpeakerSearchSheet v-model="showSpeakerSearch" :member="selectedMember" />
  </div>
</template>

<script setup>
/**
 * MobileVoiceprintsPanel.vue — v78 "团队协作" 移动端声纹 tab
 *
 * 从原 web/src/views/mobile/MobileVoiceprintView.vue 拆出 (2026-07-02):
 * - 保留: 统计概览 + 成员网格 + 详情 sheet + 说话记录
 * - 移除: 顶部 PageHeader (由父 MobileWorkspaceView 提供)
 * - 移除: VoiceTestFlow 顶栏按钮 (改由父级 header 统一管理)
 * - 修复: 原 VoiceTestFlow import 移除
 */

import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import dayjs from 'dayjs'
import SpeakerSearchSheet from '@/components/mobile/SpeakerSearchSheet.vue'

const router = useRouter()
const members = ref([])
const loading = ref(true)
const showMemberDetail = ref(false)
const showSpeakerSearch = ref(false)
const selectedMember = ref(null)

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

function goToMemberTab() {
  closeMember()
  router.replace({ path: '/workspace', query: { tab: 'members' } })
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
.mobile-voiceprints-panel {
  padding: 12px 16px;
}

.stats-overview {
  text-align: center;
  padding: 24px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  /* stylelint-disable-next-line color-named */
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
  /* stylelint-disable-next-line color-named */
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
  border-radius: var(--radius-lg);
  font-size: 13px;
  color: var(--color-text-primary);
  cursor: pointer;
}
.action-btn.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  /* stylelint-disable-next-line color-named */
  color: white;
  border: none;
}

/* ===== Sheet ===== */
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
  /* stylelint-disable-next-line color-named */
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
  transition: transform 0.3s var(--ease-sheet);
}
.member-sheet-enter-from, .member-sheet-leave-to { opacity: 0; }
.member-sheet-enter-from .sheet-panel, .member-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .sheet-panel {
  background: var(--color-bg-card);
}
[data-theme="dark"] .member-card {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .empty-state {
  background: var(--color-bg-card);
}
</style>