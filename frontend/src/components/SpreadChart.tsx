import { useEffect, useMemo, useState } from 'react'
import { api, type ChartSeries } from '../lib/api'
import EChart from './EChart'
import { lineOption } from './chartOptions'
import PeriodTabs, { type Period } from './PeriodTabs'
import SourceTag from './SourceTag'

export default function SpreadChart() {
  const [period, setPeriod] = useState<Period>('1Y')
  const [data, setData] = useState<{ left: ChartSeries[]; right: ChartSeries } | null>(null)
  useEffect(() => { api.spreads(period).then(setData).catch(() => setData(null)) }, [period])
  const option = useMemo(() => (data ? lineOption(data.left, { rightAxis: data.right, yName: 'спред, %' }) : null), [data])
  const empty = data && data.left.every((s) => !s.points.length)
  return (
    <div className="rounded-xl border border-line bg-s1 p-3 sm:col-span-2 lg:col-span-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-ink2">Спреды US − JGB (левая ось) и USD/JPY (правая ось)</span>
        <PeriodTabs value={period} onChange={setPeriod} />
      </div>
      {empty ? <div className="py-12 text-center text-sm text-mute">Нет данных — дождитесь первой загрузки FRED и Минфина Японии</div>
        : option && <EChart option={option} className="h-80 w-full" />}
      {data && <SourceTag source={[...data.left.flatMap((s) => s.sources), ...data.right.sources].filter((v, i, a) => a.indexOf(v) === i).join(' · ')} />}
    </div>
  )
}
