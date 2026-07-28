# MobileSettingsView 升级入口 patch
# W72 第 2 批 C-3 Mobile UX v3.4 商业化暗色

在设置页 (MobileSettingsView) 加"升级到专业版"入口。
- 调 BillingChip.vue 风格 (珊瑚橙渐变 + 💎 icon)
- 跳转 /mobile/subscription
- 6 主题 dark 适配 (非 scoped 块)

## Patch 实施位置

`web/src/views/mobile/MobileSettingsView.vue` template 节追加 (在设置项列表 section 末尾, 在退出登录按钮前):

```vue
<!-- W72 第 2 批 C-3: 升级到专业版入口 -->
<button
  type="button"
  class="settings-item upgrade-entry"
  @click="goSubscription"
>
  <div class="item-icon upgrade-icon">💎</div>
  <div class="item-info">
    <div class="item-title upgrade-title">升级到专业版</div>
    <div class="item-desc upgrade-desc">100 GB 空间 + 高级 RAG + 团队共享盘</div>
  </div>
  <span class="item-arrow upgrade-arrow">›</span>
</button>
```

`web/src/views/mobile/MobileSettingsView.vue` script setup 节追加:

```js
function goSubscription() {
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    try { navigator.vibrate(10) } catch (_) { /* noop */ }
  }
  router.push('/mobile/subscription')
}
```

`web/src/views/mobile/MobileSettingsView.vue` style 节 (非 scoped, 跨组件 dark 适配) 追加:

```css
.upgrade-entry {
  background: linear-gradient(90deg, rgba(255, 122, 92, 0.08), rgba(255, 179, 71, 0.08));
  border: 1px solid rgba(255, 122, 92, 0.2);
}
.upgrade-icon {
  background: linear-gradient(135deg, #FF7A5C, #FFB347) !important;
  color: white;
}
.upgrade-title {
  background: linear-gradient(90deg, #FF7A5C, #FFB347);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-weight: 700;
}
.upgrade-desc {
  color: var(--color-text-secondary);
}

[data-theme="dark"] .upgrade-entry {
  background: linear-gradient(90deg, rgba(255, 122, 92, 0.12), rgba(255, 179, 71, 0.12));
  border-color: rgba(255, 122, 92, 0.3);
}
```

## 验证

- 单元测试: tests/test_mobile_v34_commercial_e2e.py::test_settings_upgrade_entry
- Playwright 6 主题 × 3 viewport = 18 视觉快照