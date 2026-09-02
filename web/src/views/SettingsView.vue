<template>
  <div class="settings-dossier">
    <div class="sheet">
      <header class="dossier-head">
        <b>微纳米气泡课题组 · 科研工作台</b>
        <span>MEMBER FILE N°07 · OPENED 2026-09</span>
      </header>
      <h1 class="dossier-title">个人设置</h1>
      <p class="dossier-sub">PERSONAL RECORD — 3 SECTIONS · KEEP THIS FILE UP TO DATE</p>

      <div class="cols">
        <!-- 左: 标本标签式档案卡 -->
        <aside class="specimen">
          <div class="specimen-card">
            <div class="avatar-wrap">
              <span class="avatar-ring" aria-hidden="true"></span>
              <div class="avatar">
                <img v-if="previewAvatarUrl" :src="previewAvatarUrl" alt="头像" class="avatar-img">
                <span v-else>{{ (form.name || '杜').charAt(0) }}</span>
              </div>
            </div>
            <div class="specimen-name">{{ form.name || '未设置姓名' }}</div>
            <div class="specimen-tags">
              <span :class="{ admin: userInfo?.role === 'admin' }">{{ roleLabel }}</span>
              <span v-if="form.grade">{{ form.grade }}</span>
            </div>
            <dl class="meta-list">
              <div><dt>研究方向</dt><dd>{{ form.research_area || '未填写' }}</dd></div>
              <div><dt>EMAIL</dt><dd>{{ form.email || '未填写' }}</dd></div>
              <div><dt>电话</dt><dd>{{ form.phone || '未填写' }}</dd></div>
            </dl>
            <label class="avatar-btn" for="settings-avatar-upload">⇪ 更换头像 (JPG/PNG ≤ 50MB)</label>
            <input
              id="settings-avatar-upload"
              name="settings-avatar-upload"
              type="file"
              accept="image/*"
              aria-label="更换头像"
              title="更换头像"
              hidden
              @change="handleAvatarUpload"
            >
          </div>
        </aside>

        <!-- 右: 三个章节 -->
        <main>
          <!-- §1 个人资料 -->
          <section class="section">
            <div class="sec-head">
              <span class="sec-no">§1</span><h2>个人资料</h2><span class="en">PROFILE</span>
            </div>
            <div class="field-grid">
              <div class="field"><label>姓名 <i>NAME</i></label><el-input v-model="form.name" name="form-name" placeholder="请输入姓名"></el-input></div>
              <div class="field"><label>邮箱 <i>EMAIL</i></label><el-input v-model="form.email" name="form-email" placeholder="请输入邮箱"></el-input></div>
              <div class="field"><label>电话 <i>PHONE</i></label><el-input v-model="form.phone" name="form-phone" placeholder="请输入手机号"></el-input></div>
              <div class="field"><label>研究方向 <i>FIELD</i></label><el-input v-model="form.research_area" name="form-research-area" placeholder="请输入研究方向"></el-input></div>
              <div class="field full"><label>个人简介 <i>BIO</i></label><el-input v-model="form.bio" name="form-bio" type="textarea" :rows="3" placeholder="介绍一下自己"></el-input></div>
            </div>
            <div class="btn-row">
              <button type="button" class="btn btn-ink" :disabled="savingProfile" @click="saveProfile">
                {{ savingProfile ? '保存中…' : '保存资料' }}
              </button>
              <button type="button" class="btn btn-ghost" @click="resetProfile">重置</button>
            </div>
          </section>

          <!-- §2 账号安全 -->
          <section class="section">
            <div class="sec-head">
              <span class="sec-no">§2</span><h2>账号安全</h2><span class="en">SECURITY</span>
            </div>
            <el-form
              ref="passwordFormRef"
              :model="passwordForm"
              :rules="passwordRules"
              label-position="top"
              class="dossier-form"
              @keyup.enter="changePassword"
            >
              <div class="field-grid">
                <el-form-item prop="old_password">
                  <template #label><span class="f-label">旧密码 <i>OLD</i></span></template>
                  <el-input v-model="passwordForm.old_password" name="passwordForm-old_password" type="password" show-password placeholder="请输入旧密码"></el-input>
                </el-form-item>
                <el-form-item prop="new_password">
                  <template #label><span class="f-label">新密码 <i>NEW</i></span></template>
                  <el-input v-model="passwordForm.new_password" name="passwordForm-new_password" type="password" show-password placeholder="至少 6 位"></el-input>
                </el-form-item>
                <el-form-item prop="confirm_password">
                  <template #label><span class="f-label">确认新密码 <i>CONFIRM</i></span></template>
                  <el-input v-model="passwordForm.confirm_password" name="passwordForm-confirm_password" type="password" show-password placeholder="再次输入新密码"></el-input>
                </el-form-item>
              </div>
            </el-form>
            <div class="btn-row">
              <button type="button" class="btn btn-ink" :disabled="savingPassword" @click="changePassword">
                {{ savingPassword ? '修改中…' : '修改密码' }}
              </button>
            </div>

            <div class="recover">
              <div class="recover-info">
                <h3>
                  密码恢复码
                  <span class="st" :class="{ 'is-ok': recoveryHasCode }">
                    {{ recoveryHasCode ? '已生成' : '未生成' }}
                  </span>
                </h3>
                <p>
                  忘记密码时，在登录页输入「用户名 + 恢复码 + 新密码」即可自助重置，无需联系管理员。
                  恢复码只在生成时显示一次，请立即保存到个人微信收藏；重置成功后即失效，需重新生成。
                </p>
              </div>
              <button type="button" class="btn btn-ghost recover-btn" :disabled="generatingCode" @click="onGenerateRecoveryCode">
                {{ generatingCode ? '生成中…' : (recoveryHasCode ? '重新生成' : '生成恢复码') }}
              </button>
            </div>
          </section>

          <!-- §3 外观主题 -->
          <section class="section" style="margin-bottom: 0;">
            <div class="sec-head">
              <span class="sec-no">§3</span><h2>外观主题</h2><span class="en">APPEARANCE</span>
            </div>
            <div class="lever-row">
              <span class="lever-name">深色模式</span>
              <span class="lever-desc">当前：{{ themeModeLabel }} · 也可在顶栏右侧 ☀️ / 🌙 快速切换</span>
              <el-switch v-model="isDark" class="dossier-switch" aria-label="深色模式"></el-switch>
            </div>
            <div class="lever-row">
              <span class="lever-name">主题色</span>
              <span class="lever-desc">当前主色：{{ activeAccentLabel }}</span>
              <span></span>
            </div>
            <div class="theme-row">
              <button
                v-for="opt in accentOptions"
                :key="opt.value"
                type="button"
                class="swatch"
                :class="{ 'is-on': themeStore.accent === opt.value }"
                :aria-pressed="themeStore.accent === opt.value"
                :aria-label="opt.label"
                @click="themeStore.setAccent(opt.value)"
              >
                <span class="dot" :class="opt.previewClass"></span>
                <b>{{ opt.label }}</b>
                <small>{{ opt.value.toUpperCase() }}</small>
              </button>
            </div>
          </section>
        </main>
      </div>
    </div>

    <!-- 密码恢复码对话框 — 明文仅显示一次 -->
    <el-dialog
      v-model="recoveryDialogVisible"
      title="这是你的密码恢复码"
      width="440px"
      :close-on-click-modal="false"
      class="recovery-dialog"
    >
      <div class="recovery-dialog-body">
        <p class="recovery-warn">
          恢复码只显示这一次。请立即复制或截图，保存到个人微信收藏等安全位置；
          关闭本窗口后将无法再次查看。
        </p>
        <div class="recovery-code-row">
          <code class="recovery-code">{{ recoveryCode }}</code>
          <el-button size="small" type="primary" plain @click="copyRecoveryCode">复制</el-button>
        </div>
        <p class="recovery-hint">
          使用方法：登录页点击「忘记密码？」→ 输入用户名 + 本恢复码 + 新密码，即可自助重置。
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="recoveryDialogVisible = false">我已保存好</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
// v68 (2026-06-26): 主题切换接入 useThemeStore（之前桌面 SettingsView 没有主题入口）
import { useThemeStore } from '@/stores/useThemeStore'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const themeStore = useThemeStore()
const userInfo = computed(() => userStore.userInfo)

