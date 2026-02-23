import { useMemo, useEffect } from 'react'
import { useCesium } from 'resium'
import { useShallow } from 'zustand/react/shallow'
import { useSlewVisStore } from '../../store/slewVisStore'
import { useVisStore } from '../../store/visStore'
import OpportunityMetricsCard from '../OpportunityMetricsCard'

/**
 * SlewVisualizationLayer - Injects slew visualization entities into existing Cesium viewer
 * Overlays on top of mission results visualization
 */
export default function SlewVisualizationLayer(): JSX.Element | null {
  const { viewer } = useCesium()
  const { enabled, activeSchedule, hoveredOpportunityId } = useSlewVisStore(
    useShallow((s) => ({
      enabled: s.enabled,
      activeSchedule: s.activeSchedule,
      hoveredOpportunityId: s.hoveredOpportunityId,
    })),
  )

  // CRITICAL: Ensure clock stays animated when visualization is enabled
  useEffect(() => {
    if (!viewer || !enabled) return
    viewer.clock.shouldAnimate = true
  }, [viewer, enabled])

  const hoveredOpportunity = useMemo(() => {
    if (!hoveredOpportunityId || !activeSchedule) return null
    return activeSchedule.schedule.find((s) => s.opportunity_id === hoveredOpportunityId) || null
  }, [hoveredOpportunityId, activeSchedule])

  // Gate on Planning tab — hide slew visualization when user navigates away
  const activeLeftPanel = useVisStore((s) => s.activeLeftPanel)

  // Don't render if disabled, no data, or not on Planning tab
  if (!enabled || !activeSchedule || activeLeftPanel !== 'planning') return null

  return (
    <>
      {/* PR-UI-024: Footprints, slew arcs, and sensor overlays removed — path only via SlewCanvasOverlay */}

      {/* Metrics Card Overlay */}
      <OpportunityMetricsCard opportunity={hoveredOpportunity} />
    </>
  )
}
