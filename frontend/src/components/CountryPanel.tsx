import { useEffect, useMemo, useState } from 'react'
import { api, type CountryBlock, type CountryDetail, type Section } from '../lib/api'
import { fmtDate, fmtDateTime, fmtNum, fmtObsDate, fmtValue } from '../lib/format'
import { C } from '../lib/theme'
import EChart from './EChart'
import SourceTag from './SourceTag'
import Sparkline from './Sparkline'
import { tooltipBase } from './chartOptions'

const TABS = [
  { id: 'macro', name: 'Макро' },
  { id: 'budget', name: 'Бюджет' },
  { id: 'micro', name: 'Микро' },
  { id: 'calendar', name: 'Календарь' },
] as const
type TabId = typeof TABS[number]['id']

function Item({ s }: { s: Section }) {
  const missing = s.value === null
  return (
    <div className="rounded-lg bg-s2 p-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-ink2">{s.name}</span>
        <span className="num text-lg font-semibold">{missing ? <span className="text-sm text-mute">нет данных</span> : fmtValue(s.value, s.unit === '% ВВП' ? '%' : s.unit, s.decimals)}</span>
      </div>
      {s.history.length > 1 && <Sparkline points={s.history} />}
      {s.note && <div className="text-[11px] text-ink2/80">ⓘ {s.note}</div>}
      {missing ? <div className="text-[11px] text-mute">{s.error ?? 'нет данных'}</div>
        : <SourceTag source={s.source} date={s.date} fetchedAt={s.fetched_at} stale={s.stale} reason={s.stale_reason} />}
    </div>
  )
}

function BudgetChart({ s }: { s: Section }) {
  const fc = s.forecast_from ?? 9999
  const actual = [...s.history].reverse().find((p) => Number(p[0].slice(0, 4)) < fc)
  const option = useMemo(() => ({
    animation: false,
    grid: { left: 4, right: 4, top: 16, bottom: 4, containLabel: true },
    tooltip: { ...tooltipBase(), trigger: 'item', formatter: (p: any) => `${p.name}: <b>${fmtNum(p.value, 1)}%</b>${Number(p.name) >= (s.forecast_from ?? 9999) ? ' (прогноз IMF)' : ''}` },
    xAxis: { type: 'category', data: s.history.map((p) => p[0].slice(0, 4)), axisLabel: { color: C.axis, fontSize: 10 }, axisTick: { show: false }, axisLine: { lineStyle: { color: C.grid } } },
    yAxis: { type: 'value', axisLabel: { color: C.axis, fontSize: 10 }, splitLine: { lineStyle: { color: C.grid } } },
    series: [{
      type: 'bar', barMaxWidth: 22, data: s.history.map((p) => ({
        value: p[1],
        itemStyle: {
          color: Number(p[0].slice(0, 4)) >= (s.forecast_from ?? 9999) ? 'rgba(57,135,229,0.35)' : C.s1,
          borderRadius: p[1] >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4],
        },
      })),
      label: { show: true, position: 'top', color: C.text2, fontSize: 10, formatter: (p: any) => fmtNum(p.value, 1) },
    }],
  }), [s])
  return (
    <div className="rounded-lg bg-s2 p-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-ink2">{s.name}</span>
        <span className="num font-semibold">{actual ? <>{fmtNum(actual[1], 1)}% <span className="text-xs font-normal text-mute">({actual[0].slice(0, 4)})</span></> : '—'}</span>
      </div>
      {s.history.length ? <EChart option={option} className="h-36 w-full" /> : <div className="py-4 text-xs text-mute">{s.error ?? 'нет данных'}</div>}
      <div className="text-[10px] text-mute">Полупрозрачные столбцы — прогноз IMF WEO</div>
      <SourceTag source={s.source} date={s.date} fetchedAt={s.fetched_at} stale={s.stale} reason={s.stale_reason} />
    </div>
  )
}

function Block({ b, tab, heading }: { b: CountryBlock; tab: 'macro' | 'budget' | 'micro'; heading: boolean }) {
  const items = b[tab]
  return (
    <div className="flex flex-col gap-2">
      {heading && <h4 className="mt-2 text-xs font-semibold uppercase tracking-wide text-ink2">{b.name}</h4>}
      {items.length === 0 && <div className="text-xs text-mute">Нет данных для {b.name}</div>}
      {tab === 'budget' ? items.map((s) => <BudgetChart key={s.indicator} s={s} />) : items.map((s) => <Item key={s.indicator} s={s} />)}
    </div>
  )
}

