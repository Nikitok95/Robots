import { useState } from 'react'
import AlertsFeed from '../components/AlertsFeed'
import ChartModal from '../components/ChartModal'
import FedCard from '../components/FedCard'
import MetricCard from '../components/MetricCard'
import SpreadChart from '../components/SpreadChart'
import type { Card, Dashboard } from '../lib/api'

export default function DashboardPage({ data, onOpenRules }: { data: Dashboard; onOpenRules: () => void }) {
  const [open, setOpen] = useState<Card | null>(null)
  const active = new Set(data.alerts.active_metrics)
  return (
    <div className="flex flex-col gap-5">
      <AlertsFeed rules={data.alerts.rules} events={data.alerts.events} onOpenRules={onOpenRules} />
      {data.groups.map((g) => (
        <section key={g.id}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink2">{g.name}</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {g.cards.filter((c) => c.id !== 'fed_next_exp_bp').map((c) => (
              <MetricCard key={c.id} card={c} alert={active.has(c.id)} onOpen={() => setOpen(c)} />
            ))}
            {g.id === 'rates' && <FedCard fed={data.fed} bojNext={data.boj_next_meeting} />}
            {g.id === 'rates' && (() => {
              const c = g.cards.find((x) => x.id === 'fed_next_exp_bp')
              return c ? <MetricCard card={c} alert={false} onOpen={() => setOpen(c)} /> : null
            })()}
            {g.id === 'spreads' && <SpreadChart />}
          </div>
        </section>
      ))}
      {open && <ChartModal card={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
