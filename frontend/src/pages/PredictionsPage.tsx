import { useEffect, useMemo, useState } from 'react'
import Sparkline from '../components/Sparkline'
import { api, type PmEvent, type PmOutcome, type Predictions } from '../lib/api'
import { fmtDate, fmtDateTime, fmtNum } from '../lib/format'

const pct = (p: number) => `${fmtNum(p * 100, p < 0.1 && p > 0 ? 1 : 0)}%`

function fmtUsd(v: number): string {
  if (v >= 1e9) return `$${fmtNum(v / 1e9, 1)} млрд`
  if (v >= 1e6) return `$${fmtNum(v / 1e6, 1)} млн`
  return `$${fmtNum(v / 1e3, 0)} тыс.`
}

/** Change of a probability in percentage points. */
function Pp({ label, v }: { label: string; v: number | null }) {
  if (v === null || v === undefined) return null
  const pp = v * 100
  const tone = Math.abs(pp) < 0.5 ? 'text-mute' : pp > 0 ? 'text-good' : 'text-crit'
  return (
    <span className="num text-[11px] text-mute">
      {label} <span className={tone}>{pp > 0 ? '+' : pp < 0 ? '−' : ''}{fmtNum(Math.abs(pp), Math.abs(pp) < 10 ? 1 : 0)} п.п.</span>
    </span>
  )
}

function OutcomeRow({ o, lead }: { o: PmOutcome; lead: boolean }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className={`min-w-0 truncate ${lead ? 'font-medium text-ink' : 'text-ink2'}`} title={o.question}>{o.label}</span>
        <span className="num shrink-0 font-semibold text-ink">{pct(o.prob)}</span>
      </div>
      <div className="mt-0.5 h-1.5 rounded-full bg-s0">
        <div className={`h-1.5 rounded-full ${lead ? 'bg-accent' : 'bg-accent/40'}`} style={{ width: `${Math.max(1.5, o.prob * 100)}%` }} />
      </div>
    </div>
  )
}

function EventCard({ e }: { e: PmEvent }) {
  const [all, setAll] = useState(false)
  const lead = e.outcomes[0]
  const shown = all ? e.outcomes : e.outcomes.slice(0, 4)
  const points = useMemo(() => e.history.map(([d, p]) => [d, p * 100] as [string, number]), [e.history])
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-xl border border-line bg-s1 p-3">
      <a href={e.url} target="_blank" rel="noreferrer" className="text-sm font-medium leading-snug hover:text-accent">{e.title}</a>
      <div className="flex flex-wrap gap-x-3 text-[11px] text-mute">
        <span>объём <span className="num text-ink2">{fmtUsd(e.volume)}</span></span>
        {e.volume_24h > 0 && <span>за сутки <span className="num text-ink2">{fmtUsd(e.volume_24h)}</span></span>}
        {e.end_date && <span>до <span className="num text-ink2">{fmtDate(e.end_date + 'T12:00:00Z')}</span></span>}
      </div>
      <div className="flex flex-col gap-1.5">
        {shown.map((o, i) => <OutcomeRow key={o.id} o={o} lead={i === 0} />)}
      </div>
      {e.outcomes.length > 4 && (
        <button onClick={() => setAll(!all)} className="self-start text-[11px] text-accent">
          {all ? 'свернуть' : `ещё ${e.outcomes.length - 4}`}
        </button>
      )}
      {e.n_outcomes > e.outcomes.length && <div className="text-[11px] text-mute">всего исходов: {e.n_outcomes}, показаны самые вероятные</div>}
      <div className="mt-auto border-t border-line/60 pt-2">
        <div className="mb-1 flex flex-wrap items-baseline gap-x-3">
          <span className="min-w-0 truncate text-[11px] text-ink2">«{lead.label}»</span>
          <Pp label="1д" v={lead.d1} /><Pp label="1н" v={lead.w1} /><Pp label="1м" v={lead.m1} />
        </div>
        <Sparkline points={points} />
      </div>
    </div>
  )
}

