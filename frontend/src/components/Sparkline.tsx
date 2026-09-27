import { useMemo } from 'react'
import type { Point } from '../lib/api'
import { C } from '../lib/theme'
import EChart from './EChart'

export default function Sparkline({ points, highlight }: { points: Point[]; highlight?: boolean }) {
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 0, right: 0, top: 4, bottom: 2 },
    xAxis: { type: 'category', show: false, data: points.map((p) => p[0]) },
    yAxis: { type: 'value', show: false, scale: true },
    series: [{
      type: 'line', data: points.map((p) => p[1]), showSymbol: false, smooth: false,
      lineStyle: { width: 2, color: highlight ? C.s2 : C.s1 },
      areaStyle: { color: highlight ? 'rgba(217,89,38,0.10)' : 'rgba(57,135,229,0.10)' },
    }],
    tooltip: { show: false },
  }), [points, highlight])
  if (points.length < 2) return <div className="h-10 text-xs text-mute flex items-end">нет истории</div>
  return <EChart option={option} className="h-10 w-full" />
}
