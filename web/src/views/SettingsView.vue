<template>
  <div class="settings-view fade-slide-up">
    <div class="settings-grid">
      <!-- v68 (2026-06-26) Hero 卡片（全宽渐变）：头像 + 姓名 + 角色 + 邮箱 + 编辑按钮 -->
      <section class="hero-card">
        <div class="hero-bg" />
        <div class="hero-content">
          <el-avatar
            :size="88"
            :key="previewAvatarUrl"
            :src="previewAvatarUrl || userStore.userInfo?.avatar"
            :alt="`${userStore.userInfo?.name || '用户'}的头像`"
            icon="UserFilled"
            class="hero-avatar"
          />
          <div class="hero-info">
            <h2 class="hero-name">{{ form.name || '未设置姓名' }}</h2>
            <div class="hero-meta">
              <el-tag :type="roleTagType" size="small" effect="dark">{{ form.roleLabel }}</el-tag>
              <span v-if="form.email" class="hero-email">{{ form.email }}</span>
            </div>
          </div>
          <el-button type="primary" plain round class="hero-edit-btn" @click="scrollToProfile">
            <el-icon><Edit /></el-icon>
            <span>编辑资料</span>
          </el-button>
        </div>
      </section>

      <!-- 个人资料卡片（v68 加 glass-card class） -->
      <el-card class="settings-card glass glass-lg" id="profile-card">
        <template #header>
          <div class="card-header">
            <el-icon><User /></el-icon>
            <span>个人资料</span>
          </div>
        </template>

        <div class="avatar-section">
          <el-avatar :size="80" :key="previewAvatarUrl" :src="previewAvatarUrl || userStore.userInfo?.avatar" :alt="`${userStore.userInfo?.name || '用户'}的头像`" icon="UserFilled" class="settings-avatar" />
          <label class="avatar-upload-btn">
            <input
              id="settings-avatar-upload"
              name="settings-avatar-upload"
              type="file"
              accept="image/*"
              aria-label="更换头像"
              title="更换头像"
              hidden
              @change="handleAvatarUpload"
            />
            <el-icon><Camera /></el-icon>
            <span>更换头像</span>
          </label>
        </div>

        <el-form :model="form" label-width="80px" class="settings-form">
          <el-form-item label="姓名">
            <el-input v-model="form.name" name="form-name" placeholder="请输入姓名" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" name="form-email" placeholder="请输入邮箱" />
          </el-form-item>
          <el-form-item label="电话">
            <el-input v-model="form.phone" name="form-phone" placeholder="请输入手机号" />
          </el-form-item>
          <el-form-item label="个人简介">
            <el-input v-model="form.bio" name="form-bio" type="textarea" :rows="3" placeholder="介绍一下自己" />
          </el-form-item>

          <!-- 只读信息 -->
          <el-divider />
          <el-form-item label="角色">
            <el-tag :type="roleTagType">{{ form.roleLabel }}</el-tag>
          </el-form-item>
          <el-form-item label="年级">
            <span class="readonly-text">{{ form.grade || '未填写' }}</span>
          </el-form-item>
          <el-form-item label="研究方向">
            <span class="readonly-text">{{ form.research_area || '未填写' }}</span>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="savingProfile" @click="saveProfile">保存资料</el-button>
            <el-button @click="resetProfile">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 修改密码卡片（v68 改名为"账号安全" + glass-card） -->
      <el-card class="settings-card glass glass-lg">
        <template #header>
          <div class="card-header">
            <el-icon><Lock /></el-icon>
            <span>账号安全</span>
          </div>
        </template>

        <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="80px">
          <el-form-item label="旧密码" prop="old_password">
            <el-input v-model="passwordForm.old_password" name="passwordForm-old_password" type="password" show-password placeholder="请输入旧密码" />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input v-model="passwordForm.new_password" name="passwordForm-new_password" type="password" show-password placeholder="请输入新密码" />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm_password">
            <el-input v-model="passwordForm.confirm_password" name="passwordForm-confirm_password" type="password" show-password placeholder="请再次输入新密码" />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="savingPassword" @click="changePassword">修改密码</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 通知偏好卡片（v68 加 glass-card） -->
      <el-card class="settings-card glass glass-lg" v-loading="prefsLoading">
        <template #header>
          <div class="card-header">
            <el-icon><Bell /></el-icon>
            <span>通知偏好</span>
          </div>
        </template>

        <el-form :model="prefsForm" label-width="100px">
          <el-form-item label="启用提醒">
            <el-switch
              v-model="prefsForm.enabled"
              name="prefs-enabled"
              active-text="启用"
              inactive-text="关闭"
            />
            <div class="form-help">关闭后将不再推送任何微信提醒</div>
          </el-form-item>

          <el-form-item label="每日提醒时间">
            <el-time-picker
              v-model="prefsForm.digestTimeObj"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="选择时间（北京时间）"
              :disabled="!prefsForm.enabled"
              name="prefs-digest-time"
              aria-label="每日提醒时间"
              title="每日提醒时间"
              @change="onDigestTimeChange"
            />
            <div class="form-help">
              每日 {{ prefsForm.digest_time || '11:00' }} (北京时间) 统一推送待办提醒
            </div>
          </el-form-item>

          <el-form-item label="当前状态">
            <el-tag v-if="prefs?.in_digest_window" type="success">正处于提醒窗口内</el-tag>
            <el-tag v-else type="info">
              下次推送：{{ formatDateTime(prefs?.next_digest_at) }}
            </el-tag>
          </el-form-item>

          <el-form-item v-if="prefs?.snoozed_until" label="已推迟">
            <el-alert
              :title="`已推迟到 ${formatDateTime(prefs.snoozed_until)}`"
              type="warning"
              :closable="false"
              show-icon
            >
              <template #default>
                <el-button size="small" @click="onUnsnooze">立即解除</el-button>
              </template>
            </el-alert>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              :loading="prefsSaving"
              @click="onSavePrefs"
            >
              保存
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- v68 (2026-06-26) 外观主题卡片（新） -->
      <el-card class="settings-card glass glass-lg theme-card">
        <template #header>
          <div class="card-header">
            <el-icon><Brush /></el-icon>
            <span>外观主题</span>
          </div>
        </template>

        <el-form label-width="100px">
          <el-form-item label="深色模式">
            <el-switch
              v-model="isDark"
              active-text="深色"
              inactive-text="浅色"
              name="prefs-dark-mode"
              aria-label="深色模式"
              title="深色模式"
            />
            <div class="form-help">
              当前主题：<strong>{{ themeModeLabel }}</strong> · 也可在顶栏右侧 ☀️/🌙 快速切换
            </div>
          </el-form-item>

          <el-form-item label="主题色">
            <div class="theme-swatches" role="radiogroup" aria-label="主题色">
              <button
                v-for="opt in accentOptions"
                :key="opt.value"
                type="button"
                role="radio"
                :aria-checked="themeStore.accent === opt.value"
                :aria-label="opt.label"
                :title="opt.label"
                class="theme-swatch"
                :class="[opt.previewClass, { 'is-active': themeStore.accent === opt.value }]"
                @click="themeStore.setAccent(opt.value)"
              >
                <el-icon v-if="themeStore.accent === opt.value" class="theme-swatch-check"><Check /></el-icon>
                <span class="theme-swatch-name">{{ opt.label }}</span>
              </button>
            </div>
            <div class="form-help">
              当前主色：<strong>{{ activeAccentLabel }}</strong> · 支持 6 种组合（3 主色 × 明暗）
            </div>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { User, Lock, Camera, Bell, Edit, Brush, Check } from '@element-plus/icons-vue'
