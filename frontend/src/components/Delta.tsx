import { fmtChange } from '../lib/format'

export default function Delta({ label, value, mode, decimals }: {
  label: string; value: number | null; mode: 'bp' | 'pct' | 'abs'; decimals: number
}) {
  const dir = value === null || value === 0 ? 0 : value > 0 ? 1 : -1
  const arrow = dir > 0 ? '▲' : dir < 0 ? '▼' : ''
  const tone = dir > 0 ? 'text-good' : dir < 0 ? 'text-crit' : 'text-mute'
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wide text-mute">{label}</span>
      <span className="num text-xs text-ink2">
        <span className={`${tone} mr-0.5 text-[9px]`}>{arrow}</span>
        {fmtChange(value, mode, decimals)}
      </span>
    </div>
  )
}
