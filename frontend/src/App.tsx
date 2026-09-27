import { useCallback, useEffect, useState } from 'react'
import Header, { TABS, type Tab } from './components/Header'
import { api, type Dashboard } from './lib/api'
import AlertsPage from './pages/AlertsPage'
import DashboardPage from './pages/DashboardPage'
import MapPage from './pages/MapPage'
import SourcesPage from './pages/SourcesPage'

function tabFromHash(): Tab {
  const h = window.location.hash.replace('#', '')
  return (TABS.some((t) => t.id === h) ? h : 'dashboard') as Tab
}

export default function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash())
  const [dash, setDash] = useState<Dashboard | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  const load = useCallback(() => { api.dashboard().then((d) => { setDash(d); setErr(null) }).catch((e) => setErr(String(e))) }, [])
  useEffect(() => { load(); const t = setInterval(load, 5 * 60 * 1000); return () => clearInterval(t) }, [load])
  useEffect(() => {
    const h = () => setTab(tabFromHash())
    window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h)
  }, [])

  const go = (t: Tab) => { window.location.hash = t; setTab(t) }
  const refreshed = () => { load(); setVersion((v) => v + 1) }

  return (
    <div className="min-h-screen">
      <Header tab={tab} onTab={go} onRefreshed={refreshed} />
      <main className="mx-auto max-w-[1500px] px-4 py-4" key={`${tab}-${version}`}>
        {tab === 'dashboard' && (err ? <div className="text-crit">Нет связи с API: {err}</div>
          : dash ? <DashboardPage data={dash} onOpenRules={() => go('alerts')} /> : <div className="text-mute">Загрузка…</div>)}
        {tab === 'map' && <MapPage />}
        {tab === 'alerts' && <AlertsPage />}
        {tab === 'sources' && <SourcesPage />}
      </main>
    </div>
  )
}
