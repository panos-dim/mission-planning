/**
 * Inspector Component
 *
 * Displays detailed metadata for selected tree nodes.
 * Supports multiple object types with type-specific sections and actions.
 */

import React, { useMemo } from 'react'
import {
  Satellite,
  Target,
  Radio,
  MapPin,
  Clock,
  Settings,
  Eye,
  Gauge,
  Sliders,
  BarChart2,
  Calendar,
  Zap,
  FileText,
  Package,
  Navigation,
  CheckCircle,
  Download,
  Play,
  Filter,
  Trash2,
  Copy,
  ExternalLink,
  Info,
  Hash,
  Layers,
  AlertTriangle,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  ChevronRight,
  Lock,
  Unlock,
  Shield,
} from 'lucide-react'
import { useExplorerStore } from '../../store/explorerStore'
import { usePlanningStore } from '../../store/planningStore'
import { useOrdersStore } from '../../store/ordersStore'
import { useSelectionStore } from '../../store/selectionStore'
import { useConflictStore } from '../../store/conflictStore'
import { useConflictHighlightStore } from '../../store/conflictHighlightStore'
import { useLockStore } from '../../store/lockStore'
import { useRepairHighlightStore, getRepairDiffBadgeInfo } from '../../store/repairHighlightStore'
import {
  buildItemReason,
  REASON_CODE_LABELS,
  REASON_CODE_COLORS,
  type RepairItemReason,
} from '../../adapters/repairReasons'
import { useMission } from '../../context/MissionContext'
import { useGroundStations } from '../../hooks/queries'
import type { TreeNodeType } from '../../types/explorer'

// =============================================================================
// Icon Components Map
// =============================================================================

const ICON_MAP: Record<string, React.ElementType> = {
  Satellite,
  Target,
  Radio,
  MapPin,
  Clock,
  Settings,
  Eye,
  Gauge,
  Sliders,
  BarChart2,
  Calendar,
  Zap,
  FileText,
  Package,
  Navigation,
  CheckCircle,
  Download,
  Play,
  Filter,
  Trash2,
  Copy,
  ExternalLink,
  Info,
  Hash,
  Layers,
  AlertTriangle,
  AlertCircle,
  ArrowLeft,
  ChevronRight,
}

// =============================================================================
// Section Component
// =============================================================================

interface InspectorSectionProps {
  title: string
  icon?: string
  children: React.ReactNode
  defaultCollapsed?: boolean
}

const InspectorSection: React.FC<InspectorSectionProps> = ({
  title,
  icon,
  children,
  defaultCollapsed = false,
}) => {
  const [collapsed, setCollapsed] = React.useState(defaultCollapsed)
  const IconComponent = icon ? ICON_MAP[icon] : Info

  return (
    <div className="border-b border-gray-700 last:border-b-0">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full px-4 py-2 flex items-center gap-2 text-sm font-medium text-gray-300 hover:bg-gray-800"
      >
        {IconComponent && <IconComponent className="w-4 h-4 text-gray-500" />}
        <span className="flex-1 text-left">{title}</span>
        <span className="text-gray-500 text-xs">{collapsed ? '▸' : '▾'}</span>
      </button>
      {!collapsed && <div className="px-4 pb-3 space-y-2">{children}</div>}
    </div>
  )
}

// =============================================================================
// Field Components
// =============================================================================

interface FieldProps {
  label: string
  value: string | number | boolean | null | undefined
  unit?: string
  copyable?: boolean
  color?: string
}

const Field: React.FC<FieldProps> = ({ label, value, unit, copyable, color }) => {
  const displayValue = value === null || value === undefined ? '—' : String(value)

  const handleCopy = () => {
    if (copyable && value !== null && value !== undefined) {
      navigator.clipboard.writeText(String(value))
    }
  }

  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-gray-500">{label}</span>
      <span
        className={`text-gray-300 ${copyable ? 'cursor-pointer hover:text-blue-400' : ''}`}
        style={{ color }}
        onClick={copyable ? handleCopy : undefined}
        title={copyable ? 'Click to copy' : undefined}
      >
        {displayValue}
        {unit ? ` ${unit}` : ''}
        {copyable && <Copy className="inline w-3 h-3 ml-1 opacity-50" />}
      </span>
    </div>
  )
}

interface CoordinateFieldProps {
  label: string
  latitude: number
  longitude: number
  altitude?: number
}

