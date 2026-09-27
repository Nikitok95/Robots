import type { AlertEvent, AlertRule } from '../lib/api'
import { fmtObsDate } from '../lib/format'

export default function AlertsFeed({ rules, events, onOpenRules }: {
  rules: AlertRule[]; events: AlertEvent[]; onOpenRules: () => void
}) {
  const active = rules.filter((r) => r.active)
  const names = Object.fromEntries(rules.map((r) => [r.id, r.name]))
  return (
    <section className="rounded-xl border border-line bg-s1 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Алерты</h2>
        <button onClick={onOpenRules} className="text-xs text-accent hover:underline">Настроить правила →</button>
      </div>
      {active.length > 0 ? (
        <div className="mb-2 flex flex-col gap-1.5">
          {active.map((r) => (
            <div key={r.id} className="flex items-start gap-2 rounded-lg border border-crit/50 bg-crit/10 px-2.5 py-1.5 text-sm">
              <span className="text-crit">⚑</span>
              <div><b>{r.name}</b> <span className="text-ink2">— {r.last_message}</span></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mb-2 flex items-center gap-2 text-sm text-ink2"><span className="text-good">✓</span> Активных сигналов нет</div>
      )}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {events.length === 0 && <span className="text-xs text-mute">Лента событий пуста</span>}
        {events.map((e) => (
          <div key={e.id} className="min-w-64 max-w-80 shrink-0 rounded-lg bg-s2 px-2.5 py-1.5 text-xs">
            <div className="num text-mute">{fmtObsDate(e.date)} · {names[e.rule_id] ?? e.rule_id}</div>
            <div className="text-ink2">{e.message}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
