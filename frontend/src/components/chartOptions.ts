import type { ChartSeries } from '../lib/api'
import { fmtNum, fmtObsDate } from '../lib/format'
import { C } from '../lib/theme'

const axisCommon = {
  axisLine: { lineStyle: { color: C.grid } },
  axisTick: { show: false },
  axisLabel: { color: C.axis, fontSize: 11 },
  splitLine: { lineStyle: { color: C.grid } },
}

export function tooltipBase() {
  return {
    trigger: 'axis',
    axisPointer: { type: 'line', lineStyle: { color: C.axis, type: 'dashed' } },
    backgroundColor: '#232321',
    borderColor: '#33332f',
    textStyle: { color: C.text, fontSize: 12 },
  }
}

export function lineOption(series: ChartSeries[], opts: { rightAxis?: ChartSeries; yName?: string } = {}) {
  const colors = [C.s1, C.s2, C.s3]
  const all = opts.rightAxis ? [...series, opts.rightAxis] : series
  const decimalsOf = (name: string) => all.find((s) => s.name === name)?.decimals ?? 2
  return {
    animation: false,
    color: colors,
    grid: { left: 8, right: opts.rightAxis ? 8 : 16, top: 36, bottom: 56, containLabel: true },
    legend: all.length > 1 ? { top: 0, textStyle: { color: C.text2 }, icon: 'roundRect', itemWidth: 12, itemHeight: 4 } : undefined,
    tooltip: {
      ...tooltipBase(),
      valueFormatter: undefined,
      formatter: (ps: any[]) => {
        const d = fmtObsDate(ps[0]?.value?.[0])
        const rows = ps.map((p) => `${p.marker}${p.seriesName}: <b>${fmtNum(p.value[1], decimalsOf(p.seriesName))}</b>`)
        return [d, ...rows].join('<br/>')
      },
    },
    xAxis: { type: 'time', ...axisCommon, splitLine: { show: false } },
    yAxis: [
      { type: 'value', scale: true, name: opts.yName, nameTextStyle: { color: C.axis }, ...axisCommon },
      ...(opts.rightAxis ? [{ type: 'value', scale: true, name: opts.rightAxis.name, position: 'right',
        nameTextStyle: { color: C.axis }, ...axisCommon, splitLine: { show: false } }] : []),
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8, borderColor: C.grid,
      textStyle: { color: C.axis }, fillerColor: 'rgba(57,135,229,0.15)' }],
    series: all.map((s, i) => ({
      name: s.name, type: 'line', showSymbol: false, data: s.points, yAxisIndex: opts.rightAxis && i === all.length - 1 ? 1 : 0,
      lineStyle: { width: 2 }, emphasis: { focus: 'series' },
      ...(s.unit === 'USD m' ? { type: 'bar', barMaxWidth: 6, itemStyle: { borderRadius: [2, 2, 0, 0],
        color: (p: any) => (p.value[1] >= 0 ? C.s1 : C.s2) } } : {}),
    })),
  }
}
