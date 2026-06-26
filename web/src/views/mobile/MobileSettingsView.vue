<template>
  <div class="mobile-settings-view">
    <PageHeader title="个人设置" />

    <main
      class="settings-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 头像卡片 -->
      <section class="avatar-card">
        <div class="avatar-wrap">
          <MemberAvatar
            :member-id="userInfo?.id"
            :member-name="userInfo?.name"
            :size="72"
          />
          <button
            type="button"
            class="avatar-upload-btn"
            aria-label="更换头像"
            title="更换头像"
            @click="showAvatarSheet = true"
          >📷 更换</button>
        </div>
        <div class="user-info">
          <div class="user-name">{{ userInfo?.name || '未登录' }}</div>
          <div class="user-role">
            <span class="role-tag" :class="`role-${userInfo?.role}`">
              {{ roleLabel }}
            </span>
            <span v-if="userInfo?.email" class="user-email">{{ userInfo.email }}</span>
          </div>
        </div>
      </section>

      <!-- 设置项列表 -->
      <section class="settings-section">
        <button
          type="button"
          class="settings-item"
          @click="showProfileSheet = true"
        >
          <div class="item-icon" style="background: var(--color-primary-bg)">👤</div>
          <div class="item-info">
            <div class="item-title">编辑个人资料</div>
            <div class="item-desc">姓名、邮箱、电话、简介</div>
          </div>
          <span class="item-arrow">›</span>
        </button>

        <button
          type="button"
          class="settings-item"
          @click="showPasswordSheet = true"
        >
          <div class="item-icon" style="background: var(--color-warning-bg)">🔒</div>
          <div class="item-info">
            <div class="item-title">修改密码</div>
            <div class="item-desc">定期更换密码更安全</div>
          </div>
          <span class="item-arrow">›</span>
        </button>

        <button
          type="button"
          class="settings-item"
          @click="showNotifSheet = true"
        >
          <div class="item-icon" style="background: var(--color-info-bg, #ecf5ff)">🔔</div>
          <div class="item-info">
            <div class="item-title">通知偏好</div>
            <div class="item-desc">
              每日 {{ notifPrefs?.digest_time || '11:00' }} 统一推送
              <span v-if="notifPrefs?.snoozed_until" class="snoozed-badge">已推迟</span>
            </div>
          </div>
          <span class="item-arrow">›</span>
        </button>

        <button
          type="button"
          class="settings-item"
          @click="toggleTheme"
        >
          <div class="item-icon" style="background: var(--color-success-bg)">🌓</div>
          <div class="item-info">
            <div class="item-title">外观主题</div>
            <div class="item-desc">当前：{{ isDark ? '深色' : '浅色' }}</div>
          </div>
          <span class="item-arrow">›</span>
        </button>
      </section>

      <!-- 只读信息 -->
      <section class="readonly-section">
        <h3 class="section-title">账号信息</h3>
        <div class="readonly-list">
          <div class="readonly-item">
            <span class="readonly-label">研究方向</span>
            <span class="readonly-value">{{ userInfo?.research_area || '未填写' }}</span>
          </div>
          <div class="readonly-item">
            <span class="readonly-label">年级</span>
            <span class="readonly-value">{{ userInfo?.grade || '未填写' }}</span>
          </div>
          <div class="readonly-item">
            <span class="readonly-label">手机号</span>
            <span class="readonly-value">{{ userInfo?.phone || '未填写' }}</span>
          </div>
        </div>
      </section>

      <!-- 退出登录 -->
      <button
        type="button"
        class="logout-btn"
        @click="handleLogout"
      >退出登录</button>
    </main>

    <!-- 个人资料编辑 Sheet -->
    <MobileFormSheet
      v-model="showProfileSheet"
      title="编辑个人资料"
      :fields="profileFields"
      v-model:form="profileForm"
      submit-text="保存"
      :submitting="savingProfile"
      @submit="onSaveProfile"
    />

    <!-- 修改密码 Sheet -->
    <MobileFormSheet
      v-model="showPasswordSheet"
      title="修改密码"
      :fields="passwordFields"
      v-model:form="passwordForm"
      submit-text="修改密码"
      :submitting="savingPassword"
      @submit="onChangePassword"
    />

    <!-- 头像操作 Sheet -->
    <MobileActionSheet
      v-model="showAvatarSheet"
      title="更换头像"
      :actions="avatarActions"
      @select="onAvatarAction"
    />

    <!-- 通知偏好 Sheet（v2 11AM 单一窗口） -->
    <MobileFormSheet
      v-model="showNotifSheet"
      title="通知偏好"
      :fields="notifFields"
      v-model:form="notifForm"
      submit-text="保存"
      :submitting="notifSaving"
      @submit="onSaveNotif"
    />

    <input
      ref="avatarInputRef"
      type="file"
      accept="image/*"
      hidden
      aria-label="选择头像"
      title="选择头像"
      @change="handleAvatarChange"
    />
  </div>