// v68 (2026-06-26): 主题切换接入 useThemeStore（之前桌面 SettingsView 没有主题入口）
import { useThemeStore } from '@/stores/useThemeStore'
import { useUserStore } from '@/stores/user'
import { useNotificationPrefs } from '@/composables/useNotificationPrefs'

const userStore = useUserStore()
const themeStore = useThemeStore()
const userInfo = computed(() => userStore.userInfo)

// v68: 主题切换（双向绑定到 el-switch）
const isDark = computed({
  get: () => themeStore.isDark,
  set: (v) => themeStore.set(v ? 'dark' : 'light'),
})
const themeModeLabel = computed(() => (isDark.value ? '深色' : '浅色'))
// 主题色占位（未来扩展，预留 UI）
// v69 P1: 3 套主色 picker，调用 themeStore.setAccent 切换
// v77 P2.6-E.1: 收敛 preview → previewClass（_runtime-style-tokens.scss .theme-preview--*）
const accentOptions = [
  { value: 'orange', label: '活力橙', previewClass: 'theme-preview--orange' },
  { value: 'ocean',  label: '海蓝',   previewClass: 'theme-preview--ocean' },
  { value: 'forest', label: '森林绿', previewClass: 'theme-preview--forest' },
]
const activeAccentLabel = computed(
  () => accentOptions.find((o) => o.value === themeStore.accent)?.label || '活力橙'
)

