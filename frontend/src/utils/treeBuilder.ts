/**
 * Tree Builder Utility
 *
 * Transforms workspace, mission, and planning data into a hierarchical
 * tree structure for the STK-style Object Explorer.
 */

import type { TreeNode, TreeNodeType, TreeNodeBadge } from "../types/explorer";
import type {
  MissionData,
  WorkspaceData,
  SceneObject,
  AlgorithmResult,
  AcceptedOrder,
  PassData,
} from "../types";

// =============================================================================
// Icon Mapping
// =============================================================================

export const NODE_ICONS: Record<TreeNodeType, string> = {
  workspace: "FolderOpen",
  scenario: "Clock",
  assets: "Box",
  satellites: "Satellite",
  satellite: "Satellite",
  ground_stations: "Radio",
  ground_station: "Radio",
  targets: "Target",
  target: "MapPin",
  constraints: "Settings",
  sensor_constraint: "Eye",
  spacecraft_constraint: "Gauge",
  planning_constraint: "Sliders",
  runs: "Play",
  analysis_run: "BarChart2",
  planning_run: "Calendar",
  results: "CheckCircle",
  opportunities: "Zap",
  opportunity: "Zap",
  plans: "FileText",
  plan: "FileText",
  plan_item: "ChevronRight",
  orders: "Package",
  order: "Package",
  imports: "Upload",
  import_source: "File",
};

// =============================================================================
// Badge Helpers
// =============================================================================

function createBadge(
  count: number,
  color?: TreeNodeBadge["color"],
): TreeNodeBadge | undefined {
  if (count === 0) return undefined;
  return { count, color: color || "gray" };
}

// =============================================================================
// Main Tree Builder
// =============================================================================

export interface TreeBuilderInput {
  workspaceData?: WorkspaceData | null;
  missionData?: MissionData | null;
  sceneObjects?: SceneObject[];
  algorithmResults?: Record<string, AlgorithmResult>;
  acceptedOrders?: AcceptedOrder[];
  analysisRuns?: Array<{
    id: string;
    timestamp: string;
    opportunitiesCount: number;
  }>;
  planningRuns?: Array<{
    id: string;
    algorithm: string;
    timestamp: string;
    accepted: number;
  }>;
  filterByTarget?: string | null;
}

export function buildObjectTree(input: TreeBuilderInput): TreeNode {
  const {
    workspaceData,
    missionData,
    sceneObjects = [],
    algorithmResults = {},
    acceptedOrders = [],
    analysisRuns = [],
    planningRuns = [],
    filterByTarget = null,
  } = input;

  // Root workspace node
  const workspaceNode: TreeNode = {
    id: "workspace",
    type: "workspace",
    name: workspaceData?.name || "Current Workspace",
    icon: NODE_ICONS.workspace,
    isExpandable: true,
    children: [],
  };

  // Scenario node
  const scenarioNode = buildScenarioNode(workspaceData, missionData);
  workspaceNode.children!.push(scenarioNode);

  // Assets node (Satellites, Ground Stations)
  const assetsNode = buildAssetsNode(missionData, sceneObjects);
  workspaceNode.children!.push(assetsNode);

  // Targets node
  const targetsNode = buildTargetsNode(missionData, sceneObjects);
  workspaceNode.children!.push(targetsNode);

  // Constraints node
  const constraintsNode = buildConstraintsNode(missionData, workspaceData);
  workspaceNode.children!.push(constraintsNode);

  // Runs node (Analysis + Planning history)
  const runsNode = buildRunsNode(analysisRuns, planningRuns);
  workspaceNode.children!.push(runsNode);

  // Results node (Opportunities, Plans, Orders)
  const resultsNode = buildResultsNode(
    missionData,
    algorithmResults,
    acceptedOrders,
    filterByTarget,
  );
  workspaceNode.children!.push(resultsNode);

  return workspaceNode;
}

// =============================================================================
// Scenario Node Builder
// =============================================================================