const CoordinateField: React.FC<CoordinateFieldProps> = ({
  label,
  latitude,
  longitude,
  altitude,
}) => {
  const formatCoord = (val: number, isLat: boolean) => {
    const dir = isLat ? (val >= 0 ? 'N' : 'S') : val >= 0 ? 'E' : 'W'
    return `${Math.abs(val).toFixed(2)}° ${dir}`
  }

  return (
    <div className="text-xs">
      <div className="text-gray-500 mb-1">{label}</div>
      <div className="pl-2 space-y-0.5">
        <div className="flex justify-between">
          <span className="text-gray-500">Lat:</span>
          <span className="text-gray-300">{formatCoord(latitude, true)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Lon:</span>
          <span className="text-gray-300">{formatCoord(longitude, false)}</span>
        </div>
        {altitude !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-500">Alt:</span>
            <span className="text-gray-300">{altitude.toFixed(0)} m</span>
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Action Button Component
// =============================================================================

interface ActionButtonProps {
  label: string
  icon: string
  onClick: () => void
  variant?: 'primary' | 'secondary' | 'danger'
  disabled?: boolean
}

const ActionButton: React.FC<ActionButtonProps> = ({
  label,
  icon,
  onClick,
  variant = 'secondary',
  disabled = false,
}) => {
  const IconComponent = ICON_MAP[icon] || Play

  const variantClasses = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-gray-700 hover:bg-gray-600 text-gray-300',
    danger: 'bg-red-900/50 hover:bg-red-900/70 text-red-400',
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium
        transition-colors disabled:opacity-50 disabled:cursor-not-allowed
        ${variantClasses[variant]}
      `}
    >
      <IconComponent className="w-3.5 h-3.5" />
      {label}
    </button>
  )
}

// =============================================================================
// Type-Specific Inspector Content
// =============================================================================

const WorkspaceInspector: React.FC<{ metadata?: Record<string, unknown> }> = ({ metadata }) => (
  <>
    <InspectorSection title="Summary" icon="Layers">
      <Field label="Satellites" value={metadata?.satellitesCount as number} />
      <Field label="Targets" value={metadata?.targetsCount as number} />
      <Field label="Opportunities" value={metadata?.opportunitiesCount as number} />
      <Field label="Plans" value={metadata?.plansCount as number} />
    </InspectorSection>
    <InspectorSection title="Info" icon="Info">
      <Field label="Created" value={formatDate(metadata?.createdAt as string)} />
      <Field label="Updated" value={formatDate(metadata?.updatedAt as string)} />
    </InspectorSection>
  </>
)

const AssetsInspector: React.FC<{ metadata?: Record<string, unknown> }> = ({ metadata }) => (
  <>
    <InspectorSection title="Contents" icon="Layers">
      <Field label="Satellites" value={metadata?.satellitesCount as number} />
      <Field label="Ground Stations" value={metadata?.groundStationsCount as number} />
    </InspectorSection>
  </>
)

const TargetsContainerInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Coverage" icon="Target">
      <Field label="Total Targets" value={metadata?.targetsCount as number} />
      <Field label="With Passes" value={metadata?.coveredTargets as number} />
      <Field label="Total Opportunities" value={metadata?.totalOpportunities as number} />
    </InspectorSection>
  </>
)

const ConstraintsInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Mission" icon="Settings">
      <Field label="Type" value={(metadata?.missionType as string)?.toUpperCase()} />
      <Field
        label="Elevation Mask"
        value={metadata?.elevationMask ? `${metadata.elevationMask}°` : undefined}
      />
    </InspectorSection>
    <InspectorSection title="Sensor" icon="Eye">
      <Field label="FOV Angle" value={metadata?.sensorFov ? `${metadata.sensorFov}°` : undefined} />
    </InspectorSection>
    <InspectorSection title="Spacecraft" icon="Gauge">
      <Field
        label="Max Tilt Angle"
        value={metadata?.maxRoll ? `${metadata.maxRoll}°` : undefined}
      />
    </InspectorSection>
  </>
)

const RunsInspector: React.FC<{ metadata?: Record<string, unknown> }> = ({ metadata }) => (
  <>
    <InspectorSection title="Status" icon="BarChart2">
      <Field label="Analysis" value={metadata?.hasAnalysis ? 'Complete' : 'Not run'} />
      <Field label="Passes Found" value={metadata?.passesFound as number} />
      <Field label="Last Run" value={formatDateTime(metadata?.lastRunTime as string)} />
    </InspectorSection>
  </>
)

const ResultsInspector: React.FC<{ metadata?: Record<string, unknown> }> = ({ metadata }) => (
  <>
    <InspectorSection title="Summary" icon="BarChart2">
      <Field label="Opportunities" value={metadata?.opportunitiesCount as number} />
      <Field label="Unique Targets" value={metadata?.uniqueTargets as number} />
      <Field
        label="Avg Elevation"
        value={
          typeof metadata?.avgElevation === 'number'
            ? `${(metadata.avgElevation as number).toFixed(1)}°`
            : undefined
        }
      />
    </InspectorSection>
  </>
)

const OpportunitiesContainerInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Summary" icon="Layers">
      <Field label="Total" value={metadata?.totalCount as number} />
      <Field label="Unique Targets" value={metadata?.uniqueTargets as number} />
    </InspectorSection>
  </>
)

const ScenarioInspector: React.FC<{ metadata?: Record<string, unknown> }> = ({ metadata }) => (
  <>
    <InspectorSection title="Time Window" icon="Clock">
      <Field label="Mode" value={metadata?.missionMode as string} />
      <Field label="Start" value={formatDateTime(metadata?.timeWindowStart as string)} />
      <Field label="End" value={formatDateTime(metadata?.timeWindowEnd as string)} />
      <Field label="Duration" value={metadata?.duration as string} />
    </InspectorSection>
  </>
)

// Satellites container inspector
const SatellitesContainerInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Summary" icon="Satellite">
      <Field label="Count" value={metadata?.count as number} />
      <Field label="Primary" value={metadata?.primarySatellite as string} />
    </InspectorSection>
  </>
)

// Ground stations container inspector
const GroundStationsContainerInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Summary" icon="Radio">
      <Field label="Count" value={metadata?.count as number} />
    </InspectorSection>
  </>
)

// Individual ground station inspector
const GroundStationInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Details" icon="Radio">
      <Field label="Type" value={metadata?.type as string} />
      <Field label="Status" value={metadata?.status as string} />
    </InspectorSection>
  </>
)

// Constraint sub-node inspectors
const SensorConstraintInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Parameters" icon="Eye">
      <Field
        label="FOV Angle"
        value={metadata?.fovHalfAngle ? `${metadata.fovHalfAngle}°` : undefined}
      />
      <Field label="Mode" value={(metadata?.imagingMode as string)?.toUpperCase()} />
    </InspectorSection>
  </>
)

const SpacecraftConstraintInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Limits" icon="Gauge">
      <Field
        label="Max Tilt Angle"
        value={metadata?.maxRoll ? `${metadata.maxRoll}°` : undefined}
      />
      <Field
        label="Slew Rate"
        value={metadata?.slewRate ? `${metadata.slewRate} °/s` : undefined}
      />
    </InspectorSection>
  </>
)

const PlanningConstraintInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Parameters" icon="Sliders">
      <Field label="Total Passes" value={metadata?.totalPasses as number} />
      <Field label="Scheduled Passes" value={metadata?.scheduledPasses as number} />
      <Field
        label="Coverage"
        value={
          metadata?.coveragePercentage !== undefined ? `${metadata.coveragePercentage}%` : undefined
        }
      />
      {typeof metadata?.note === 'string' && (
        <div className="text-xs text-gray-500 italic mt-1">{metadata.note}</div>
      )}
    </InspectorSection>
  </>
)

// Run sub-node inspectors
const AnalysisRunInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Status" icon="BarChart2">
      <Field label="State" value={metadata?.status as string} />
      <Field label="Passes Found" value={metadata?.passesFound as number} />
    </InspectorSection>
    <InspectorSection title="Time Window" icon="Clock">
      <Field label="Start" value={formatDateTime(metadata?.startTime as string)} />
      <Field label="End" value={formatDateTime(metadata?.endTime as string)} />
    </InspectorSection>
    <InspectorSection title="Target Coverage" icon="Target">
      <Field label="Total Targets" value={metadata?.totalTargets as number} />
      <Field label="With Passes" value={metadata?.targetsWithPasses as number} />
      <Field
        label="Coverage"
        value={
          typeof metadata?.targetCoverage === 'number'
            ? `${(metadata.targetCoverage as number).toFixed(1)}%`
            : undefined
        }
      />
    </InspectorSection>
  </>
)

const PlanningRunInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Status" icon="Calendar">
      <Field label="State" value={metadata?.status as string} />
      <Field label="Algorithm" value={metadata?.algorithm as string} />
    </InspectorSection>
    {metadata?.status === 'Complete' && (
      <InspectorSection title="Results" icon="CheckCircle">
        <Field label="Accepted" value={metadata?.accepted as number} />
        <Field
          label="Total Value"
          value={
            typeof metadata?.totalValue === 'number'
              ? (metadata.totalValue as number).toFixed(1)
              : undefined
          }
        />
        <Field
          label="Runtime"
          value={
            typeof metadata?.runtime === 'number'
              ? `${(metadata.runtime as number).toFixed(0)} ms`
              : undefined
          }
        />
      </InspectorSection>
    )}
  </>
)

// Container inspectors for plans, orders, imports
const PlansContainerInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Schedule" icon="FileText">
      <Field label="Status" value={metadata?.status as string} />
      <Field label="Scheduled" value={metadata?.scheduledCount as number} />
      <Field label="Coverage" value={metadata?.coverage as string} />
      <Field label="Algorithm" value={metadata?.algorithm as string} />
    </InspectorSection>
  </>
)

const OrdersContainerInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Summary" icon="Package">
      <Field label="Count" value={metadata?.count as number} />
    </InspectorSection>
  </>
)

const ImportsContainerInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Summary" icon="Layers">
      <Field label="Count" value={metadata?.count as number} />
    </InspectorSection>
  </>
)

const ImportSourceInspector: React.FC<{
  metadata?: Record<string, unknown>
}> = ({ metadata }) => (
  <>
    <InspectorSection title="Details" icon="Layers">
      <Field label="Type" value={metadata?.type as string} />
      <Field label="Status" value={metadata?.status as string} />
    </InspectorSection>
  </>
)

const SatelliteInspector: React.FC<{
  metadata?: Record<string, unknown>
  onAction?: (action: string) => void
}> = ({ metadata, onAction }) => (
  <>
    <InspectorSection title="Orbit" icon="Satellite">
      <Field label="Source" value={(metadata?.orbitSource as string) || 'TLE'} />
      {typeof metadata?.color === 'string' && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Color</span>
          <div
            className="w-4 h-4 rounded border border-gray-600"
            style={{ backgroundColor: metadata.color }}
          />
        </div>
      )}
    </InspectorSection>
    <InspectorSection title="Capabilities" icon="Gauge">
      <Field label="Max Tilt Angle" value={metadata?.maxRoll as number} unit="°" />
      <Field label="Slew Rate" value={metadata?.agility ? `${metadata.agility} °/s` : undefined} />
      <Field label="Sensor FOV" value={metadata?.sensorFov as number} unit="°" />
    </InspectorSection>
    {onAction && (
      <div className="px-4 py-3 flex gap-2">
        <ActionButton
          label="Fly To"
          icon="Navigation"
          onClick={() => onAction('flyTo')}
          variant="primary"
        />
      </div>
    )}
  </>
)

const TargetInspector: React.FC<{
  metadata?: Record<string, unknown>
  onAction?: (action: string) => void
}> = ({ metadata, onAction }) => (
  <>
    <InspectorSection title="Properties" icon="Target">
      <Field label="Priority" value={metadata?.priority as number} />
      {typeof metadata?.color === 'string' && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Color</span>
          <div
            className="w-4 h-4 rounded border border-gray-600"
            style={{ backgroundColor: metadata.color }}
          />
        </div>
      )}
    </InspectorSection>
    <InspectorSection title="Location" icon="MapPin">
      {metadata?.latitude !== undefined && metadata?.longitude !== undefined && (
        <CoordinateField
          label="Position"
          latitude={metadata.latitude as number}
          longitude={metadata.longitude as number}
        />
      )}
    </InspectorSection>
    <InspectorSection title="Statistics" icon="BarChart2">
      <Field label="Opportunities" value={metadata?.opportunitiesCount as number} />
      <Field
        label="Best Off-Nadir"
        value={
          typeof metadata?.bestElevation === 'number'
            ? (90 - (metadata.bestElevation as number)).toFixed(1)
            : undefined
        }
        unit="°"
      />
      <Field
        label="Mean Off-Nadir"
        value={
          typeof metadata?.meanElevation === 'number'
            ? (90 - (metadata.meanElevation as number)).toFixed(1)
            : undefined
        }
        unit="°"
      />
    </InspectorSection>
    {onAction && (
      <div className="px-4 py-3 flex gap-2">
        <ActionButton label="Fly To" icon="Navigation" onClick={() => onAction('flyTo')} />
        <ActionButton
          label="Filter Opps"
          icon="Filter"
          onClick={() => onAction('filterOpportunities')}
        />
      </div>
    )}
  </>
)

const OpportunityInspector: React.FC<{
  metadata?: Record<string, unknown>
  onAction?: (action: string) => void
}> = ({ metadata, onAction }) => {
  const geometryTca = metadata?.geometry_tca as Record<string, unknown> | undefined
  const lighting = metadata?.lighting as Record<string, unknown> | undefined
  const quality = metadata?.quality as Record<string, unknown> | undefined
  const maneuver = metadata?.maneuver as Record<string, unknown> | undefined
  const sarData = metadata?.sar_data as Record<string, unknown> | undefined
  const isSAR = !!sarData

  return (
    <>
      <InspectorSection title="Overview" icon="Zap">
        <Field label="Target" value={metadata?.target as string} />
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Satellite</span>
          <div className="flex items-center gap-2">
            {typeof metadata?.satellite_color === 'string' && (
              <div
                className="w-3 h-3 rounded-full border border-gray-600"
                style={{ backgroundColor: metadata.satellite_color }}
              />
            )}
            <span className="text-white">{(metadata?.satellite_name as string) || '—'}</span>
          </div>
        </div>
        <Field label="Pass #" value={metadata?.pass_index as number} />
        <Field label="Duration" value={(metadata?.duration_s as number)?.toFixed(0)} unit="s" />
        {isSAR && <Field label="Type" value="SAR Opportunity" />}
      </InspectorSection>

      {sarData && (
        <InspectorSection title="SAR Parameters" icon="Radio">
          <Field label="Imaging Mode" value={(sarData.imaging_mode as string)?.toUpperCase()} />
          <Field label="Look Side" value={sarData.look_side as string} />
          <Field label="Pass Direction" value={sarData.pass_direction as string} />
          <Field
            label="Incidence (Center)"
            value={(sarData.incidence_center_deg as number)?.toFixed(1)}
            unit="°"
          />
          {typeof sarData.incidence_near_deg === 'number' && (
            <Field
              label="Incidence (Near)"
              value={(sarData.incidence_near_deg as number)?.toFixed(1)}
              unit="°"
            />
          )}
          {typeof sarData.incidence_far_deg === 'number' && (
            <Field
              label="Incidence (Far)"
              value={(sarData.incidence_far_deg as number)?.toFixed(1)}
              unit="°"
            />
          )}
          <Field
            label="Swath Width"
            value={(sarData.swath_width_km as number)?.toFixed(1)}
            unit="km"
          />
          {typeof sarData.scene_length_km === 'number' && (
            <Field
              label="Scene Length"
              value={(sarData.scene_length_km as number)?.toFixed(1)}
              unit="km"
            />
          )}
          <Field
            label="Quality Score"
            value={(sarData.quality_score as number)?.toFixed(0)}
            unit="/100"
          />
        </InspectorSection>
      )}

      <InspectorSection title="Timing" icon="Clock">
        <Field
          label="Acquisition of Signal"
          value={formatDateTime(metadata?.start_time as string)}
        />
        <Field
          label="Closest Approach"
          value={formatDateTime(metadata?.max_elevation_time as string)}
        />
        <Field label="Loss of Signal" value={formatDateTime(metadata?.end_time as string)} />
      </InspectorSection>

      <InspectorSection title="Geometry at Closest Approach" icon="Gauge">
        <Field
          label="Off-Nadir"
          value={
            typeof metadata?.max_elevation === 'number'
              ? (90 - (metadata.max_elevation as number)).toFixed(1)
              : undefined
          }
          unit="°"
        />
        {geometryTca && (
          <>
            <Field
              label="Incidence"
              value={(geometryTca.incidence_angle_deg as number)?.toFixed(1)}
              unit="°"
            />
            <Field label="Range" value={(geometryTca.range_km as number)?.toFixed(0)} unit="km" />
            <Field
              label="Azimuth"
              value={(geometryTca.azimuth_deg as number)?.toFixed(1)}
              unit="°"
            />
          </>
        )}
        <Field label="Pass Type" value={metadata?.pass_type as string} />
      </InspectorSection>

      {lighting && (
        <InspectorSection title="Lighting" icon="Zap">
          <Field label="Target Sunlit" value={lighting.target_sunlit ? 'Yes' : 'No'} />
          <Field
            label="Sun Elevation"
            value={(lighting.sun_elevation_deg as number)?.toFixed(1)}
            unit="°"
          />
          <Field label="Local Solar Time" value={lighting.local_solar_time as string} />
        </InspectorSection>
      )}

      {quality && (
        <InspectorSection title="Quality" icon="BarChart2">
          <Field label="Score" value={(quality.quality_score as number)?.toFixed(0)} unit="/100" />
          <Field label="Feasible" value={quality.imaging_feasible ? 'Yes' : 'No'} />
          {typeof quality.feasibility_reason === 'string' && (
            <div className="text-xs text-yellow-400 mt-1 px-0">{quality.feasibility_reason}</div>
          )}
        </InspectorSection>
      )}

      {maneuver && (
        <InspectorSection title="Maneuver" icon="Navigation">
          <Field label="Roll" value={(maneuver.roll_angle_deg as number)?.toFixed(1)} unit="°" />
          <Field
            label="Slew from Nadir"
            value={(maneuver.slew_angle_deg as number)?.toFixed(1)}
            unit="°"
          />
          {typeof maneuver.slew_time_s === 'number' && (
            <Field label="Slew Time" value={maneuver.slew_time_s.toFixed(1)} unit="s" />
          )}
        </InspectorSection>
      )}

      {onAction && (
        <div className="px-4 py-3 flex gap-2">
          <ActionButton
            label="Jump to Time"
            icon="Clock"
            onClick={() => onAction('jumpToTime')}
            variant="primary"
          />
        </div>
      )}
    </>
  )
}

const PlanInspector: React.FC<{
  metadata?: Record<string, unknown>
  onAction?: (action: string) => void
}> = ({ metadata, onAction }) => {
  return (
    <>
      <InspectorSection title="Algorithm" icon="Settings">
        <Field label="Name" value={metadata?.algorithm as string} />
        <Field label="Runtime" value={metadata?.runtime as number} unit="ms" />
      </InspectorSection>
      <InspectorSection title="Metrics" icon="BarChart2">
        <Field label="Accepted" value={metadata?.accepted as number} />
        <Field label="Rejected" value={metadata?.rejected as number} />
        <Field label="Total Value" value={(metadata?.totalValue as number)?.toFixed(1)} />
        <Field
          label="Mean Incidence"
          value={(metadata?.meanIncidence as number)?.toFixed(1)}
          unit="°"
        />
        <Field
          label="Utilization"
          value={`${((metadata?.utilization as number) * 100)?.toFixed(1)}%`}
        />
      </InspectorSection>
      {onAction && (
        <div className="px-4 py-3 flex gap-2">
          <ActionButton
            label="Set Active"
            icon="CheckCircle"
            onClick={() => onAction('setActive')}
            variant="primary"
          />
          <ActionButton label="Export" icon="Download" onClick={() => onAction('export')} />
        </div>
      )}
    </>
  )
}

const PlanItemInspector: React.FC<{
  metadata?: Record<string, unknown>
  onAction?: (action: string) => void
}> = ({ metadata, onAction }) => (
  <>
    <InspectorSection title="Overview" icon="Target">
      <Field label="Target" value={metadata?.target_id as string} />
      <Field label="Satellite" value={metadata?.satellite_id as string} />
      <Field label="Off-Nadir" value={(metadata?.incidence_angle as number)?.toFixed(1)} unit="°" />
    </InspectorSection>
    <InspectorSection title="Timing" icon="Clock">
      <Field label="Start" value={formatDateTime(metadata?.start_time as string)} />
      <Field label="End" value={formatDateTime(metadata?.end_time as string)} />
    </InspectorSection>
    <InspectorSection title="Attitude" icon="Gauge">
      <Field label="Roll" value={(metadata?.roll_angle as number)?.toFixed(1)} unit="°" />
      <Field label="Pitch" value={(metadata?.pitch_angle as number)?.toFixed(1)} unit="°" />
      <Field label="Δ Roll" value={(metadata?.delta_roll as number)?.toFixed(1)} unit="°" />
      <Field label="Δ Pitch" value={(metadata?.delta_pitch as number)?.toFixed(1)} unit="°" />
      <Field label="Slew Time" value={(metadata?.maneuver_time as number)?.toFixed(1)} unit="s" />
      <Field label="Slack" value={(metadata?.slack_time as number)?.toFixed(1)} unit="s" />
    </InspectorSection>
    <InspectorSection title="Value" icon="Zap">
      <Field label="Value" value={(metadata?.value as number)?.toFixed(2)} />
      <Field
        label="Density"
        value={metadata?.density === 'inf' ? '∞' : (metadata?.density as number)?.toFixed(2)}
      />
    </InspectorSection>
    {onAction && (
      <div className="px-4 py-3 flex gap-2">
        <ActionButton
          label="Jump to Time"
          icon="Clock"
          onClick={() => onAction('jumpToTime')}
          variant="primary"
        />
      </div>
    )}
  </>
)

const OrderInspector: React.FC<{
  metadata?: Record<string, unknown>
  onAction?: (action: string) => void
}> = ({ metadata, onAction }) => {
  const schedule = metadata?.schedule as
    | Array<{
        target_id: string
        satellite_id: string
        start_time: string
        end_time: string
        roll_angle?: number
        pitch_angle?: number
        incidence_angle?: number
      }>
    | undefined

  return (
    <>
      <InspectorSection title="Order Info" icon="Package">
        <Field label="Name" value={metadata?.name as string} />
        <Field label="Created" value={formatDateTime(metadata?.created_at as string)} />
        <Field label="Algorithm" value={metadata?.algorithm as string} />
      </InspectorSection>
      <InspectorSection title="Metrics" icon="BarChart2">
        <Field label="Accepted" value={metadata?.accepted as number} />
        <Field label="Total Value" value={(metadata?.totalValue as number)?.toFixed(1)} />
        <Field
          label="Utilization"
          value={`${((metadata?.utilization as number) * 100)?.toFixed(1)}%`}
        />
      </InspectorSection>
      <InspectorSection title="Coverage" icon="Layers">
        <Field label="Satellites" value={metadata?.satellites as number} />
        <Field label="Targets" value={metadata?.targets as number} />
      </InspectorSection>
      {schedule && schedule.length > 0 && (
        <InspectorSection title={`Schedule (${schedule.length} passes)`} icon="Calendar">
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {schedule.map((item, idx) => (
              <div key={idx} className="bg-gray-800/50 rounded p-2 text-xs border border-gray-700">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-white font-medium">{item.target_id}</span>
                  <span className="text-gray-400 text-[10px]">{item.satellite_id}</span>
                </div>
                <div className="text-gray-400 text-[10px] mb-1">
                  {formatDateTime(item.start_time)}
                </div>
                <div className="flex gap-3 text-[10px]">
                  {item.incidence_angle !== undefined && (
                    <span className="text-blue-400">
                      Off-Nadir: {item.incidence_angle.toFixed(1)}°
                    </span>
                  )}
                  {item.roll_angle !== undefined && (
                    <span className="text-green-400">Roll: {item.roll_angle.toFixed(1)}°</span>
                  )}
                  {item.pitch_angle !== undefined && item.pitch_angle !== 0 && (
                    <span className="text-yellow-400">Pitch: {item.pitch_angle.toFixed(1)}°</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </InspectorSection>
      )}
      {onAction && (
        <div className="px-4 py-3 flex gap-2">
          <ActionButton
            label="Export"
            icon="Download"
            onClick={() => onAction('export')}
            variant="primary"
          />
        </div>
      )}
    </>
  )
}

// =============================================================================
// Repair Change Badge Component (PR-REPAIR-UX-01 + PR-OPS-REPAIR-EXPLAIN-01)
// =============================================================================

interface RepairChangeBadgeProps {
  type: 'kept' | 'dropped' | 'added' | 'moved'
  movedInfo?: {
    from_start: string
    to_start: string
    from_roll_deg?: number
    to_roll_deg?: number
  }
  /** PR-OPS-REPAIR-EXPLAIN-01: structured reason for this item */
  itemReason?: RepairItemReason
}

const RepairChangeBadge: React.FC<RepairChangeBadgeProps> = ({ type, movedInfo, itemReason }) => {
  const [showDetail, setShowDetail] = React.useState(false)
  const badgeInfo = getRepairDiffBadgeInfo(type)

  // Derive reason if not provided
  const reason = itemReason ?? buildItemReason(type)
  const reasonLabel = REASON_CODE_LABELS[reason.reason_code]
  const reasonColor = REASON_CODE_COLORS[reason.reason_code]

  return (
    <div className={`px-3 py-2 rounded-lg border ${badgeInfo.bgColor} border-opacity-50`}>
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className={`text-xs font-medium uppercase px-2 py-0.5 rounded ${badgeInfo.bgColor} ${badgeInfo.color}`}
        >
          Repair: {badgeInfo.label}
        </span>
        {/* PR-OPS-REPAIR-EXPLAIN-01: Reason code chip */}
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${reasonColor.bg} ${reasonColor.text}`}>
          {reasonLabel}
        </span>
      </div>

      {/* PR-OPS-REPAIR-EXPLAIN-01: Short reason line */}
      <div className="mt-1.5 text-xs text-gray-300">{reason.short_reason}</div>

      {/* Moved item: from→to time */}
      {type === 'moved' && movedInfo && (
        <div className="mt-2 text-xs text-gray-400">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">Time shift:</span>
            <span>{formatDateTime(movedInfo.from_start)}</span>
            <ArrowRight className="w-3 h-3" />
            <span className={badgeInfo.color}>{formatDateTime(movedInfo.to_start)}</span>
          </div>
          {movedInfo.from_roll_deg !== undefined && movedInfo.to_roll_deg !== undefined && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-gray-500">Roll:</span>
              <span>{movedInfo.from_roll_deg.toFixed(1)}°</span>
              <ArrowRight className="w-3 h-3" />
              <span className={badgeInfo.color}>{movedInfo.to_roll_deg.toFixed(1)}°</span>
            </div>
          )}
        </div>
      )}

      {/* Dropped item: show reason */}
      {type === 'dropped' && (
        <div className="mt-1 text-xs text-red-400/80">Dropped due to: {reason.short_reason}</div>
      )}

      {/* PR-OPS-REPAIR-EXPLAIN-01: Expandable detail reason */}
      {reason.detail_reason && reason.detail_reason !== reason.short_reason && (
        <button
          onClick={() => setShowDetail(!showDetail)}
          className="mt-1 text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-0.5"
        >
          {showDetail ? (
            <>
              <ChevronRight className="w-3 h-3 rotate-90" /> Hide details
            </>
          ) : (
            <>
              <ChevronRight className="w-3 h-3" /> Show details
            </>
          )}
        </button>
      )}
      {showDetail && reason.detail_reason && (
        <div className="mt-1 text-[10px] text-gray-400 bg-gray-800/50 rounded p-1.5">
          {reason.detail_reason}
        </div>
      )}

      <div className="mt-1 text-[10px] text-gray-500 italic">Preview only — not committed</div>
    </div>
  )
}

// =============================================================================
// Conflict Inspector Component
// =============================================================================

interface ConflictInspectorProps {
  conflictId: string
  conflictData?: {
    type?: string
    severity?: string
    description?: string
    acquisition_ids?: string[]
    detected_at?: string
    satellite_id?: string
  }
  onAcquisitionClick?: (acquisitionId: string) => void
  onBackToSchedule?: () => void
  onFocusMap?: () => void
  onFocusTimeline?: () => void
}

const ConflictInspector: React.FC<ConflictInspectorProps> = ({
  conflictId,
  conflictData,
  onAcquisitionClick,
  onBackToSchedule,
  onFocusMap,
  onFocusTimeline,
}) => {
  const getSeverityColor = (severity?: string) => {
    switch (severity) {
      case 'error':
        return 'text-red-400'
      case 'warning':
        return 'text-yellow-400'
      default:
        return 'text-blue-400'
    }
  }

  const getSeverityBgColor = (severity?: string) => {
    switch (severity) {
      case 'error':
        return 'bg-red-900/30'
      case 'warning':
        return 'bg-yellow-900/30'
      default:
        return 'bg-blue-900/30'
    }
  }

  const getTypeLabel = (type?: string) => {
    switch (type) {
      case 'temporal_overlap':
        return 'Time Overlap'
      case 'slew_infeasible':
        return 'Slew Infeasible'
      default:
        return type || 'Unknown'
    }
  }

  const SeverityIcon = conflictData?.severity === 'error' ? AlertCircle : AlertTriangle

  return (
    <>
      {/* Back to Schedule link */}
      {onBackToSchedule && (
        <div className="px-4 py-2 border-b border-gray-700">
          <button
            onClick={onBackToSchedule}
            className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            <ArrowLeft className="w-3 h-3" />
            Back to schedule
          </button>
        </div>
      )}

      {/* Conflict Summary */}
      <InspectorSection title="Conflict Details" icon="AlertTriangle">
        <div className="flex items-center gap-2 mb-2">
          <SeverityIcon className={`w-4 h-4 ${getSeverityColor(conflictData?.severity)}`} />
          <span
            className={`text-xs font-medium uppercase ${getSeverityColor(conflictData?.severity)}`}
          >
            {conflictData?.severity || 'info'}
          </span>
          <span
            className={`text-xs px-2 py-0.5 rounded ${getSeverityBgColor(conflictData?.severity)}`}
          >
            {getTypeLabel(conflictData?.type)}
          </span>
        </div>
        <Field label="Conflict ID" value={conflictId} copyable />
        {conflictData?.satellite_id && (
          <Field label="Satellite" value={conflictData.satellite_id} />
        )}
        {conflictData?.detected_at && (
          <Field label="Detected" value={formatDateTime(conflictData.detected_at)} />
        )}
      </InspectorSection>

      {/* Description */}
      {conflictData?.description && (
        <InspectorSection title="Description" icon="Info">
          <p className="text-xs text-gray-300 leading-relaxed">{conflictData.description}</p>
        </InspectorSection>
      )}

      {/* Involved Acquisitions */}
      <InspectorSection
        title={`Involved Acquisitions (${conflictData?.acquisition_ids?.length || 0})`}
        icon="Calendar"
      >
        {conflictData?.acquisition_ids && conflictData.acquisition_ids.length > 0 ? (
          <div className="space-y-1">
            {conflictData.acquisition_ids.map((acqId, index) => (
              <button
                key={acqId}
                onClick={() => onAcquisitionClick?.(acqId)}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-left rounded
                         bg-gray-800/50 hover:bg-gray-700/50 transition-colors group"
              >
                <span className="text-xs text-gray-500 w-4">{index + 1}.</span>
                <span className="flex-1 text-xs text-gray-300 font-mono truncate">
                  {acqId.length > 20 ? `${acqId.slice(0, 20)}...` : acqId}
                </span>
                <ChevronRight className="w-3 h-3 text-gray-500 group-hover:text-blue-400 transition-colors" />
              </button>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-500">No acquisitions linked</p>
        )}
      </InspectorSection>

      {/* Quick Actions (PR-CONFLICT-UX-02) */}
      {(onFocusMap || onFocusTimeline) && (
        <div className="px-4 py-3 border-t border-gray-700">
          <div className="text-xs text-gray-500 mb-2">Quick Actions</div>
          <div className="flex gap-2">
            {onFocusMap && (
              <ActionButton
                label="Focus on Map"
                icon="MapPin"
                onClick={onFocusMap}
                variant="secondary"
              />
            )}
            {onFocusTimeline && (
              <ActionButton
                label="Focus Timeline"
                icon="Clock"
                onClick={onFocusTimeline}
                variant="secondary"
              />
            )}
          </div>
        </div>
      )}

      {/* Action hint */}
      <div className="px-4 py-3 text-xs text-gray-500 italic">
        Click an acquisition above to view its details and navigate on the timeline.
      </div>
    </>
  )
}

// =============================================================================
// Main Inspector Component
// =============================================================================

interface InspectorProps {
  onAction?: (action: string, nodeId: string, nodeType: TreeNodeType) => void
}

const Inspector: React.FC<InspectorProps> = ({ onAction }) => {
  const { selectedNodeId, selectedNodeType, setActivePlan, setFilterByTarget } = useExplorerStore()
  const { state, navigateToImagingTime, flyToObject } = useMission()
  const planningResults = usePlanningStore((s) => s.results)
  const setActiveAlgorithm = usePlanningStore((s) => s.setActiveAlgorithm)
  const orders = useOrdersStore((s) => s.orders)
  const { removeOrder } = useOrdersStore()

  // Ground stations count for Inspector metadata
  const { data: groundStationsData } = useGroundStations()
  const groundStationsCount = groundStationsData?.ground_stations?.length ?? 0

  // Unified selection store for map/table selections
  const {
    selectedType: unifiedSelectedType,
    selectedTargetId,
    selectedOpportunityId,
    selectedAcquisitionId,
    selectedConflictId,
    clearSelection,
    selectAcquisition,
  } = useSelectionStore()

  // PR-LOCK-OPS-01: Lock store for acquisition lock control
  const lockLevels = useLockStore((s) => s.levels)
  const toggleLock = useLockStore((s) => s.toggleLock)
  const lockPending = useLockStore((s) => s.pending)
  const lastSelectionSource = useSelectionStore((s) => s.lastSelectionSource)

  // Conflict store for conflict details
  const conflicts = useConflictStore((s) => s.conflicts)

  // Get selected conflict data
  const selectedConflictData = useMemo(() => {
    if (!selectedConflictId) return undefined
    return conflicts.find((c) => c.id === selectedConflictId)
  }, [selectedConflictId, conflicts])

  // Handle acquisition click from conflict inspector
  const handleConflictAcquisitionClick = (acquisitionId: string) => {
    console.log('[Inspector] Navigate to acquisition from conflict:', acquisitionId)
    selectAcquisition(acquisitionId, 'inspector')
  }

  // Handle back to schedule (clear conflict selection)
  const handleBackToSchedule = () => {
    clearSelection()
  }

  // Conflict highlight store for focus actions (PR-CONFLICT-UX-02)
  const { focusTimelineOnConflict } = useConflictHighlightStore()

  // Repair highlight store for repair diff item display (PR-REPAIR-UX-01)
  const selectedRepairItem = useRepairHighlightStore((s) => s.selectedDiffItem)
  const repairDiff = useRepairHighlightStore((s) => s.repairDiff)
  const clearRepairSelection = useRepairHighlightStore((s) => s.clearSelection)
  const focusTimelineOnRepairItem = useRepairHighlightStore((s) => s.focusTimelineOnRepairItem)

  // PR-OPS-REPAIR-EXPLAIN-01: Derive per-item reason for inspector badge
  const selectedRepairItemReason = useMemo(() => {
    if (!selectedRepairItem || !repairDiff) return undefined
    const { id, type } = selectedRepairItem
    let backendReason: string | undefined
    if (type === 'dropped') {
      backendReason = repairDiff.reason_summary.dropped?.find((r) => r.id === id)?.reason
    } else if (type === 'moved') {
      backendReason = repairDiff.reason_summary.moved?.find((r) => r.id === id)?.reason
    }
    return buildItemReason(type, backendReason)
  }, [selectedRepairItem, repairDiff])

  // Handle focus on map for conflict (PR-CONFLICT-UX-02)
  const handleConflictFocusMap = () => {
    if (!selectedConflictData?.acquisition_ids?.length) return

    console.log(
      '[Inspector] Focus map on conflict:',
      selectedConflictId,
      'acquisitions:',
      selectedConflictData.acquisition_ids.length,
    )

    // Fly to the first acquisition's target if available
    const firstAcqId = selectedConflictData.acquisition_ids[0]
    if (firstAcqId) {
      // Try to fly to target associated with the acquisition
      flyToObject(`target_${firstAcqId}`)
    }
  }

  // Handle focus timeline on conflict (PR-CONFLICT-UX-02)
  const handleConflictFocusTimeline = () => {
    if (!selectedConflictData) return

    console.log('[Inspector] Focus timeline on conflict:', selectedConflictId)

    // Trigger timeline focus via the conflict highlight store
    focusTimelineOnConflict()
  }

  // Find selected node metadata from tree or unified selection
  const metadata = useMemo(() => {
    // First check unified selection store (from map/table clicks)
    if (unifiedSelectedType === 'target' && selectedTargetId) {
      const target = state.missionData?.targets?.find((t) => t.name === selectedTargetId)
      if (target) {
        return {
          name: target.name || selectedTargetId,
          latitude: target.latitude,
          longitude: target.longitude,
          priority: target.priority,
          type: 'target',
        }
      }
    }

    if (unifiedSelectedType === 'opportunity' && selectedOpportunityId) {
      // Find opportunity in planning results
      for (const algo of Object.keys(planningResults || {})) {
        const result = planningResults?.[algo]
        const opp = result?.schedule?.find((s) => s.opportunity_id === selectedOpportunityId)
        if (opp) {
          return {
            name: `${opp.target_id} - ${opp.satellite_id}`,
            ...opp,
            type: 'opportunity',
          }
        }
      }
    }

    if (unifiedSelectedType === 'acquisition' && selectedAcquisitionId) {
      // Find acquisition in orders
      for (const order of orders || []) {
        const acq = order.schedule?.find((s) => s.opportunity_id === selectedAcquisitionId)
        if (acq) {
          return {
            name: `${acq.target_id} - ${acq.satellite_id}`,
            ...acq,
            order_id: order.order_id,
            type: 'acquisition',
          }
        }
      }
    }

    if (unifiedSelectedType === 'conflict' && selectedConflictId) {
      return {
        name: `Conflict ${selectedConflictId}`,
        conflict_id: selectedConflictId,
        type: 'conflict',
      }
    }

    // Fall back to tree selection
    if (!selectedNodeId) return undefined

    return findNodeMetadata(
      selectedNodeId,
      selectedNodeType,
      state,
      planningResults,
      orders,
      groundStationsCount,
    )
  }, [
    selectedNodeId,
    selectedNodeType,
    state,
    planningResults,
    orders,
    groundStationsCount,
    unifiedSelectedType,
    selectedTargetId,
    selectedOpportunityId,
    selectedAcquisitionId,
    selectedConflictId,
  ])

  // Handle action from inspector buttons
  const handleAction = (action: string) => {
    if (!selectedNodeId || !selectedNodeType) return

    // Handle common actions
    switch (action) {
      case 'flyTo':
        flyToObject(selectedNodeId)
        break

      case 'jumpToTime': {
        // Extract pass index from node ID and navigate
        const passIndex = extractPassIndex(selectedNodeId)
        if (passIndex !== null) {
          navigateToImagingTime(passIndex)
        }
        break
      }

      case 'track': {
        // Track satellite - fly to it and keep following
        flyToObject(selectedNodeId)
        console.log('[Inspector] Track satellite:', selectedNodeId)
        break
      }

      case 'highlight': {
        // Highlight opportunity/plan item on map by flying to target and jumping to time
        flyToObject(selectedNodeId)
        const passIdx = extractPassIndex(selectedNodeId)
        if (passIdx !== null) {
          navigateToImagingTime(passIdx)
        }
        console.log('[Inspector] Highlight:', selectedNodeId)
        break
      }

      case 'filterOpportunities': {
        // Filter opportunities by target
        const targetName = extractTargetName(selectedNodeId)
        if (targetName) {
          setFilterByTarget(targetName)
          console.log('[Inspector] Filter opportunities by target:', targetName)
        }
        break
      }

      case 'setActive': {
        // Set plan as active
        const algorithm = extractAlgorithmFromPlanId(selectedNodeId)
        if (algorithm) {
          setActivePlan(selectedNodeId)
          setActiveAlgorithm(algorithm)
          console.log('[Inspector] Set active plan:', algorithm)
        }
        break
      }

      case 'export': {
        // Export plan or order to JSON file based on node type
        if (selectedNodeType === 'plan') {
          const algo = extractAlgorithmFromPlanId(selectedNodeId)
          if (algo && planningResults && planningResults[algo]) {
            const result = planningResults[algo]
            const exportData = {
              algorithm: algo,
              exported_at: new Date().toISOString(),
              schedule: result.schedule,
              metrics: result.metrics,
            }
            downloadJson(exportData, `plan_${algo}_${Date.now()}.json`)
            console.log('[Inspector] Export plan:', algo)
          }
        } else if (selectedNodeType === 'order') {
          const orderId = extractOrderId(selectedNodeId)
          const order = orders?.find((o) => o.order_id === orderId)
          if (order) {
            downloadJson(order, `order_${order.name.replace(/\s+/g, '_')}_${Date.now()}.json`)
            console.log('[Inspector] Export order:', orderId)
          }
        }
        break
      }

      case 'load': {
        // Load order - set as active
        const orderId = extractOrderId(selectedNodeId)
        if (orderId) {
          console.log('[Inspector] Load order:', orderId)
          // Orders are already loaded in ordersStore - just log for now
        }
        break
      }

      case 'delete': {
        // Delete order
        const orderId = extractOrderId(selectedNodeId)
        if (orderId && window.confirm('Are you sure you want to delete this order?')) {
          removeOrder(orderId)
          console.log('[Inspector] Delete order:', orderId)
        }
        break
      }
    }

    // Delegate to parent handler for other actions
    if (onAction) {
      onAction(action, selectedNodeId, selectedNodeType)
    }
  }

  // Check if we have any selection (tree or unified)
  const hasTreeSelection = selectedNodeId && selectedNodeType
  const hasUnifiedSelection = unifiedSelectedType !== null

  if (!hasTreeSelection && !hasUnifiedSelection) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-500 p-4">
        <Info className="w-8 h-8 mb-2 opacity-50" />
        <p className="text-sm text-center">Select an object to view its properties</p>
      </div>
    )
  }

  // For unified selection without tree selection, render simplified content
  if (!hasTreeSelection && hasUnifiedSelection && metadata) {
    const typeLabels: Record<string, string> = {
      target: 'Target',
      opportunity: 'Opportunity',
      acquisition: 'Acquisition',
      conflict: 'Conflict',
    }
    const TypeIcon = unifiedSelectedType === 'target' ? MapPin : Zap

    return (
      <div className="flex flex-col h-full bg-gray-900">
        {/* Header with clear button */}
        <div className="px-4 py-3 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <TypeIcon className="w-5 h-5 text-blue-400" />
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-white truncate">
                {(metadata.name as string) || 'Selected Item'}
              </h3>
              <p className="text-xs text-gray-500">
                {typeLabels[unifiedSelectedType || ''] || 'Unknown'}
              </p>
            </div>
            <button
              onClick={clearSelection}
              className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
              title="Clear selection (Esc)"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content based on unified type */}
        <div className="flex-1 overflow-y-auto">
          {unifiedSelectedType === 'target' && (
            <>
              <InspectorSection title="Location" icon="MapPin">
                <CoordinateField
                  label="Position"
                  latitude={metadata.latitude as number}
                  longitude={metadata.longitude as number}
                />
              </InspectorSection>
              {metadata.priority !== undefined && (
                <InspectorSection title="Properties" icon="Settings">
                  <Field label="Priority" value={metadata.priority as number} />
                </InspectorSection>
              )}
            </>
          )}
          {unifiedSelectedType === 'opportunity' && (
            <>
              {/* Repair Change Badge (PR-REPAIR-UX-01 + PR-OPS-REPAIR-EXPLAIN-01) */}
              {selectedRepairItem && (
                <div className="px-4 py-2">
                  <RepairChangeBadge
                    type={selectedRepairItem.type}
                    movedInfo={selectedRepairItem.movedInfo}
                    itemReason={selectedRepairItemReason}
                  />
                </div>
              )}
              <InspectorSection title="Overview" icon="Target">
                <Field label="Target" value={metadata.target_id as string} />
                <Field label="Satellite" value={metadata.satellite_id as string} />
              </InspectorSection>
              <InspectorSection title="Timing" icon="Clock">
                <Field label="Start" value={formatDateTime(metadata.start_time as string)} />
                <Field label="End" value={formatDateTime(metadata.end_time as string)} />
              </InspectorSection>
              {metadata.roll_angle !== undefined && (
                <InspectorSection title="Attitude" icon="Gauge">
                  <Field
                    label="Roll"
                    value={(metadata.roll_angle as number)?.toFixed(1)}
                    unit="°"
                  />
                  <Field
                    label="Pitch"
                    value={(metadata.pitch_angle as number)?.toFixed(1)}
                    unit="°"
                  />
                </InspectorSection>
              )}
              {/* Quick Actions for repair items */}
              {selectedRepairItem && (
                <div className="px-4 py-3 border-t border-gray-700">
                  <div className="text-xs text-gray-500 mb-2">Quick Actions</div>
                  <div className="flex gap-2">
                    <ActionButton
                      label="Focus Timeline"
                      icon="Clock"
                      onClick={focusTimelineOnRepairItem}
                      variant="secondary"
                    />
                    <ActionButton
                      label="Clear"
                      icon="X"
                      onClick={clearRepairSelection}
                      variant="secondary"
                    />
                  </div>
                </div>
              )}
            </>
          )}
          {/* PR-LOCK-OPS-01: Acquisition section with lock control */}
          {unifiedSelectedType === 'acquisition' && selectedAcquisitionId && (
            <>
              {/* Repair Change Badge (when selected from repair report) */}
              {selectedRepairItem && (
                <div className="px-4 py-2">
                  <RepairChangeBadge
                    type={selectedRepairItem.type}
                    movedInfo={selectedRepairItem.movedInfo}
                    itemReason={selectedRepairItemReason}
                  />
                </div>
              )}
              <InspectorSection title="Overview" icon="Target">
                <Field label="Target" value={metadata.target_id as string} />
                <Field label="Satellite" value={metadata.satellite_id as string} />
                {typeof metadata.order_id === 'string' && (
                  <Field label="Order" value={metadata.order_id} />
                )}
              </InspectorSection>
              <InspectorSection title="Timing" icon="Clock">
                <Field label="Start" value={formatDateTime(metadata.start_time as string)} />
                <Field label="End" value={formatDateTime(metadata.end_time as string)} />
              </InspectorSection>

              {/* PR-LOCK-OPS-01: Lock Control Section */}
              <div className="px-4 py-3 border-t border-gray-700">
                <div className="text-xs text-gray-500 mb-2 flex items-center gap-1">
                  <Shield size={12} />
                  Lock Control
                </div>
                {(() => {
                  const isRepairPreview = lastSelectionSource === 'repair'
                  const acqLockLevel = lockLevels.get(selectedAcquisitionId) ?? 'none'
                  const isLocked = acqLockLevel === 'hard'
                  const isPending = lockPending.has(selectedAcquisitionId)

                  if (isRepairPreview) {
                    return (
                      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50">
                        <Lock size={14} className="text-gray-500" />
                        <div>
                          <div className="text-xs text-gray-400">
                            Locking available after commit
                          </div>
                          <div className="text-[10px] text-gray-500">
                            Commit the repair plan first, then lock items
                          </div>
                        </div>
                      </div>
                    )
                  }

                  return (
                    <button
                      onClick={() => toggleLock(selectedAcquisitionId)}
                      disabled={isPending}
                      className={`
                        w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all
                        ${isPending ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                        ${
                          isLocked
                            ? 'bg-red-950/30 border-red-800/40 hover:bg-red-950/50'
                            : 'bg-gray-800/50 border-gray-700/50 hover:bg-gray-800 hover:border-gray-600'
                        }
                      `}
                    >
                      {isLocked ? (
                        <Shield size={16} className="text-red-400" />
                      ) : (
                        <Unlock size={16} className="text-gray-400" />
                      )}
                      <div className="flex-1 text-left">
                        <div
                          className={`text-xs font-medium ${isLocked ? 'text-red-300' : 'text-gray-300'}`}
                        >
                          {isLocked ? 'Hard Locked' : 'Unlocked'}
                        </div>
                        <div className="text-[10px] text-gray-500">
                          {isLocked
                            ? 'Protected from repair — click to unlock'
                            : 'Flexible — click to lock (protect from repair)'}
                        </div>
                      </div>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                          isLocked ? 'bg-red-900/40 text-red-300' : 'bg-gray-700 text-gray-400'
                        }`}
                      >
                        {isLocked ? 'Unlock' : 'Lock'}
                      </span>
                    </button>
                  )
                })()}
              </div>

              {/* Quick Actions for repair items */}
              {selectedRepairItem && (
                <div className="px-4 py-3 border-t border-gray-700">
                  <div className="text-xs text-gray-500 mb-2">Quick Actions</div>
                  <div className="flex gap-2">
                    <ActionButton
                      label="Focus Timeline"
                      icon="Clock"
                      onClick={focusTimelineOnRepairItem}
                      variant="secondary"
                    />
                    <ActionButton
                      label="Clear"
                      icon="X"
                      onClick={clearRepairSelection}
                      variant="secondary"
                    />
                  </div>
                </div>
              )}
            </>
          )}
          {unifiedSelectedType === 'conflict' && selectedConflictId && (
            <ConflictInspector
              conflictId={selectedConflictId}
              conflictData={selectedConflictData}
              onAcquisitionClick={handleConflictAcquisitionClick}
              onBackToSchedule={handleBackToSchedule}
              onFocusMap={handleConflictFocusMap}
              onFocusTimeline={handleConflictFocusTimeline}
            />
          )}
        </div>
      </div>
    )
  }

  // Get icon for node type
  const getNodeIcon = (type: TreeNodeType): React.ElementType => {
    const iconMap: Record<TreeNodeType, React.ElementType> = {
      workspace: Layers,
      scenario: Clock,
      assets: Layers,
      satellites: Satellite,
      satellite: Satellite,
      ground_stations: Radio,
      ground_station: Radio,
      targets: Target,
      target: MapPin,
      constraints: Settings,
      sensor_constraint: Eye,
      spacecraft_constraint: Gauge,
      planning_constraint: Sliders,
      runs: Play,
      analysis_run: BarChart2,
      planning_run: Calendar,
      results: CheckCircle,
      opportunities: Zap,
      opportunity: Zap,
      plans: FileText,
      plan: FileText,
      plan_item: FileText,
      orders: Package,
      order: Package,
      imports: Layers,
      import_source: Layers,
    }
    return iconMap[type] || Info
  }

  // At this point we know hasTreeSelection is true, so selectedNodeType is not null
  const NodeIcon = getNodeIcon(selectedNodeType!)

  // Get subtitle for node type - only show when it adds info beyond the name
  const getNodeSubtitle = (type: TreeNodeType, _name?: string): string | null => {
    // Container nodes where name IS the type - no subtitle needed
    const containerTypes: TreeNodeType[] = [
      'workspace',
      'scenario',
      'assets',
      'satellites',
      'ground_stations',
      'targets',
      'constraints',
      'runs',
      'results',
      'opportunities',
      'plans',
      'orders',
      'imports',
    ]
    if (containerTypes.includes(type)) return null

    // For individual items, show the type as context
    const labelMap: Partial<Record<TreeNodeType, string>> = {
      satellite: 'Satellite',
      ground_station: 'Ground Station',
      target: 'Target',
      opportunity: 'Opportunity',
      plan: 'Plan',
      plan_item: 'Plan Item',
      order: 'Order',
      sensor_constraint: 'Sensor Constraint',
      spacecraft_constraint: 'Spacecraft Constraint',
      planning_constraint: 'Planning Constraint',
      analysis_run: 'Analysis Run',
      planning_run: 'Planning Run',
      import_source: 'Import Source',
    }
    return labelMap[type] || null
  }

  const subtitle = getNodeSubtitle(selectedNodeType!, metadata?.name as string)

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <NodeIcon className="w-5 h-5 text-blue-400" />
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-white truncate">
              {(metadata?.name as string) || selectedNodeId}
            </h3>
            {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {renderInspectorContent(selectedNodeType!, metadata, handleAction)}
      </div>
    </div>
  )
}

// =============================================================================
// Helper Functions
// =============================================================================

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleDateString()
  } catch {
    return dateStr
  }
}

function formatDateTime(dateStr: string | undefined): string {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function extractPassIndex(nodeId: string): number | null {
  const match = nodeId.match(/opportunity_(\d+)_|plan_item_\w+_(\d+)/)
  if (match) {
    return parseInt(match[1] || match[2], 10)
  }
  return null
}

function extractTargetName(nodeId: string): string | null {
  // Format: target_mission_0_Athens or target_0_Athens
  const match = nodeId.match(/target_(?:mission_)?(?:\d+_)?(.+)$/)
  return match ? match[1] : null
}

function extractAlgorithmFromPlanId(nodeId: string): string | null {
  // Format: plan_first_fit or plan_best_fit
  const match = nodeId.match(/^plan_(.+)$/)
  return match ? match[1] : null
}

function extractOrderId(nodeId: string): string | null {
  // Format: order_<order_id>
  const match = nodeId.match(/^order_(.+)$/)
  return match ? match[1] : null
}

function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function calculateDuration(startTime: string, endTime: string): string {
  try {
    const start = new Date(startTime)
    const end = new Date(endTime)
    const hours = (end.getTime() - start.getTime()) / (1000 * 60 * 60)
    if (hours < 24) {
      return `${hours.toFixed(1)} hours`
    } else {
      const days = hours / 24
      return `${days.toFixed(1)} days`
    }
  } catch {
    return 'Unknown'
  }
}

function findNodeMetadata(
  nodeId: string,
  nodeType: TreeNodeType | null,
  state: ReturnType<typeof useMission>['state'],
  planningResults?: Record<string, import('../../types').AlgorithmResult> | null,
  orders?: import('../../types').AcceptedOrder[],
  groundStationsCount: number = 0,
): Record<string, unknown> | undefined {
  if (!nodeType) return undefined

  const missionData = state.missionData

  // Handle different node types
  switch (nodeType) {
    case 'workspace': {
      // Get workspace data from state or mission data
      const satellites = missionData?.satellites || []
      const targets = missionData?.targets || []
      const passes = missionData?.passes || []
      return {
        name: missionData?.satellite_name || 'Current Workspace',
        createdAt: missionData?.start_time,
        updatedAt: new Date().toISOString(),
        schemaVersion: '1.0',
        satellitesCount: satellites.length || (missionData?.satellite_name ? 1 : 0),
        targetsCount: targets.length,
        opportunitiesCount: passes.length,
        plansCount: 0,
      }
    }

    case 'assets': {
      const satellites = missionData?.satellites || []
      const satCount = satellites.length || (missionData?.satellite_name ? 1 : 0)
      return {
        name: 'Assets',
        description: 'Satellites and ground stations',
        satellitesCount: satCount,
        groundStationsCount: 0,
      }
    }

    case 'targets': {
      const targets = missionData?.targets || []
      const passes = missionData?.passes || []
      return {
        name: 'Targets',
        description: 'Ground targets for imaging or communication',
        targetsCount: targets.length,
        totalOpportunities: passes.length,
        coveredTargets: new Set(passes.map((p) => p.target)).size,
      }
    }

    case 'constraints': {
      return {
        name: 'Constraints',
        description: 'Mission and spacecraft constraints',
        sensorFov: missionData?.sensor_fov_half_angle_deg,
        maxRoll: missionData?.max_spacecraft_roll_deg,
        elevationMask: missionData?.elevation_mask,
        missionType: missionData?.mission_type,
      }
    }

    case 'runs': {
      return {
        name: 'Runs',
        description: 'Analysis and planning runs',
        hasAnalysis: !!missionData?.passes?.length,
        lastRunTime: missionData?.start_time,
        passesFound: missionData?.passes?.length || 0,
      }
    }

    case 'results': {
      const passes = missionData?.passes || []
      return {
        name: 'Results',
        description: 'Feasibility analysis results',
        opportunitiesCount: passes.length,
        uniqueTargets: new Set(passes.map((p) => p.target)).size,
        avgElevation:
          passes.length > 0
            ? passes.reduce((sum, p) => sum + (p.max_elevation || 0), 0) / passes.length
            : 0,
      }
    }

    case 'opportunities': {
      const passes = missionData?.passes || []
      return {
        name: 'Opportunities',
        description: 'Satellite pass opportunities',
        totalCount: passes.length,
        uniqueTargets: new Set(passes.map((p) => p.target)).size,
      }
    }

    case 'scenario': {
      const startTime = missionData?.start_time
      const endTime = missionData?.end_time
      return {
        missionMode: missionData?.mission_type?.toUpperCase() || 'N/A',
        timeWindowStart: startTime,
        timeWindowEnd: endTime,
        duration: startTime && endTime ? calculateDuration(startTime, endTime) : null,
      }
    }

    case 'satellite': {
      // Extract satellite name from nodeId
      const satName = nodeId.replace(/^satellite_(mission_)?/, '')
      const satObj = state.sceneObjects.find(
        (o) => o.type === 'satellite' && (nodeId.includes(o.id) || o.name === satName),
      )

      // Find satellite in mission data satellites array for color
      const satellites = missionData?.satellites || []
      const missionSat = satellites.find((s) => s.name === satName || s.id === satName)

      // Get capabilities from mission data
      return {
        name: satObj?.name || missionSat?.name || missionData?.satellite_name || satName,
        color: satObj?.color || missionSat?.color,
        orbitSource: 'TLE',
        maxRoll: missionData?.max_spacecraft_roll_deg,
        sensorFov: missionData?.sensor_fov_half_angle_deg,
        // Slew rate is satellite_agility (°/s) - NOT max_spacecraft_roll_deg
        agility: missionData?.satellite_agility,
      }
    }

    case 'target': {
      // Extract target name from nodeId
      // nodeId format: "target_target_1_Istanbul" or "target_mission_1_Istanbul"
      // We need to extract just "Istanbul"
      const targetNameMatch = nodeId.match(/target_(?:target_|mission_)?(?:\d+_)?(.+)$/)
      const targetName = targetNameMatch
        ? targetNameMatch[1]
        : nodeId.replace(/^target_(?:target_|mission_)?(?:\d+_)?/, '')

      // Find in scene objects first
      const targetObj = state.sceneObjects.find(
        (o) => o.type === 'target' && (nodeId.includes(o.id) || o.name === targetName),
      )

      // Find in mission data targets for priority/color
      const missionTarget = missionData?.targets?.find((t) => t.name === targetName)

      // Calculate statistics from passes
      const targetPasses = missionData?.passes?.filter((p) => p.target === targetName) || []
      const elevations = targetPasses
        .map((p) => p.max_elevation)
        .filter((e): e is number => e !== undefined && e !== null)

      return {
        name: targetObj?.name || missionTarget?.name || targetName,
        latitude: targetObj?.position?.latitude || missionTarget?.latitude,
        longitude: targetObj?.position?.longitude || missionTarget?.longitude,
        priority: missionTarget?.priority ?? 1,
        color: targetObj?.color || missionTarget?.color,
        opportunitiesCount: targetPasses.length,
        bestElevation: elevations.length > 0 ? Math.max(...elevations) : undefined,
        meanElevation:
          elevations.length > 0
            ? elevations.reduce((a, b) => a + b, 0) / elevations.length
            : undefined,
      }
    }

    case 'sensor_constraint':
      return {
        name: 'Sensor',
        fovHalfAngle: missionData?.sensor_fov_half_angle_deg,
        imagingMode: missionData?.mission_type,
      }

    case 'spacecraft_constraint':
      return {
        name: 'Spacecraft',
        maxRoll: missionData?.max_spacecraft_roll_deg,
        // Slew rate is satellite_agility (°/s) - NOT max_spacecraft_roll_deg (which is max angle)
        slewRate: missionData?.satellite_agility,
      }

    case 'planning_constraint': {
      // Calculate coverage from planning results if available
      const totalOpportunities = missionData?.passes?.length || 0
      const hasResults = planningResults && Object.keys(planningResults).length > 0
      let scheduledCount = 0
      let coveragePercent: number | undefined

      if (hasResults) {
        // Get the first algorithm's results for coverage calculation
        const firstAlgo = Object.keys(planningResults)[0]
        scheduledCount = planningResults[firstAlgo]?.metrics?.opportunities_accepted || 0
        coveragePercent =
          totalOpportunities > 0 ? Math.round((scheduledCount / totalOpportunities) * 100) : 0
      }

      return {
        name: 'Planning',
        totalPasses: missionData?.total_passes || totalOpportunities,
        scheduledPasses: hasResults ? scheduledCount : undefined,
        coveragePercentage: coveragePercent,
        note: !hasResults ? 'Run Mission Planning to calculate' : undefined,
      }
    }

    case 'opportunity': {
      const oppMatch = nodeId.match(/opportunity_(\d+)_(.+)$/)
      if (oppMatch && missionData?.passes) {
        const passIndex = parseInt(oppMatch[1], 10)
        const targetName = oppMatch[2]
        const pass = missionData.passes[passIndex]
        if (pass) {
          // Calculate duration from start/end times if not provided
          let duration = pass.duration_s
          if (!duration && pass.start_time && pass.end_time) {
            const start = new Date(pass.start_time).getTime()
            const end = new Date(pass.end_time).getTime()
            duration = (end - start) / 1000
          }
          // Get satellite color
          const satellites = missionData.satellites || []
          const satIndex = satellites.findIndex(
            (s) => s.id === pass.satellite_id || s.name === pass.satellite_id,
          )
          const satelliteColor = satIndex >= 0 ? satellites[satIndex]?.color : undefined
          return {
            ...pass,
            name: `${targetName} Pass #${passIndex + 1}`,
            pass_index: passIndex + 1,
            satellite_name: pass.satellite_id || missionData.satellite_name,
            satellite_color: satelliteColor,
            duration_s: duration,
          }
        }
      }
      break
    }

    // Container nodes for satellites and ground stations
    case 'satellites': {
      const satellites = missionData?.satellites || []
      const satCount = satellites.length || (missionData?.satellite_name ? 1 : 0)
      return {
        name: 'Satellites',
        description: 'Orbital assets for the mission',
        count: satCount,
        primarySatellite: missionData?.satellite_name,
      }
    }

    case 'ground_stations': {
      return {
        name: 'Ground Stations',
        description: 'Ground-based communication stations',
        count: groundStationsCount,
      }
    }

    case 'ground_station': {
      // Extract station name from nodeId
      const stationName = nodeId.replace(/^ground_station_/, '')
      return {
        name: stationName,
        type: 'Ground Station',
        status: 'Active',
      }
    }

    // Run sub-nodes
    case 'analysis_run': {
      const analysisTargets = missionData?.targets || []
      const analysisPasses = missionData?.passes || []
      const targetsWithPasses = new Set(analysisPasses.map((p) => p.target)).size
      const targetCoverage =
        analysisTargets.length > 0 ? (targetsWithPasses / analysisTargets.length) * 100 : 0
      return {
        name: 'Visibility Analysis',
        description: 'Satellite pass detection',
        status: analysisPasses.length ? 'Complete' : 'Not run',
        passesFound: analysisPasses.length,
        totalTargets: analysisTargets.length,
        targetsWithPasses: targetsWithPasses,
        targetCoverage: targetCoverage,
        startTime: missionData?.start_time,
        endTime: missionData?.end_time,
      }
    }

    case 'planning_run': {
      // Check if planning results exist
      const hasPlanningResults = planningResults && Object.keys(planningResults).length > 0

      if (hasPlanningResults) {
        const algorithms = Object.keys(planningResults)
        const firstAlgo = algorithms[0]
        const result = planningResults[firstAlgo]
        return {
          name: 'Mission Planning',
          description: 'Schedule optimization',
          status: 'Complete',
          algorithm: algorithms
            .map((a) => a.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()))
            .join(', '),
          accepted: result?.metrics?.opportunities_accepted,
          totalValue: result?.metrics?.total_value,
          runtime: result?.metrics?.runtime_ms,
        }
      }

      return {
        name: 'Mission Planning',
        description: 'Schedule optimization',
        status: 'Not run',
        algorithm: 'N/A',
      }
    }

    // Plan nodes
    case 'plan': {
      // Extract algorithm from nodeId: plan_<algorithm>
      const planMatch = nodeId.match(/^plan_(.+)$/)
      const algorithm = planMatch ? planMatch[1] : null
      console.log('[Plan Inspector] nodeId:', nodeId, 'algorithm:', algorithm)
      console.log('[Plan Inspector] planningResults:', planningResults)
      const result = algorithm && planningResults ? planningResults[algorithm] : null
      console.log('[Plan Inspector] result:', result)

      if (result) {
        return {
          name:
            algorithm?.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()) ||
            'Mission Plan',
          algorithm: algorithm,
          runtime: result.metrics.runtime_ms,
          accepted: result.metrics.opportunities_accepted,
          rejected: result.metrics.opportunities_rejected,
          totalValue: result.metrics.total_value,
          meanIncidence: result.metrics.mean_incidence_deg,
          utilization: result.metrics.utilization,
          itemCount: result.schedule.length,
          status: 'Complete',
        }
      }
      return {
        name: 'Mission Plan',
        description: 'Scheduled imaging/communication plan',
        itemCount: 0,
        status: 'Draft',
      }
    }

    case 'plan_item': {
      // Extract algorithm and index from nodeId: plan_item_<algorithm>_<index>
      const itemMatch = nodeId.match(/plan_item_(.+)_(\d+)$/)
      if (itemMatch && planningResults) {
        const algorithm = itemMatch[1]
        const itemIndex = parseInt(itemMatch[2], 10)
        const result = planningResults[algorithm]
        const scheduleItem = result?.schedule?.[itemIndex]

        if (scheduleItem) {
          return {
            name: `${scheduleItem.target_id} - Item ${itemIndex + 1}`,
            ...scheduleItem,
          }
        }
      }
      return { name: 'Plan Item', status: 'Unknown' }
    }

    case 'order': {
      // Extract order ID from nodeId: order_<order_id>
      const orderMatch = nodeId.match(/^order_(.+)$/)
      const orderId = orderMatch ? orderMatch[1] : null
      const order = orderId && orders ? orders.find((o) => o.order_id === orderId) : null

      if (order) {
        // Get unique satellites and targets from schedule
        const satellites = new Set(order.schedule.map((s) => s.satellite_id))
        const targets = new Set(order.schedule.map((s) => s.target_id))
        return {
          name: order.name,
          order_id: order.order_id,
          created_at: order.created_at,
          algorithm: order.algorithm,
          accepted: order.metrics.accepted,
          totalValue: order.metrics.total_value,
          utilization: order.metrics.utilization,
          satellites: satellites.size,
          targets: targets.size,
          schedule: order.schedule,
          status: 'Accepted',
        }
      }
      return {
        name: 'Tasking Order',
        description: 'Generated tasking command',
        status: 'Draft',
        format: 'JSON',
      }
    }

    case 'orders': {
      // Filter orders to match what's shown in tree (only current scenario orders)
      const currentPlanningAlgorithms = planningResults ? Object.keys(planningResults) : []
      const filteredOrders =
        orders?.filter((order) => {
          if (currentPlanningAlgorithms.length === 0) return false
          const currentResult = planningResults?.[order.algorithm]
          if (!currentResult) return false
          if (order.schedule.length !== currentResult.schedule.length) return false
          if (order.schedule.length > 0 && currentResult.schedule.length > 0) {
            const orderFirst = order.schedule[0]
            const currentFirst = currentResult.schedule[0]
            return (
              orderFirst.target_id === currentFirst.target_id &&
              orderFirst.start_time === currentFirst.start_time
            )
          }
          return true
        }) || []

      return {
        name: 'Orders',
        description: 'Tasking orders for satellite operations',
        count: filteredOrders.length,
      }
    }

    case 'plans': {
      const planningResults = usePlanningStore.getState().results
      const activeAlgo = usePlanningStore.getState().activeAlgorithm
      const activeResult = activeAlgo && planningResults ? planningResults[activeAlgo] : null
      const scheduledCount = activeResult?.schedule?.length || 0
      const coverage = activeResult?.target_statistics?.coverage_percentage
      return {
        name: 'Plans',
        scheduledCount,
        algorithm: activeAlgo ? activeAlgo.replace(/_/g, ' ') : undefined,
        coverage: coverage ? `${coverage.toFixed(1)}%` : undefined,
        status: scheduledCount > 0 ? 'Complete' : 'No plan',
      }
    }

    case 'imports': {
      return {
        name: 'Imports',
        description: 'External data imports',
        count: 0,
      }
    }

    case 'import_source': {
      return {
        name: 'Import Source',
        type: 'External',
        status: 'Available',
      }
    }

    default:
      return undefined
  }
}

function renderInspectorContent(
  nodeType: TreeNodeType,
  metadata: Record<string, unknown> | undefined,
  onAction: (action: string) => void,
): React.ReactNode {
  switch (nodeType) {
    // Top-level containers
    case 'workspace':
      return <WorkspaceInspector metadata={metadata} />
    case 'assets':
      return <AssetsInspector metadata={metadata} />
    case 'targets':
      return <TargetsContainerInspector metadata={metadata} />
    case 'constraints':
      return <ConstraintsInspector metadata={metadata} />
    case 'runs':
      return <RunsInspector metadata={metadata} />
    case 'results':
      return <ResultsInspector metadata={metadata} />
    case 'opportunities':
      return <OpportunitiesContainerInspector metadata={metadata} />
    case 'plans':
      return <PlansContainerInspector metadata={metadata} />
    case 'orders':
      return <OrdersContainerInspector metadata={metadata} />
    case 'imports':
      return <ImportsContainerInspector metadata={metadata} />

    // Scenario
    case 'scenario':
      return <ScenarioInspector metadata={metadata} />

    // Assets children
    case 'satellites':
      return <SatellitesContainerInspector metadata={metadata} />
    case 'satellite':
      return <SatelliteInspector metadata={metadata} onAction={onAction} />
    case 'ground_stations':
      return <GroundStationsContainerInspector metadata={metadata} />
    case 'ground_station':
      return <GroundStationInspector metadata={metadata} />

    // Targets children
    case 'target':
      return <TargetInspector metadata={metadata} onAction={onAction} />

    // Constraints children
    case 'sensor_constraint':
      return <SensorConstraintInspector metadata={metadata} />
    case 'spacecraft_constraint':
      return <SpacecraftConstraintInspector metadata={metadata} />
    case 'planning_constraint':
      return <PlanningConstraintInspector metadata={metadata} />

    // Runs children
    case 'analysis_run':
      return <AnalysisRunInspector metadata={metadata} />
    case 'planning_run':
      return <PlanningRunInspector metadata={metadata} />

    // Results children
    case 'opportunity':
      return <OpportunityInspector metadata={metadata} onAction={onAction} />

    // Plans children
    case 'plan':
      return <PlanInspector metadata={metadata} onAction={onAction} />
    case 'plan_item':
      return <PlanItemInspector metadata={metadata} onAction={onAction} />

    // Orders children
    case 'order':
      return <OrderInspector metadata={metadata} onAction={onAction} />

    // Imports children
    case 'import_source':
      return <ImportSourceInspector metadata={metadata} />

    default:
      return (
        <div className="p-4 text-sm text-gray-500">
          No inspector available for this object type.
        </div>
      )
  }
}

export default Inspector
