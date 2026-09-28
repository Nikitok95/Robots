import { useEffect, useState } from 'react'
import { api, type Status } from '../lib/api'
import { fmtDateTime } from '../lib/format'

export const TABS = [
  { id: 'dashboard', name: 'Дашборд' },
  { id: 'map', name: 'Карта' },
  { id: 'predictions', name: 'Прогнозы' },
  { id: 'alerts', name: 'Алерты' },
  { id: 'sources', name: 'Источники' },
] as const
export type Tab = typeof TABS[number]['id']

export default function Header({ tab, onTab, onRefreshed }: { tab: Tab; onTab: (t: Tab) => void; onRefreshed: () => void }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () => api.status().then((s) => { setStatus(s); return s }).catch(() => null)
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t) }, [])

  const running = status && Object.keys(status.running).length > 0

  async function refresh() {
    setBusy(true)
    try {
      await api.refresh('all')
      // poll until the run finishes
      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 3000))
        const s = await load()
        if (s && Object.keys(s.running).length === 0) break
      }
      onRefreshed()
    } finally { setBusy(false) }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-s0/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5">
        <div className="text-base font-semibold tracking-tight">Macro Carry Monitor</div>
        <nav className="order-3 -mx-1 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => onTab(t.id)}
                    className={`shrink-0 rounded-lg px-3 py-1.5 text-sm ${tab === t.id ? 'bg-s2 text-ink' : 'text-ink2 hover:text-ink'}`}>
              {t.name}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <div className="text-right text-[11px] leading-tight text-mute">
            <div>Обновлено: <span className="num text-ink2">{fmtDateTime(status?.last_refresh?.finished_at)}</span></div>
            <div>Europe/Madrid{running ? ' · идёт загрузка…' : ''}</div>
          </div>
          <button onClick={refresh} disabled={busy}
                  className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60">
            {busy ? 'Обновляю…' : 'Обновить сейчас'}
          </button>
        </div>
      </div>
    </header>
  )
}
