# MobileFileList / MobileDriveView 长按 ActionSheet 升级空间 patch
# W72 第 2 批 C-3 Mobile UX v3.4 商业化暗色

在文件长按弹出的 MobileActionSheet 中加"升级空间"选项。

## Patch 实施位置

### `web/src/views/mobile/MobileFileList.vue`

`onLongPressFile(file)` 函数调整:

```js
function onLongPressFile(file) {
  // CLAUDE.md 2026-06-27 教训: 长按必含 navigator.vibrate(10)
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    try { navigator.vibrate(10) } catch (_) { /* noop */ }
  }
  selectedFile.value = file
  showActionSheet.value = true
  // W72 第 2 批 C-3: 长按 ActionSheet 加 "升级空间" 选项
  actionSheetActions.value = [
    { name: '预览', icon: '👁', callback: () => preview(file) },
    { name: '下载', icon: '⬇️', callback: () => download(file) },
    { name: '重命名', icon: '✏️', callback: () => rename(file) },
    { name: '可见性', icon: '🔓', callback: () => changeVisibility(file) },
    { name: '加入知识库', icon: '📚', callback: () => addToKb(file) },
    { name: '升级空间', icon: '💎', callback: () => goSubscription(), highlight: true },
    { name: '删除', icon: '🗑', danger: true, callback: () => deleteFile(file) },
  ]
}

function goSubscription() {
  showActionSheet.value = false
  if (typeof navigator !== 'undefined' && navigator.vibrate) {
    try { navigator.vibrate(10) } catch (_) { /* noop */ }
  }
  router.push('/mobile/subscription')
}
```

template 节对应 `:actions` 改为 `actionSheetActions`, 加 `highlight` class:

```vue
<MobileActionSheet
  v-model:show="showActionSheet"
  title="文件操作"
  :actions="actionSheetActions"
/>
```

style 节追加 (非 scoped, dark 跨组件):

```css
[data-theme="dark"] .action-item.highlight {
  background: rgba(255, 122, 92, 0.12);
  color: #FFB347;
}
```

### `web/src/views/mobile/MobileDriveView.vue`

相同模式, 在 `onLongPressFile(file)` 中追加 "升级空间" action.

## 验证

- 单元测试: tests/test_mobile_v34_commercial_e2e.py::test_long_press_action_sheet_upgrade_option
- Playwright 6 主题 × 3 viewport = 18 视觉快照 (含 ActionSheet 弹层)
- 长按 vibrate(10) 反馈 2 case