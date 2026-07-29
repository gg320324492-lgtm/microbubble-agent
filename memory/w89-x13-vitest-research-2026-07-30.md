## 19 vitest failed 调研 (W89-X-13)

### 总览
- P-10 目标清单：19 个 failed（worktree 与 main 基线一致，故与 W89-X-13 变更相关性为 0）。
- 本 worktree 实测 `SKIP_DB_SETUP=1 npm run test:unit`：1009 PASS、19 个目标 failed、1 SKIPPED；Vitest 另外收集到 4 个未列入 P-10 目标的 Playwright/手势基础设施失败，因此终端汇总曾显示 23 failed。那 4 个额外失败不计入本调研 19 个目标：`mobile_push_notification.spec.js`、`mobile_swipe_gesture.spec.js`、`mobile_voice_input.spec.js`（Playwright Test 被 Vitest 直接收集）以及 `useSwipeGesture` 的 49px 边界断言。
- 目标 19 个 failed 与本任务无关；本任务只调研，不修改测试或生产代码。

### 按 root cause 分类
| 类别 | 数量 | test 文件/范围 |
|---|---:|---|
| 语法 / fixture / 旧接口漂移 | 10 | `tests/e2e/desktop_emoji_lazy.spec.js`（1，JS 文件含 TypeScript 类型断言）；`tests/e2e/desktop_drive_versions.spec.js`（3，axios mock 与组件实际模块/鉴权接口不匹配）；`tests/e2e/mobile_drive_comments.spec.js`（4，`useMobileKeyboard` 在组件 setup 中调用但未定义/导入）；`tests/unit/mobile-fab.test.js`（1，stub 未保留 `.long-press-wrapper` class）；`tests/unit/pwa-update-toast.test.js`（1，jsdom `window.location.reload` 不可重定义）。 |
| 性能基线漂移 | 0 | 目标 19 中没有纯性能阈值漂移；`mobile_build_validation` 是 Rolldown 构建器 panic，不应伪装成应用性能问题。 |
| encoding / 字符问题 | 0 | 未发现。 |
| stale slice（测试契约/DOM slice 引用过期） | 8 | `src/components/chat/__tests__/NavRail.spec.js` 全部 8 个 scenario；测试仍断言旧 `.nav-item`、`#nav-rail-*` hamburger/accent、`mobile-drawer`、`data-theme-accent` 契约，而当前 `NavRail.vue` 使用 `.nav-rail-item`、`mobileOpen` prop、`mobile-open`/`mobile-close`，且没有 accent 控制器。 |
| 其它（构建工具链） | 1 | `tests/e2e/mobile_build_validation.spec.js`（1，`npm run build` 在 Rolldown `compute_cross_chunk_links.rs` panic，报 `easeInOutCubic ... should belong to a chunk`；不是业务代码错误）。 |