// v68: Hero "编辑资料" 按钮 → 平滑滚动到下方 profile-card
function scrollToProfile() {
  document.getElementById('profile-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const roleMap = { admin: '管理员', leader: '组长', member: '成员' }
const roleTagMap = { admin: 'danger', leader: 'warning', member: '' }

const roleLabel = computed(() => roleMap[userInfo.value?.role] || '成员')
const roleTagType = computed(() => roleTagMap[userInfo.value?.role] || '')

const savingProfile = ref(false)
const savingPassword = ref(false)
const passwordFormRef = ref(null)
const avatarChanged = ref(false)
const avatarObjectName = ref('')
const previewAvatarUrl = ref(userInfo.value?.avatar || '')

// 当 MainLayout.onMounted 的 GET /auth/me 异步返回时，同步所有表单字段
watch(() => userStore.userInfo, (newInfo) => {
  if (!newInfo) return
  if (newInfo.avatar) {
    previewAvatarUrl.value = newInfo.avatar
    form.avatar = newInfo.avatar
  }
  form.name = newInfo.name || ''
  form.email = newInfo.email || ''
  form.phone = newInfo.phone || ''
  form.bio = newInfo.bio || ''
  form.grade = newInfo.grade || ''
  form.research_area = newInfo.research_area || ''
  form.roleLabel = roleMap[newInfo.role] || '成员'
})

const initForm = () => ({
  name: userInfo.value?.name || '',
  email: userInfo.value?.email || '',
  phone: userInfo.value?.phone || '',
  bio: userInfo.value?.bio || '',
  avatar: userInfo.value?.avatar || '',
  grade: userInfo.value?.grade || '',
  research_area: userInfo.value?.research_area || '',
  roleLabel: roleLabel.value
})

const form = reactive(initForm())

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const validateConfirmPassword = (_rule, value, callback) => {
  if (value !== passwordForm.new_password) {
    callback(new Error('两次输入的新密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

// 上传前压缩大图片（手机端网络不稳定，小文件成功率更高）
const compressImage = (file, maxWidth = 1024, quality = 0.8) => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      if (width > maxWidth) {
        height = Math.round((maxWidth / width) * height)
        width = maxWidth
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, width, height)
      canvas.toBlob((blob) => {
        if (!blob) return reject(new Error('图片压缩失败'))
        const name = file.name.replace(/\.[^.]+$/, '') || 'avatar'
        resolve(new File([blob], `${name}.jpg`, { type: 'image/jpeg' }))
      }, 'image/jpeg', quality)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片加载失败'))
    }
    img.src = url
  })
}

const handleAvatarUpload = async (e) => {
  const file = e.target.files[0]
  if (!file) return

  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 50MB')
    return
  }

  // 文件 >= 1MB 时先压缩再上传；HEIC 等不受支持的格式跳过压缩
  let uploadFile = file
  if (file.size >= 1024 * 1024) {
    try {
      uploadFile = await compressImage(file)
    } catch {
      // HEIC/WebP 等 Canvas 不支持的格式直接用原文件
    }
  }

  let objectName
  try {
    // 1. 上传文件到 MinIO
    const formData = new FormData()
    formData.append('file', uploadFile)
    formData.append('prefix', 'avatars')

    const res = await axios.post('/api/v1/upload', formData, {
      timeout: 60000
    })
    if (!res.data?.object_name) {
      ElMessage.error('上传返回数据异常')
      return
    }
    objectName = res.data.object_name

    // 2. 立即保存到后端（自动持久化）
    await axios.put('/api/v1/auth/profile', { avatar: objectName })
  } catch (err) {
    const detail = err.response?.data?.detail || err.message
    console.error('[头像上传失败]', { detail })
    ElMessage.error(`头像上传失败: ${detail}`)
    return
  }

  // 3. 获取完整 URL（容错：失败时用本地构建的兜底）
  let resolvedUrl
  try {
    const meRes = await axios.get('/api/v1/auth/me')
    resolvedUrl = meRes.data?.avatar
  } catch {
    // GET 失败不影响保存结果
  }
  resolvedUrl = resolvedUrl || `${window.location.origin}/minio/microbubble/${objectName}`

  // 4. 无论如何都更新 localStorage（防止刷新后回退）
  const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
  stored.avatar = resolvedUrl
  localStorage.setItem('user_info', JSON.stringify(stored))

  // 5. 刷新 store
  userStore.loadFromStorage()

  // 6. 更新预览
  form.avatar = resolvedUrl
  previewAvatarUrl.value = resolvedUrl
  avatarObjectName.value = objectName
  avatarChanged.value = false

  ElMessage.success('头像已更新')
}

const saveProfile = async () => {
  savingProfile.value = true
  try {
    const payload = {
      name: form.name,
      email: form.email || undefined,
      phone: form.phone || undefined,
      bio: form.bio || undefined
    }
    // 只在用户新上传头像时发送 object_name，避免覆盖已存储的 object_name
    if (avatarChanged.value) {
      payload.avatar = avatarObjectName.value || undefined
    }

    const res = await axios.put('/api/v1/auth/profile', payload)
    const updated = res.data

    // 更新 localStorage
    const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
    Object.assign(stored, {
      name: updated.name,
      email: updated.email,
      phone: updated.phone,
      bio: updated.bio,
      avatar: updated.avatar
    })
    localStorage.setItem('user_info', JSON.stringify(stored))

    // 刷新 userStore
    userStore.loadFromStorage()

    // 更新预览中的头像为后端解析后的完整 URL
    form.avatar = updated.avatar || form.avatar
    previewAvatarUrl.value = updated.avatar || previewAvatarUrl.value
    avatarChanged.value = false

    ElMessage.success('个人资料已保存')
  } catch (err) {
    const msg = err.response?.data?.detail || '保存失败'
    ElMessage.error(msg)
  } finally {
    savingProfile.value = false
  }
}

const resetProfile = () => {
  Object.assign(form, initForm())
  previewAvatarUrl.value = userInfo.value?.avatar || ''
}

const changePassword = async () => {
  if (!passwordFormRef.value) return
  try {
    await passwordFormRef.value.validate()
  } catch {
    return
  }

  savingPassword.value = true
  try {
    await axios.post('/api/v1/auth/change-password', {
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password
    })

    ElMessage.success('密码修改成功')
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
  } catch (err) {
    const msg = err.response?.data?.detail || '密码修改失败'
    ElMessage.error(msg)
  } finally {
    savingPassword.value = false
  }
}

// === 2026-06-15 v2 通知偏好（11AM 单一窗口）===
const { prefs, loading: prefsLoading, fetchPrefs, savePrefs, unsnooze } = useNotificationPrefs()
const prefsSaving = ref(false)
const prefsForm = reactive({
  enabled: true,
  digest_time: '11:00',
  digestTimeObj: '11:00',
})

onMounted(async () => {
  await fetchPrefs()
  if (prefs.value) {
    prefsForm.enabled = prefs.value.enabled
    prefsForm.digest_time = prefs.value.digest_time
    prefsForm.digestTimeObj = prefs.value.digest_time
  }
})

function onDigestTimeChange(val) {
  if (typeof val === 'string' && /^\d{2}:\d{2}$/.test(val)) {
    prefsForm.digest_time = val
  } else if (val instanceof Date) {
    const hh = String(val.getHours()).padStart(2, '0')
    const mm = String(val.getMinutes()).padStart(2, '0')
    prefsForm.digest_time = `${hh}:${mm}`
  }
}

async function onSavePrefs() {
  prefsSaving.value = true
  try {
    await savePrefs({
      enabled: prefsForm.enabled,
      digest_time: prefsForm.digest_time,
    })
  } catch (e) {
    // 错误已由 composable 内部 ElMessage 处理
  } finally {
    prefsSaving.value = false
  }
}

async function onUnsnooze() {
  prefsSaving.value = true
  try {
    await unsnooze()
    ElMessage.success('已解除推迟')
  } finally {
    prefsSaving.value = false
  }
}

function formatDateTime(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}
</script>

<style scoped>
/* ============================================================
   v68 (2026-06-26) SettingsView 全面视觉升级
   - 玻璃态卡片（backdrop-filter blur + 半透明白色）
   - 顶部 Hero 渐变卡（avatar + 姓名 + 角色 + 邮箱 + 编辑）
   - 卡片 hover translateY(-2px) 浮起
   - Dark mode 用 :global([data-theme="dark"]) 避开 scoped [data-theme] specificity 坑
   - 参考 MainLayout.vue:317-320 (.aside 玻璃) + MobileHeader.vue:60-69 (dark glass)
     + Dashboard.vue:782-790 (渐变 hero) 范式统一
   ============================================================ */
.settings-view {
  padding: 28px;
  max-width: 1080px;
  margin: 0 auto;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

/* ===== Hero 卡片（全宽渐变） ===== */
.hero-card {
  grid-column: 1 / -1;
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  min-height: 140px;
}
.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.4) 0%, transparent 50%),
    var(--gradient-welcome-hero);
}
.hero-content {
  position: relative;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 24px 28px;
  color: var(--color-bg-card);
}
.hero-avatar {
  border: 4px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.2);  /* fallback when avatar missing */
}
.hero-info {
  flex: 1;
  min-width: 0;
}
.hero-name {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-bg-card);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
.hero-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.hero-email {
  font-size: 13px;
  opacity: 0.92;
  color: var(--color-bg-card);
}
.hero-edit-btn {
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.5);
  color: var(--color-bg-card);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.hero-edit-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  border-color: rgba(255, 255, 255, 0.8);
  color: var(--color-bg-card);
}
.hero-card :deep(.el-tag) {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.4);
  color: var(--color-bg-card);
}