function buildScenarioNode(
  workspaceData: WorkspaceData | null | undefined,
  missionData: MissionData | null | undefined,
): TreeNode {
  const missionMode =
    missionData?.mission_type?.toUpperCase() ||
    workspaceData?.mission_mode ||
    "N/A";
  const startTime = missionData?.start_time || workspaceData?.time_window_start;
  const endTime = missionData?.end_time || workspaceData?.time_window_end;

  return {
    id: "scenario",
    type: "scenario",
    name: "Scenario",
    icon: NODE_ICONS.scenario,
    isExpandable: false,
    isLeaf: true,
    metadata: {
      missionMode,
      timeWindowStart: startTime,
      timeWindowEnd: endTime,
      duration:
        startTime && endTime ? calculateDuration(startTime, endTime) : null,
    },
  };
}

// =============================================================================
// Assets Node Builder
// =============================================================================

function buildAssetsNode(
  missionData: MissionData | null | undefined,
  sceneObjects: SceneObject[],
): TreeNode {
  const satellites = sceneObjects.filter((obj) => obj.type === "satellite");
  const groundStations = sceneObjects.filter(
    (obj) => obj.type === "ground_station",
  );

  // Also check missionData for satellites
  const missionSatellites = missionData?.satellites || [];
  const satelliteName = missionData?.satellite_name;

  const satelliteNodes: TreeNode[] = [];

  // Add satellites from scene objects
  satellites.forEach((sat) => {
    satelliteNodes.push({
      id: `satellite_${sat.id}`,
      type: "satellite",
      name: sat.name,
      icon: NODE_ICONS.satellite,
      isLeaf: true,
      metadata: {
        color: sat.color,
        position: sat.position,
      },
    });
  });

  // Add satellites from mission data if not already present
  if (satelliteName && !satelliteNodes.some((n) => n.name === satelliteName)) {
    satelliteNodes.push({
      id: `satellite_mission_${satelliteName}`,
      type: "satellite",
      name: satelliteName,
      icon: NODE_ICONS.satellite,
      isLeaf: true,
    });
  }

  missionSatellites.forEach((sat) => {
    if (!satelliteNodes.some((n) => n.name === sat.name)) {
      satelliteNodes.push({
        id: `satellite_${sat.id}`,
        type: "satellite",
        name: sat.name,
        icon: NODE_ICONS.satellite,
        isLeaf: true,
        metadata: { color: sat.color },
      });
    }
  });

  const groundStationNodes: TreeNode[] = groundStations.map((gs) => ({
    id: `ground_station_${gs.id}`,
    type: "ground_station" as TreeNodeType,
    name: gs.name,
    icon: NODE_ICONS.ground_station,
    isLeaf: true,
    metadata: {
      position: gs.position,
      color: gs.color,
    },
  }));

  return {
    id: "assets",
    type: "assets",
    name: "Assets",
    icon: NODE_ICONS.assets,
    isExpandable: true,
    children: [
      {
        id: "satellites",
        type: "satellites",
        name: "Satellites",
        icon: NODE_ICONS.satellites,
        isExpandable: satelliteNodes.length > 0,
        badge: createBadge(satelliteNodes.length, "blue"),
        children: satelliteNodes,
      },
      {
        id: "ground_stations",
        type: "ground_stations",
        name: "Ground Stations",
        icon: NODE_ICONS.ground_stations,
        isExpandable: groundStationNodes.length > 0,
        badge: createBadge(groundStationNodes.length, "gray"),
        children: groundStationNodes,
      },
    ],
  };
}

// =============================================================================
// Targets Node Builder
// =============================================================================

