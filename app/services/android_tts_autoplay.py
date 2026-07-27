"""Android Chrome autoplay capability policy for Edge-TTS clients.

This module deliberately does not alter the existing TTS pipeline.  It exposes a
small, serialisable policy and the browser-side hooks a web client can install
progressively after a user gesture.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AutoplayAction(str, Enum):
    PLAY = "play"
    RESUME = "resume"
    VIBRATE = "vibrate"
    WAIT_FOR_GESTURE = "wait_for_gesture"


@dataclass(frozen=True)
class AndroidAutoplayState:
    user_gesture: bool = False
    visible: bool = True
    context_state: str = "suspended"
    effective_gain: float = 1.0


class AndroidTTSAutoplayGuard:
    """Resolve Android Chrome autoplay without changing audio generation."""

    def action(self, state: AndroidAutoplayState) -> AutoplayAction:
        if state.effective_gain <= 0:
            return AutoplayAction.VIBRATE
        if not state.user_gesture:
            return AutoplayAction.WAIT_FOR_GESTURE
        if state.visible and state.context_state != "running":
            return AutoplayAction.RESUME
        return AutoplayAction.PLAY

    @staticmethod
    def browser_hooks() -> str:
        """Return progressive browser hooks for the mobile UI integration.

        ``GainNode.gain`` is used for mute detection because AudioContext has no
        standards-based ``volume`` property.
        """
        return """
<button type="button" @click="triggerTTS">播放语音</button>
<script>
const AudioContextCtor = window.AudioContext || window.webkitAudioContext
const audioContext = new AudioContextCtor()
const gainNode = audioContext.createGain()

async function triggerTTS() {
  if (audioContext.state !== 'running') await audioContext.resume()
  if (gainNode.gain.value === 0) navigator.vibrate?.(30)
  else await playEdgeTTS()
}

document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && audioContext.state === 'suspended') {
    await audioContext.resume()
  }
})

async function keepTTSActive() {
  const lock = await navigator.wakeLock?.request('screen')
  if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing'
  return lock
}
</script>
""".strip()