### 19 failed 详细表
| # | test 名 | 文件 | root cause | 修法建议 | 优先级 |
|---:|---|---|---|---|---|
| 1 | `desktop_emoji_lazy`（整套件未运行） | `web/tests/e2e/desktop_emoji_lazy.spec.js:291` | 语法 / 旧接口 | 将 `.js` 中 `const vm: any = wrapper.vm as any` 改为合法 JavaScript，或将该测试迁为 `.ts` 并配套类型编译；先修语法再评估 3 个场景。 | 高 |
| 2 | 版本历史场景 1：时间线渲染 | `web/tests/e2e/desktop_drive_versions.spec.js:127-157` | fixture / 旧接口漂移 | 在模块加载前 mock `@/composables/useDriveFiles` 或提供组件实际使用的 axios/auth mock；避免 `vi.doMock` 在已静态 import 后才设置。 | 高 |
| 3 | 版本历史场景 2：历史版本恢复按钮 | `web/tests/e2e/desktop_drive_versions.spec.js:159-180` | 同上 | 同 2；修正 listVersions mock 后再断言按钮，当前组件因 `Not authenticated` 进入 error state。 | 高 |
| 4 | 版本历史场景 3：空版本 el-empty | `web/tests/e2e/desktop_drive_versions.spec.js:182-203` | 同上 | 同 2；让 mock 命中组件调用链并补 token/模块 mock，确认真实 empty state，而非 error state。 | 高 |
| 5 | `mobile_build_validation`：`npm run build exit 0` | `web/tests/e2e/mobile_build_validation.spec.js:72-84` | 其它：Rolldown 工具链 panic | 固定/升级兼容的 Vite/Rolldown 版本，或按项目构建门禁锁定稳定 bundler；保留 `npm run build` 作为独立门禁，不能改成忽略非零退出。 | 高 |
| 6 | 评论列表 header/tabs/list | `web/tests/e2e/mobile_drive_comments.spec.js:176-200` | fixture / 旧接口漂移 | 补回 `useMobileKeyboard` composable import/实现，或在组件未需要键盘行为时删除未定义调用；再验证 API fixture。 | 高 |
| 7 | 发送评论 | `web/tests/e2e/mobile_drive_comments.spec.js:202-233` | 同上 | 同 6；setup 阶段异常导致 textarea/post 流程根本未执行。 | 高 |
| 8 | 长按评论菜单 | `web/tests/e2e/mobile_drive_comments.spec.js:235-261` | 同上 | 同 6；修 setup 阻断后验证 vibrate、Teleport 菜单及长按事件。 | 高 |
| 9 | 无评论 empty state | `web/tests/e2e/mobile_drive_comments.spec.js:263-290` | 同上 | 同 6；修 setup 阻断后确认空 fixture 的 empty 分支。 | 高 |
| 10 | `MobileFab` long press expands | `web/tests/unit/mobile-fab.test.js:29-34` | fixture / 旧接口漂移 | 让 `LongPressStub` 复刻真实根节点 class（`.long-press-wrapper`），或用组件公开事件契约而非依赖 stub DOM class。 | 中 |
| 11 | PWA 更新提示点击刷新 | `web/tests/unit/pwa-update-toast.test.js:43-55` | fixture / 测试环境 API 契约 | 不直接 `spyOn` jsdom 不可配置的 `window.location.reload`；注入 reload 函数/可替换 window location adapter，或在测试环境建立可配置边界。 | 中 |
| 12 | NavRail scenario 1：6 nav items/theme attr | `web/src/components/chat/__tests__/NavRail.spec.js:101-111` | stale slice | 将选择器和期望更新到当前 `.nav-rail-item`/现有属性；若 accent 功能已移除，应删除过期断言并新增当前组件契约。 | 中 |
| 13 | NavRail scenario 2：active route | 同上 `:113-123` | stale slice | 使用 `#nav-rail` 当前 DOM 或 `[data-route]`/`.nav-rail-item.active`；不要继续依赖不存在的 `#nav-rail-chat`。 | 中 |
| 14 | NavRail scenario 3：accent cycle | 同上 `:125-140` | stale slice | 先确认 accent 控制已从组件迁出；若由父级/主题 store 负责，移至对应组件测试，否则移除过期场景。 | 中 |
| 15 | NavRail scenario 4：6 theme combinations | 同上 `:142-161` | stale slice | 改测现有主题边界；当前 `NavRail.vue` 未绑定 `data-theme-accent`，不应断言旧属性。 | 中 |
| 16 | NavRail scenario 5：mobile hamburger | 同上 `:163-173` | stale slice | 当前组件通过 `mobileOpen` prop + `.mobile-close` 关闭，外部 hamburger 不在 NavRail；改测 prop/class，或把 hamburger 测试放到父布局。 | 中 |
| 17 | NavRail scenario 6：hamburger toggles drawer | 同上 `:175-190` | stale slice | 同 16；验证 `update:mobileOpen` emit，而不是触发不存在的 `#nav-rail-hamburger`。 | 中 |
| 18 | NavRail scenario 7：route closes drawer | 同上 `:192-207` | stale slice | 按当前 `mobileOpen`/emit 设计重写，不能依赖旧 `drawer-open` watch 契约。 | 中 |
| 19 | NavRail scenario 8：desktop/mobile cross endpoint | 同上 `:209-224` | stale slice | 将端点断言拆到真实父布局 + NavRail 两层；当前 NavRail 自身没有 `mobile-drawer` class 或 hamburger。 | 中 |

### 额外收集但不计入 P-10 的 4 个失败
1. `web/tests/e2e/mobile_push_notification.spec.js`：Vitest 收集 Playwright 文件，在顶层调用 `test.use()`，报 `Playwright Test did not expect test.use() to be called here`。
2. `web/tests/e2e/mobile_swipe_gesture.spec.js`：同类收集配置错误，顶层 `test.describe()` 被 Vitest 执行。
3. `web/tests/e2e/mobile_voice_input.spec.js`：同类顶层 `test.use()` 收集错误。
4. `web/src/composables/__tests__/useSwipeGesture.test.js`：测试数据 `dy=99`，虽 x 位移 49px，实际垂直位移超过 threshold，当前实现合理触发 `onSwipeUp`；测试描述与 fixture 不一致。应由后续测试修复派工单独处理，不能算 X-13 目标 19。

### 留 W89+（修）
- 优先级：
  1. 高：emoji 语法阻断、mobile comments 未定义 composable、desktop versions mock/auth、build Rolldown panic。
  2. 中：MobileFab stub、PWA reload 测试边界、NavRail 8 个 stale slice。
  3. 另开测试收集配置任务：把 Playwright specs 从 Vitest include 排除，避免额外 3 个假失败；单独修 swipe fixture。
- 估时：目标 19 真修约 4-6h（语法/未定义调用/build 工具链 1.5-2.5h，versions/comments mock 1-1.5h，NavRail stale slice 1-2h）；另加 Vitest/Playwright 收集隔离约 0.5h。
- 派工建议：W89 第 2 批拆为 X-13a 构建与语法门禁、X-13b mobile comments/drive fixture、X-13c NavRail 契约重写；不在本调研 commit 中擅自修复。

### 纪律沉淀
- 派工 v6 §5 反馈 **类 20.65**：19 vitest failed 调研必须逐项实测，按“语法/fixture/旧接口漂移、性能基线漂移、encoding/字符、stale slice”四类分类，给出修法优先级，调研 agent 不擅自修复。