function buildTargetsNode(
  missionData: MissionData | null | undefined,
  sceneObjects: SceneObject[],
): TreeNode {
  // Filter to actual targets, excluding visualization entities
  const targetObjects = sceneObjects.filter((obj) => {
    if (obj.type !== "target") return false;
    // Exclude visualization helper entities that shouldn't appear as targets
    const id = obj.id?.toLowerCase() || "";
    const name = obj.name?.toLowerCase() || "";
    if (
      id.includes("agility_envelope") ||
      id.includes("coverage") ||
      id.includes("ground_track") ||
      id.includes("footprint") ||
      id.includes("pointing_cone") ||
      name.includes("coverage area") ||
      name.includes("sensor cone")
    ) {
      return false;
    }
    return true;
  });
  const missionTargets = missionData?.targets || [];

  const targetNodes: TreeNode[] = [];

  // Add targets from scene objects
  targetObjects.forEach((target) => {
    targetNodes.push({
      id: `target_${target.id}`,
      type: "target",
      name: target.name,
      icon: NODE_ICONS.target,
      isLeaf: true,
      metadata: {
        latitude: target.position?.latitude,
        longitude: target.position?.longitude,
        color: target.color,
      },
    });
  });

  // Add targets from mission data if not already present
  missionTargets.forEach((target, idx) => {
    if (!targetNodes.some((n) => n.name === target.name)) {
      targetNodes.push({
        id: `target_mission_${idx}_${target.name}`,
        type: "target",
        name: target.name,
        icon: NODE_ICONS.target,
        isLeaf: true,
        metadata: {
          latitude: target.latitude,
          longitude: target.longitude,
          priority: target.priority,
          color: target.color,
        },
      });
    }
  });

  return {
    id: "targets",
    type: "targets",
    name: "Targets",
    icon: NODE_ICONS.targets,
    isExpandable: targetNodes.length > 0,
    badge: createBadge(targetNodes.length, "green"),
    children: targetNodes,
  };
}

// =============================================================================
// Constraints Node Builder
// =============================================================================

function buildConstraintsNode(
  missionData: MissionData | null | undefined,
  workspaceData: WorkspaceData | null | undefined,
): TreeNode {
  const constraints = workspaceData?.scenario_config?.constraints || {};

  return {
    id: "constraints",
    type: "constraints",
    name: "Constraints",
    icon: NODE_ICONS.constraints,
    isExpandable: true,
    children: [
      {
        id: "sensor_constraint",
        type: "sensor_constraint",
        name: "Sensor",
        icon: NODE_ICONS.sensor_constraint,
        isLeaf: true,
        metadata: {
          fovHalfAngle:
            missionData?.sensor_fov_half_angle_deg ||
            constraints.sensor_fov_half_angle_deg,
        },
      },
      {
        id: "spacecraft_constraint",
        type: "spacecraft_constraint",
        name: "Spacecraft",
        icon: NODE_ICONS.spacecraft_constraint,
        isLeaf: true,
        metadata: {
          maxRoll:
            missionData?.max_spacecraft_roll_deg ||
            constraints.max_spacecraft_roll_deg,
          maxPitch: constraints.max_spacecraft_pitch_deg,
          elevationMask: missionData?.elevation_mask,
        },
      },
      {
        id: "planning_constraint",
        type: "planning_constraint",
        name: "Planning",
        icon: NODE_ICONS.planning_constraint,
        isLeaf: true,
        metadata: {
          qualityConfig: workspaceData?.scenario_config?.quality_config,
        },
      },
    ],
  };
}

// =============================================================================
// Runs Node Builder
// =============================================================================

function buildRunsNode(
  analysisRuns: Array<{
    id: string;
    timestamp: string;
    opportunitiesCount: number;
  }>,
  planningRuns: Array<{
    id: string;
    algorithm: string;
    timestamp: string;
    accepted: number;
  }>,
): TreeNode {
  const analysisRunNodes: TreeNode[] = analysisRuns.map((run) => ({
    id: `analysis_run_${run.id}`,
    type: "analysis_run" as TreeNodeType,
    name: formatRunTimestamp(run.timestamp),
    icon: NODE_ICONS.analysis_run,
    isLeaf: true,
    badge: createBadge(run.opportunitiesCount, "blue"),
    metadata: {
      timestamp: run.timestamp,
      opportunitiesCount: run.opportunitiesCount,
    },
  }));

  const planningRunNodes: TreeNode[] = planningRuns.map((run) => ({
    id: `planning_run_${run.id}`,
    type: "planning_run" as TreeNodeType,
    name: `${formatAlgorithmName(run.algorithm)} - ${formatRunTimestamp(
      run.timestamp,
    )}`,
    icon: NODE_ICONS.planning_run,
    isLeaf: true,
    badge: createBadge(run.accepted, "green"),
    metadata: {
      algorithm: run.algorithm,
      timestamp: run.timestamp,
      accepted: run.accepted,
    },
  }));

  return {
    id: "runs",
    type: "runs",
    name: "Runs",
    icon: NODE_ICONS.runs,
    isExpandable: true,
    children: [
      {
        id: "analysis_runs",
        type: "analysis_run",
        name: "Analysis Runs",
        icon: NODE_ICONS.analysis_run,
        isExpandable: analysisRunNodes.length > 0,
        badge: createBadge(analysisRunNodes.length),
        children: analysisRunNodes,
      },
      {
        id: "planning_runs",
        type: "planning_run",
        name: "Planning Runs",
        icon: NODE_ICONS.planning_run,
        isExpandable: planningRunNodes.length > 0,
        badge: createBadge(planningRunNodes.length),
        children: planningRunNodes,
      },
    ],
  };
}

