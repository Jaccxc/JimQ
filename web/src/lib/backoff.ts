/**
 * WS 重連退避:指數退避 + jitter,有上限(純函式,可測)。
 *
 * 瀏覽器 WebSocket 不自動重連,client 自實作。研究指引(frontend-viz §2.5):
 * 指數退避 + jitter,避免重連風暴。
 */

/** 初始退避(ms)。 */
export const BACKOFF_BASE_MS = 500
/** 退避上限(ms)。 */
export const BACKOFF_MAX_MS = 30_000

/**
 * 計算第 attempt 次(0-based)重連等待毫秒。
 * = min(base * 2^attempt, MAX) + 等量 full-jitter(rng()∈[0,1))。
 * 結果封頂於 MAX。注入 rng 以利測試決定論。
 */
export function nextBackoffMs(
  attempt: number,
  rng: () => number = Math.random,
): number {
  const exp = Math.min(BACKOFF_BASE_MS * 2 ** attempt, BACKOFF_MAX_MS)
  const jitter = Math.floor(rng() * exp)
  return Math.min(exp + jitter, BACKOFF_MAX_MS)
}
