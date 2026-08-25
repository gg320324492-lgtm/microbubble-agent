# Desktop 科研登录页实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 Scientific Research OS 登录页升级为已确认的科研叙事双栏界面，同时保持现有认证与跳转逻辑不变。

**架构：** 仅重构 `LoginView.vue` 的模板、语义属性和 scoped CSS。左侧身份区提供产品与本地运行状态，右侧保留现有 Pinia 登录提交函数；组件测试固定页面文案、无障碍错误反馈、表单 loading 行为与令牌消费，避免把视觉实现散落到业务层。

**技术栈：** Vue 3 `<script setup>`、Pinia、Vue Router、Vue Test Utils、Vitest、happy-dom、既有 `research-design-tokens.css`。

---

## 文件结构

- 修改：`desktop/vitest.config.ts` — 为登录页组件测试启用 happy-dom。
- 创建：`desktop/tests/unit/login-view.dom.test.ts` — 登录页的语义与交互 UI 契约。
- 修改：`desktop/src/renderer/src/views/LoginView.vue` — 已确认的双栏模板、ARIA 属性和响应式样式；不改 `onSubmit` 认证分支。

### 任务 1：建立登录页 UI 契约测试

**文件：**
- 修改：`desktop/vitest.config.ts`
- 创建：`desktop/tests/unit/login-view.dom.test.ts`

- [ ] **步骤 1：为目标测试文件启用浏览器环境**

在 `environmentMatchGlobs` 中加入：

```ts
['tests/unit/login-view.dom.test.ts', 'happy-dom']
```

- [ ] **步骤 2：编写失败的登录页 UI 契约测试**

创建 `desktop/tests/unit/login-view.dom.test.ts`：

```ts
// @vitest-environment happy-dom
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/login', name: 'login', component: LoginView }, { path: '/', name: 'home', component: { template: '<main />' } }]
})

async function mountLogin() {
  setActivePinia(createPinia())
  await router.push('/login')
  await router.isReady()
  return mount(LoginView, { global: { plugins: [router] } })
}

beforeEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('科研登录页', () => {
  it('展示 Scientific Research OS 身份区和本地账号说明', async () => {
    const wrapper = await mountLogin()
    expect(wrapper.get('[data-testid="login-identity"]').text()).toContain('Scientific Research OS')
    expect(wrapper.text()).toContain('进入科研工作台')
    expect(wrapper.text()).toContain('账号和实验数据仅保存在本机')
  })

  it('为账号与密码提供关联 label、autocomplete 和可见聚焦类', async () => {
    const wrapper = await mountLogin()
    const username = wrapper.get<HTMLInputElement>('#login-username')
    const password = wrapper.get<HTMLInputElement>('#login-password')
    expect(wrapper.get('label[for="login-username"]').text()).toBe('用户名')
    expect(wrapper.get('label[for="login-password"]').text()).toBe('密码')
    expect(username.attributes('autocomplete')).toBe('username')
    expect(password.attributes('autocomplete')).toBe('current-password')
  })

  it('空表单提交时以 alert 呈现中文错误', async () => {
    const wrapper = await mountLogin()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('请输入用户名和密码')
  })

  it('提交期间禁用输入与登录按钮', async () => {
    const wrapper = await mountLogin()
    const authStore = useAuthStore()
    let finish!: (value: { success: false; error: { code: 'NETWORK_ERROR'; message: string } }) => void
    vi.spyOn(authStore, 'login').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    await wrapper.get('#login-username').setValue('researcher_01')
    await wrapper.get('#login-password').setValue('password')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('#login-username').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#login-password').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').text()).toBe('登录中…')
    finish({ success: false, error: { code: 'NETWORK_ERROR', message: '测试结束' } })
    await flushPromises()
  })
})
```

- [ ] **步骤 3：运行测试确认失败**

运行：`npm run test:unit -- tests/unit/login-view.dom.test.ts`

预期：FAIL，原因是现有登录页没有 `data-testid="login-identity"`、`#login-username`、本地账号说明和 `role="alert"`。

- [ ] **步骤 4：提交测试基线**

```bash
git add desktop/vitest.config.ts desktop/tests/unit/login-view.dom.test.ts
git commit -m "test(desktop): define research login UI contract"
```

### 任务 2：实现语义化科研双栏登录页

**文件：**
- 修改：`desktop/src/renderer/src/views/LoginView.vue`
- 测试：`desktop/tests/unit/login-view.dom.test.ts`

- [ ] **步骤 1：保持认证函数，仅修正本地产品文案与缺失字段校验文案**

保留 `onSubmit` 内的 `authStore.login`、`window.api.auth.getBackendUrl` 和 `router.push({ name: 'home' })`。将空值提示改为：

```ts
if (!form.username || !form.password) {
  error.value = '请输入用户名和密码'
  return
}
```

- [ ] **步骤 2：替换模板为双栏且带无障碍语义的结构**

