<template>
  <div class="mobile-settings-view mg-page">
    <PageHeader title="个人设置" />

    <main
      class="settings-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 头像卡片 -->
      <section class="avatar-card mg-glass mg-rise">
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
            <span class="role-tag mg-chip" :class="`role-${roleTagClass}`">
              {{ roleLabel }}
            </span>
            <span v-if="userInfo?.email" class="user-email">{{ userInfo.email }}</span>
          </div>
        </div>
      </section>

      <!-- 设置项列表 -->
      <section class="settings-section mg-glass mg-rise mg-stagger-1">
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

        <!-- 2026-08-31: 通知偏好 / 推送通知 两项按需求移除 (每日 digest 走后端固定 11:00 窗口) -->

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

        <!-- 2026-08-31: 思考模式选择器迁至对话页输入区 (MobileInputBar), 此处不再重复 -->
      </section>

      <!-- 只读信息 -->
      <section class="readonly-section mg-glass mg-rise mg-stagger-2">
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
      <!-- 注: 不加 mg-rise (animation fill:both 会永久盖掉 :active 的 scale/opacity 反馈) -->
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
const avatarInputRef = ref(null)

const savingProfile = ref(false)
const savingPassword = ref(false)

// 2026-09-05 角色扁平化: 展示年级身份称谓 (导师/博士/硕士/本科生...)
const roleLabel = computed(() => userStore.userRole)
const roleTagClass = computed(() => ({
  导师: 'advisor', 博士后: 'postdoc', 博士: 'phd', 硕士: 'master',
  本科生: 'undergrad', 校友: 'alumni',
}[roleLabel.value] || 'member'))
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

onMounted(() => {
  // 同步最新用户信息
  profileForm.name = userInfo.value?.name || ''
  profileForm.email = userInfo.value?.email || ''
  profileForm.phone = userInfo.value?.phone || ''
  profileForm.bio = userInfo.value?.bio || ''
})
</script>

<style scoped>
/* ============================================================
   液态毛玻璃 (Liquid Glass) 升级 — 2026-08-31
   分组 section = mg-glass 卡 (template 挂类, scoped 定尺寸);
   行分隔 1px rgba(124,107,216,.12); 头像圈渐变描边;
   危险操作 (退出登录) 走 --mg-danger; 颜色一律 --mg-* token
   ============================================================ */
.mobile-settings-view {
  min-height: 100vh;
  /* background 交给全局 .mg-page (本视图无同名全局竞争类, 单类即可命中) */
}

.settings-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 头像卡片 (mg-glass surface) */
.avatar-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 16px;
  margin-bottom: 14px;
}
.avatar-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
/* 头像圈渐变描边: gradient 作 padding 露出 3px 圆环 */
.avatar-wrap :deep(.el-avatar) {
  padding: 3px;
  border-radius: 50%;
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-weight: 800;
  box-shadow: var(--mg-shadow-sm);
}
.avatar-wrap :deep(.el-avatar > img) {
  border-radius: 50%;
}
.avatar-circle {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--mg-gradient-btn);
  /* stylelint-disable-next-line color-named */
  color: white;
  font-size: 28px;
  font-weight: var(--font-weight-semibold, 600);
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-upload-btn {
  background: var(--mg-glass-bg-strong);
  border: 1px solid var(--mg-glass-border);
  font-size: 11px;
  font-weight: 700;
  color: var(--mg-primary);
  cursor: pointer;
  padding: 8px 14px;
  min-height: 44px;
  border-radius: var(--mg-radius-pill);
  transition: transform 150ms ease;
}
.avatar-upload-btn:active { transform: scale(0.95); }

