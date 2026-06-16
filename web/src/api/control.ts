/**
 * 卡 #24 (W5) — 策略控制平面 REST client。
 *
 * - startStrategy:POST /strategies/{id}/start({params})→ ControlAccepted。
 * - stopStrategy:POST /strategies/{id}/stop → ControlAccepted。
 * - killAll:POST /kill(header 全域急停)→ ControlAccepted。
 *
 * 後端發 ControlCommand 信封到 Redis command stream;engine worker 對測試節點
 * 動作(kill = 停止 + 取消未成交單)。走 vite proxy /api。fetch 可注入(測試)。
 */

/** 控制端點回應(對齊 api ControlAccepted)。 */
export interface ControlAccepted {
  strategy_id: string | null
  command_type: string
  correlation_id: string
}

export interface ClientOptions {
  baseUrl?: string
  fetchImpl?: typeof fetch
}

async function postControl(
  path: string,
  body: unknown,
  opts: ClientOptions,
): Promise<ControlAccepted> {
  const base = opts.baseUrl ?? '/api/v1'
  const f = opts.fetchImpl ?? fetch
  const init: RequestInit = { method: 'POST' }
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  const res = await f(`${base}${path}`, init)
  if (!res.ok) {
    throw new Error(`control ${path} ${res.status} ${res.statusText ?? ''}`.trim())
  }
  return (await res.json()) as ControlAccepted
}

export async function startStrategy(
  strategyId: string,
  params: Record<string, unknown> = {},
  opts: ClientOptions = {},
): Promise<ControlAccepted> {
  return postControl(`/strategies/${strategyId}/start`, { params }, opts)
}

export async function stopStrategy(
  strategyId: string,
  opts: ClientOptions = {},
): Promise<ControlAccepted> {
  return postControl(`/strategies/${strategyId}/stop`, undefined, opts)
}

export async function killAll(opts: ClientOptions = {}): Promise<ControlAccepted> {
  return postControl('/kill', undefined, opts)
}
