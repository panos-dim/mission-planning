import React, { useMemo, useEffect, useState } from 'react'
import { Entity, useCesium } from 'resium'
import {
  Cartesian2,
  Cartesian3,
  Color,
  DistanceDisplayCondition,
  LabelStyle,
  VerticalOrigin,
  JulianDate,
} from 'cesium'
import { useSlewVisStore } from '../../store/slewVisStore'
import { useMission } from '../../context/MissionContext'
import {
  scheduleToFootprints,
  scheduleToSlewArcs,
  VisualFootprint,
  VisualSlewArc
} from '../../utils/slewVisualization'
import LiveSlewControls from '../LiveSlewControls'
import OpportunityMetricsCard from '../OpportunityMetricsCard'

/**
 * SlewVisualizationLayer - Injects slew visualization entities into existing Cesium viewer
 * Overlays on top of mission results visualization
 */
export default function SlewVisualizationLayer(): JSX.Element | null {
  const { viewer } = useCesium()
  const { state } = useMission()
  const {
    enabled,
    activeSchedule,
    showFootprints,
    showSlewArcs,
    colorBy,
    hoveredOpportunityId,
  } = useSlewVisStore()

  const [currentOpportunityId, setCurrentOpportunityId] = useState<string | null>(null)

  // CRITICAL: Ensure clock stays animated when visualization is enabled
  useEffect(() => {
    if (!viewer || !enabled) return
    viewer.clock.shouldAnimate = true
  }, [viewer, enabled])

  const hoveredOpportunity = useMemo(() => {
    if (!hoveredOpportunityId || !activeSchedule) return null
    return activeSchedule.schedule.find(s => s.opportunity_id === hoveredOpportunityId) || null
  }, [hoveredOpportunityId, activeSchedule])

  const currentOpportunity = useMemo(() => {
    if (!currentOpportunityId || !activeSchedule) return null
    return activeSchedule.schedule.find(s => s.opportunity_id === currentOpportunityId) || null
  }, [currentOpportunityId, activeSchedule])

  // Track current opportunity based on timeline position
  useEffect(() => {
    if (!viewer || !enabled || !activeSchedule || !state.missionData) return

    const updateCurrentOpportunity = () => {
      const currentTime = JulianDate.toDate(viewer.clock.currentTime)
      
      // Find which opportunity is currently active
      const active = activeSchedule.schedule.find(opp => {
        const startTime = new Date(opp.start_time)
        const endTime = new Date(opp.end_time)
        return currentTime >= startTime && currentTime <= endTime
      })

      setCurrentOpportunityId(active?.opportunity_id || null)
    }

    // Update on interval - throttled to avoid blocking clock
    updateCurrentOpportunity() // Initial update
    
    const intervalId = setInterval(updateCurrentOpportunity, 1000) // 1 Hz update (reduced from 10 Hz)

    return () => {
      clearInterval(intervalId)
    }
  }, [viewer, enabled, activeSchedule, state.missionData])

  // Process schedule into visual elements
  const visualData = useMemo(() => {
    if (!activeSchedule || !state.missionData) {
      return { footprints: [], slewArcs: [] }
    }

    const footprints = scheduleToFootprints(
      activeSchedule.schedule,
      state.missionData,
      colorBy
    )

    const slewArcs = scheduleToSlewArcs(
      activeSchedule.schedule,
      state.missionData,
      viewer // Pass viewer to get actual satellite position
    )

    return { footprints, slewArcs }
  }, [activeSchedule, state.missionData, colorBy])


  // Don't render if disabled or no data
  if (!enabled || !activeSchedule) return null

  // Convert lat/lon to Cartesian3
  // IMPORTANT: Cartesian3.fromDegrees expects (longitude, latitude, height)
  const toCartesian = (lat: number, lon: number, heightKm: number = 0) => {
    return Cartesian3.fromDegrees(lon, lat, heightKm * 1000)
  }

  // Parse color string to Cesium Color
  const parseColor = (colorStr: string): Color => {
    const match = colorStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/)
    if (match) {
      const r = parseInt(match[1]) / 255
      const g = parseInt(match[2]) / 255
      const b = parseInt(match[3]) / 255
      const a = match[4] ? parseFloat(match[4]) : 1
      return new Color(r, g, b, a)
    }
    return Color.BLUE.withAlpha(0.6)
  }

  return (
    <>
      {/* Controls Panel Overlay */}
      <LiveSlewControls />

      {/* Metrics Card Overlay */}
      <OpportunityMetricsCard opportunity={hoveredOpportunity} />

      {/* Render footprints - DISABLED: 2D mode cannot handle ellipse entities without blocking */}
      {false && showFootprints && visualData.footprints.map((footprint: VisualFootprint) => (
        <Entity
          key={`slew-footprint-${footprint.opportunityId}`}
          position={toCartesian(footprint.lat, footprint.lon)}
          ellipse={{
            semiMajorAxis: footprint.radiusKm * 1000,
            semiMinorAxis: footprint.radiusKm * 1000,
            material: parseColor(footprint.color),
            height: 0,
            outline: true,
            outlineColor: Color.WHITE.withAlpha(0.8),
            outlineWidth: 2,
          }}
          label={{
            text: `${footprint.incidenceAngle.toFixed(1)}°`,
            font: 'bold 16px sans-serif',
            fillColor: Color.WHITE,
            outlineColor: Color.BLACK,
            outlineWidth: 2,
            style: LabelStyle.FILL_AND_OUTLINE,
            verticalOrigin: VerticalOrigin.CENTER,
            pixelOffset: new Cartesian2(0, 0),
            showBackground: true,
            backgroundColor: Color.BLACK.withAlpha(0.6),
            backgroundPadding: new Cartesian2(6, 4),
            distanceDisplayCondition: new DistanceDisplayCondition(0, 10000000),
          }}
        />
      ))}

      {/* Render slew arcs - DISABLED: 2D mode cannot handle polyline entities without blocking */}
      {false && showSlewArcs && visualData.slewArcs.map((arc: VisualSlewArc, idx: number) => (
        <React.Fragment key={`slew-group-${idx}`}>
          <Entity
            polyline={{
              positions: [
                toCartesian(arc.fromLat, arc.fromLon, 0),
                toCartesian(arc.toLat, arc.toLon, 0),
              ],
              width: 3,
              material: parseColor(arc.color),
              arcType: 0, // NONE - straight line for performance
            }}
          />
          <Entity
            key={`slew-arc-label-${idx}`}
            position={toCartesian(
              (arc.fromLat + arc.toLat) / 2,
              (arc.fromLon + arc.toLon) / 2,
              0
            )}
            label={{
              text: `Δ${Math.abs(arc.deltaRoll).toFixed(1)}° / ${arc.slewTime.toFixed(1)}s`,
              font: 'bold 12px monospace',
              fillColor: Color.CYAN,
              outlineColor: Color.BLACK,
              outlineWidth: 2,
              style: LabelStyle.FILL_AND_OUTLINE,
              showBackground: true,
              backgroundColor: Color.BLACK.withAlpha(0.7),
              backgroundPadding: new Cartesian2(6, 3),
              pixelOffset: new Cartesian2(0, -10),
              distanceDisplayCondition: new DistanceDisplayCondition(0, 5000000),
            }}
          />
        </React.Fragment>
      ))}

      {/* Animated Sensor POV - DISABLED: 2D mode cannot handle entities without blocking */}
      {false && currentOpportunity !== null && state.missionData !== null && (() => {
        const target = state.missionData!.targets.find(t => t.name === currentOpportunity!.target_id)
        if (!target) return null
        
        // TypeScript guard: target is definitely defined here
        const targetLat = target!.latitude
        const targetLon = target!.longitude
        const radiusKm = 15 // Match footprint radius

        return (
          <Entity
            key="active-sensor-fov"
            position={toCartesian(targetLat, targetLon)}
            ellipse={{
              semiMajorAxis: radiusKm * 1000,
              semiMinorAxis: radiusKm * 1000,
              material: Color.CYAN.withAlpha(0.4),
              height: 0,
              outline: true,
              outlineColor: Color.CYAN,
              outlineWidth: 4,
            }}
            label={{
              text: `🛰️ IMAGING NOW`,
              font: 'bold 14px sans-serif',
              fillColor: Color.CYAN,
              outlineColor: Color.BLACK,
              outlineWidth: 3,
              style: LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: VerticalOrigin.CENTER,
              pixelOffset: new Cartesian2(0, 0),
              showBackground: true,
              backgroundColor: Color.BLACK.withAlpha(0.8),
              backgroundPadding: new Cartesian2(8, 4),
            }}
          />
        )
      })()}
    </>
  )
}
