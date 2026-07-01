<template>
  <div class="voiceprints-panel">
    <h2 class="panel-title">课题组声纹中心</h2>
    <div v-if="loading" v-loading="true" class="loading">加载中...</div>
    <div v-else-if="members.length === 0" class="empty">
      暂无录入声纹的成员。请前往"成员"tab 录入。
    </div>
    <div v-else class="cards-grid">
      <VoiceprintCard
        v-for="m in members"
        :key="m.id"
        :member="m"
        @select="onSelect"
      />
    </div>

    <el-drawer
      v-model="drawerVisible"
      :title="drawerTitle"
      size="50%"
    >
      <div v-if="selectedMember">
        <h3>置信度历史</h3>
        <ConfidenceChart :history="history" />
        <h3>该成员说过的内容</h3>
        <SpeakerSearch :member-id="selectedMember.id" @jump="onJump" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
/**
 * VoiceprintsPanel.vue — v78 "团队协作" 声纹 tab 子组件
 *
 * 从原 web/src/views/VoiceprintView.vue 拆出 (2026-07-02):
 * - 保留: 声纹卡片网格 + el-drawer 详情 + ConfidenceChart + SpeakerSearch
 * - 移除: 无独立路由逻辑, 全部内嵌于 WorkspaceView 容器
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import VoiceprintCard from '@/components/voiceprint/VoiceprintCard.vue'
import ConfidenceChart from '@/components/voiceprint/ConfidenceChart.vue'
import SpeakerSearch from '@/components/voiceprint/SpeakerSearch.vue'

const router = useRouter()
const members = ref([])
const loading = ref(true)
const drawerVisible = ref(false)
const selectedMember = ref(null)
const history = ref([])

const drawerTitle = computed(() => selectedMember.value ? `${selectedMember.value.name} 的声纹画像` : '')

onMounted(async () => {
  await loadMembers()
})

async function loadMembers() {
  loading.value = true
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  try {
    const resp = await fetch(`${apiUrl}/voiceprint/fingerprints`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
    })
    if (resp.ok) {
      members.value = await resp.json()
    }
  } finally {
    loading.value = false
  }
}

async function onSelect(memberId) {
  selectedMember.value = members.value.find((m) => m.id === memberId)
  drawerVisible.value = true
  await loadHistory(memberId)
}

async function loadHistory(memberId) {
  const apiUrl = import.meta.env.VITE_API_BASE || '/api/v1'
  const resp = await fetch(`${apiUrl}/voiceprint/${memberId}/history?limit=20`, {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
  })
  if (resp.ok) {
    history.value = await resp.json()
  }
}

function onJump(meetingId) {
  drawerVisible.value = false
  router.push(`/meetings/${meetingId}`)
}
</script>

<style scoped>
.voiceprints-panel {
  padding: 16px 0;
}

.panel-title {
  color: var(--color-text-primary);
  margin-bottom: var(--space-4);
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.loading, .empty {
  padding: 40px;
  text-align: center;
  color: var(--color-text-secondary);
}
</style>

<!-- v60-v67 教训: dark mode 跨组件覆盖必须非 scoped 块 -->
<style>
[data-theme="dark"] .voiceprints-panel {
  color: var(--color-text-primary);
}
[data-theme="dark"] .panel-title {
  color: var(--color-text-primary);
}
</style>