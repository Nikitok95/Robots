import { useEffect, useMemo, useState } from 'react'
import { api, type Card, type ChartSeries } from '../lib/api'
import { fmtNum, fmtObsDate } from '../lib/format'
import EChart from './EChart'
import { lineOption } from './chartOptions'
import Modal from './Modal'
import PeriodTabs, { type Period } from './PeriodTabs'
import SourceTag from './SourceTag'

export default function ChartModal({ card, onClose }: { card: Card; onClose: () => void }) {
  const [period, setPeriod] = useState<Period>('1Y')
  const [data, setData] = useState<ChartSeries | null>(null)
  const [table, setTable] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setErr(null)
    api.series(card.id, period).then(setData).catch((e) => setErr(String(e)))
  }, [card.id, period])

  const option = useMemo(() => (data ? lineOption([data]) : null), [data])

  return (
    <Modal title={card.name} onClose={onClose} wide>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <PeriodTabs value={period} onChange={setPeriod} />
        <button onClick={() => setTable((t) => !t)} className="rounded-lg border border-line px-3 py-1 text-xs text-ink2 hover:text-ink">
          {table ? 'График' : 'Таблица'}
        </button>
      </div>
      {card.note && <div className="mb-2 rounded-lg bg-s2 px-3 py-2 text-xs text-ink2">ⓘ {card.note}</div>}
      {err && <div className="text-sm text-crit">{err}</div>}
      {data && !data.points.length && <div className="py-16 text-center text-mute">Нет данных за период</div>}
      {data && data.points.length > 0 && (table ? (
        <div className="max-h-[60vh] overflow-y-auto">
          <table className="num w-full text-sm">
            <thead className="sticky top-0 bg-s1 text-left text-xs text-mute"><tr><th className="py-1">Дата</th><th className="py-1 text-right">Значение</th></tr></thead>
            <tbody>{[...data.points].reverse().map(([d, v]) => (
              <tr key={d} className="border-t border-line/60"><td className="py-1">{fmtObsDate(d)}</td><td className="py-1 text-right">{fmtNum(v, data.decimals)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      ) : option && <EChart option={option} className="h-[55vh] min-h-72 w-full" />)}
      <SourceTag className="mt-3" source={data?.sources.join(', ') || card.source} date={card.date}
                 fetchedAt={card.fetched_at} stale={card.stale} reason={card.stale_reason} />
    </Modal>
  )
}
