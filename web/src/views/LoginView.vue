<template>
  <div class="login-shell">
    <!-- ══ 左 2/3：气泡科学图解海报 ══ -->
    <section class="poster" aria-hidden="true">
      <div class="poster__rule"></div>
      <header class="poster__head">
        <b class="poster__brand">
          <img src="/lab-logo.png" alt="" class="poster__logo">微纳米气泡课题组
        </b>
        <span>PL. 01 — SINGLE CAVITATION BUBBLE — SCALE ×24,000</span>
      </header>

      <div class="bubble-stage">
        <div class="bubble">
          <span class="nano n1"></span>
          <span class="nano n2"></span>
          <span class="nano n3"></span>
          <span class="nano n4"></span>
        </div>
      </div>

      <div class="anno anno--shell"><b>气体壳层</b>PAGE 面 · 厚度 ~2 nm</div>
      <div class="anno anno--charge"><b>ζ 电位</b>· 负电表面阻止聚并 ·</div>
      <div class="anno anno--lifespan"><b>超长存续</b>上升速度 &lt; 1 mm/s</div>

      <h1 class="poster__title">小气泡，<br>大世界。</h1>
      <p class="poster__foot">
        <span>科研智能工作台 · 任务 / 会议 / 知识一体化</span>
        <span class="coral">ENTER YOUR ACCOUNT →</span>
      </p>
    </section>

    <!-- ══ 右 1/3：登录表单 ══ -->
    <aside class="gate">
      <span class="gate__no">RESEARCH OS / 2026</span>
        <div v-if="mode === 'login'" key="login" class="gate__inner">
          <h2>登录工作台</h2>
          <p class="gate__lede">如同一颗微泡稳定地悬浮于水中，你的数据稳定地留在这台机器上。</p>

      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        label-position="top"
        class="gate__form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <template #label>
            <span class="f-label">用户名 <i>USERNAME</i></span>
          </template>
          <el-input
            v-model="loginForm.username"
            name="login-username"
            placeholder="请输入用户名"
            size="large"
            autocomplete="username"
          />
        </el-form-item>

        <el-form-item prop="password">
          <template #label>
            <span class="f-label">密码 <i>PASSWORD</i></span>
          </template>
          <el-input
            v-model="loginForm.password"
            name="login-password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="gate__button"
          :loading="loading"
          @click="handleLogin"
        >
          {{ loading ? '登录中…' : '进入工作台' }}
        </el-button>
      </el-form>

      <div class="gate__aux">
        <a href="#" class="gate__forgot" @click.prevent="switchMode('reset')">忘记密码？</a>
      </div>
        </div>
        <div v-else key="reset" class="gate__inner">
          <h2>重置密码</h2>
          <p class="gate__lede">输入用户名与恢复码，直接设置新密码，全程自助。</p>

          <el-form
            ref="resetFormRef"
            :model="resetForm"
            :rules="resetRules"
            label-position="top"
            class="gate__form"
            @keyup.enter="handleReset"
          >
            <el-form-item prop="username">
              <template #label>
                <span class="f-label">用户名 <i>USERNAME</i></span>
              </template>
              <el-input
                v-model="resetForm.username"
                name="reset-username"
                placeholder="请输入用户名"
                size="large"
                autocomplete="username"
              />
            </el-form-item>

            <el-form-item prop="recovery_code">
              <template #label>
                <span class="f-label">恢复码 <i>RECOVERY CODE</i></span>
              </template>
              <el-input
                v-model="resetForm.recovery_code"
                name="reset-recovery-code"
                placeholder="abcd-efgh-jkmn"
                size="large"
              />
            </el-form-item>

            <el-form-item prop="new_password">
              <template #label>
                <span class="f-label">新密码 <i>NEW PASSWORD</i></span>
              </template>
              <el-input
                v-model="resetForm.new_password"
                name="reset-new-password"
                type="password"
                placeholder="至少 6 位"
                size="large"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>

            <el-form-item prop="confirm_password">
              <template #label>
                <span class="f-label">确认新密码 <i>CONFIRM</i></span>
              </template>
              <el-input
                v-model="resetForm.confirm_password"
                name="reset-confirm-password"
                type="password"
                placeholder="再次输入新密码"
                size="large"
                show-password
                autocomplete="new-password"
              />
            </el-form-item>

            <el-button
              type="primary"
              size="large"
              class="gate__button"
              :loading="resetting"
              @click="handleReset"
            >
              {{ resetting ? '重置中…' : '重置密码' }}
            </el-button>
          </el-form>

          <div class="gate__aux">
            <a href="#" class="gate__forgot" @click.prevent="switchMode('login')">← 返回登录</a>
          </div>
          <p class="gate__note">
            没有恢复码？能正常登录时在【设置 → 账号安全 → 密码恢复码】生成并保存到个人微信收藏；
            重置成功后恢复码即失效，需重新生成。
          </p>
        </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