</template>

<script setup>
/**
 * MobileSettingsView.vue — 移动端个人设置
 *
 * PR #8a: 用 PageHeader + 卡片列表 + MobileFormSheet/ActionSheet 组合
 * - 头像卡片（点击触发 ActionSheet 选择）
 * - 设置项列表（编辑资料 / 改密码 / 主题）
 * - 只读信息卡片
 * - 退出登录
 */

import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/useThemeStore'
import { useNotificationPrefs } from '@/composables/useNotificationPrefs'
import PageHeader from '@/components/mobile/PageHeader.vue'
import MobileFormSheet from '@/components/mobile/MobileFormSheet.vue'
import MobileActionSheet from '@/components/mobile/MobileActionSheet.vue'
import MemberAvatar from '@/components/mobile/MemberAvatar.vue'

const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

const userInfo = computed(() => userStore.userInfo)

const showProfileSheet = ref(false)
const showPasswordSheet = ref(false)
const showAvatarSheet = ref(false)
const showNotifSheet = ref(false)
const avatarInputRef = ref(null)

const savingProfile = ref(false)
const savingPassword = ref(false)

// 通知偏好（v2 11AM 单一窗口）
const { prefs: notifPrefs, loading: notifLoading, fetchPrefs: fetchNotifPrefs, savePrefs: saveNotifPrefs } = useNotificationPrefs()
const notifSaving = ref(false)
const notifForm = reactive({
  enabled: true,
  digest_time: '11:00',
})
const notifFields = computed(() => [
  {
    key: 'enabled',
    label: '启用提醒',
    type: 'switch',
  },
  {
    key: 'digest_time',
    label: '每日提醒时间 (HH:MM)',
    type: 'input',
    placeholder: '11:00',
    rules: [
      (v) => /^([01]\d|2[0-3]):[0-5]\d$/.test(v) || '格式错误，应为 HH:MM (00:00-23:59)',
    ],
  },
])

async function onSaveNotif(form) {
  notifSaving.value = true
  try {
    await saveNotifPrefs({
      enabled: form.enabled,
      digest_time: form.digest_time,
    })
    showNotifSheet.value = false
  } catch (e) {
    // 错误已由 composable 内部 ElMessage 处理
  } finally {
    notifSaving.value = false
  }
}

const roleMap = { admin: '管理员', leader: '组长', member: '成员' }
const roleLabel = computed(() => roleMap[userInfo.value?.role] || '成员')
const isDark = computed(() => themeStore.isDark)

// 个人资料表单
const profileForm = reactive({
  name: userInfo.value?.name || '',
  email: userInfo.value?.email || '',
  phone: userInfo.value?.phone || '',
  bio: userInfo.value?.bio || '',
})

const profileFields = computed(() => [
  { key: 'name', label: '姓名', type: 'input', required: true, maxlength: 50 },
  { key: 'email', label: '邮箱', type: 'input', placeholder: 'example@lab.cn' },
  { key: 'phone', label: '电话', type: 'input', placeholder: '11 位手机号' },
  { key: 'bio', label: '个人简介', type: 'textarea', rows: 3, maxlength: 200 },
])

// 密码表单
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const passwordFields = computed(() => [
  { key: 'old_password', label: '旧密码', type: 'input', required: true },
  {
    key: 'new_password',
    label: '新密码',
    type: 'input',
    required: true,
    rules: [(v) => (v && v.length >= 6) || '密码至少6位'],
  },
  {
    key: 'confirm_password',
    label: '确认密码',
    type: 'input',
    required: true,
    rules: [(v) => v === passwordForm.new_password || '两次密码不一致'],
  },
])

// 头像操作
const avatarActions = [
  { name: '拍照', icon: '📷', color: 'var(--color-primary)' },
  { name: '从相册选择', icon: '🖼️', color: '#67C23A' },
  { name: '恢复默认头像', icon: '🔄', color: '#909399' },
]

function onAvatarAction(action) {
  if (action.name === '拍照' || action.name === '从相册选择') {
    avatarInputRef.value?.click()
  } else if (action.name === '恢复默认头像') {
    updateAvatar(null)
  }
}

