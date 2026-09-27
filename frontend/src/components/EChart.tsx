import * as echarts from 'echarts'
import { useEffect, useRef } from 'react'

interface Props {
  option: echarts.EChartsCoreOption
  className?: string
  onEvents?: Record<string, (p: any) => void>
  onInit?: (c: echarts.ECharts) => void
}

/** Minimal ECharts wrapper: resizes with its container, disposes on unmount. */
export default function EChart({ option, className, onEvents, onInit }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const c = echarts.init(ref.current, undefined, { renderer: 'canvas' })
    chart.current = c
    onInit?.(c)
    const ro = new ResizeObserver(() => c.resize())
    ro.observe(ref.current)
    return () => { ro.disconnect(); c.dispose(); chart.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { chart.current?.setOption(option, true) }, [option])

  useEffect(() => {
    const c = chart.current
    if (!c || !onEvents) return
    Object.entries(onEvents).forEach(([ev, fn]) => c.on(ev, fn))
    return () => { Object.keys(onEvents).forEach((ev) => c.off(ev)) }
  }, [onEvents])

  return <div ref={ref} className={className} />
}
