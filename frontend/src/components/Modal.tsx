import { useEffect, type ReactNode } from 'react'

export default function Modal({ title, onClose, children, wide }: {
  title: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div className={`max-h-[92vh] w-full overflow-y-auto rounded-t-2xl border border-line bg-s1 p-4 sm:rounded-2xl ${wide ? 'sm:max-w-5xl' : 'sm:max-w-3xl'}`}
           onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-start justify-between gap-4">
          <div className="text-lg font-semibold">{title}</div>
          <button onClick={onClose} className="rounded-md px-2 text-2xl leading-none text-mute hover:text-ink" aria-label="Закрыть">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}
