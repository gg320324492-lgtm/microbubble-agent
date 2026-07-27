"""Abort-safe Edge-TTS recovery policy for Android Chrome."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryPoint:
    text: str
    offset_seconds: float = 0.0


class AndroidTTSRecovery:
    """Bound retries and expose browser cleanup/recovery hooks."""

    max_retries = 3
    threshold = 0.55

    @staticmethod
    def backoff_seconds(attempt: int) -> float:
        if attempt < 1 or attempt > AndroidTTSRecovery.max_retries:
            raise ValueError("attempt must be between 1 and 3")
        return float(2 ** (attempt - 1))

    @staticmethod
    def audio_focus_accepted(score: float) -> bool:
        return score >= AndroidTTSRecovery.threshold

    @staticmethod
    def browser_hooks() -> str:
        return """
const controller = new AbortController()
const recoveryPoint = { text: '', offsetSeconds: 0 }
function cancelTTS() { controller.abort(); audioContext.close() }
window.addEventListener('beforeunload', () => {
  sessionStorage.setItem('tts-recovery', JSON.stringify(recoveryPoint))
})
window.addEventListener('load', () => {
  const saved = sessionStorage.getItem('tts-recovery')
  if (saved) Object.assign(recoveryPoint, JSON.parse(saved))
})
async function retryTTS(request, attempt = 1) {
  try { return await fetch(request, { signal: controller.signal }) }
  catch (error) {
    if (error.name === 'AbortError' || attempt >= 3) throw error
    await new Promise(resolve => setTimeout(resolve, 1000 * 2 ** (attempt - 1)))
    return retryTTS(request, attempt + 1)
  }
}
""".strip()