/* ===== 玻璃态卡片 ===== */
/* v77 P2.5: backdrop-filter / 半透 background / border 由 .glass 工具类提供 (assets/glass.css)
   保留 hover 上浮 + EP 子组件穿透（:deep） */
.settings-card.glass {
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  transition: transform 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
}
.settings-card.glass:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.14);
}
.settings-card.glass :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: transparent;
}
.settings-card.glass :deep(.el-card__body) {
  background: transparent;
}

.settings-card {
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
}

.settings-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary);
}

.avatar-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.settings-avatar {
  border: 3px solid var(--color-primary-bg);
  box-shadow: var(--shadow-primary);
}

.avatar-upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--color-primary);
  cursor: pointer;
  padding: 4px 12px;
  border: 1px dashed var(--color-primary);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast);
}

.avatar-upload-btn:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
}

.settings-form {
  padding: 0 8px;
}

.readonly-text {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

/* ===== 主题卡片特有样式 ===== */
.theme-card :deep(.el-form-item__content) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

/* v69 P1: 主题色 swatches（3 个色块，active 有白圈+Check） */
.theme-swatches {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.theme-swatch {
  position: relative;
  width: 84px;
  height: 64px;
  border-radius: var(--radius-lg);
  border: 2px solid transparent;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-bg-card);
  font-size: 12px;
  font-weight: 600;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
  box-shadow: var(--shadow-sm);
  transition: transform var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
  outline: none;
  padding: 0;
}
.theme-swatch:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.theme-swatch:focus-visible {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-bg);
}
.theme-swatch.is-active {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
}
.theme-swatch-check {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(255, 255, 255, 0.95);
  color: var(--color-primary);
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}
.theme-swatch-name {
  position: relative;
  z-index: 1;
}

