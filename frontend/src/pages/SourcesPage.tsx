import { useEffect, useState } from 'react'
import { api, type SourceRow, type Sources } from '../lib/api'
import { fmtDateTime, fmtObsDate } from '../lib/format'

function Row({ r }: { r: SourceRow }) {
  const ok = r.last_success && !r.last_error
  return (
    <tr className="border-t border-line/60 align-top">
      <td className="py-1.5 pr-2">{ok ? <span className="text-good">● OK</span> : r.last_attempt || r.last_error ? <span className="text-crit">● ошибка</span> : <span className="text-mute">○ не запускалось</span>}</td>
      <td className="py-1.5 pr-2 font-medium">{r.name ?? r.series_id}</td>
      <td className="py-1.5 pr-2 text-ink2">{r.source ?? '—'}</td>
      <td className="num py-1.5 pr-2 text-ink2">{r.last_date ? fmtObsDate(r.last_date) : '—'}</td>
      <td className="num py-1.5 pr-2 text-ink2">{fmtDateTime(r.last_success)}</td>
      <td className="max-w-md py-1.5 text-xs text-crit/90">{r.last_error}</td>
    </tr>
  )
}

function Table({ rows }: { rows: SourceRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[800px] text-sm">
        <thead className="text-left text-xs text-mute"><tr>
          <th className="py-1">Статус</th><th>Метрика</th><th>Источник</th><th>Данные на</th><th>Успешно</th><th>Ошибка</th>
        </tr></thead>
        <tbody>{rows.map((r) => <Row key={r.series_id} r={r} />)}</tbody>
      </table>
    </div>
  )
}

export default function SourcesPage() {
  const [s, setS] = useState<Sources | null>(null)
  useEffect(() => { api.sources().then(setS) }, [])
  if (!s) return <div className="text-mute">Загрузка…</div>
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink2">Живая проверка источников: статус последней загрузки каждой метрики. Используйте после деплоя, чтобы увидеть, какие endpoint'ы работают.</p>
      <section className="rounded-xl border border-line bg-s1 p-4">
        <h3 className="mb-2 font-semibold">Адаптеры и ключи</h3>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {s.adapters.map((a) => (
            <a key={a.name} href={a.homepage} target="_blank" rel="noreferrer" className="rounded-lg bg-s2 px-3 py-2 text-sm hover:ring-1 hover:ring-accent/50">
              <div className="font-medium">{a.label}</div>
              <div className="text-xs text-mute">{a.needs_key ? (a.key_set ? `ключ ${a.needs_key.toUpperCase()} задан` : `нужен ключ ${a.needs_key.toUpperCase()}`) : 'без ключа'}</div>
            </a>
          ))}
        </div>
      </section>
      <section className="rounded-xl border border-line bg-s1 p-4"><h3 className="mb-2 font-semibold">Метрики дашборда</h3><Table rows={s.series} /></section>
      <section className="rounded-xl border border-line bg-s1 p-4"><h3 className="mb-2 font-semibold">Фьючерсы на fed funds и календари</h3><Table rows={[...s.fed_futures, ...s.calendars]} /></section>
      <section className="rounded-xl border border-line bg-s1 p-4">
        <h3 className="mb-2 font-semibold">Данные карты: {s.countries.ok} из {s.countries.total} серий OK</h3>
        {s.countries.failed.length > 0 && <Table rows={s.countries.failed} />}
      </section>
    </div>
  )
}
