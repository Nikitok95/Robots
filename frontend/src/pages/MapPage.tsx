import * as echarts from 'echarts'
import { useEffect, useMemo, useState } from 'react'
import CountryPanel from '../components/CountryPanel'
import EChart from '../components/EChart'
import { api, type MapCountry, type MapData } from '../lib/api'
import { fmtChange, fmtDate, fmtNum } from '../lib/format'
import { C, DIV, SEQ } from '../lib/theme'

type MetricId = 'policy_rate' | 'cpi_yoy' | 'fx_1m' | 'real_rate'
const METRICS: { id: MetricId; name: string; diverging: boolean }[] = [
  { id: 'policy_rate', name: 'Ставка ЦБ', diverging: false },
  { id: 'cpi_yoy', name: 'Инфляция CPI г/г', diverging: false },
  { id: 'fx_1m', name: 'Валюта к USD, 1М', diverging: true },
  { id: 'real_rate', name: 'Реальная ставка', diverging: true },
]

function metricValue(c: MapCountry, m: MetricId): number | null {
  if (m === 'fx_1m') return c.values.fx?.strength_1m ?? null
  return c.values[m]?.value ?? null
}

const esc = (s: string) => s.replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]!))

function tooltipHtml(c: MapCountry, geoName: string): string {
  const v = c.values
  const small = (s: string | null | undefined) => (s ? `<span style="color:${C.muted};font-size:10px"> · ${esc(s)}</span>` : '')
  const row = (label: string, val: string, src?: string | null, stale?: boolean) =>
    `<div style="display:flex;justify-content:space-between;gap:12px"><span style="color:${C.text2}">${label}</span><span><b>${val}</b>${stale ? ' <span style="color:#fab219">⚠</span>' : ''}${small(src)}</span></div>`
  const title = c.member_of ? `${esc(geoName)} → Еврозона (EUR)` : `${esc(c.name)} (${esc(c.currency)})`
  const fx = v.fx
  const ev = c.next_event
  return [
    `<div style="font-weight:600;margin-bottom:4px">${title}</div>`,
    fx?.value != null
      ? row(fx.quote, `${fmtNum(fx.value, 4)} <span style="color:${C.muted}">1D ${fmtChange(fx.d1, 'pct')} · 1M ${fmtChange(fx.m1, 'pct')}</span>`, fx.source, fx.stale)
      : row('Курс', '—'),
    row('Ставка ЦБ', v.policy_rate?.value != null ? `${fmtNum(v.policy_rate.value)}%` : '—', v.policy_rate?.source, v.policy_rate?.stale),
    row('CPI г/г', v.cpi_yoy?.value != null ? `${fmtNum(v.cpi_yoy.value, 1)}%` : '—', v.cpi_yoy?.source, v.cpi_yoy?.stale),
    row('10Y', v.y10?.value != null ? `${fmtNum(v.y10.value)}%` : '—', v.y10?.source, v.y10?.stale),
    c.national?.cpi_yoy?.value != null ? row(`CPI ${esc(geoName)}`, `${fmtNum(c.national.cpi_yoy.value, 1)}%`, c.national.cpi_yoy.source) : '',
    ev ? `<div style="margin-top:4px;border-top:1px solid #33332f;padding-top:4px;color:${C.text2}">Ближайшее: <b style="color:${C.text}">${esc(ev.title)}</b> ${fmtDate(ev.ts)}${ev.forecast ? ` · прогноз ${esc(ev.forecast)}` : ''}${ev.previous ? ` · пред. ${esc(ev.previous)}` : ''}${small(ev.source)}</div>`
      : `<div style="margin-top:4px;color:${C.muted}">Событий календаря нет</div>`,
    c.note ? `<div style="color:${C.muted};font-size:11px;margin-top:2px">ⓘ ${esc(c.note)}</div>` : '',
  ].join('')
}

