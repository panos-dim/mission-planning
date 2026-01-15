import React, { useEffect, useRef, useState } from 'react'
import { useCesium } from 'resium'
import { Cartesian3, SceneTransforms, JulianDate } from 'cesium'
import { useSlewVisStore } from '../../store/slewVisStore'
import { useMission } from '../../context/MissionContext'
import {
  scheduleToFootprints,
  scheduleToSlewArcs,
} from '../../utils/slewVisualization'

/**
 * Canvas-based overlay for slew visualization that works in 2D mode
 * without blocking Cesium's render thread
 */
export const SlewCanvasOverlay: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { viewer } = useCesium()
  const {
    enabled,
    activeSchedule,
    showFootprints,
    showSlewArcs,
    showSlewLabels,
    colorBy,
  } = useSlewVisStore()
  const { state } = useMission()
  const [currentOpportunityId, setCurrentOpportunityId] = useState<string | null>(null)
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

    // Generate visual data
    const footprints = showFootprints ? scheduleToFootprints(
      activeSchedule.schedule,
      state.missionData,
      colorBy
    ) : []

    const slewArcs = showSlewArcs ? scheduleToSlewArcs(
      activeSchedule.schedule,
      state.missionData,
      viewer // Pass viewer to get actual satellite position
    ) : []
    
    // Track current opportunity based on timeline
    const updateCurrentOpportunity = () => {
      const currentTime = JulianDate.toDate(viewer.clock.currentTime)
      const active = activeSchedule.schedule.find(opp => {
        const startTime = new Date(opp.start_time)
        const endTime = new Date(opp.end_time)
        return currentTime >= startTime && currentTime <= endTime
      })
      setCurrentOpportunityId(active?.opportunity_id || null)
    }

    // Render loop
    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      
      // Update current opportunity
      updateCurrentOpportunity()
      
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
          Math.pow(toScreen.x - fromScreen.x, 2) + 
          Math.pow(toScreen.y - fromScreen.y, 2)
        )
        
        if (lineLength > 20) { // Only animate lines longer than 20 pixels
          // Calculate light position along the line (0 to 1)
          const lightProgress = (animationTime + (index * 0.2)) % 1 // Stagger animations
          const lightX = fromScreen.x + (toScreen.x - fromScreen.x) * lightProgress
          const lightY = fromScreen.y + (toScreen.y - fromScreen.y) * lightProgress
          
          // Draw single animated light dot
          ctx.beginPath()
          ctx.arc(lightX, lightY, 4, 0, 2 * Math.PI)
          ctx.fillStyle = 'rgba(255, 255, 255, 0.8)'
          ctx.fill()
        }

        // Draw label at midpoint (only if labels enabled)
        if (showSlewLabels) {
          const midX = (fromScreen.x + toScreen.x) / 2
          const midY = (fromScreen.y + toScreen.y) / 2

          // Sequence number (1-indexed) with delta roll and slew time
          const sequenceNum = index + 1
          ctx.font = 'bold 12px monospace'
          ctx.fillStyle = 'cyan'
          ctx.strokeStyle = 'black'
          ctx.lineWidth = 3
          const text = `#${sequenceNum}: Δ${Math.abs(arc.deltaRoll).toFixed(1)}° / ${arc.slewTime.toFixed(1)}s`
          
          // Draw text background
          const metrics = ctx.measureText(text)
          ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
          ctx.fillRect(midX - metrics.width / 2 - 6, midY - 18, metrics.width + 12, 22)
          
          // Draw text
          ctx.strokeText(text, midX - metrics.width / 2, midY - 5)
          ctx.fillStyle = 'cyan'
          ctx.fillText(text, midX - metrics.width / 2, midY - 5)
        }
      })

      // Draw footprints
      footprints.forEach(footprint => {
        const position = Cartesian3.fromDegrees(footprint.lon, footprint.lat, 0)
        const screenPos = SceneTransforms.worldToWindowCoordinates(viewer.scene, position)

        if (!screenPos) return

        // Calculate radius in screen pixels (approximate)
        const offsetPos = Cartesian3.fromDegrees(
          footprint.lon + (footprint.radiusKm / 111), // rough km to degrees
          footprint.lat,
          0
        )
        const offsetScreen = SceneTransforms.worldToWindowCoordinates(viewer.scene, offsetPos)
        const radiusPixels = offsetScreen ? Math.abs(screenPos.x - offsetScreen.x) : 30

        // Parse color
        const colorMatch = footprint.color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/)
        const fillColor = colorMatch 
          ? `rgba(${colorMatch[1]}, ${colorMatch[2]}, ${colorMatch[3]}, ${colorMatch[4] || '0.6'})`
          : 'rgba(239, 68, 68, 0.6)'
        const strokeColor = colorMatch
          ? `rgb(${colorMatch[1]}, ${colorMatch[2]}, ${colorMatch[3]})`
          : 'rgb(239, 68, 68)'

        // Draw circle
        ctx.beginPath()
        ctx.arc(screenPos.x, screenPos.y, radiusPixels, 0, 2 * Math.PI)
        ctx.fillStyle = fillColor
        ctx.fill()
        ctx.strokeStyle = strokeColor
        ctx.lineWidth = 2
        ctx.stroke()

        // Draw label: [roll, pitch] - cross-track and along-track angles (only if labels enabled)
        if (showSlewLabels) {
          // AEROSPACE CONVENTION: Positive roll = target on LEFT (roll right), Negative = target on RIGHT (roll left)
          // AEROSPACE CONVENTION: Positive pitch = forward looking, Negative = backward looking
          const rollSign = footprint.rollAngle >= 0 ? '+' : ''
          const pitchSign = footprint.pitchAngle >= 0 ? '+' : ''
          const label = `[${rollSign}${footprint.rollAngle.toFixed(1)}°, ${pitchSign}${footprint.pitchAngle.toFixed(1)}°]`
          ctx.font = 'bold 16px sans-serif'
          ctx.fillStyle = 'white'
          ctx.strokeStyle = 'black'
          ctx.lineWidth = 3
          
          const labelMetrics = ctx.measureText(label)
          const labelX = screenPos.x - labelMetrics.width / 2
          const labelY = screenPos.y + 5
          
          // Draw label background
          ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
          ctx.fillRect(labelX - 6, labelY - 16, labelMetrics.width + 12, 22)
          
          // Draw label text
          ctx.strokeText(label, labelX, labelY)
          ctx.fillStyle = 'white'
          ctx.fillText(label, labelX, labelY)
        }
      })

      // Draw "IMAGING NOW" cyan circle for active opportunity
      if (currentOpportunityId) {
        const currentOpp = activeSchedule.schedule.find(s => s.opportunity_id === currentOpportunityId)
        if (currentOpp) {
          const target = state.missionData!.targets.find(t => t.name === currentOpp.target_id)
          if (target) {
            const position = Cartesian3.fromDegrees(target.longitude, target.latitude, 0)
            const screenPos = SceneTransforms.worldToWindowCoordinates(viewer.scene, position)

            if (screenPos) {
              // Calculate radius (match footprint size)
              const radiusKm = 15
              const offsetPos = Cartesian3.fromDegrees(
                target.longitude + (radiusKm / 111),
                target.latitude,
                0
              )
              const offsetScreen = SceneTransforms.worldToWindowCoordinates(viewer.scene, offsetPos)
              const radiusPixels = offsetScreen ? Math.abs(screenPos.x - offsetScreen.x) : 30

              // Draw cyan circle
              ctx.beginPath()
              ctx.arc(screenPos.x, screenPos.y, radiusPixels, 0, 2 * Math.PI)
              ctx.fillStyle = 'rgba(0, 255, 255, 0.4)'
              ctx.fill()
              ctx.strokeStyle = 'cyan'
              ctx.lineWidth = 4
              ctx.stroke()

              // Draw "IMAGING NOW" label
              const imagingLabel = '🛰️ IMAGING NOW'
              ctx.font = 'bold 14px sans-serif'
              ctx.fillStyle = 'cyan'
              ctx.strokeStyle = 'black'
              ctx.lineWidth = 3

              const imagingMetrics = ctx.measureText(imagingLabel)
              const imagingX = screenPos.x - imagingMetrics.width / 2
              const imagingY = screenPos.y + 5

              // Draw label background
              ctx.fillStyle = 'rgba(0, 0, 0, 0.8)'
              ctx.fillRect(imagingX - 8, imagingY - 16, imagingMetrics.width + 16, 24)

              // Draw label text
              ctx.strokeText(imagingLabel, imagingX, imagingY)
              ctx.fillStyle = 'cyan'
              ctx.fillText(imagingLabel, imagingX, imagingY)
            }
          }
        }
      }
    }

    // Render on camera move
    const removePostRender = viewer.scene.postRender.addEventListener(render)

    return () => {
      removePostRender()
      resizeObserver.disconnect()
    }
  }, [viewer, enabled, activeSchedule, state.missionData, showFootprints, showSlewArcs, showSlewLabels, colorBy, currentOpportunityId])

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
