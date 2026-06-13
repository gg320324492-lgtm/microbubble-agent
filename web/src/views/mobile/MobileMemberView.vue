<template>
  <div class="mobile-member-view">
    <PageHeader title="成员管理" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="搜索"
          title="搜索"
          @click="showSearch = true"
        >🔍</button>
        <button
          type="button"
          class="header-action primary"
          aria-label="添加"
          title="添加"
          @click="showCreate = true"
        >+</button>
      </template>
    </PageHeader>

    <main
      class="member-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <CardList
        :items="members"
        :field-config="memberFieldConfig"
        :loading="loading"
        empty-icon="👥"
        empty-title="暂无成员"
        empty-hint="点击右上角 + 添加"
        @item-click="viewMember"
      >
        <template #item-actions="{ item }">
          <div class="member-actions">
            <button
              type="button"
              class="action-btn"
              :class="{ active: item.voice_enrolled_at }"
              @click.stop="handleVoiceprint(item)"
            >
              🎤 {{ item.voice_enrolled_at ? '已录入' : '录入声纹' }}
            </button>
          </div>
        </template>
      </CardList>
    </main>

    <!-- 搜索 Sheet -->
    <MobileSearchSheet
      v-model:show="showSearch"
      v-model:keyword="searchKeyword"
      title="搜索成员"
      placeholder="搜索姓名..."
      :filters="searchFilters"
      v-model:filters="activeFilters"
      @confirm="onSearchConfirm"
      @reset="onSearchReset"
    />

    <!-- 声纹录入全屏流程 -->
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
 * MobileMemberView.vue — 移动端成员管理
 *
 * PR #8b: CardList + 集成 PR #5 VoiceprintEnrollFlow
 */

import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import PageHeader from '@/components/mobile/PageHeader.vue'
import CardList from '@/components/mobile/CardList.vue'
import MobileSearchSheet from '@/components/mobile/MobileSearchSheet.vue'
import VoiceprintEnrollFlow from '@/components/mobile/VoiceprintEnrollFlow.vue'

const members = ref([])
const loading = ref(false)
const showSearch = ref(false)
const showCreate = ref(false)
const showEnroll = ref(false)
const enrollingMember = ref(null)

const searchKeyword = ref('')
const activeFilters = ref({ grade: '' })

const searchFilters = computed(() => [
  {
    key: 'grade',
    label: '年级',
    options: [
      { value: '', label: '全部' },
      { value: '教授', label: '教授' },
      { value: '博士后', label: '博士后' },
      { value: '博一', label: '博一' },
      { value: '博二', label: '博二' },
      { value: '研一', label: '研一' },
      { value: '研二', label: '研二' },
      { value: '研三', label: '研三' },
    ],
  },
])

const memberFieldConfig = computed(() => ({
  title: (m) => m.name,
  subtitle: (m) => `${m.role || ''} · ${m.grade || ''}`,
  badge: (m) => ({
    label: m.voice_enrolled_at ? '✓ 声纹' : '未录入',
    type: m.voice_enrolled_at ? 'success' : 'info',
  }),
  fields: (m) => [
    { key: 'email', label: '邮箱', value: m.email || '—' },
    { key: 'research', label: '方向', value: m.research_area || '—' },
  ],
}))

async function fetchMembers() {
  loading.value = true
  try {
    const params = {}
    if (searchKeyword.value) params.name = searchKeyword.value
    if (activeFilters.value.grade) params.grade = activeFilters.value.grade
    const res = await axios.get('/api/v1/members', { params })
    members.value = res.data?.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function onSearchConfirm({ keyword, filters }) {
  searchKeyword.value = keyword
  Object.assign(activeFilters.value, filters)
  fetchMembers()
}

function onSearchReset() {
  searchKeyword.value = ''
  activeFilters.value = { grade: '' }
  fetchMembers()
}

function viewMember(member) {
  // 简化：弹窗显示详情
  // 实际可以跳转到详情页
}

function handleVoiceprint(member) {
  enrollingMember.value = member
  showEnroll.value = true
}

function onEnrollSuccess() {
  showEnroll.value = false
  enrollingMember.value = null
  fetchMembers()
}

onMounted(() => {
  fetchMembers()
})
</script>

<style scoped>
.mobile-member-view {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.member-main {
  flex: 1;
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
  margin-left: 4px;
}
.header-action:active { background: var(--color-primary-bg); }
.header-action.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
  font-weight: 600;
  font-size: 22px;
}

.member-actions {
  margin-top: 6px;
}
.action-btn {
  width: 100%;
  padding: 8px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 12px;
  background: var(--color-bg-page);
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.action-btn.active {
  background: var(--color-success-bg);
  color: var(--color-success, #67C23A);
}
.action-btn:active { opacity: 0.7; }
</style>