// =============================================================================
// Results Node Builder
// =============================================================================

function buildResultsNode(
  missionData: MissionData | null | undefined,
  algorithmResults: Record<string, AlgorithmResult>,
  acceptedOrders: AcceptedOrder[],
  filterByTarget: string | null = null,
): TreeNode {
  // Build opportunities from mission passes
  const passes = missionData?.passes || [];
  const isSARMission =
    missionData?.imaging_type === "sar" || !!missionData?.sar;

  // Filter passes by target if filter is active
  const filteredPasses = filterByTarget
    ? passes.filter((pass) => pass.target === filterByTarget)
    : passes;

  // Helper to create opportunity node with SAR badges
  const createOpportunityNode = (
    pass: PassData,
    originalIdx: number,
    idx: number,
  ): TreeNode => {
    const passAny = pass as unknown as Record<string, unknown>;
    const targetName =
      pass.target || (passAny.target_name as string) || `Target ${idx}`;
    const startTime = pass.start_time || (passAny.aos_time as string) || "";
    const sarData = pass.sar_data;

    // Build name with SAR badges if applicable
    let displayName = `${targetName} - ${formatPassTime(startTime)}`;
    if (sarData) {
      const lookBadge = sarData.look_side === "LEFT" ? "L" : "R";
      const dirBadge = sarData.pass_direction === "ASCENDING" ? "↑" : "↓";
      displayName = `${targetName} [${lookBadge}${dirBadge}] - ${formatPassTime(
        startTime,
      )}`;
    }

    return {
      id: `opportunity_${originalIdx}_${targetName}`,
      type: "opportunity" as TreeNodeType,
      name: displayName,
      icon: NODE_ICONS.opportunity,
      isLeaf: true,
      metadata: {
        ...pass,
        index: originalIdx,
      },
    };
  };

  // For SAR missions, group opportunities by look_side and pass_direction
  let opportunityChildren: TreeNode[];

  if (isSARMission && filteredPasses.some((p) => p.sar_data)) {
    // Group by look side first
    const leftPasses = filteredPasses.filter(
      (p) => p.sar_data?.look_side === "LEFT",
    );
    const rightPasses = filteredPasses.filter(
      (p) => p.sar_data?.look_side === "RIGHT",
    );

    const leftNodes = leftPasses.map((pass, idx) => {
      const originalIdx = passes.indexOf(pass);
      return createOpportunityNode(pass, originalIdx, idx);
    });

    const rightNodes = rightPasses.map((pass, idx) => {
      const originalIdx = passes.indexOf(pass);
      return createOpportunityNode(pass, originalIdx, idx);
    });

    // Create grouping nodes
    opportunityChildren = [];

    if (leftNodes.length > 0) {
      opportunityChildren.push({
        id: "opportunities_left",
        type: "opportunities" as TreeNodeType,
        name: "Left Looking",
        icon: "ArrowLeft",
        isExpandable: true,
        badge: createBadge(leftNodes.length, "red"),
        children: leftNodes,
      });
    }

    if (rightNodes.length > 0) {
      opportunityChildren.push({
        id: "opportunities_right",
        type: "opportunities" as TreeNodeType,
        name: "Right Looking",
        icon: "ArrowRight",
        isExpandable: true,
        badge: createBadge(rightNodes.length, "blue"),
        children: rightNodes,
      });
    }

    // Add any passes without SAR data as "Other"
    const otherPasses = filteredPasses.filter((p) => !p.sar_data);
    if (otherPasses.length > 0) {
      const otherNodes = otherPasses.map((pass, idx) => {
        const originalIdx = passes.indexOf(pass);
        return createOpportunityNode(pass, originalIdx, idx);
      });
      opportunityChildren.push({
        id: "opportunities_other",
        type: "opportunities" as TreeNodeType,
        name: "Other",
        icon: NODE_ICONS.opportunities,
        isExpandable: true,
        badge: createBadge(otherNodes.length, "gray"),
        children: otherNodes,
      });
    }
  } else {
    // Non-SAR: flat list of opportunities
    opportunityChildren = [];
    filteredPasses.forEach((pass, idx) => {
      try {
        const originalIdx = passes.indexOf(pass);
        opportunityChildren.push(createOpportunityNode(pass, originalIdx, idx));
      } catch (error) {
        console.error(
          "[TreeBuilder] Error creating opportunity node:",
          error,
          pass,
        );
      }
    });
  }

  // Build plans from algorithm results
  const planNodes: TreeNode[] = Object.entries(algorithmResults)
    .filter(([, result]) => result?.schedule && result?.metrics) // Filter out invalid results
    .map(([algorithm, result]) => {
      const planItemNodes: TreeNode[] = (result.schedule || []).map(
        (item, idx) => ({
          id: `plan_item_${algorithm}_${idx}`,
          type: "plan_item" as TreeNodeType,
          name: `${item.target_id} @ ${formatPassTime(item.start_time)}`,
          icon: NODE_ICONS.plan_item,
          isLeaf: true,
          metadata: {
            ...item,
            algorithm,
          },
        }),
      );

      return {
        id: `plan_${algorithm}`,
        type: "plan" as TreeNodeType,
        name: formatAlgorithmName(algorithm),
        icon: NODE_ICONS.plan,
        isExpandable: planItemNodes.length > 0,
        badge: createBadge(
          result.metrics?.opportunities_accepted ?? 0,
          "green",
        ),
        children: planItemNodes,
        metadata: {
          algorithm,
          metrics: result.metrics,
        },
      };
    });

  // Build orders - only show orders that were created from current planning results
  // This ensures old orders from previous runs don't appear in the Object Explorer
  const currentPlanningAlgorithms = Object.keys(algorithmResults);

  const filteredOrders = acceptedOrders.filter((order) => {
    // If no current planning results, don't show any orders in tree
    if (currentPlanningAlgorithms.length === 0) return false;

    // Check if this order's algorithm matches one of the current planning results
    // AND the schedule has matching items (same opportunity IDs or similar signature)
    const currentResult = algorithmResults[order.algorithm];
    if (!currentResult) return false;

    // Compare schedule lengths as a quick check
    if (order.schedule.length !== currentResult.schedule.length) return false;

    // Compare first and last schedule items for a signature match
    if (order.schedule.length > 0 && currentResult.schedule.length > 0) {
      const orderFirst = order.schedule[0];
      const currentFirst = currentResult.schedule[0];
      const orderLast = order.schedule[order.schedule.length - 1];
      const currentLast =
        currentResult.schedule[currentResult.schedule.length - 1];

      // Check if start times and targets match for first and last items
      const firstMatches =
        orderFirst.target_id === currentFirst.target_id &&
        orderFirst.start_time === currentFirst.start_time;
      const lastMatches =
        orderLast.target_id === currentLast.target_id &&
        orderLast.start_time === currentLast.start_time;

      return firstMatches && lastMatches;
    }

    return true;
  });

  const orderNodes: TreeNode[] = filteredOrders.map((order) => ({
    id: `order_${order.order_id}`,
    type: "order" as TreeNodeType,
    name: order.name,
    icon: NODE_ICONS.order,
    isLeaf: true,
    // No badge on leaf order nodes - accepted count shown in inspector instead
    metadata: {
      ...order,
    },
  }));

  return {
    id: "results",
    type: "results",
    name: "Results",
    icon: NODE_ICONS.results,
    isExpandable: true,
    children: [
      {
        id: "opportunities",
        type: "opportunities",
        name: "Opportunities",
        icon: NODE_ICONS.opportunities,
        isExpandable: opportunityChildren.length > 0,
        badge: createBadge(filteredPasses.length, "blue"),
        children: opportunityChildren,
      },
      {
        id: "plans",
        type: "plans",
        name: "Plans",
        icon: NODE_ICONS.plans,
        isExpandable: planNodes.length > 0,
        badge: createBadge(planNodes.length, "green"),
        children: planNodes,
      },
      {
        id: "orders",
        type: "orders",
        name: "Orders",
        icon: NODE_ICONS.orders,
        isExpandable: orderNodes.length > 0,
        badge: createBadge(orderNodes.length, "yellow"),
        children: orderNodes,
      },
    ],
  };
}

