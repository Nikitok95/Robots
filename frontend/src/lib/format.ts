export const TZ = 'Europe/Madrid'

const dtf = new Intl.DateTimeFormat('ru-RU', {
  timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
})
const df = new Intl.DateTimeFormat('ru-RU', { timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric' })
const dfUtc = new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', day: '2-digit', month: '2-digit', year: 'numeric' })

/** ISO timestamp (UTC) -> Madrid local date+time */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : dtf.format(d)
}

/** Observation date (YYYY-MM-DD, calendar date of the data) -> dd.mm.yyyy */
export function fmtObsDate(s: string | null | undefined): string {
  if (!s) return '—'
  const d = new Date(`${s.slice(0, 10)}T00:00:00Z`)
  return Number.isNaN(d.getTime()) ? s : dfUtc.format(d)
}

/** Calendar event time -> Madrid date only */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : df.format(d)
}

export function fmtNum(v: number | null | undefined, decimals = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return v.toLocaleString('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function fmtValue(v: number | null | undefined, unit: string, decimals = 2): string {
  const n = fmtNum(v, decimals)
  if (n === '—') return n
  switch (unit) {
    case '%': return `${n}%`
    case 'bp': return `${n} б.п.`
    case 'USD': return `$${n}`
    case 'USD bn': return `$${n} млрд`
    case 'USD m': return `$${n} млн`
    case 'BTC': return `${n} BTC`
    case 'contracts': return `${n} контр.`
    default: return n
  }
}

export function fmtChange(v: number | null, mode: 'bp' | 'pct' | 'abs', decimals = 2): string {
  if (v === null || v === undefined) return '—'
  const sign = v > 0 ? '+' : v < 0 ? '−' : ''
  const a = Math.abs(v)
  if (mode === 'bp') return `${sign}${fmtNum(a, a < 10 ? 1 : 0)} б.п.`
  if (mode === 'pct') return `${sign}${fmtNum(a, 2)}%`
  return `${sign}${fmtNum(a, decimals)}`
}

export const monthYear = (s: string) => s.slice(0, 7)
