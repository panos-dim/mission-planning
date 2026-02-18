/**
 * SelectionIndicator — Custom entity selection indicator
 *
 * Rendered as a sibling of the Resium <Viewer>.
 * Uses direct DOM manipulation + Web Animations API for perfectly smooth
 * pulsing from frame 1 — no CSS animation cold-start stutter.
 */

import React, { useEffect, useRef } from 'react'
import { SceneTransforms, Cartesian2, defined, Viewer } from 'cesium'

interface SelectionIndicatorProps {
  viewerRef: React.RefObject<{ cesiumElement: Viewer | undefined } | null>
}

const scratchCartesian2 = new Cartesian2()

// Web Animations API keyframes for the two rings
const outerKeyframes: Keyframe[] = [
  { transform: 'translate(-50%, -50%) scale(1)', opacity: 1, borderColor: 'rgba(59, 130, 246, 1)' },
  {
    transform: 'translate(-50%, -50%) scale(1.15)',
    opacity: 0.7,
    borderColor: 'rgba(59, 130, 246, 0.8)',
  },
  { transform: 'translate(-50%, -50%) scale(1)', opacity: 1, borderColor: 'rgba(59, 130, 246, 1)' },
]
const innerKeyframes: Keyframe[] = [
  { transform: 'translate(-50%, -50%) scale(1)', opacity: 1, borderColor: 'rgba(96, 165, 250, 1)' },
  {
    transform: 'translate(-50%, -50%) scale(1.1)',
    opacity: 0.65,
    borderColor: 'rgba(96, 165, 250, 0.7)',
  },
  { transform: 'translate(-50%, -50%) scale(1)', opacity: 1, borderColor: 'rgba(96, 165, 250, 1)' },
]
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

    // Start Web Animations (paused initially)
    outerAnimRef.current = outerEl.animate(outerKeyframes, animOpts)
    innerAnimRef.current = innerEl.animate(innerKeyframes, { ...animOpts, delay: 300 })
    outerAnimRef.current.pause()
    innerAnimRef.current.pause()

    const hide = () => {
      el.style.opacity = '0'
    }

    const show = (x: number, y: number) => {
      el.style.opacity = '1'
      el.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`
    }

    const restartAnimations = () => {
      // Reset to frame 0 and play — instant smooth start
      if (outerAnimRef.current) {
        outerAnimRef.current.currentTime = 0
        outerAnimRef.current.play()
      }
      if (innerAnimRef.current) {
        innerAnimRef.current.currentTime = 0
        innerAnimRef.current.play()
      }
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

      // Detect target change → restart animations cleanly
      if (viewer.selectedEntity !== lastEntityRef.current) {
        lastEntityRef.current = viewer.selectedEntity
        restartAnimations()
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