// =============================================================================
// Helper Functions
// =============================================================================

function calculateDuration(startTime: string, endTime: string): string {
  try {
    const start = new Date(startTime);
    const end = new Date(endTime);
    const hours = (end.getTime() - start.getTime()) / (1000 * 60 * 60);

    if (hours < 24) {
      return `${hours.toFixed(1)} hours`;
    } else {
      const days = hours / 24;
      return `${days.toFixed(1)} days`;
    }
  } catch {
    return "Unknown";
  }
}

function formatRunTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return timestamp;
  }
}

function formatPassTime(time: string): string {
  try {
    const date = new Date(time);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return time;
  }
}

export function formatAlgorithmName(algorithm: string): string {
  const nameMap: Record<string, string> = {
    first_fit: "First-Fit",
    best_fit: "Best-Fit",
    optimal: "Optimal",
    roll_pitch_first_fit: "Roll+Pitch First-Fit",
    roll_pitch_best_fit: "Roll+Pitch Best-Fit",
  };
  return (
    nameMap[algorithm] ||
    algorithm.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

// =============================================================================
// Tree Search Utility
// =============================================================================

export function filterTree(root: TreeNode, query: string): Set<string> {
  const matchingIds = new Set<string>();
  const normalizedQuery = query.toLowerCase().trim();

  if (!normalizedQuery) return matchingIds;

  function traverse(node: TreeNode, ancestorIds: string[]): boolean {
    const nameMatches = node.name.toLowerCase().includes(normalizedQuery);
    let hasMatchingDescendant = false;

    if (node.children) {
      for (const child of node.children) {
        if (traverse(child, [...ancestorIds, node.id])) {
          hasMatchingDescendant = true;
        }
      }
    }

    if (nameMatches || hasMatchingDescendant) {
      matchingIds.add(node.id);
      ancestorIds.forEach((id) => matchingIds.add(id));
      return true;
    }

    return false;
  }

  traverse(root, []);
  return matchingIds;
}

// =============================================================================
// Tree Traversal Utilities
// =============================================================================

export function findNodeById(
  root: TreeNode,
  targetId: string,
): TreeNode | null {
  if (root.id === targetId) return root;

  if (root.children) {
    for (const child of root.children) {
      const found = findNodeById(child, targetId);
      if (found) return found;
    }
  }

  return null;
}

export function getAllNodeIds(root: TreeNode): string[] {
  const ids: string[] = [root.id];

  if (root.children) {
    for (const child of root.children) {
      ids.push(...getAllNodeIds(child));
    }
  }

  return ids;
}

export function getExpandableNodeIds(root: TreeNode): string[] {
  const ids: string[] = [];

  if (root.isExpandable && root.children && root.children.length > 0) {
    ids.push(root.id);
  }

  if (root.children) {
    for (const child of root.children) {
      ids.push(...getExpandableNodeIds(child));
    }
  }

  return ids;
}
