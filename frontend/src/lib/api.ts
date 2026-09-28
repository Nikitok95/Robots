export type Point = [string, number]

export interface SeriesState {
  value: number | null
  date: string | null
  source: string | null
  fetched_at: string | null
  stale: boolean
  stale_reason: string | null
  error?: string | null
}

export interface Card extends SeriesState {
  id: string
  name: string
  group: string
  unit: string
  freq: string
  decimals: number
  change_mode: 'bp' | 'pct' | 'abs'
  note: string
  changes: { d1: number | null; w1: number | null; m1: number | null }
  spark: Point[]
}

export interface FedMeeting {
  date: string
  error?: string
  implied_rate?: number
  expected_change_bp?: number
  cumulative_change_bp?: number
  distribution?: { low: number; high: number; change_bp: number; prob: number }[]
}

export interface FedSnapshot {
  error?: string
  as_of?: string
  effr?: number
  target?: [number, number]
  meetings?: FedMeeting[]
  contracts?: Record<string, string>
  source?: string
}

export interface AlertRule {
  id: string
  name: string
  description: string
  enabled: boolean
  params: Record<string, number>
  metrics: string[]
  active: boolean
  last_message: string
}

export interface AlertEvent {
  id: number
  rule_id: string
  date: string
  triggered_at: string
  message: string
  details: Record<string, unknown>
}

export interface RefreshLog {
  job: string
  started_at: string
  finished_at: string | null
  ok: number
  failed: number
}

export interface Dashboard {
  groups: { id: string; name: string; cards: Card[] }[]
  fed: FedSnapshot
  boj_next_meeting: { date: string; source: string } | null
  alerts: { rules: AlertRule[]; active_metrics: string[]; events: AlertEvent[] }
  last_refresh: RefreshLog | null
}

export interface ChartSeries {
  id: string
  name: string
  unit: string
  decimals: number
  note: string
  period: string
  points: Point[]
  sources: string[]
  /** Bollinger bands: [date, SMA, upper, lower]; only for configured series. */
  bands?: { window: number; k: number; points: [string, number, number, number][] }
}

export interface IndState extends SeriesState {
  indicator: string
  name: string
  unit: string
  decimals: number
  note?: string
}

export interface FxState {
  quote: string
  value: number | null
  date: string | null
  source: string | null
  stale: boolean
  d1: number | null
  m1: number | null
  strength_1d: number | null
  strength_1m: number | null
}

export interface CalEvent {
  id: string
  currency: string | null
  country: string | null
  ts: string
  title: string
  impact: string | null
  actual: string | null
  forecast: string | null
  previous: string | null
  source: string
  fetched_at: string
}

export interface MapCountry {
  code: string
  name: string
  currency: string
  group: string
  geo: string[]
  point: [number, number] | null
  member_of: string | null
  note: string | null
  values: {
    policy_rate: IndState
    cpi_yoy: IndState
    y10: IndState
    real_rate: IndState
    fx: FxState
  }
  national: Record<string, IndState>
  next_event: CalEvent | null
}

export interface MapData {
  countries: MapCountry[]
  metrics: { id: string; name: string; unit: string }[]
}

export interface Section extends IndState {
  history: Point[]
  forecast_from: number | null
}

export interface CountryBlock {
  code: string
  name: string
  macro: Section[]
  budget: Section[]
  micro: Section[]
}

export interface CountryDetail {
  code: string
  name: string
  currency: string
  member_of: string | null
  note: string | null
  summary: MapCountry['values']
  cb: {
    name: string
    next_meeting: { date: string; source: string; title?: string } | null
    decisions: { date: string; from: number; to: number; change_bp: number }[]
  }
  blocks: CountryBlock[]
  calendar: CalEvent[]
}

export interface SourceRow {
  series_id: string
  name?: string
  group?: string
  source: string | null
  last_attempt: string | null
  last_success: string | null
  last_error: string | null
  last_date?: string | null
}

export interface Sources {
  series: SourceRow[]
  countries: { total: number; ok: number; failed: SourceRow[] }
  calendars: SourceRow[]
  fed_futures: SourceRow[]
  adapters: { name: string; label: string; homepage: string; needs_key: string | null; key_set: boolean }[]
}

export interface Status {
  last_refresh: RefreshLog | null
  running: Record<string, boolean>
  next_runs: Record<string, string | null>
  timezone: string
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.json() as Promise<T>
}

export const api = {
  dashboard: () => req<Dashboard>('/dashboard'),
  series: (id: string, period: string) => req<ChartSeries>(`/series/${id}?period=${period}`),
  spreads: (period: string) => req<{ left: ChartSeries[]; right: ChartSeries }>(`/charts/spreads?period=${period}`),
  refresh: (job = 'all') => req<{ started: string }>(`/refresh?job=${job}`, { method: 'POST' }),
  status: () => req<Status>('/status'),
  sources: () => req<Sources>('/sources'),
  rules: () => req<AlertRule[]>('/alerts/rules'),
  updateRule: (id: string, body: { enabled?: boolean; params?: Record<string, number> }) =>
    req<AlertRule>(`/alerts/rules/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  events: (limit = 100) => req<AlertEvent[]>(`/alerts/events?limit=${limit}`),
  map: () => req<MapData>('/map'),
  country: (code: string) => req<CountryDetail>(`/map/country/${code}`),
}