export default function CountryPanel({ code, onClose }: { code: string; onClose: () => void }) {
  const [d, setD] = useState<CountryDetail | null>(null)
  const [tab, setTab] = useState<TabId>('macro')
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { setD(null); api.country(code).then(setD).catch((e) => setErr(String(e))) }, [code])
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose}>
      <aside className="flex h-full w-full flex-col border-l border-line bg-s1 sm:max-w-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 border-b border-line p-4">
          <div>
            <div className="text-lg font-semibold">{d?.name ?? code} {d && <span className="text-mute">· {d.currency}</span>}</div>
            {d?.member_of && <div className="text-xs text-ink2">Член еврозоны: данные Еврозоны и национальные</div>}
            {d?.note && <div className="text-xs text-ink2">ⓘ {d.note}</div>}
          </div>
          <button onClick={onClose} className="px-2 text-2xl leading-none text-mute hover:text-ink" aria-label="Закрыть">×</button>
        </div>
        <div className="flex gap-1 border-b border-line px-3 py-2">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
                    className={`rounded-lg px-3 py-1.5 text-sm ${tab === t.id ? 'bg-s2 text-ink' : 'text-ink2 hover:text-ink'}`}>{t.name}</button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {err && <div className="text-sm text-crit">{err}</div>}
          {!d && !err && <div className="text-mute">Загрузка…</div>}
          {d && tab === 'macro' && (
            <div className="flex flex-col gap-3">
              <div className="rounded-lg border border-line p-3">
                <div className="mb-1 text-sm font-semibold">Центробанк {d.cb.name ? `(${d.cb.name})` : ''}</div>
                <div className="text-sm text-ink2">Ставка: <b className="num text-ink">{d.summary.policy_rate?.value != null ? `${fmtNum(d.summary.policy_rate.value)}%` : '—'}</b></div>
                <SourceTag source={d.summary.policy_rate?.source ?? null} date={d.summary.policy_rate?.date} stale={d.summary.policy_rate?.stale} />
                <div className="mt-1 text-sm text-ink2">Следующее заседание: <b className="text-ink">{d.cb.next_meeting ? fmtDate(d.cb.next_meeting.date.length > 10 ? d.cb.next_meeting.date : d.cb.next_meeting.date + 'T12:00:00Z') : 'нет данных'}</b></div>
                {d.cb.next_meeting && <SourceTag source={d.cb.next_meeting.source} />}
                {d.cb.decisions.length > 0 && (
                  <table className="num mt-2 w-full text-xs">
                    <thead className="text-left text-mute"><tr><th className="py-0.5">Дата</th><th>Было</th><th>Стало</th><th className="text-right">Изм.</th></tr></thead>
                    <tbody>{d.cb.decisions.map((x) => (
                      <tr key={x.date} className="border-t border-line/60">
                        <td className="py-0.5">{fmtObsDate(x.date)}</td><td>{fmtNum(x.from)}%</td><td>{fmtNum(x.to)}%</td>
                        <td className={`text-right ${x.change_bp > 0 ? 'text-good' : 'text-crit'}`}>{x.change_bp > 0 ? '▲ +' : '▼ '}{x.change_bp} б.п.</td>
                      </tr>
                    ))}</tbody>
                  </table>
                )}
              </div>
              {d.blocks.map((b) => <Block key={b.code} b={b} tab="macro" heading={d.blocks.length > 1} />)}
            </div>
          )}
          {d && (tab === 'budget' || tab === 'micro') && (
            <div className="flex flex-col gap-3">
              {tab === 'micro' && <div className="rounded-lg bg-s2 px-3 py-2 text-[11px] text-ink2">ⓘ PMI и рост зарплат — проприетарные данные: подключаются ключом Trading Economics (TRADINGECONOMICS_API_KEY). Бесплатная замена PMI — OECD Business Confidence.</div>}
              {d.blocks.map((b) => <Block key={b.code} b={b} tab={tab} heading={d.blocks.length > 1} />)}
            </div>
          )}
          {d && tab === 'calendar' && (
            <div>
              {d.calendar.length === 0 && <div className="text-sm text-mute">Нет событий на ближайшие 2 недели в подключённых календарях (Forex Factory покрывает USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD, CNY; для остальных нужен ключ TE или FMP).</div>}
              <div className="divide-y divide-line/70">
                {d.calendar.map((e) => (
                  <div key={e.id} className="py-2 text-sm">
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">{e.impact === 'High' && <span className="mr-1 text-crit" title="высокая важность">●</span>}{e.title}</span>
                      <span className="num shrink-0 text-xs text-ink2">{fmtDateTime(e.ts)}</span>
                    </div>
                    <div className="num text-xs text-ink2">Прогноз: <b className="text-ink">{e.forecast ?? '—'}</b> · Пред.: {e.previous ?? '—'}{e.actual ? ` · Факт: ${e.actual}` : ''}</div>
                    <SourceTag source={e.source} fetchedAt={e.fetched_at} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}
