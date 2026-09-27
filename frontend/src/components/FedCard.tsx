import type { Dashboard } from '../lib/api'
import { fmtDate, fmtNum } from '../lib/format'
import SourceTag from './SourceTag'

export default function FedCard({ fed, bojNext }: { fed: Dashboard['fed']; bojNext: Dashboard['boj_next_meeting'] }) {
  return (
    <div className="flex min-w-0 flex-col gap-3 rounded-xl border border-line bg-s1 p-3 sm:col-span-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-ink2">Вероятности решений ФРС</span>
        {fed.target && <span className="num text-xs text-mute">текущий диапазон {fmtNum(fed.target[0])}–{fmtNum(fed.target[1])}% · EFFR {fmtNum(fed.effr ?? null)}%</span>}
      </div>
      {fed.error && <div className="text-sm text-crit">{fed.error}</div>}
      <div className="grid gap-3 sm:grid-cols-2">
        {(fed.meetings ?? []).map((m) => (
          <div key={m.date} className="rounded-lg bg-s2 p-2.5">
            <div className="mb-2 flex items-baseline justify-between">
              <span className="text-sm font-semibold">FOMC {fmtDate(m.date + 'T12:00:00Z')}</span>
              {m.expected_change_bp !== undefined && (
                <span className="num text-xs text-ink2">ожид. {m.expected_change_bp > 0 ? '+' : ''}{fmtNum(m.expected_change_bp, 1)} б.п.</span>
              )}
            </div>
            {m.error && <div className="text-xs text-crit">{m.error}</div>}
            {(m.distribution ?? []).map((d) => (
              <div key={d.change_bp} className="mb-1.5">
                <div className="num flex justify-between text-xs">
                  <span className="text-ink2">{fmtNum(d.low)}–{fmtNum(d.high)}% <span className="text-mute">({d.change_bp > 0 ? '+' : ''}{d.change_bp} б.п.)</span></span>
                  <span className="font-semibold text-ink">{fmtNum(d.prob * 100, 1)}%</span>
                </div>
                <div className="mt-0.5 h-1.5 rounded-full bg-s0">
                  <div className="h-1.5 rounded-full bg-accent" style={{ width: `${Math.max(2, d.prob * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="text-[11px] text-ink2/80">
        ⓘ Расчёт методом CME FedWatch из цен 30-Day Fed Funds futures ({Object.values(fed.contracts ?? {}).join(', ') || 'ZQ'}).
        Упрощённая модель: шаг 25 б.п., без учёта внеплановых заседаний.
      </div>
      <SourceTag source={fed.source ?? null} date={fed.as_of} />
      {bojNext && (
        <div className="border-t border-line pt-2 text-xs text-ink2">
          Следующее заседание BOJ: <b className="text-ink">{fmtDate(bojNext.date.length > 10 ? bojNext.date : bojNext.date + 'T12:00:00Z')}</b>
          <SourceTag source={bojNext.source} />
        </div>
      )}
    </div>
  )
}