// v68: 主题切换（双向绑定到 el-switch）
const isDark = computed({
  get: () => themeStore.isDark,
  set: (v) => themeStore.set(v ? 'dark' : 'light'),
})
const themeModeLabel = computed(() => (isDark.value ? '深色' : '浅色'))
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

const roleMap = { admin: '管理员', leader: '组长', member: '成员' }
const roleLabel = computed(() => roleMap[userInfo.value?.role] || '成员')

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
})

const initForm = () => ({
  name: userInfo.value?.name || '',
  email: userInfo.value?.email || '',
  phone: userInfo.value?.phone || '',
  bio: userInfo.value?.bio || '',
  avatar: userInfo.value?.avatar || '',
  grade: userInfo.value?.grade || '',
  research_area: userInfo.value?.research_area || ''
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

// === 密码恢复码 (2026-09-02): 生成/轮换 + 一次性展示 ===
const recoveryHasCode = ref(false)
const recoveryGeneratedAt = ref('')
const generatingCode = ref(false)
const recoveryDialogVisible = ref(false)
const recoveryCode = ref('')

const fetchRecoveryStatus = async () => {
  try {
    const resp = await axios.get('/api/v1/auth/recovery-code/status')
    recoveryHasCode.value = resp.data.has_code
    recoveryGeneratedAt.value = resp.data.generated_at || ''
  } catch (err) {
    console.warn('[recovery] status fetch failed:', err)
  }
}

const copyRecoveryCode = async () => {
  try {
    await navigator.clipboard.writeText(recoveryCode.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选中复制')
  }
}

const onGenerateRecoveryCode = async () => {
  if (recoveryHasCode.value) {
    try {
      await ElMessageBox.confirm(
        '重新生成会使旧恢复码立即失效。如果你的其他设备/记录里存的是旧码，将无法再用于重置。确定重新生成？',
        '重新生成恢复码',
        { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning', customClass: 'dossier-messagebox' }
      )
    } catch {
      return
    }
  }

  generatingCode.value = true
  try {
    const resp = await axios.post('/api/v1/auth/recovery-code')
    recoveryCode.value = resp.data.code
    recoveryDialogVisible.value = true
    recoveryHasCode.value = true
    recoveryGeneratedAt.value = new Date().toISOString()
  } catch (err) {
    const msg = err.response?.data?.error?.message || err.response?.data?.detail || '生成失败，请重试'
    ElMessage.error(msg)
  } finally {
    generatingCode.value = false
  }
}

onMounted(() => {
  fetchRecoveryStatus()
})
</script>

<style scoped>
/* ═══ A · 研究档案 DOSSIER — 与登录页 D「剖面海报」同产品家族 (2026-09) ═══ */
.settings-dossier {
  --paper: #f4f6f4;
  --card: #fdfefc;
  --ink: #16232a;
  --teal: #0e766e;
  --teal-soft: #198e83;
  --coral: #ef7256;
  --line: #cdd8d4;
  --line-dash: #b9c9c5;
  --muted: #5f6f6b;
  --shadow-ink: rgba(22, 35, 42, 0.12);
  --font-serif: 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
  --font-mono: Consolas, 'SFMono-Regular', 'Courier New', monospace;

  min-height: 100%;
  background: var(--paper);
  color: var(--ink);
  font-size: 14px;
  line-height: 1.6;
}

/* 深色主题: 同一设计语言换墨盘 (对应 D-deck 配色) */
[data-theme="dark"] .settings-dossier {
  --paper: #12191d;
  --card: #172126;
  --ink: #e2ecea;
  --teal: #35c2a4;
  --teal-soft: #4ad0b4;
  --coral: #ff8a6b;
  --line: #263740;
  --line-dash: #31454f;
  --muted: #8ba4a0;
  --shadow-ink: rgba(0, 0, 0, 0.45);
}

.sheet { max-width: 1120px; margin: 0 auto; padding: 40px clamp(20px, 4vw, 56px) 96px; }

/* ── 卷宗头 ─────────────────────────────── */
.dossier-head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em; color: var(--muted);
  border-bottom: 1.5px solid var(--ink); padding-bottom: 14px;
}
.dossier-head b { font-family: var(--font-serif); font-size: 15px; letter-spacing: 0.06em; color: var(--ink); }
.dossier-title {
  font-family: var(--font-serif);
  font-size: clamp(30px, 3.2vw, 40px); font-weight: 900;
  letter-spacing: 0.02em; margin: 28px 0 6px;
}
.dossier-sub { font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.14em; color: var(--teal); }

/* ── 主体双栏 ────────────────────────────── */
.cols { display: grid; grid-template-columns: 300px 1fr; gap: clamp(28px, 4vw, 56px); margin-top: 36px; }

/* 左: 标本标签式档案卡 */
.specimen { position: sticky; top: 24px; align-self: start; }
.specimen-card {
  background: var(--card);
  border: 1px solid var(--ink);
  box-shadow: 4px 4px 0 var(--shadow-ink);
  padding: 26px 24px 22px;
  position: relative;
}
.specimen-card::before {
  content: 'MEMBER SPECIMEN';
  position: absolute; top: -9px; left: 20px;
  background: var(--paper); padding: 0 8px;
  font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.28em; color: var(--muted);
}
.avatar-wrap { display: grid; place-items: center; margin-bottom: 16px; position: relative; }
.avatar {
  width: 108px; height: 108px; border-radius: 50%;
  background: radial-gradient(circle at 32% 28%, var(--card), #dbe8e4 60%, #b9d3cc);
  border: 1.5px solid rgba(14, 118, 110, 0.45);
  display: grid; place-items: center;
  font-size: 34px; color: var(--teal); font-family: var(--font-serif);
  overflow: hidden;
}
[data-theme="dark"] .avatar { background: radial-gradient(circle at 32% 28%, #1c2a31, #1f3038 60%, #274049); }
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.avatar-ring {
  position: absolute; width: 128px; height: 128px; border-radius: 50%;
  border: 1px dashed var(--line-dash);
}
.specimen-name { font-family: var(--font-serif); font-size: 24px; font-weight: 900; text-align: center; }
.specimen-tags {
  display: flex; justify-content: center; gap: 8px; margin-top: 8px; flex-wrap: wrap;
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.12em;
}
.specimen-tags span { border: 1px solid var(--teal); color: var(--teal); padding: 2px 8px; border-radius: 999px; }
.specimen-tags span.admin { border-color: var(--coral); color: var(--coral); }

.meta-list { margin-top: 18px; border-top: 1px dashed var(--line-dash); padding-top: 6px; }
.meta-list div {
  display: flex; justify-content: space-between; gap: 12px;
  padding: 7px 0; border-bottom: 1px dashed var(--line-dash);
  font-size: 12.5px;
}
.meta-list dt { font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.1em; color: var(--muted); }
.meta-list dd { color: var(--ink); text-align: right; word-break: break-all; }

.avatar-btn {
  display: block; width: 100%; margin-top: 16px;
  border: 1px dashed var(--line-dash); border-radius: 8px;
  padding: 8px; font: inherit; font-size: 12px; color: var(--muted);
  cursor: pointer; text-align: center;
  transition: border-color 150ms ease, color 150ms ease;
}
.avatar-btn:hover { border-color: var(--teal); color: var(--teal); }

/* ── 章节 ───────────────────────────────── */
.section { margin-bottom: 48px; }
.sec-head {
  display: flex; align-items: baseline; gap: 14px;
  border-bottom: 1px solid var(--line); padding-bottom: 10px;
}
.sec-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.2em; color: var(--coral); }
.sec-head h2 { font-family: var(--font-serif); font-size: 21px; font-weight: 900; letter-spacing: 0.03em; margin: 0; }
.sec-head .en { margin-left: auto; font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.22em; color: var(--muted); }

/* 表单区: 双列下划线字段 */
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; margin-top: 20px; }
.field { display: flex; flex-direction: column; }
.field.full { grid-column: 1 / -1; }
.field > label {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12px; font-weight: 700; letter-spacing: 0.06em; margin-bottom: 2px;
}
.field > label i {
  font-style: normal; font-family: var(--font-mono);
  font-weight: 400; font-size: 9.5px; letter-spacing: 0.16em; color: var(--muted);
}
/* el-input 重塑为下划线输入框 (与登录页同款) */
.section :deep(.el-input__wrapper),
.field :deep(.el-input__wrapper) {
  background: transparent;
  box-shadow: none;
  border-radius: 0;
  border-bottom: 1.5px solid var(--ink);
  padding: 0 2px;
  transition: border-color 150ms ease;
}
.section :deep(.el-input__wrapper:hover),
.field :deep(.el-input__wrapper:hover) { box-shadow: none; }
.section :deep(.el-input__wrapper.is-focus),
.field :deep(.el-input__wrapper.is-focus) { box-shadow: none; border-bottom-color: var(--teal-soft); }
.section :deep(.el-input__inner),
.field :deep(.el-input__inner) {
  height: 42px; line-height: 42px;
  font-size: 14.5px; color: var(--ink);
  caret-color: var(--teal);
}
.section :deep(.el-textarea__inner),
.field :deep(.el-textarea__inner) {
  background: transparent;
  border: 0; border-bottom: 1.5px solid var(--ink); border-radius: 0;
  box-shadow: none;
  font-size: 14.5px; color: var(--ink); line-height: 1.7;
  padding: 8px 2px;
  transition: border-color 150ms ease;
}
.section :deep(.el-textarea__inner:focus),
.field :deep(.el-textarea__inner:focus) { border-bottom-color: var(--teal-soft); }
.field :deep(.el-input__inner::placeholder),
.field :deep(.el-textarea__inner::placeholder),
.section :deep(.el-input__inner::placeholder) { color: #9fb0ab; }
[data-theme="dark"] .section :deep(.el-input__inner::placeholder),
[data-theme="dark"] .field :deep(.el-input__inner::placeholder),
[data-theme="dark"] .field :deep(.el-textarea__inner::placeholder) { color: #52706b; }
.section :deep(.el-input__suffix) { color: var(--muted); }
.section :deep(.el-form-item.is-error .el-input__wrapper),
.field :deep(.el-form-item.is-error .el-input__wrapper) {
  border-bottom-color: #c45656;
  box-shadow: none;
}
.section :deep(.el-form-item__error) { padding-top: 4px; font-size: 11.5px; }
.section :deep(.el-form-item) { margin-bottom: 0; }
.dossier-form .field-grid { margin-top: 20px; }
.dossier-form .f-label {
  display: flex; justify-content: space-between; align-items: baseline; width: 100%;
  font-size: 12px; font-weight: 700; letter-spacing: 0.06em; color: var(--ink);
}
.dossier-form .f-label i {
  font-style: normal; font-family: var(--font-mono);
  font-weight: 400; font-size: 9.5px; letter-spacing: 0.16em; color: var(--muted);
}
/* Chrome 自动填充白底修正 */
.dossier-form :deep(.el-input__inner:-webkit-autofill),
.field :deep(.el-input__inner:-webkit-autofill) {
  -webkit-box-shadow: 0 0 0 1000px var(--card) inset;
  -webkit-text-fill-color: var(--ink);
  transition: background-color 99999s ease-in-out 0s;
}

/* 按钮: 墨色药丸 / 虚线幽灵 */
.btn-row { display: flex; gap: 12px; margin-top: 24px; }
.btn {
  height: 46px; padding: 0 30px; border-radius: 999px; cursor: pointer;
  font: inherit; font-size: 14px; font-weight: 700; letter-spacing: 0.08em;
  transition: transform 140ms ease, background 140ms ease, box-shadow 140ms ease, color 140ms ease, border-color 140ms ease;
}
.btn:focus-visible { outline: 2px solid var(--teal); outline-offset: 3px; }
.btn:disabled { opacity: 0.6; cursor: default; transform: none !important; box-shadow: none !important; }
.btn-ink { background: var(--ink); color: var(--paper); border: 1.5px solid var(--ink); }
.btn-ink:hover:not(:disabled) {
  background: var(--teal); border-color: var(--teal); color: #fbfcfb;
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(14, 118, 110, 0.26);
}
.btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--line-dash); }
.btn-ghost:hover:not(:disabled) { color: var(--ink); border-color: var(--ink); }

/* 恢复码 */
.recover {
  margin-top: 26px; border: 1px dashed var(--line-dash); border-radius: 12px;
  padding: 18px 20px; display: flex; gap: 20px; align-items: center; justify-content: space-between;
}
.recover-info h3 { font-size: 13.5px; font-weight: 700; display: flex; align-items: center; gap: 10px; margin: 0; }
.recover-info .st {
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.14em;
  color: var(--coral); border: 1px solid var(--coral); border-radius: 999px; padding: 1px 8px;
}
.recover-info .st.is-ok { color: var(--teal); border-color: var(--teal); }
.recover-info p { font-size: 12px; color: var(--muted); margin: 6px 0 0; max-width: 480px; line-height: 1.8; }
.recover-btn { flex: none; height: 42px; padding: 0 22px; font-size: 12.5px; }

/* 外观: 仪表行 + 色板 */
.lever-row {
  display: flex; align-items: center; gap: 16px;
  padding: 15px 2px; border-bottom: 1px dashed var(--line-dash);
}
.lever-row:first-of-type { margin-top: 8px; }
.lever-name { font-size: 13.5px; font-weight: 700; min-width: 96px; }
.lever-desc { font-size: 12px; color: var(--muted); flex: 1; }
.lever-row > span:last-child:not(.lever-desc) { width: 52px; }

/* el-switch 重塑为仪器拨杆 */
.dossier-switch :deep(.el-switch__core) {
  min-width: 52px; height: 26px; border-radius: 999px;
  background: var(--line-dash); border: 1.5px solid var(--ink);
  transition: background 170ms ease, border-color 170ms ease;
}
.dossier-switch.is-checked :deep(.el-switch__core) {
  background: rgba(14, 118, 110, 0.14); border-color: var(--teal);
}
.dossier-switch :deep(.el-switch__action) {
  background: var(--ink); border: none;
  transition: all 180ms cubic-bezier(0.16, 1, 0.3, 1);
}
.dossier-switch.is-checked :deep(.el-switch__action) { background: var(--teal); color: #fff; }

.theme-row { display: flex; gap: 14px; margin-top: 20px; flex-wrap: wrap; }
.swatch {
  width: 132px; border: 1px solid var(--line-dash); border-radius: 12px;
  padding: 14px; cursor: pointer; background: var(--card);
  text-align: left; font: inherit; color: var(--ink);
  transition: border-color 150ms ease, transform 150ms ease, box-shadow 150ms ease;
  position: relative;
}
.swatch:hover { border-color: var(--ink); transform: translateY(-2px); }
.swatch:focus-visible { outline: 2px solid var(--teal); outline-offset: 3px; }
.swatch .dot { display: block; width: 100%; height: 34px; border-radius: 7px; margin-bottom: 10px; }
.swatch b { font-size: 12.5px; }
.swatch small {
  display: block; font-family: var(--font-mono);
  font-size: 9.5px; letter-spacing: 0.12em; color: var(--muted); margin-top: 2px;
}
.swatch.is-on { border: 1.5px solid var(--ink); box-shadow: 3px 3px 0 var(--shadow-ink); }
.swatch.is-on::after {
  content: '✓'; position: absolute; top: 8px; right: 10px;
  color: var(--ink); font-weight: 700;
}

/* ── 恢复码对话框 — 档案语言同款 (标本标签 + 墨线 + 硬阴影) ── */
.settings-dossier :deep(.el-dialog.recovery-dialog) {
  background: var(--card);
  border: 1px solid var(--ink);
  border-radius: 6px;
  box-shadow: 6px 6px 0 var(--shadow-ink);
  position: relative;
}
/* 顶部标本标签 (遮住边框线, 同 .specimen-card::before 手法) */
.settings-dossier :deep(.el-dialog.recovery-dialog)::before {
  content: 'MEMBER FILE · RECOVERY CODE';
  position: absolute; top: -9px; left: 22px;
  background: var(--card); padding: 0 8px;
  font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.28em; color: var(--teal);
}
.settings-dossier :deep(.el-dialog.recovery-dialog .el-dialog__header) {
  padding: 24px 28px 14px;
  margin-right: 0;
}
.settings-dossier :deep(.el-dialog.recovery-dialog .el-dialog__title) {
  font-family: var(--font-serif);
  font-size: 19px; font-weight: 900; letter-spacing: 0.02em; color: var(--ink);
}
.settings-dossier :deep(.el-dialog.recovery-dialog .el-dialog__headerbtn) {
  top: 22px; right: 22px; width: auto; height: auto;
}
.settings-dossier :deep(.el-dialog.recovery-dialog .el-dialog__close) {
  color: var(--muted); font-size: 17px;
  transition: color 150ms ease;
}
.settings-dossier :deep(.el-dialog.recovery-dialog .el-dialog__headerbtn:hover .el-dialog__close) {
  color: var(--ink);
}
.settings-dossier :deep(.el-dialog.recovery-dialog .el-dialog__body) {
  padding: 0 28px 6px;
  color: var(--ink);
}
/* 警示改为珊瑚虚线「印章」框 */
.settings-dossier :deep(.el-dialog.recovery-dialog .recovery-warn) {
  color: var(--coral);
  border: 1px dashed var(--coral);
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 12.5px; line-height: 1.75;
  margin: 0 0 16px;
  opacity: 0.92;
}
/* 恢复码展示条: 墨线 + 硬阴影 */
.settings-dossier :deep(.el-dialog.recovery-dialog .recovery-code-row) {
  display: flex; align-items: center; gap: 12px;
  background: var(--paper);
  border: 1px solid var(--ink);
  border-radius: 6px;
  box-shadow: 3px 3px 0 var(--shadow-ink);
  padding: 16px 18px;
}
.settings-dossier :deep(.el-dialog.recovery-dialog .recovery-code) {
  flex: 1; font-family: var(--font-mono);
  font-size: 22px; font-weight: 700; letter-spacing: 0.12em; color: var(--ink);
  user-select: all;
}
.settings-dossier :deep(.el-dialog.recovery-dialog .recovery-hint) {
  margin: 16px 0 0; font-size: 12.5px; line-height: 1.8; color: var(--muted);
}
/* 弹窗内按钮 (复制 / 我已保存好): 墨线药丸, hover 转 teal
   特异性 0,5,0 压过全局 :root .el-button--primary:not(...) (0,4,0) 的橙色 */
.settings-dossier :deep(.el-dialog.recovery-dialog .el-button--primary) {
  background: transparent;
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  color: var(--ink);
  font-weight: 700;
}
.settings-dossier :deep(.el-dialog.recovery-dialog .el-button--primary:hover:not(.is-disabled)) {
  background: var(--teal);
  border-color: var(--teal);
  color: #fbfcfb;
}
.settings-dossier :deep(.el-dialog.recovery-dialog .el-dialog__footer) {
  padding: 14px 28px 24px;
}


/* ── 响应式 ─────────────────────────────── */
@media (max-width: 900px) {
  .cols { grid-template-columns: 1fr; }
  .specimen { position: static; }
  .field-grid { grid-template-columns: 1fr; }
  .dossier-head { flex-direction: column; gap: 4px; }
  .recover { flex-direction: column; align-items: stretch; }
  .recover-btn { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .btn, .swatch, .avatar-btn { transition: none !important; }
}
</style>

<!-- ElMessageBox 全局确认框 (teleport 到 body, scoped 够不到) — 档案语言同款 -->
<style>
/* 变量自带深色覆盖 — MessageBox 在 body 下, 复用 data-theme 属性选择器 */
.el-message-box.dossier-messagebox {
  --dp-paper: #f4f6f4; --dp-card: #fdfefc; --dp-ink: #16232a;
  --dp-teal: #0e766e; --dp-coral: #ef7256; --dp-mut: #5f6f6b;
  --dp-line: #cdd8d4; --dp-shadow: rgba(22, 35, 42, 0.12);
}
[data-theme="dark"] .el-message-box.dossier-messagebox {
  --dp-paper: #12191d; --dp-card: #172126; --dp-ink: #e2ecea;
  --dp-teal: #35c2a4; --dp-coral: #ff8a6b; --dp-mut: #8ba4a0;
  --dp-line: #31454f; --dp-shadow: rgba(0, 0, 0, 0.45);
}
.el-message-box.dossier-messagebox {
  background: var(--dp-card);
  border: 1px solid var(--dp-ink);
  border-radius: 6px;
  box-shadow: 6px 6px 0 var(--dp-shadow);
  position: relative;
  padding: 0;
  width: 440px;
  max-width: calc(100vw - 32px);
}
/* 顶部标本标签压边框线 (同恢复码弹窗手法) */
.el-message-box.dossier-messagebox::before {
  content: 'MEMBER FILE · CONFIRM';
  position: absolute; top: -9px; left: 22px;
  background: var(--dp-card); padding: 0 8px;
  font-family: Consolas, 'SFMono-Regular', monospace;
  font-size: 9.5px; letter-spacing: 0.28em; color: var(--dp-teal);
}
.el-message-box.dossier-messagebox .el-message-box__header {
  padding: 22px 26px 6px;
}
.el-message-box.dossier-messagebox .el-message-box__title {
  font-family: 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
  font-size: 18px; font-weight: 900; letter-spacing: 0.02em; color: var(--dp-ink);
}
.el-message-box.dossier-messagebox .el-message-box__headerbtn {
  top: 20px; right: 20px;
}
.el-message-box.dossier-messagebox .el-message-box__headerbtn .el-message-box__close {
  color: var(--dp-mut); font-size: 17px;
  transition: color 150ms ease;
}
.el-message-box.dossier-messagebox .el-message-box__headerbtn:hover .el-message-box__close,
.el-message-box.dossier-messagebox .el-message-box__headerbtn:focus .el-message-box__close {
  color: var(--dp-ink);
}
.el-message-box.dossier-messagebox .el-message-box__content {
  color: var(--dp-ink);
  font-size: 13.5px; line-height: 1.8;
  padding: 10px 26px 8px;
}
/* 警示图标染珊瑚色 */
.el-message-box.dossier-messagebox .el-message-box__status svg {
  color: var(--dp-coral);
}
.el-message-box.dossier-messagebox .el-message-box__btns {
  padding: 10px 26px 20px;
}
/* 按钮: 取消=墨线幽灵 / 确认=墨线药丸 hover 转 teal
   特异性 0,5,0 压过全局 :root .el-button--primary:not(...) (0,4,0) 的 #B84523 橙 */
.el-overlay .el-message-box.dossier-messagebox .el-message-box__btns .el-button--primary {
  background: transparent;
  border: 1.5px solid var(--dp-ink);
  border-radius: 999px;
  color: var(--dp-ink);
  font-weight: 700;
  padding: 9px 22px;
}
.el-overlay .el-message-box.dossier-messagebox .el-message-box__btns .el-button--primary:hover,
.el-overlay .el-message-box.dossier-messagebox .el-message-box__btns .el-button--primary:focus {
  background: var(--dp-teal);
  border-color: var(--dp-teal);
  color: #fbfcfb;
}
.el-overlay .el-message-box.dossier-messagebox .el-message-box__btns .el-button:not(.el-button--primary) {
  background: transparent;
  border: 1px solid var(--dp-line);
  border-radius: 999px;
  color: var(--dp-mut);
  padding: 9px 22px;
  transition: color 150ms ease, border-color 150ms ease;
}
.el-overlay .el-message-box.dossier-messagebox .el-message-box__btns .el-button:not(.el-button--primary):hover {
  color: var(--dp-ink);
  border-color: var(--dp-ink);
  background: transparent;
}
@media (max-width: 480px) {
  .el-message-box.dossier-messagebox .el-message-box__btns .el-button {
    padding: 9px 16px;
  }
}
</style>