function FedCompare({ c }: { c: NonNullable<Predictions['fed_compare']> }) {
  return (
    <section className="rounded-xl border border-line bg-s1 p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold">ФРС {fmtDate(c.meeting + 'T12:00:00Z')}: Polymarket против фьючерсов</h3>
        <a href={c.url} target="_blank" rel="noreferrer" className="text-xs text-accent">{c.event}</a>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="text-left text-xs text-mute"><tr>
            <th className="py-1">Решение</th><th>Polymarket</th><th>Фьючерсы ZQ</th><th className="text-right">Разница</th>
          </tr></thead>
          <tbody>
            {c.rows.map((r) => {
              const diff = r.futures === null ? null : (r.polymarket - r.futures) * 100
              return (
                <tr key={r.label} className="border-t border-line/60">
                  <td className="py-1.5 pr-2">{r.change_bp === 0 ? 'без изменений' : `${r.change_bp > 0 ? '+' : '−'}${Math.abs(r.change_bp)}${r.plus ? '+' : ''} б.п.`}</td>
                  <td className="num w-1/4 pr-2">
                    <div className="flex items-center gap-2"><span className="w-12">{pct(r.polymarket)}</span>
                      <div className="h-1.5 flex-1 rounded-full bg-s0"><div className="h-1.5 rounded-full bg-accent" style={{ width: `${Math.max(1, r.polymarket * 100)}%` }} /></div></div>
                  </td>
                  <td className="num w-1/4 pr-2">
                    {r.futures === null ? '—' : <div className="flex items-center gap-2"><span className="w-12">{pct(r.futures)}</span>
                      <div className="h-1.5 flex-1 rounded-full bg-s0"><div className="h-1.5 rounded-full bg-ink2/60" style={{ width: `${Math.max(1, r.futures * 100)}%` }} /></div></div>}
                  </td>
                  <td className={`num text-right ${diff !== null && Math.abs(diff) >= 10 ? 'font-semibold text-warn' : 'text-ink2'}`}>
                    {diff === null ? '—' : `${diff > 0 ? '+' : diff < 0 ? '−' : ''}${fmtNum(Math.abs(diff), 0)} п.п.`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {c.futures_error && <div className="mt-2 text-xs text-crit">Фьючерсы: {c.futures_error}</div>}
      <div className="mt-2 text-[11px] text-ink2/80">ⓘ Расхождение от 10 п.п. выделено: рынок ставок и фьючерсы по-разному видят ближайшее решение.</div>
    </section>
  )
}

export default function PredictionsPage() {
  const [d, setD] = useState<Predictions | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [sec, setSec] = useState<string>('all')
  const [q, setQ] = useState('')
  useEffect(() => { api.predictions().then(setD).catch((e) => setErr(String(e))) }, [])
  if (err) return <div className="text-crit">Нет связи с API: {err}</div>
  if (!d) return <div className="text-mute">Загрузка…</div>
  const needle = q.trim().toLowerCase()
  const match = (e: PmEvent) => !needle || e.title.toLowerCase().includes(needle)
    || e.outcomes.some((o) => o.label.toLowerCase().includes(needle))
  const total = d.sections.reduce((n, s) => n + s.events.length, 0)
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-ink2">
          Вероятности с рынков предсказаний <a href={d.homepage} target="_blank" rel="noreferrer" className="text-accent">{d.source}</a>: цена исхода = вероятность в глазах рынка.
          Только открытые события с объёмом от {fmtUsd(d.min_volume)}, обновление раз в час.
        </p>
        <span className="text-[11px] text-mute">данные на <span className="num text-ink2">{fmtDateTime(d.fetched_at)}</span></span>
      </div>
      {d.error && <div className="rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit">Последнее обновление не удалось: {d.error}. Показан прошлый снимок.</div>}
      {d.fed_compare && <FedCompare c={d.fed_compare} />}
      <div className="flex flex-wrap items-center gap-2">
        {[{ id: 'all', name: 'Все', n: total }, ...d.sections.map((s) => ({ id: s.id, name: s.name, n: s.events.length }))].map((t) => (
          <button key={t.id} onClick={() => setSec(t.id)}
                  className={`rounded-lg px-3 py-1.5 text-sm ${sec === t.id ? 'bg-s2 text-ink' : 'text-ink2 hover:text-ink'}`}>
            {t.name} <span className="num text-mute">{t.n}</span>
          </button>
        ))}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Поиск: Fed, Iran, France…"
               className="ml-auto w-full rounded-lg border border-line bg-s1 px-3 py-1.5 text-sm outline-none focus:border-accent sm:w-64" />
      </div>
      {d.sections.filter((s) => sec === 'all' || s.id === sec).map((s) => {
        const evs = s.events.filter(match)
        if (!evs.length) return null
        return (
          <section key={s.id}>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink2">{s.name}</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {evs.map((e) => <EventCard key={e.id} e={e} />)}
            </div>
          </section>
        )
      })}
      {total === 0 && <div className="text-mute">Снимок ещё не загружен: первое обновление идёт раз в час или по кнопке «Обновить сейчас».</div>}
    </div>
  )
}
