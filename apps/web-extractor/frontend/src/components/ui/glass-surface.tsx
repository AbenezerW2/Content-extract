import { useCallback, useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react"

import "./glass-surface.css"

type Channel = "R" | "G" | "B"

type GlassSurfaceProps = {
  children?: ReactNode
  width?: number | string
  height?: number | string
  borderRadius?: number
  borderWidth?: number
  brightness?: number
  opacity?: number
  blur?: number
  displace?: number
  backgroundOpacity?: number
  saturation?: number
  distortionScale?: number
  redOffset?: number
  greenOffset?: number
  blueOffset?: number
  xChannel?: Channel
  yChannel?: Channel
  mixBlendMode?: CSSProperties["mixBlendMode"]
  className?: string
  style?: CSSProperties
}

type GlassStyle = CSSProperties & {
  "--glass-frost": number
  "--glass-saturation": number
  "--filter-id": string
}

function supportsSvgFilters(filterId: string) {
  if (typeof document === "undefined") return false
  const probe = document.createElement("div")
  probe.style.backdropFilter = `url(#${filterId})`
  return probe.style.backdropFilter !== ""
}

/** React Bits' liquid-glass surface, adapted for typed React and responsive cards. */
export function GlassSurface({
  children,
  width = 200,
  height = 80,
  borderRadius = 20,
  borderWidth = 0.07,
  brightness = 50,
  opacity = 0.93,
  blur = 11,
  displace = 0,
  backgroundOpacity = 0,
  saturation = 1,
  distortionScale = -180,
  redOffset = 0,
  greenOffset = 10,
  blueOffset = 20,
  xChannel = "R",
  yChannel = "G",
  mixBlendMode = "difference",
  className = "",
  style = {},
}: GlassSurfaceProps) {
  const uniqueId = useId().replace(/:/g, "-")
  const filterId = `glass-filter-${uniqueId}`
  const redGradientId = `red-gradient-${uniqueId}`
  const blueGradientId = `blue-gradient-${uniqueId}`
  const [svgSupported] = useState(() => supportsSvgFilters(filterId))
  const containerRef = useRef<HTMLDivElement | null>(null)
  const imageRef = useRef<SVGFEImageElement | null>(null)
  const redChannelRef = useRef<SVGFEDisplacementMapElement | null>(null)
  const greenChannelRef = useRef<SVGFEDisplacementMapElement | null>(null)
  const blueChannelRef = useRef<SVGFEDisplacementMapElement | null>(null)
  const blurRef = useRef<SVGFEGaussianBlurElement | null>(null)

  const generateDisplacementMap = useCallback(() => {
    const rectangle = containerRef.current?.getBoundingClientRect()
    const actualWidth = Math.max(1, rectangle?.width || 400)
    const actualHeight = Math.max(1, rectangle?.height || 200)
    const edgeSize = Math.min(actualWidth, actualHeight) * borderWidth * 0.5
    const innerWidth = Math.max(1, actualWidth - edgeSize * 2)
    const innerHeight = Math.max(1, actualHeight - edgeSize * 2)
    const svg = `
      <svg viewBox="0 0 ${actualWidth} ${actualHeight}" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="${redGradientId}" x1="100%" y1="0%" x2="0%" y2="0%">
            <stop offset="0%" stop-color="#0000"/><stop offset="100%" stop-color="red"/>
          </linearGradient>
          <linearGradient id="${blueGradientId}" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#0000"/><stop offset="100%" stop-color="blue"/>
          </linearGradient>
        </defs>
        <rect width="${actualWidth}" height="${actualHeight}" fill="black"/>
        <rect width="${actualWidth}" height="${actualHeight}" rx="${borderRadius}" fill="url(#${redGradientId})"/>
        <rect width="${actualWidth}" height="${actualHeight}" rx="${borderRadius}" fill="url(#${blueGradientId})" style="mix-blend-mode:${mixBlendMode}"/>
        <rect x="${edgeSize}" y="${edgeSize}" width="${innerWidth}" height="${innerHeight}" rx="${borderRadius}" fill="hsl(0 0% ${brightness}% / ${opacity})" style="filter:blur(${blur}px)"/>
      </svg>
    `
    return `data:image/svg+xml,${encodeURIComponent(svg)}`
  }, [blueGradientId, blur, borderRadius, borderWidth, brightness, mixBlendMode, opacity, redGradientId])

  const updateDisplacementMap = useCallback(() => {
    imageRef.current?.setAttribute("href", generateDisplacementMap())
  }, [generateDisplacementMap])

  useEffect(() => {
    updateDisplacementMap()
    const channels = [
      { ref: redChannelRef, offset: redOffset },
      { ref: greenChannelRef, offset: greenOffset },
      { ref: blueChannelRef, offset: blueOffset },
    ]
    for (const { ref, offset } of channels) {
      ref.current?.setAttribute("scale", String(distortionScale + offset))
      ref.current?.setAttribute("xChannelSelector", xChannel)
      ref.current?.setAttribute("yChannelSelector", yChannel)
    }
    blurRef.current?.setAttribute("stdDeviation", String(displace))
  }, [blueOffset, displace, distortionScale, greenOffset, redOffset, updateDisplacementMap, xChannel, yChannel])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let frame: number | undefined
    const resizeObserver = new ResizeObserver(() => {
      if (frame !== undefined) window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(updateDisplacementMap)
    })
    resizeObserver.observe(container)
    return () => {
      if (frame !== undefined) window.cancelAnimationFrame(frame)
      resizeObserver.disconnect()
    }
  }, [updateDisplacementMap])

  const containerStyle: GlassStyle = {
    ...style,
    width: typeof width === "number" ? `${width}px` : width,
    height: typeof height === "number" ? `${height}px` : height,
    borderRadius: `${borderRadius}px`,
    "--glass-frost": backgroundOpacity,
    "--glass-saturation": saturation,
    "--filter-id": `url(#${filterId})`,
  }

  return (
    <div ref={containerRef} className={`glass-surface ${svgSupported ? "glass-surface--svg" : "glass-surface--fallback"} ${className}`} style={containerStyle}>
      <svg className="glass-surface__filter" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <filter id={filterId} colorInterpolationFilters="sRGB" x="0%" y="0%" width="100%" height="100%">
            <feImage ref={imageRef} x="0" y="0" width="100%" height="100%" preserveAspectRatio="none" result="map" />
            <feDisplacementMap ref={redChannelRef} in="SourceGraphic" in2="map" result="displaced-red" />
            <feColorMatrix in="displaced-red" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="red" />
            <feDisplacementMap ref={greenChannelRef} in="SourceGraphic" in2="map" result="displaced-green" />
            <feColorMatrix in="displaced-green" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="green" />
            <feDisplacementMap ref={blueChannelRef} in="SourceGraphic" in2="map" result="displaced-blue" />
            <feColorMatrix in="displaced-blue" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="blue" />
            <feBlend in="red" in2="green" mode="screen" result="red-green" />
            <feBlend in="red-green" in2="blue" mode="screen" result="output" />
            <feGaussianBlur ref={blurRef} in="output" stdDeviation="0.7" />
          </filter>
        </defs>
      </svg>
      <div className="glass-surface__content">{children}</div>
    </div>
  )
}
