import type { Card } from '../lib/api'
import { fmtValue } from '../lib/format'
import Delta from './Delta'
import SourceTag from './SourceTag'
import Sparkline from './Sparkline'

export default function MetricCard({ card, alert, onOpen }: { card: Card; alert: boolean; onOpen: () => void }) {
  const missing = card.value === null
  return (
    <button
      onClick={onOpen}
      className={`group flex min-w-0 flex-col gap-2 rounded-xl border bg-s1 p-3 text-left transition hover:border-accent/60 ${
        alert ? 'border-crit/70 ring-1 ring-crit/40' : 'border-line'}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-ink2">{card.name}</span>
        {alert && <span className="shrink-0 rounded bg-crit/20 px-1.5 text-[10px] font-semibold text-crit">⚑ алерт</span>}
      </div>
      <div className="num text-2xl font-semibold text-ink">
        {missing ? <span className="text-base text-mute">нет данных</span> : fmtValue(card.value, card.unit, card.decimals)}
      </div>
      <div className="grid grid-cols-3 gap-1">
        <Delta label="1D" value={card.changes.d1} mode={card.change_mode} decimals={card.decimals} />
        <Delta label="1W" value={card.changes.w1} mode={card.change_mode} decimals={card.decimals} />
        <Delta label="1M" value={card.changes.m1} mode={card.change_mode} decimals={card.decimals} />
      </div>
      <Sparkline points={card.spark} highlight={alert} />
      {card.note && <div className="text-[11px] text-ink2/80">ⓘ {card.note}</div>}
      <SourceTag source={card.source} date={card.date} fetchedAt={card.fetched_at}
                 stale={card.stale || (missing && !!card.error)} reason={card.stale_reason ?? card.error} />
      {missing && card.error && <div className="line-clamp-2 text-[11px] text-crit/90" title={card.error}>{card.error}</div>}
    </button>
  )
}