.user-info {
  flex: 1;
  min-width: 0;
}
.user-name {
  font-size: 18px;
  font-weight: 800;
  color: var(--mg-text-strong);
  margin-bottom: 6px;
}
.user-role {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
/* role-tag: 底色/文字由 mg-chip 全局类提供 (紫 tint), 此处只留尺寸与语义变体 */
.role-tag {
  font-size: 11px;
}
/* 身份称谓配色 (2026-09-05 角色扁平化): 导师=暖红 / 博字辈=金 / 硕士=主色 / 本科生=绿 */
.role-advisor { background: var(--mg-danger-soft); color: var(--mg-danger); }
.role-postdoc, .role-phd { background: var(--mg-warning-soft); color: var(--mg-warning); }
.role-undergrad { background: var(--mg-success-soft, var(--mg-primary-soft)); color: var(--mg-success, var(--mg-primary)); }
.user-email {
  font-size: 12px;
  color: var(--mg-text-soft);
}

/* 设置项分组卡 (mg-glass surface) */
.settings-section {
  margin-bottom: 14px;
  overflow: hidden;
}
/* 嵌套的 "思考模式" 分组不重复起卡, 融入外层玻璃卡 */
.settings-section .settings-section {
  background: transparent;
  border: none;
  box-shadow: none;
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
  margin-bottom: 0;
  padding: 4px 0 10px;
}
.settings-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 48px;
  padding: 12px 14px;
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(124, 107, 216, 0.12);
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background 150ms ease;
}
.settings-item:last-child { border-bottom: none; }
.settings-item:active {
  background: rgba(124, 107, 216, 0.08);
}
/* 行尾嵌套分组前的最后一行按钮去掉分隔线 */
.settings-item + .settings-section { border-top: 1px solid rgba(124, 107, 216, 0.12); }
/* 图标块: 柔渐变底 (对齐样稿 d-task .em: 34px 圆角 12px;
   inline style 的旧 --color-* tint 用 !important 覆盖) */
.item-icon {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: var(--mg-gradient-soft) !important;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.item-info { flex: 1; min-width: 0; }
.item-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--mg-text-strong);
  margin-bottom: 2px;
}
.item-desc {
  font-size: 11px;
  color: var(--mg-text-soft);
}
.item-arrow {
  font-size: 20px;
  color: var(--mg-text-faint);
}

/* 只读信息 (mg-glass surface) */
.readonly-section {
  padding: 16px;
  margin-bottom: 14px;
}
.section-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--mg-text-strong);
  margin: 6px 2px 12px;
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
  color: var(--mg-text-soft);
}
.readonly-value {
  flex: 1;
  color: var(--mg-text-strong);
  font-weight: 600;
  overflow-wrap: anywhere;
}

/* 退出登录 — 危险操作用 --mg-danger */
.logout-btn {
  width: 100%;
  padding: 14px;
  margin-top: 4px;
  background: var(--mg-danger-soft);
  color: var(--mg-danger);
  border: 1.5px solid var(--mg-danger);
  border-radius: var(--mg-radius-md);
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 150ms ease, opacity 150ms ease;
  -webkit-tap-highlight-color: transparent;
}
.logout-btn:active { transform: scale(0.97); opacity: 0.8; }
/* 2026-08-31: snoozed-badge / push-status-* 样式随「通知偏好 / 推送通知」两项移除 */
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped）
     2026-08-31 液态毛玻璃: --mg-* token 在 [data-theme="dark"] 下自动翻转,
     本块保留 --color-* 兜底 + vant/third-party 组件玻璃化覆盖 (视图根 class 锁范围) -->
<style>
[data-theme="dark"] .mobile-settings-view .settings-group {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
}
[data-theme="dark"] .mobile-settings-view .settings-item .item-label {
  color: var(--color-text-primary);
}
[data-theme="dark"] .mobile-settings-view .theme-swatch {
  border: 2px solid var(--color-border-light);
}
[data-theme="dark"] .mobile-settings-view .theme-swatch.active {
  border-color: var(--color-primary);
}
/* 2026-08-31: 思考模式 mode-* 样式迁至 MobileChatView (选择器移入对话输入区) */
</style>