import { ref, unref } from 'vue'

/**
 * Shared mobile quick-action state for Floating Action Buttons.
 *
 * Each action is { name, label, icon, handler, danger? }. Handlers are
 * intentionally kept on the page so this composable remains domain-agnostic.
 */
export function useMobileFab(initialActions = []) {
  const actions = ref(unref(initialActions) || [])
  const isExpanded = ref(false)

  function vibrate() {
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
      navigator.vibrate(10)
    }
  }

  function toggle() {
    isExpanded.value = !isExpanded.value
    vibrate()
  }

  function close() {
    if (isExpanded.value) {
      isExpanded.value = false
      vibrate()
    }
  }

  function expand() {
    if (!isExpanded.value) {
      isExpanded.value = true
      vibrate()
    }
  }

  function setActions(nextActions) {
    actions.value = unref(nextActions) || []
  }

  return { actions, isExpanded, toggle, close, expand, setActions }
}

export default useMobileFab
