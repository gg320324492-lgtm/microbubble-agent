"""Android Chrome background/tab audio-focus state policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AudioFocusAction(str, Enum):
    PLAY = "play"
    PAUSE = "pause"
    RESUME = "resume"


@dataclass(frozen=True)
class AndroidBackgroundState:
    visible: bool
    focused: bool
    context_state: str


class AndroidTTSBackgroundPolicy:
    """Translate browser visibility/focus events to audio-focus actions."""

    def action(self, state: AndroidBackgroundState) -> AudioFocusAction:
        if not state.visible or not state.focused:
            return AudioFocusAction.PAUSE
        if state.context_state != "running":
            return AudioFocusAction.RESUME
        return AudioFocusAction.PLAY

    @staticmethod
    def browser_hooks() -> str:
        return """
const AudioFocusRequest = Object.freeze({ PLAY: 'play', PAUSE: 'pause' })
const onAudioFocus = (focus) => focus === AudioFocusRequest.PAUSE
  ? audioContext.suspend()
  : audioContext.resume()
document.addEventListener('visibilitychange', () =>
  onAudioFocus(document.visibilityState === 'visible' ? AudioFocusRequest.PLAY : AudioFocusRequest.PAUSE))
window.addEventListener('blur', () => onAudioFocus(AudioFocusRequest.PAUSE))
window.addEventListener('focus', () => onAudioFocus(AudioFocusRequest.PLAY))
""".strip()
