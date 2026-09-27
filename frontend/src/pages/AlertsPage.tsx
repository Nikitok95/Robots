import { useEffect, useState } from 'react'
import { api, type AlertEvent, type AlertRule } from '../lib/api'
import { fmtDateTime, fmtObsDate } from '../lib/format'

const PARAM_LABELS: Record<string, string> = {
  usdjpy_drop_pct: 'Падение USD/JPY за день, %',
  etf_outflow_musd: 'Отток из ETF больше, млн $',
  real_yield_bp_1w: 'Рост US 10Y real за неделю, б.п.',
  move_rise_1w: 'Рост MOVE за неделю больше, пунктов',
  inflow_days: 'Дней притоков подряд',
  usdjpy_min: 'USD/JPY от',
  usdjpy_max: 'USD/JPY до',
  funding_max: 'Funding ниже, % (8ч)',
  funding_min: 'Funding выше, % (8ч)',
  oi_growth_pct_3d: 'Рост OI за 3 дня больше, %',
}

function RuleEditor({ rule, onSaved }: { rule: AlertRule; onSaved: (r: AlertRule) => void }) {
  const [params, setParams] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(rule.params).map(([k, v]) => [k, String(v)])))
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  async function save(enabled?: boolean) {
    setSaving(true); setMsg(null)
    try {
      const p = Object.fromEntries(Object.entries(params).map(([k, v]) => [k, Number(v.replace(',', '.'))]))
      if (Object.values(p).some((v) => Number.isNaN(v))) throw new Error('Введите числа')
      onSaved(await api.updateRule(rule.id, { params: p, ...(enabled !== undefined ? { enabled } : {}) }))
      setMsg('Сохранено')
    } catch (e) { setMsg(String(e)) } finally { setSaving(false) }
  }

  return (
    <div className={`rounded-xl border bg-s1 p-4 ${rule.active ? 'border-crit/60' : 'border-line'}`}>
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{rule.active && <span className="mr-1 text-crit">⚑</span>}{rule.name}</h3>
        <label className="flex items-center gap-2 text-sm text-ink2">
          <input type="checkbox" checked={rule.enabled} onChange={(e) => save(e.target.checked)} className="size-4 accent-[var(--accent)]" />
          включено
        </label>
      </div>
      <p className="mb-3 text-sm text-ink2">{rule.description}</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Object.keys(rule.params).map((k) => (
          <label key={k} className="flex flex-col gap-1 text-xs text-mute">
            {PARAM_LABELS[k] ?? k}
            <input value={params[k]} inputMode="decimal"
                   onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
                   className="num rounded-lg border border-line bg-s2 px-2.5 py-1.5 text-sm text-ink outline-none focus:border-accent" />
          </label>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button onClick={() => save()} disabled={saving} className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60">
          Сохранить пороги
        </button>
        {msg && <span className="text-xs text-ink2">{msg}</span>}
        <span className="ml-auto text-xs text-mute">{rule.active ? `Сейчас: ${rule.last_message}` : rule.last_message ? `Последняя проверка: ${rule.last_message}` : ''}</span>
      </div>
    </div>
  )
}

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([])
  const [events, setEvents] = useState<AlertEvent[]>([])
  const load = () => { api.rules().then(setRules); api.events(200).then(setEvents) }
  useEffect(load, [])
  const names = Object.fromEntries(rules.map((r) => [r.id, r.name]))
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink2">Пороги хранятся в базе. После сохранения правила пересчитываются за последние 60 дней, новые срабатывания попадают в ленту.</p>
      {rules.map((r) => <RuleEditor key={r.id} rule={r} onSaved={() => load()} />)}
      <section className="rounded-xl border border-line bg-s1 p-4">
        <h3 className="mb-2 font-semibold">Лента событий</h3>
        {events.length === 0 && <div className="text-sm text-mute">Срабатываний пока нет</div>}
        <div className="divide-y divide-line/70">
          {events.map((e) => (
            <div key={e.id} className="grid gap-1 py-2 text-sm sm:grid-cols-[110px_220px_1fr]">
              <span className="num text-ink2">{fmtObsDate(e.date)}</span>
              <span className="font-medium">{names[e.rule_id] ?? e.rule_id}</span>
              <span className="text-ink2">{e.message} <span className="text-[11px] text-mute">· записано {fmtDateTime(e.triggered_at)}</span></span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