```vue
<main class="login-root">
  <section class="login-shell" aria-labelledby="login-title">
    <aside class="login-identity" data-testid="login-identity" aria-label="Scientific Research OS 产品说明">
      <div class="login-brand"><span class="login-brand__mark" aria-hidden="true">∿</span><span>MicroBubble Lab</span></div>
      <p class="login-identity__kicker">SCIENTIFIC RESEARCH OS</p>
      <h1>让每一次实验，沉淀为可用的研究。</h1>
      <p>连接实验设备、原始数据、分析结果与实验记录，在同一套本地科研工作台中持续推进。</p>
      <p class="login-identity__status"><span aria-hidden="true"></span>本地科研系统已就绪 <b aria-hidden="true">•</b> 离线数据存储</p>
    </aside>
    <form class="login-form" @submit.prevent="onSubmit">
      <p class="login-form__eyebrow">欢迎回来</p>
      <h2 id="login-title">进入科研工作台</h2>
      <p class="login-form__lede">请使用你的本地科研账号登录。</p>
      <label for="login-username">用户名</label>
      <input id="login-username" v-model="form.username" type="text" autocomplete="username" :disabled="loading" placeholder="例如：researcher_01" />
      <label for="login-password">密码</label>
      <input id="login-password" v-model="form.password" type="password" autocomplete="current-password" :disabled="loading" placeholder="输入你的密码" />
      <button type="submit" :disabled="loading">{{ loading ? '登录中…' : '安全登录' }}</button>
      <p v-if="error" class="login-form__error" role="alert">{{ error }}</p>
      <p class="login-form__local-note"><span aria-hidden="true">▣</span>账号和实验数据仅保存在本机。首次使用请联系系统管理员创建本地账号。</p>
    </form>
  </section>
</main>
```

- [ ] **步骤 3：运行目标测试确认通过**

运行：`npm run test:unit -- tests/unit/login-view.dom.test.ts`

预期：PASS，4 tests passed。

- [ ] **步骤 4：提交语义模板实现**

```bash
git add desktop/src/renderer/src/views/LoginView.vue desktop/tests/unit/login-view.dom.test.ts
git commit -m "feat(desktop): redesign scientific login screen"
```

### 任务 3：实现令牌化视觉与响应式布局

**文件：**
- 修改：`desktop/src/renderer/src/views/LoginView.vue`
- 测试：`desktop/tests/unit/login-view.dom.test.ts`

- [ ] **步骤 1：为令牌化样式补充失败的源代码契约**

在测试文件追加：

```ts
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

it('消费科研设计令牌并在窄窗口堆叠双栏布局', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/views/LoginView.vue'), 'utf8')
  expect(source).toContain('var(--research-instrument-950)')
  expect(source).toContain('var(--research-teal-700)')
  expect(source).toContain('@media (max-width: 760px)')
})
```

- [ ] **步骤 2：运行测试确认失败**

运行：`npm run test:unit -- tests/unit/login-view.dom.test.ts`

预期：FAIL，原因是现有 scoped CSS 尚未消费上述令牌或定义窄窗口布局。

- [ ] **步骤 3：添加最少 scoped CSS 实现**

在 `LoginView.vue` 的 `<style scoped>` 中实现以下结构：

```css
.login-root { min-height:100vh; display:grid; place-items:center; padding:clamp(20px,4vw,56px); background:var(--research-mist-50); color:var(--research-text-primary); font-family:var(--research-font-ui); }
.login-shell { width:min(1120px,100%); min-height:580px; display:grid; grid-template-columns:minmax(360px,45%) minmax(420px,55%); overflow:hidden; border:1px solid var(--research-border-subtle); border-radius:22px; background:var(--research-paper-0); box-shadow:var(--research-shadow-modal); }
.login-identity { position:relative; padding:48px; overflow:hidden; color:var(--research-instrument-text); background:linear-gradient(145deg,var(--research-instrument-950),var(--research-instrument-900)); }
.login-form { width:min(100%,390px); justify-self:center; align-self:center; padding:48px 0; }
.login-form input { width:100%; height:48px; border:1px solid var(--research-border-strong); border-radius:var(--research-radius-input); }
.login-form input:focus { outline:0; border:2px solid var(--research-teal-700); box-shadow:var(--research-shadow-focus-primary); }
.login-form button { width:100%; height:50px; border:0; border-radius:var(--research-radius-button); color:var(--research-text-inverse); background:var(--research-teal-700); }
@media (max-width: 760px) { .login-shell { grid-template-columns:1fr; } .login-identity { min-height:250px; padding:30px; } .login-form { padding:36px 28px; } }
```

补齐标题、状态点、本地说明、错误提示、hover、disabled 与装饰网格的规则；不得引入外部图片、硬编码原设计色或全局样式。

- [ ] **步骤 4：运行登录页测试确认通过**

运行：`npm run test:unit -- tests/unit/login-view.dom.test.ts`

预期：PASS，5 tests passed。

- [ ] **步骤 5：提交视觉实现**

```bash
git add desktop/src/renderer/src/views/LoginView.vue desktop/tests/unit/login-view.dom.test.ts
git commit -m "style(desktop): apply scientific login visual system"
```

### 任务 4：全量验证与交付检查

**文件：**
- 验证：`desktop/tests/unit/login-view.dom.test.ts`
- 验证：`desktop/src/renderer/src/views/LoginView.vue`

- [ ] **步骤 1：运行全部桌面单元测试**

运行：`npm run test:unit`

预期：PASS，0 failed。

- [ ] **步骤 2：运行静态类型检查**

运行：`npm run typecheck`

预期：exit 0。

- [ ] **步骤 3：构建 Electron 渲染与主进程产物**

运行：`npm run build`

预期：exit 0，生成 `out/main`、`out/preload` 与 `out/renderer`。

- [ ] **步骤 4：人工验收**

运行：`npm run dev`

预期：登录页展示深色科研身份区和明亮表单区；在窄窗口中上下堆叠；空表单出现中文 alert；正确账号沿用既有跳转。

- [ ] **步骤 5：提交验证结果**

```bash
git status --short
git log -3 --oneline
```

预期：仅包含本计划相关提交；任何已有未提交文件保持原样。
