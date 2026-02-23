import React, { useEffect, useRef } from 'react'
import { useCesium } from 'resium'
import { Cartesian3, SceneTransforms } from 'cesium'
import { useShallow } from 'zustand/react/shallow'
import { useSlewVisStore } from '../../store/slewVisStore'
import { useMission } from '../../context/MissionContext'
import { scheduleToSlewArcs } from '../../utils/slewVisualization'

/**
 * Canvas-based overlay for slew visualization that works in 2D mode
 * without blocking Cesium's render thread
 */
export const SlewCanvasOverlay: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { viewer } = useCesium()
  const { enabled, activeSchedule, showSlewArcs, showSlewLabels } = useSlewVisStore(
    useShallow((s) => ({
      enabled: s.enabled,
      activeSchedule: s.activeSchedule,
      showSlewArcs: s.showSlewArcs,
      showSlewLabels: s.showSlewLabels,
    })),
  )
  const { state } = useMission()
  const animationStartTime = useRef<number>(performance.now())

  useEffect(() => {
    if (!viewer || !canvasRef.current || !enabled || !activeSchedule || !state.missionData) {
      return
    }

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Resize canvas to match viewport
    const resizeCanvas = () => {
      const container = viewer.container
      canvas.width = container.clientWidth
      canvas.height = container.clientHeight
    }
    resizeCanvas()

    // Listen for window resize (includes sidebar drag)
    const resizeObserver = new ResizeObserver(() => {
      resizeCanvas()
    })
    resizeObserver.observe(viewer.container)

    // PR-UI-024: Footprints/coverage removed — path only

    const slewArcs = showSlewArcs
      ? scheduleToSlewArcs(
          activeSchedule.schedule,
          state.missionData,
          viewer, // Pass viewer to get actual satellite position
        )
      : []

    // Render loop
    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Calculate animation time based on performance.now()
      const currentTime = performance.now()
      const animationTime = ((currentTime - animationStartTime.current) / 3000) % 1 // 3 second cycle

      // Draw slew arcs with sequence numbers
      slewArcs.forEach((arc, index) => {
        const fromPos = Cartesian3.fromDegrees(arc.fromLon, arc.fromLat, 0)
        const toPos = Cartesian3.fromDegrees(arc.toLon, arc.toLat, 0)

        const fromScreen = SceneTransforms.worldToWindowCoordinates(viewer.scene, fromPos)
        const toScreen = SceneTransforms.worldToWindowCoordinates(viewer.scene, toPos)

        if (!fromScreen || !toScreen) {
          return
        }

        // Parse color
        const colorMatch = arc.color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/)
        const color = colorMatch
          ? `rgba(${colorMatch[1]}, ${colorMatch[2]}, ${colorMatch[3]}, ${colorMatch[4] || '1'})`
          : 'rgba(168, 85, 247, 0.5)'

        // Draw main line
        ctx.beginPath()
        ctx.moveTo(fromScreen.x, fromScreen.y)
        ctx.lineTo(toScreen.x, toScreen.y)
        ctx.strokeStyle = color
        ctx.lineWidth = 3
        ctx.stroke()

        // Add animated light effect to show direction
        const lineLength = Math.sqrt(
          Math.pow(toScreen.x - fromScreen.x, 2) + Math.pow(toScreen.y - fromScreen.y, 2),
        )

        if (lineLength > 20) {
          // Only animate lines longer than 20 pixels
          // Calculate light position along the line (0 to 1)
          const lightProgress = (animationTime + index * 0.2) % 1 // Stagger animations
          const lightX = fromScreen.x + (toScreen.x - fromScreen.x) * lightProgress
          const lightY = fromScreen.y + (toScreen.y - fromScreen.y) * lightProgress

          // Draw single animated light dot
          ctx.beginPath()
          ctx.arc(lightX, lightY, 4, 0, 2 * Math.PI)
          ctx.fillStyle = 'rgba(255, 255, 255, 0.8)'
          ctx.fill()
        }
      })

      // PR-UI-024: Draw off-nadir labels below each scheduled target
      if (showSlewLabels) {
        const targets = state.missionData!.targets
        activeSchedule.schedule.forEach((opp) => {
          const target = targets.find((t) => t.name === opp.target_id)
          if (!target) return

          const worldPos = Cartesian3.fromDegrees(target.longitude, target.latitude, 0)
          const screenPos = SceneTransforms.worldToWindowCoordinates(viewer.scene, worldPos)
          if (!screenPos) return

          const roll = Math.abs(opp.roll_angle ?? 0)
          const pitch = Math.abs(opp.pitch_angle ?? 0)
          const offNadir = Math.sqrt(roll * roll + pitch * pitch)
          const text = `${offNadir.toFixed(1)}°`

          ctx.font = 'bold 11px sans-serif'
          const metrics = ctx.measureText(text)
          const labelX = screenPos.x - metrics.width / 2
          const labelY = screenPos.y + 22 // Below the target marker

          // Background pill
          ctx.fillStyle = 'rgba(0, 0, 0, 0.75)'
          const pad = 4
          ctx.beginPath()
          ctx.roundRect(labelX - pad, labelY - 12, metrics.width + pad * 2, 16, 4)
          ctx.fill()

          // Text
          ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
          ctx.fillText(text, labelX, labelY)
        })
      }
    }

    // Use requestAnimationFrame so animation runs independently of Cesium clock/camera
    let rafId: number
    const loop = () => {
      render()
      rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(rafId)
      resizeObserver.disconnect()
    }
  }, [viewer, enabled, activeSchedule, state.missionData, showSlewArcs, showSlewLabels])

  if (!enabled) return null

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 10,
      }}
    />
  )
}