export default function MapPage() {
  const [geoReady, setGeoReady] = useState(false)
  const [data, setData] = useState<MapData | null>(null)
  const [metric, setMetric] = useState<MetricId>('policy_rate')
  const [selected, setSelected] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    fetch('/world.json').then((r) => r.json()).then((geo) => { echarts.registerMap('world', geo); setGeoReady(true) })
      .catch((e) => setErr(`GeoJSON: ${e}`))
    api.map().then(setData).catch((e) => setErr(String(e)))
  }, [])

  const byGeo = useMemo(() => {
    const m = new Map<string, MapCountry>()
    data?.countries.forEach((c) => c.geo.forEach((g) => m.set(g, c)))
    return m
  }, [data])

  const option = useMemo(() => {
    if (!data || !geoReady) return null
    const md = METRICS.find((m) => m.id === metric)!
    const regions = [...byGeo.entries()].map(([name, c]) => ({ name, value: metricValue(c, metric), code: c.code }))
    const points = data.countries.filter((c) => c.point).map((c) => ({
      name: c.name, value: [...c.point!, metricValue(c, metric) ?? '-'], code: c.code }))
    const vals = [...regions.map((r) => r.value), ...points.map((p) => p.value[2])].filter((v): v is number => typeof v === 'number')
    let min = Math.min(...vals), max = Math.max(...vals)
    if (md.diverging) { const a = Math.max(Math.abs(min), Math.abs(max), 0.5); min = -a; max = a }
    if (!vals.length) { min = 0; max = 1 }
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item', backgroundColor: '#232321', borderColor: '#33332f', textStyle: { color: C.text, fontSize: 12 },
        extraCssText: 'max-width:340px;white-space:normal',
        formatter: (p: any) => {
          const c = p.seriesType === 'scatter' ? data.countries.find((x) => x.code === p.data?.code) : byGeo.get(p.name)
          return c ? tooltipHtml(c, p.name) : `<span style="color:${C.muted}">${esc(p.name)} — нет в списке</span>`
        },
      },
      visualMap: {
        type: 'continuous', min, max, calculable: false, orient: 'horizontal', left: 'center', bottom: 4,
        itemWidth: 12, itemHeight: 200,
        text: [`${fmtNum(max, 1)}% ${md.id === 'fx_1m' ? 'сильнее' : 'выше'}`, `${md.id === 'fx_1m' ? 'слабее' : 'ниже'} ${fmtNum(min, 1)}%`],
        textStyle: { color: C.text2, fontSize: 11 }, seriesIndex: [0, 1],
        inRange: { color: md.diverging ? DIV : [...SEQ].reverse() },
        outOfRange: { color: C.noData },
        formatter: (v: number) => `${fmtNum(v, 1)}%`,
      },
      geo: {
        map: 'world', roam: true, zoom: 1.15, center: [15, 25], scaleLimit: { min: 1, max: 12 },
        itemStyle: { areaColor: C.noData, borderColor: '#121211', borderWidth: 0.5 },
        emphasis: { disabled: true },
        select: { disabled: true },
        regions: regions.filter((r) => r.value == null).map((r) => ({ name: r.name, itemStyle: { areaColor: '#3a3a36', borderColor: '#5c5c57' } })),
      },
      series: [
        { type: 'map', geoIndex: 0, data: regions },
        { type: 'scatter', coordinateSystem: 'geo', data: points, symbolSize: 14,
          itemStyle: { borderColor: C.text2, borderWidth: 1.5 }, label: { show: true, formatter: '{b}', position: 'right', color: C.text2, fontSize: 10 } },
      ],
    }
  }, [data, geoReady, metric, byGeo])

  const onEvents = useMemo(() => ({
    click: (p: any) => {
      const code = p.data?.code ?? byGeo.get(p.name)?.code
      if (code) setSelected(code)
    },
  }), [byGeo])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink2">Раскраска:</span>
        <div className="inline-flex flex-wrap rounded-lg border border-line bg-s2 p-0.5">
          {METRICS.map((m) => (
            <button key={m.id} onClick={() => setMetric(m.id)}
                    className={`rounded-md px-3 py-1 text-xs font-medium ${metric === m.id ? 'bg-accent text-white' : 'text-ink2 hover:text-ink'}`}>{m.name}</button>
          ))}
        </div>
        <span className="text-xs text-mute">Еврозона окрашена единым блоком EUR · серые — страны вне списка</span>
      </div>
      {err && <div className="text-sm text-crit">{err}</div>}
      <div className="relative rounded-xl border border-line bg-s1">
        {option ? <EChart option={option} onEvents={onEvents} className="h-[62vh] min-h-[380px] w-full" />
          : <div className="flex h-[62vh] items-center justify-center text-mute">Загрузка карты…</div>}
      </div>
      {data && (
        <div className="overflow-x-auto rounded-xl border border-line bg-s1 p-3">
          <table className="num w-full min-w-[720px] text-sm">
            <thead className="text-left text-xs text-mute"><tr>
              <th className="py-1">Страна</th><th>Курс к USD</th><th>1D</th><th>1M</th><th>Ставка ЦБ</th><th>CPI г/г</th><th>Реальная</th><th>10Y</th>
            </tr></thead>
            <tbody>{data.countries.filter((c) => !c.member_of).map((c) => (
              <tr key={c.code} onClick={() => setSelected(c.code)} className="cursor-pointer border-t border-line/60 hover:bg-s2">
                <td className="py-1.5 font-medium">{c.name} <span className="text-mute">{c.currency}</span></td>
                <td>{c.values.fx?.value != null ? `${c.values.fx.quote} ${fmtNum(c.values.fx.value, 4)}` : '—'}</td>
                <td>{fmtChange(c.values.fx?.d1 ?? null, 'pct')}</td>
                <td>{fmtChange(c.values.fx?.m1 ?? null, 'pct')}</td>
                <td>{c.values.policy_rate?.value != null ? `${fmtNum(c.values.policy_rate.value)}%` : '—'}</td>
                <td>{c.values.cpi_yoy?.value != null ? `${fmtNum(c.values.cpi_yoy.value, 1)}%` : '—'}</td>
                <td>{c.values.real_rate?.value != null ? `${fmtNum(c.values.real_rate.value)}%` : '—'}</td>
                <td>{c.values.y10?.value != null ? `${fmtNum(c.values.y10.value)}%` : '—'}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {selected && <CountryPanel code={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
