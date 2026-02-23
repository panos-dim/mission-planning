/**
 * SelectionIndicator — Custom entity selection indicator
 *
 * Rendered as a sibling of the Resium <Viewer>.
 * Uses direct DOM manipulation + Web Animations API for perfectly smooth
 * pulsing from frame 1 — no CSS animation cold-start stutter.
 */

import React, { useEffect, useRef } from 'react'
import { SceneTransforms, Cartesian2, defined, Viewer } from 'cesium'
import { getSatCssColor } from '../../utils/satelliteColors'

interface SelectionIndicatorProps {
  viewerRef: React.RefObject<{ cesiumElement: Viewer | undefined } | null>
}

const scratchCartesian2 = new Cartesian2()

// Default blue keyframes (non-satellite entities)
const DEFAULT_BLUE = 'rgba(59, 130, 246, 1)'
const DEFAULT_BLUE_DIM = 'rgba(59, 130, 246, 0.8)'
const DEFAULT_LIGHT = 'rgba(96, 165, 250, 1)'
const DEFAULT_LIGHT_DIM = 'rgba(96, 165, 250, 0.7)'

function makeOuterKeyframes(color: string, colorDim: string): Keyframe[] {
  return [
    { transform: 'translate(-50%, -50%) scale(1)', opacity: 1, borderColor: color },
    { transform: 'translate(-50%, -50%) scale(1.15)', opacity: 0.7, borderColor: colorDim },
    { transform: 'translate(-50%, -50%) scale(1)', opacity: 1, borderColor: color },
  ]
}
function makeInnerKeyframes(color: string, colorDim: string): Keyframe[] {
  return [
    { transform: 'translate(-50%, -50%) scale(1)', opacity: 1, borderColor: color },
    { transform: 'translate(-50%, -50%) scale(1.1)', opacity: 0.65, borderColor: colorDim },
    { transform: 'translate(-50%, -50%) scale(1)', opacity: 1, borderColor: color },
  ]
}

/**
 * Convert a hex CSS color to rgba strings at two opacity levels for keyframes.
 */
function hexToRgbaStrings(hex: string): [string, string] {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return [`rgba(${r}, ${g}, ${b}, 1)`, `rgba(${r}, ${g}, ${b}, 0.75)`]
}

const animOpts: KeyframeAnimationOptions = {
  duration: 2000,
  iterations: Infinity,
  easing: 'ease-in-out',
}

const SelectionIndicator: React.FC<SelectionIndicatorProps> = ({ viewerRef }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const outerRef = useRef<HTMLDivElement>(null)
  const innerRef = useRef<HTMLDivElement>(null)
  const rafRef = useRef<number | null>(null)
  const lastEntityRef = useRef<any>(null)
  const outerAnimRef = useRef<Animation | null>(null)
  const innerAnimRef = useRef<Animation | null>(null)

  useEffect(() => {
    const el = containerRef.current
    const outerEl = outerRef.current
    const innerEl = innerRef.current
    if (!el || !outerEl || !innerEl) return

    // Start Web Animations with default blue (paused initially)
    outerAnimRef.current = outerEl.animate(
      makeOuterKeyframes(DEFAULT_BLUE, DEFAULT_BLUE_DIM),
      animOpts,
    )
    innerAnimRef.current = innerEl.animate(
      makeInnerKeyframes(DEFAULT_LIGHT, DEFAULT_LIGHT_DIM),
      { ...animOpts, delay: 300 },
    )
    outerAnimRef.current.pause()
    innerAnimRef.current.pause()

    const hide = () => {
      el.style.opacity = '0'
    }

    const show = (x: number, y: number) => {
      el.style.opacity = '1'
      el.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`
    }

    const restartAnimations = (entityId?: string) => {
      // Determine color: satellite entities use their registered color
      let outerColor = DEFAULT_BLUE
      let outerDim = DEFAULT_BLUE_DIM
      let innerColor = DEFAULT_LIGHT
      let innerDim = DEFAULT_LIGHT_DIM

      if (entityId?.startsWith('sat_') && !entityId.includes('ground_track')) {
        const [full, dim] = hexToRgbaStrings(getSatCssColor(entityId))
        outerColor = full
        outerDim = dim
        innerColor = full
        innerDim = dim
      }

      // Cancel old animations and create new ones with updated colors
      outerAnimRef.current?.cancel()
      innerAnimRef.current?.cancel()
      outerAnimRef.current = outerEl.animate(
        makeOuterKeyframes(outerColor, outerDim),
        animOpts,
      )
      innerAnimRef.current = innerEl.animate(
        makeInnerKeyframes(innerColor, innerDim),
        { ...animOpts, delay: 300 },
      )
    }

    const tick = () => {
      const viewer = viewerRef.current?.cesiumElement
      if (!viewer?.selectedEntity) {
        hide()
        lastEntityRef.current = null
        outerAnimRef.current?.pause()
        innerAnimRef.current?.pause()
        rafRef.current = requestAnimationFrame(tick)
        return
      }

      // Detect target change → restart animations with entity-appropriate color
      if (viewer.selectedEntity !== lastEntityRef.current) {
        lastEntityRef.current = viewer.selectedEntity
        const eid = (viewer.selectedEntity as { id?: string }).id
        restartAnimations(eid)
      }

      try {
        const entityPos = viewer.selectedEntity.position?.getValue(viewer.clock.currentTime) ?? null

        if (!entityPos) {
          hide()
          rafRef.current = requestAnimationFrame(tick)
          return
        }

        const screen = SceneTransforms.worldToWindowCoordinates(
          viewer.scene,
          entityPos,
          scratchCartesian2,
        )

        if (defined(screen)) {
          const canvas = viewer.scene.canvas
          const onScreen =
            screen.x >= -40 &&
            screen.y >= -40 &&
            screen.x <= canvas.clientWidth + 40 &&
            screen.y <= canvas.clientHeight + 40

          if (onScreen) {
            show(screen.x, screen.y)
          } else {
            hide()
          }
        } else {
          hide()
        }
      } catch {
        hide()
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      outerAnimRef.current?.cancel()
      innerAnimRef.current?.cancel()
    }
  }, [viewerRef])

  return (
    <div
      ref={containerRef}
      className="pointer-events-none"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        zIndex: 50,
        willChange: 'transform, opacity',
        opacity: 0,
      }}
    >
      <div ref={outerRef} className="selection-ring selection-ring-outer" />
      <div ref={innerRef} className="selection-ring selection-ring-inner" />
      <div className="selection-crosshair" />
    </div>
  )
}

export default SelectionIndicator