async function handleAvatarChange(e) {
  const f = e.target.files?.[0]
  if (!f) return
  if (f.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片不能超过5MB')
    return
  }
  // 简化：直接上传不压缩（mobile/compressImage 桌面端已有）
  try {
    const fd = new FormData()
    fd.append('file', f, 'avatar.jpg')
    const uploadRes = await axios.post('/api/v1/upload', fd, {
      params: { prefix: 'avatars' },
    })
    await updateAvatar(uploadRes.data?.url)
  } catch (err) {
    ElMessage.error('上传失败：' + (err.response?.data?.detail || err.message))
  }
  e.target.value = ''
}

async function updateAvatar(url) {
  try {
    const payload = { avatar: url || '' }
    await axios.put('/api/v1/auth/profile', payload)
    const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
    stored.avatar = url || ''
    localStorage.setItem('user_info', JSON.stringify(stored))
    userStore.loadFromStorage()
    ElMessage.success(url ? '头像已更新' : '已恢复默认头像')
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

// 主题
function toggleTheme() {
  themeStore.toggle()
}

// 保存个人资料
async function onSaveProfile(form) {
  savingProfile.value = true
  try {
    await axios.put('/api/v1/auth/profile', form)
    // 同步 localStorage
    const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
    Object.assign(stored, form)
    localStorage.setItem('user_info', JSON.stringify(stored))
    userStore.loadFromStorage()
    ElMessage.success('已保存')
    showProfileSheet.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingProfile.value = false
  }
}

// 修改密码
async function onChangePassword(form) {
  savingPassword.value = true
  try {
    await axios.post('/api/v1/auth/change-password', {
      old_password: form.old_password,
      new_password: form.new_password,
    })
    ElMessage.success('密码已修改')
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    showPasswordSheet.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改失败')
  } finally {
    savingPassword.value = false
  }
}

// 退出登录
function handleLogout() {
  userStore.logout()
  ElMessage.success('已退出')
  router.push('/login')
}

onMounted(async () => {
  // 同步最新用户信息
  profileForm.name = userInfo.value?.name || ''
  profileForm.email = userInfo.value?.email || ''
  profileForm.phone = userInfo.value?.phone || ''
  profileForm.bio = userInfo.value?.bio || ''
  // 加载通知偏好
  await fetchNotifPrefs()
  if (notifPrefs.value) {
    notifForm.enabled = notifPrefs.value.enabled
    notifForm.digest_time = notifPrefs.value.digest_time
  }
})
</script>

<style scoped>
.mobile-settings-view {
  min-height: 100vh;
  background: var(--color-bg-page);
}

.settings-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 头像卡片 */
.avatar-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
}
.avatar-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.avatar-circle {
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
.avatar-upload-btn {
  background: transparent;
  border: none;
  font-size: 11px;
  color: var(--color-primary);
  cursor: pointer;
  padding: 4px 8px;
}

.user-info {
  flex: 1;
  min-width: 0;
}
.user-name {
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin-bottom: 6px;
}
.user-role {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.role-tag {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
.role-admin { background: var(--color-danger-bg); color: var(--color-danger, #F56C6C); }
.role-leader { background: var(--color-warning-bg); color: var(--color-warning, #E6A23C); }
.user-email {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* 设置项 */
.settings-section {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  overflow: hidden;
}
.settings-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--color-border-light);
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.settings-item:last-child { border-bottom: none; }
.settings-item:active { background: var(--color-bg-hover); }
.item-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.item-info { flex: 1; min-width: 0; }
.item-title {
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  margin-bottom: 2px;
}
.item-desc {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.item-arrow {
  font-size: 20px;
  color: var(--color-text-placeholder);
}

/* 只读信息 */
.readonly-section {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 16px;
}
.section-title {
  font-size: 13px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-secondary);
  margin: 0 0 12px;
}
.readonly-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.readonly-item {
  display: flex;
  font-size: 13px;
}
.readonly-label {
  flex: 0 0 70px;
  color: var(--color-text-secondary);
}
.readonly-value {
  flex: 1;
  color: var(--color-text-primary);
  overflow-wrap: anywhere;
}

/* 退出 */
.logout-btn {
  width: 100%;
  padding: 14px;
  margin-top: 12px;
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
  border: 1px solid var(--color-danger, #F56C6C);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.logout-btn:active { opacity: 0.7; }
.snoozed-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  background: var(--color-warning-bg, #fdf6ec);
  color: var(--color-warning, #E6A23C);
  border-radius: 8px;
  font-size: 10px;
}
</style>