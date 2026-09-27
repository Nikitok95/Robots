import { fmtDateTime, fmtObsDate } from '../lib/format'

/** "Источник · дата данных · обновлено" line shown next to every value. */
export default function SourceTag({ source, date, fetchedAt, stale, reason, className = '' }: {
  source: string | null; date?: string | null; fetchedAt?: string | null
  stale?: boolean; reason?: string | null; className?: string
}) {
  return (
    <div className={`text-[11px] leading-snug text-mute ${className}`}>
      {stale && (
        <span className="mr-1 inline-flex items-center gap-1 rounded bg-warn/15 px-1.5 py-px font-medium text-warn"
              title={reason ?? ''}>⚠ устарело</span>
      )}
      <span title={source ?? ''}>{source ?? 'источник не получен'}</span>
      {date && <span> · данные на {fmtObsDate(date)}</span>}
      {fetchedAt && <span> · обновлено {fmtDateTime(fetchedAt)}</span>}
    </div>
  )
}