.form-help {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

/* Dark mode 规则移到非 scoped 块（见下方 \3c style> 块）—
   v68 首次部署尝试 :global([data-theme="dark"]) .glass-card 在 scoped 块里，
   Vue 编译器把 :global() + 后代选择器处理错：编译产物变成
   [data-theme=dark]{...} 单独的规则，剥掉了 .glass-card，作用到 <html> 而不是卡片
   （与 sw.js v61 教训同款）。 */

@media (max-width: 768px) {
  .settings-view {
    padding: 12px;
  }

  .settings-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .settings-form :deep(.el-form-item__label) {
    width: 64px !important;
  }

  .hero-card {
    min-height: auto;
  }

  .hero-content {
    padding: 16px;
    gap: 12px;
    flex-wrap: wrap;
  }

  .hero-name {
    font-size: 18px;
  }

  .hero-edit-btn {
    margin-left: auto;
  }
}
</style>

<!-- v68 dark mode 规则必须放非 scoped 块（继承 sw.js v61/v62 教训）：
     scoped 块里 :global([data-theme="dark"]) .xxx 的 :global() + 后代选择器组合
     会被 Vue 编译器处理错（剥掉后代选择器、产物变成 [data-theme=dark]{...} 单独规则
     作用到 <html> 而不是目标元素）。非 scoped 块彻底绕过 Vue scoped 编译。 -->
<style>
/* v77 P2.5: .glass 工具类自带 dark mode 适配, 无需手动覆盖 */
[data-theme="dark"] .hero-bg {
  background:
    radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
    var(--gradient-welcome-hero);
}
[data-theme="dark"] .hero-edit-btn {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.3);
  color: var(--color-bg-card);
}
[data-theme="dark"] .hero-edit-btn:hover {
  background: rgba(255, 255, 255, 0.22);
  border-color: rgba(255, 255, 255, 0.6);
}
/* v69 P1: theme-swatch dark 模式强调边框（用高亮白边框 + 阴影增强 active 感） */
[data-theme="dark"] .theme-swatch.is-active {
  border-color: rgba(255, 255, 255, 0.95);
  box-shadow: 0 4px 20px rgba(255, 255, 255, 0.18), var(--shadow-primary);
}
</style>
