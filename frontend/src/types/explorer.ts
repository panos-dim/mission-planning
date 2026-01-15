/**
 * STK-Style Object Explorer Tree Types
 *
 * Defines the hierarchical structure for the workspace-aware object explorer
 * that mimics STK/SaVoir-like navigation and inspection patterns.
 */

// =============================================================================
// Tree Node Types
// =============================================================================

export type TreeNodeType =
  | "workspace"
  | "scenario"
  | "assets"
  | "satellites"
  | "satellite"
  | "ground_stations"
  | "ground_station"
  | "targets"
  | "target"
  | "constraints"
  | "sensor_constraint"
  | "spacecraft_constraint"
  | "planning_constraint"
  | "runs"
  | "analysis_run"
  | "planning_run"
  | "results"
  | "opportunities"
  | "opportunity"
  | "plans"
  | "plan"
  | "plan_item"
  | "orders"
  | "order"
  | "imports"
  | "import_source";

export interface TreeNodeBadge {
  count: number;
  color?: "blue" | "green" | "yellow" | "red" | "gray";
}

export interface TreeNode {
  id: string;
  type: TreeNodeType;
  name: string;
  icon?: string;
  children?: TreeNode[];
  badge?: TreeNodeBadge;
  metadata?: Record<string, unknown>;
  parentId?: string;
  isExpandable?: boolean;
  isLeaf?: boolean;
}

export interface TreeState {
  expandedNodes: Set<string>;
  selectedNodeId: string | null;
  searchQuery: string;
  filteredNodeIds: Set<string> | null;
}

// =============================================================================
// Inspector Metadata Types
// =============================================================================

export interface InspectorSection {
  id: string;
  title: string;
  collapsed?: boolean;
  fields: InspectorField[];
}

export interface InspectorField {
  key: string;
  label: string;
  value: string | number | boolean | null | undefined;
  type:
    | "text"
    | "number"
    | "date"
    | "duration"
    | "coordinate"
    | "angle"
    | "badge"
    | "link";
  unit?: string;
  color?: string;
  copyable?: boolean;
}

export interface InspectorAction {
  id: string;
  label: string;
  icon: string;
  onClick: () => void;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
}

export interface InspectorData {
  nodeId: string;
  nodeType: TreeNodeType;
  title: string;
  subtitle?: string;
  icon?: string;
  lastUpdated?: string;
  sections: InspectorSection[];
  actions: InspectorAction[];
}

// =============================================================================
// Workspace Tree Structure
// =============================================================================

export interface WorkspaceTreeData {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  schemaVersion: string;
  appVersion: string | null;

  // Scenario info
  scenario: {
    missionMode: "OPTICAL" | "SAR" | "COMMUNICATION" | null;
    timeWindowStart: string | null;
    timeWindowEnd: string | null;
  };

  // Asset counts
  counts: {
    satellites: number;
    groundStations: number;
    targets: number;
    opportunities: number;
    plans: number;
    orders: number;
  };

  // Config hash for change detection
  configHash?: string;
}

// =============================================================================
// Satellite Inspector Data
// =============================================================================

export interface SatelliteInspectorData {
  id: string;
  name: string;
  orbitSource: string; // TLE file name or ID
  orbitEpoch?: string;
  color?: string;

  // Capabilities
  sensorFov?: number;
  maxRoll?: number;
  maxPitch?: number;
  rollRate?: number;
  pitchRate?: number;

  // Run stats
  opportunitiesCount: number;
  scheduledCount: number;
}

// =============================================================================
// Target Inspector Data
// =============================================================================

export interface TargetInspectorData {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  altitude?: number;
  priority: number;
  value?: number;
  color?: string;

  // Statistics
  opportunitiesCount: number;
  bestIncidence?: number;
  meanIncidence?: number;
}

// =============================================================================
// Opportunity Inspector Data
// =============================================================================

export interface OpportunityInspectorData {
  id: string;
  satelliteId: string;
  satelliteName: string;
  targetId: string;
  targetName: string;

  // Timing
  startTime: string;
  endTime: string;
  optimalTime?: string;
  durationSeconds: number;

  // Geometry
  incidenceAngle?: number;
  offNadir?: number;
  maxElevation?: number;

  // Scoring
  value?: number;
  qualityScore?: number;
}

// =============================================================================
// Planning Run Inspector Data
// =============================================================================

export interface PlanningRunInspectorData {
  id: string;
  algorithm: string;
  algorithmDisplayName: string;
  timestamp: string;

  // Parameters snapshot
  params: {
    imagingTimeS: number;
    maxRollRateDps: number;
    maxPitchRateDps?: number;
    qualityModel: string;
    valueSource: string;
  };

  // Metrics
  metrics: {
    accepted: number;
    rejected: number;
    totalValue: number;
    meanIncidence?: number;
    runtimeMs: number;
    utilization: number;
  };
}

// =============================================================================
// Plan Item Inspector Data
// =============================================================================

export interface PlanItemInspectorData {
  id: string;
  opportunityId: string;
  satelliteId: string;
  targetId: string;
  targetName: string;

  // Timing
  startTime: string;
  endTime: string;

  // Maneuver
  deltaRoll: number;
  deltaPitch?: number;
  slewTime: number;
  slackTime: number;

  // Value
  value: number;
  density: number | "inf";
  incidenceAngle?: number;
}

// =============================================================================
// Order Inspector Data
// =============================================================================

export interface OrderInspectorData {
  id: string;
  name: string;
  createdAt: string;
  algorithm: string;

  // Metrics snapshot
  metrics: {
    accepted: number;
    rejected: number;
    totalValue: number;
    meanIncidence: number;
    imagingTimeS: number;
    maneuverTimeS: number;
    utilization: number;
    runtimeMs: number;
  };

  // Coverage
  satellitesInvolved: string[];
  targetsCovered: string[];
}

// =============================================================================
// Analysis Run Inspector Data
// =============================================================================

export interface AnalysisRunInspectorData {
  id: string;
  timestamp: string;

  // Inputs
  inputs: {
    timeWindowStart: string;
    timeWindowEnd: string;
    missionMode: string;
    elevationMask?: number;
    maxRoll?: number;
  };

  // Outputs
  outputs: {
    opportunitiesCount: number;
    meanIncidence?: number;
    runtimeMs?: number;
  };
}

// =============================================================================
// Context Menu Types
// =============================================================================

export interface ContextMenuAction {
  id: string;
  label: string;
  icon: string;
  onClick: () => void;
  dividerBefore?: boolean;
  dividerAfter?: boolean;
  disabled?: boolean;
  variant?: "default" | "danger";
}

export interface ContextMenuState {
  isOpen: boolean;
  x: number;
  y: number;
  nodeId: string | null;
  nodeType: TreeNodeType | null;
  actions: ContextMenuAction[];
}

// =============================================================================
// Tree Builder Utilities
// =============================================================================

export interface TreeBuilderOptions {
  includeEmptyGroups?: boolean;
  maxDepth?: number;
  filterFn?: (node: TreeNode) => boolean;
}
