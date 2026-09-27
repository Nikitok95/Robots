export const PERIODS = ['1M', '3M', '1Y', '5Y'] as const
export type Period = typeof PERIODS[number]

export default function PeriodTabs({ value, onChange }: { value: string; onChange: (p: Period) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-s2 p-0.5">
      {PERIODS.map((p) => (
        <button key={p} onClick={() => onChange(p)}
                className={`rounded-md px-3 py-1 text-xs font-medium ${value === p ? 'bg-accent text-white' : 'text-ink2 hover:text-ink'}`}>
          {p}
        </button>
      ))}
    </div>
  )
}
