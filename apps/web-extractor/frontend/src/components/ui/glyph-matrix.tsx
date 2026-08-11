import { useEffect, useRef } from "react"

import { cn } from "@/lib/utils"

interface GlyphMatrixProps extends React.HTMLAttributes<HTMLCanvasElement> {
  glyphs?: string
  cellSize?: number
  mutationRate?: number
  interval?: number
  driftSpeed?: number
  fadeBottom?: number
  color?: string
}

/** A low-overhead matrix of glyph columns that continuously drift downward. */
export function GlyphMatrix({
  glyphs = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
  cellSize = 14,
  mutationRate = 0.04,
  interval = 90,
  driftSpeed = 14,
  className,
  fadeBottom = 0.6,
  color = "#6b7280",
  style,
  ...props
}: GlyphMatrixProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const rgbaRef = useRef({ r: 107, g: 114, b: 128, a: 1 })

  useEffect(() => {
    const probe = document.createElement("canvas")
    probe.width = 1
    probe.height = 1
    const probeContext = probe.getContext("2d")
    if (!probeContext) return

    probeContext.fillStyle = "#6b7280"
    probeContext.fillStyle = color
    probeContext.fillRect(0, 0, 1, 1)
    const [r, g, b, a] = probeContext.getImageData(0, 0, 1, 1).data
    rgbaRef.current = { r, g, b, a: a / 255 }
  }, [color])

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext("2d")
    if (!canvas || !context || !glyphs.length) return

    let columns = 0
    let rows = 0
    let cells: string[] = []
    let alphas = new Float32Array()
    let columnOffsets = new Float32Array()
    let columnSpeeds = new Float32Array()
    let timer: number | undefined
    let stopped = false
    let previousTime = performance.now()
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)")

    const resize = () => {
      // A modest cap keeps the full-window canvas crisp without multiplying
      // its memory and paint cost on high-DPI Windows displays.
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
      const width = canvas.clientWidth
      const height = canvas.clientHeight

      canvas.width = Math.max(1, Math.round(width * dpr))
      canvas.height = Math.max(1, Math.round(height * dpr))
      context.setTransform(dpr, 0, 0, dpr, 0, 0)

      columns = Math.ceil(width / cellSize)
      rows = Math.ceil(height / cellSize) + 1
      const total = columns * rows
      cells = Array.from(
        { length: total },
        () => glyphs[Math.floor(Math.random() * glyphs.length)],
      )
      alphas = Float32Array.from(
        { length: total },
        () => 0.14 + Math.random() * 0.42,
      )
      const gridHeight = rows * cellSize
      columnOffsets = Float32Array.from(
        { length: columns },
        () => Math.random() * gridHeight,
      )
      columnSpeeds = Float32Array.from(
        { length: columns },
        () => driftSpeed * (0.65 + Math.random() * 0.7),
      )
      previousTime = performance.now()
    }

    const draw = () => {
      const width = canvas.clientWidth
      const height = canvas.clientHeight
      context.clearRect(0, 0, width, height)
      context.font = `${cellSize - 2}px ui-monospace, SFMono-Regular, Consolas, Menlo, monospace`
      context.textBaseline = "top"

      const { r, g, b, a: colorAlpha } = rgbaRef.current
      const gridHeight = rows * cellSize
      for (let x = 0; x < columns; x += 1) {
        for (let y = 0; y < rows; y += 1) {
          const drawY = (y * cellSize + columnOffsets[x]) % gridHeight
          if (drawY > height) continue
          const fade = fadeBottom > 0 ? 1 - (drawY / height) * fadeBottom : 1
          const index = y * columns + x
          const alpha = alphas[index] * fade * colorAlpha
          context.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`
          context.fillText(cells[index], x * cellSize, drawY)
        }
      }
    }

    const schedule = () => {
      if (stopped || document.hidden) return
      timer = window.setTimeout(tick, interval)
    }

    const tick = () => {
      if (stopped) return
      const now = performance.now()
      const elapsedSeconds = Math.min(0.25, (now - previousTime) / 1000)
      previousTime = now
      // Windows maps its "Animation effects" preference to reduced motion.
      // Keep the requested living background, but make it gentler instead of
      // turning the canvas into an unexpectedly static image.
      const motionScale = reducedMotion.matches ? 0.35 : 1
      const gridHeight = rows * cellSize
      for (let x = 0; x < columns; x += 1) {
        columnOffsets[x] = (columnOffsets[x] + columnSpeeds[x] * elapsedSeconds * motionScale) % gridHeight
      }
      const total = columns * rows
      const effectiveMutationRate = mutationRate * (reducedMotion.matches ? 0.25 : 1)
      const mutations = Math.max(1, Math.floor(total * effectiveMutationRate))
      for (let count = 0; count < mutations; count += 1) {
        const index = Math.floor(Math.random() * total)
        cells[index] = glyphs[Math.floor(Math.random() * glyphs.length)]
        alphas[index] = 0.14 + Math.random() * 0.46
      }
      draw()
      schedule()
    }

    const restart = () => {
      if (timer !== undefined) window.clearTimeout(timer)
      previousTime = performance.now()
      draw()
      schedule()
    }

    resize()
    draw()
    schedule()

    const resizeObserver = new ResizeObserver(() => {
      resize()
      draw()
    })
    resizeObserver.observe(canvas)
    document.addEventListener("visibilitychange", restart)
    reducedMotion.addEventListener("change", restart)

    return () => {
      stopped = true
      if (timer !== undefined) window.clearTimeout(timer)
      resizeObserver.disconnect()
      document.removeEventListener("visibilitychange", restart)
      reducedMotion.removeEventListener("change", restart)
    }
  }, [glyphs, cellSize, mutationRate, interval, driftSpeed, fadeBottom, color])

  return (
    <canvas
      ref={canvasRef}
      className={cn("pointer-events-none", className)}
      style={{ width: "100%", height: "100%", display: "block", ...style }}
      aria-hidden="true"
      {...props}
    />
  )
}