// 登录 / 自助重置 双模式 (2026-09-02 恢复码)
const mode = ref('login')
const resetFormRef = ref(null)
const resetting = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const resetForm = reactive({
  username: '',
  recovery_code: '',
  new_password: '',
  confirm_password: ''
})

// 统一错误提取: 新统一异常格式 {"error":{"message":...}} 优先, 兼容旧 {"detail":...}
const apiErrMsg = (err, fallback) =>
  err?.response?.data?.error?.message || err?.response?.data?.detail || fallback

const switchMode = (target) => {
  mode.value = target
  if (target === 'reset') {
    resetForm.username = loginForm.username
  }
}

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

const resetRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  recovery_code: [
    { required: true, message: '请输入恢复码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== resetForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  // v2.1 修复: 不再使用 validate(callback) + async callback
  // element-plus validate callback 期望同步返 boolean, async callback 内部 await 永远不会被等
  // → loading 永远 true → 按钮转圈
  // 改用 validate() promise 模式 (element-plus 2.x 返 Promise<boolean>)

  let isValid = false
  loading.value = true
  try {
    isValid = await loginFormRef.value.validate()
  } catch {
    isValid = false
  }

  if (!isValid) {
    loading.value = false
    return
  }

  try {
    const res = await axios.post('/api/v1/auth/login', {
      username: loginForm.username,
      password: loginForm.password
    })

    const { access_token, refresh_token, user } = res.data

    // 保存令牌和用户信息
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    localStorage.setItem('user_info', JSON.stringify(user))

    // 设置axios默认header
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

    ElMessage.success('登录成功')
    router.push('/')
  } catch (error) {
    const message = apiErrMsg(error, '登录失败，请重试')
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

const handleReset = async () => {
  if (!resetFormRef.value) return

  let isValid = false
  resetting.value = true
  try {
    isValid = await resetFormRef.value.validate()
  } catch {
    isValid = false
  }

  if (!isValid) {
    resetting.value = false
    return
  }

  try {
    await axios.post('/api/v1/auth/reset-password-self', {
      username: resetForm.username,
      recovery_code: resetForm.recovery_code,
      new_password: resetForm.new_password
    })

    ElMessage.success('密码重置成功，请使用新密码登录')
    loginForm.username = resetForm.username
    loginForm.password = ''
    mode.value = 'login'
  } catch (error) {
    ElMessage.error(apiErrMsg(error, '重置失败，请检查用户名和恢复码'))
  } finally {
    resetting.value = false
  }
}
</script>

<style scoped>
/* ═══ D · 剖面海报 — 气泡科学图解 (docs/design-proposals/login-2026-09/D-poster.html) ═══ */
.login-shell {
  --paper: #f4f6f4;
  --ink: #16232a;
  --teal: #0e766e;
  --teal-soft: #198e83;
  --coral: #ef7256;
  --line: #cdd8d4;
  --muted: #5f6f6b;
  --font-serif: 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
  --font-mono: Consolas, 'SFMono-Regular', 'Courier New', monospace;

  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.35fr 0.65fr;
  background: var(--paper);
  color: var(--ink);
  overflow: hidden;
}

/* ── 左：海报画布 ─────────────────────────────── */
.poster { position: relative; overflow: hidden; }
.poster__rule { position: absolute; left: 64px; top: 64px; bottom: 64px; width: 1px; background: var(--line); }
.poster__head {
  position: absolute; left: 84px; top: 56px; right: 64px;
  display: flex; justify-content: space-between; align-items: baseline;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.2em; color: var(--muted);
}
.poster__brand {
  font-family: var(--font-serif);
  font-size: 15px; font-weight: 900; letter-spacing: 0.06em; color: var(--ink);
  display: inline-flex; align-items: center; gap: 9px;
}
.poster__logo { width: 22px; height: 22px; object-fit: contain; }

.poster__title {
  position: absolute; left: 84px; bottom: 120px; z-index: 3;
  font-family: var(--font-serif);
  font-size: clamp(44px, 4.6vw, 64px);
  font-weight: 900; line-height: 1.25; letter-spacing: 0.015em;
  margin: 0;
}

.poster__foot {
  position: absolute; left: 84px; right: 64px; bottom: 44px;
  display: flex; justify-content: space-between;
  font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.16em; color: var(--muted);
}
.poster__foot .coral { color: var(--coral); }

/* 主角气泡 */
.bubble-stage { position: absolute; inset: 0; display: grid; place-items: center; }
.bubble {
  position: relative;
  width: min(46vh, 480px); height: min(46vh, 480px);
  margin: 0 0 16vh 4vw;
  border-radius: 50%;
  background:
    radial-gradient(circle at 30% 26%, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.35) 34%, rgba(204, 235, 229, 0.25) 55%, rgba(14, 118, 110, 0.10) 78%),
    radial-gradient(circle at 68% 74%, rgba(25, 142, 131, 0.16), transparent 50%);
  border: 1.5px solid rgba(14, 118, 110, 0.45);
  box-shadow:
    inset 0 0 46px rgba(14, 118, 110, 0.10),
    inset -18px -26px 60px rgba(14, 118, 110, 0.08),
    0 30px 70px rgba(22, 35, 42, 0.10);
  animation: bubble-breathe 7s ease-in-out infinite;
}
@keyframes bubble-breathe {
  50% { transform: scale(1.018) translateY(-4px); }
}
.bubble::after {
  content: '';
  position: absolute; inset: 12%;
  border-radius: 50%;
  border: 1px dashed rgba(14, 118, 110, 0.30);
}
.bubble .nano {
  position: absolute; border-radius: 50%;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(14, 118, 110, 0.35);
}
.bubble .n1 { width: 11%; height: 11%; left: 24%; top: 58%; }
.bubble .n2 { width: 6%;  height: 6%;  left: 46%; top: 70%; }
.bubble .n3 { width: 8%;  height: 8%;  left: 62%; top: 52%; }
.bubble .n4 { width: 4%;  height: 4%;  left: 36%; top: 40%; }

/* 标注引线 */
.anno {
  position: absolute; z-index: 4;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.06em;
  color: var(--teal);
  white-space: nowrap;
}
.anno b {
  display: block; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 12.5px; font-weight: 700; color: var(--ink); margin-bottom: 2px; letter-spacing: 0.02em;
}
.anno::after { content: ''; position: absolute; background: rgba(14, 118, 110, 0.4); height: 1px; }
.anno--shell { left: 4%; top: 16%; }
.anno--shell::after { width: 9vw; left: 100%; margin-left: 12px; top: 14px; transform: rotate(16deg); transform-origin: left; }
.anno--charge { right: 4%; top: 34%; text-align: right; }
.anno--charge b { color: var(--coral); }
.anno--charge::after { width: 7vw; right: 100%; margin-right: 12px; top: 14px; transform: rotate(14deg); transform-origin: right; }
.anno--lifespan { left: 8%; bottom: 34%; }
.anno--lifespan::after { width: 8vw; left: 100%; margin-left: 12px; top: 10px; transform: rotate(-18deg); transform-origin: left; }

/* ── 右：登录栏 ───────────────────────────────── */
.gate {
  border-left: 1px solid var(--line);
  background: #fbfcfb;
  display: flex; flex-direction: column; justify-content: center;
  padding: 0 clamp(36px, 3.4vw, 56px);
  position: relative;
  animation: fadeSlideUp var(--duration-slow, 300ms) var(--ease-out, ease-out) both;
}
.gate__no {
  position: absolute; top: 56px; left: clamp(36px, 3.4vw, 56px);
  writing-mode: vertical-rl;
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.4em; color: var(--line);
}
.gate h2 {
  font-family: var(--font-serif); font-size: 26px; font-weight: 900; letter-spacing: 0.02em;
  margin: 0;
}
.gate__lede { margin-top: 10px; font-size: 13px; line-height: 1.9; color: var(--muted); }

.gate__form { margin-top: 30px; }
.gate__form :deep(.el-form-item) { margin-bottom: 22px; }

.f-label {
  display: flex; justify-content: space-between; align-items: baseline; width: 100%;
  font-size: 12px; font-weight: 700; letter-spacing: 0.08em; color: var(--ink);
}
.f-label i {
  font-style: normal; font-family: var(--font-mono);
  font-weight: 400; font-size: 10px; letter-spacing: 0.14em; color: var(--muted);
}

/* el-input 重塑为下划线输入框 */
.gate__form :deep(.el-input__wrapper) {
  background: transparent;
  box-shadow: none;
  border-radius: 0;
  border-bottom: 1.5px solid var(--ink);
  padding: 0 2px;
  transition: border-color 160ms ease;
}
.gate__form :deep(.el-input__wrapper:hover) { box-shadow: none; }
.gate__form :deep(.el-input__wrapper.is-focus) {
  box-shadow: none;
  border-bottom-color: var(--teal-soft);
}
.gate__form :deep(.el-input__inner) {
  height: 47px; line-height: 47px;
  font-size: 15px; color: var(--ink);
  caret-color: var(--teal);
}
.gate__form :deep(.el-input__inner::placeholder) { color: #adbab6; font-size: 13.5px; }
.gate__form :deep(.el-input__suffix) { color: #97a5a1; }
.gate__form :deep(.el-form-item.is-error .el-input__wrapper) {
  border-bottom-color: #c45656;
  box-shadow: none;
}
.gate__form :deep(.el-form-item__error) { padding-top: 5px; font-size: 11.5px; }
/* Chrome 自动填充白底覆盖透明输入框 */
.gate__form :deep(.el-input__inner:-webkit-autofill) {
  -webkit-box-shadow: 0 0 0 1000px #fbfcfb inset;
  -webkit-text-fill-color: var(--ink);
  transition: background-color 99999s ease-in-out 0s;
}

/* 全局 variables.css 的 `:root .el-button--primary:not(.is-text):not(.is-link)` (0,4,0)
   把所有实心主色按钮压成 #B84523 — 这里用更高特异性选择器赢回海报的墨色按钮 */
.login-shell .gate .el-button--primary.gate__button {
  width: 100%; height: 52px; margin-top: 12px;
  background: var(--ink); border: 1.5px solid var(--ink); border-radius: 999px;
  color: #fbfcfb;
  font-size: 15px; font-weight: 700; letter-spacing: 0.12em;
  transition: transform 150ms ease, box-shadow 150ms ease, background 150ms ease;
}
.login-shell .gate .el-button--primary.gate__button:hover,
.login-shell .gate .el-button--primary.gate__button:focus {
  background: var(--teal); border-color: var(--teal); color: #fbfcfb;
  transform: translateY(-2px);
  box-shadow: 0 12px 26px rgba(14, 118, 110, 0.28);
}
.login-shell .gate .el-button--primary.gate__button:active { transform: translateY(0); }

.gate__aux {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
.gate__forgot {
  font-size: 12.5px;
  color: var(--teal);
  text-decoration: none;
  border-bottom: 1px dotted var(--teal);
  padding-bottom: 1px;
  transition: color 150ms ease, border-color 150ms ease;
}
.gate__forgot:hover { color: var(--teal-soft); border-bottom-style: solid; }
.gate__forgot:focus-visible { outline: 2px solid var(--teal); outline-offset: 3px; border-bottom-style: solid; }

.gate__note {
  margin-top: 30px; padding-top: 18px; border-top: 1px dashed var(--line);
  font-size: 11.5px; line-height: 1.9; color: var(--muted);
}
.gate__note::before { content: '◉ '; color: var(--teal); }

/* ── 响应式：窄屏海报折叠到上方 ───────────────── */
@media (max-width: 980px) {
  .login-shell { grid-template-columns: 1fr; overflow: auto; }
  .poster { min-height: 56vh; }
  .bubble { width: 46vw; height: 46vw; margin-bottom: 24vh; }
  .gate { border-left: 0; border-top: 1px solid var(--line); padding: 56px 32px; }
  .gate__no { display: none; }
}
@media (max-width: 768px) {
  .poster__head { left: 32px; right: 24px; }
  .poster__head span { display: none; }
  .poster__title { left: 32px; bottom: 90px; font-size: 40px; }
  .poster__foot { left: 32px; right: 24px; }
  .anno--charge { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .bubble { animation: none; }
  .gate { animation: none; }
  .gate__button { transition: none; }
}
</style>
