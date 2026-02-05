/**
 * Schedule API Client
 *
 * Provides functions for interacting with the schedule persistence endpoints:
 * - Commit schedules (direct commit)
 * - Get schedule horizon (view committed acquisitions)
 * - Get schedule state
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "";

// =============================================================================
// Types
// =============================================================================

export interface DirectCommitItem {
  opportunity_id: string;
  satellite_id: string;
  target_id: string;
  start_time: string;
  end_time: string;
  roll_angle_deg: number;
  pitch_angle_deg?: number;
  value?: number;
  incidence_angle_deg?: number;
  sar_mode?: string;
  look_side?: string;
  pass_direction?: string;
}

export interface DirectCommitRequest {
  items: DirectCommitItem[];
  algorithm: string;
  mode?: string; // OPTICAL | SAR
  lock_level?: string; // soft | hard
  workspace_id?: string;
  notes?: string;
}

export interface DirectCommitResponse {
  success: boolean;
  message: string;
  plan_id: string;
  committed: number;
  acquisition_ids: string[];
}

export interface AcquisitionSummary {
  id: string;
  satellite_id: string;
  target_id: string;
  start_time: string;
  end_time: string;
  state: string;
  lock_level: string;
  order_id?: string;
}

export interface HorizonInfo {
  start: string;
  end: string;
  freeze_cutoff: string;
}

export interface ScheduleHorizonResponse {
  success: boolean;
  horizon: HorizonInfo;
  acquisitions: AcquisitionSummary[];
  statistics: {
    total_acquisitions: number;
    by_state: Record<string, number>;
    by_satellite: Record<string, number>;
  };
}

export interface OrderSummary {
  id: string;
  target_id: string;
  priority: number;
  status: string;
  requested_window_start?: string;
  requested_window_end?: string;
}

export interface ScheduleStateResponse {
  success: boolean;
  message: string;
  state: {
    acquisitions: AcquisitionSummary[];
    orders: OrderSummary[];
    conflicts: unknown[];
    horizon?: HorizonInfo;
  };
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Directly commit acquisitions to the database.
 * This is the main function for "Promote to Orders" workflow.
 */
export async function commitScheduleDirect(
  request: DirectCommitRequest,
): Promise<DirectCommitResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/schedule/commit/direct`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Get schedule horizon with acquisitions.
 * Returns committed acquisitions within the specified time window.
 */
export async function getScheduleHorizon(params?: {
  from?: string;
  to?: string;
  workspace_id?: string;
  include_tentative?: boolean;
}): Promise<ScheduleHorizonResponse> {
  const searchParams = new URLSearchParams();

  if (params?.from) searchParams.set("from", params.from);
  if (params?.to) searchParams.set("to", params.to);
  if (params?.workspace_id)
    searchParams.set("workspace_id", params.workspace_id);
  if (params?.include_tentative !== undefined) {
    searchParams.set("include_tentative", String(params.include_tentative));
  }

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/schedule/horizon${queryString ? `?${queryString}` : ""}`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Get current schedule state (acquisitions, orders, conflicts).
 */
export async function getScheduleState(
  workspace_id?: string,
): Promise<ScheduleStateResponse> {
  const searchParams = new URLSearchParams();
  if (workspace_id) searchParams.set("workspace_id", workspace_id);

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/schedule/state${queryString ? `?${queryString}` : ""}`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Orders API
// =============================================================================

export interface Order {
  id: string;
  created_at: string;
  updated_at: string;
  status: string;
  target_id: string;
  priority: number;
  constraints?: Record<string, unknown>;
  requested_window?: {
    start?: string;
    end?: string;
  };
  source: string;
  notes?: string;
  external_ref?: string;
  workspace_id?: string;
  // PS2.5 Extended fields
  order_type?: string;
  due_time?: string;
  earliest_start?: string;
  latest_end?: string;
  batch_id?: string;
  tags?: string[];
  requested_satellite_group?: string;
  user_notes?: string;
  reject_reason?: string;
}

export interface OrderListResponse {
  success: boolean;
  orders: Order[];
  total: number;
}

/**
 * List orders with optional filters.
 */
export async function listOrders(params?: {
  status?: string;
  workspace_id?: string;
  limit?: number;
  offset?: number;
}): Promise<OrderListResponse> {
  const searchParams = new URLSearchParams();

  if (params?.status) searchParams.set("status", params.status);
  if (params?.workspace_id)
    searchParams.set("workspace_id", params.workspace_id);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/orders${queryString ? `?${queryString}` : ""}`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Create a new order.
 */
export async function createOrder(params: {
  target_id: string;
  priority?: number;
  constraints?: Record<string, unknown>;
  requested_window_start?: string;
  requested_window_end?: string;
  notes?: string;
  external_ref?: string;
  workspace_id?: string;
}): Promise<{ success: boolean; order: Order }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/orders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Update order status.
 */
export async function updateOrderStatus(
  orderId: string,
  status: string,
): Promise<{ success: boolean; message: string; order?: Order }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/orders/${orderId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ status }),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Conflicts API
// =============================================================================

export interface Conflict {
  id: string;
  detected_at: string;
  type: "temporal_overlap" | "slew_infeasible";
  severity: "error" | "warning" | "info";
  description?: string;
  acquisition_ids: string[];
  resolved_at?: string;
  resolution_action?: string;
}

export interface ConflictsSummary {
  total: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  error_count: number;
  warning_count: number;
  conflict_ids: string[];
}

export interface ConflictListResponse {
  success: boolean;
  conflicts: Conflict[];
  summary: {
    total: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
  };
}

export interface RecomputeConflictsRequest {
  workspace_id: string;
  from_time?: string;
  to_time?: string;
  satellite_id?: string;
}

export interface RecomputeConflictsResponse {
  success: boolean;
  message: string;
  detected: number;
  persisted: number;
  conflict_ids: string[];
  summary: {
    total: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
  };
}

/**
 * Get schedule conflicts.
 */
export async function getConflicts(params?: {
  workspace_id?: string;
  from?: string;
  to?: string;
  satellite_id?: string;
  conflict_type?: string;
  severity?: string;
  include_resolved?: boolean;
}): Promise<ConflictListResponse> {
  const searchParams = new URLSearchParams();

  if (params?.workspace_id)
    searchParams.set("workspace_id", params.workspace_id);
  if (params?.from) searchParams.set("from", params.from);
  if (params?.to) searchParams.set("to", params.to);
  if (params?.satellite_id)
    searchParams.set("satellite_id", params.satellite_id);
  if (params?.conflict_type)
    searchParams.set("conflict_type", params.conflict_type);
  if (params?.severity) searchParams.set("severity", params.severity);
  if (params?.include_resolved !== undefined) {
    searchParams.set("include_resolved", String(params.include_resolved));
  }

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/schedule/conflicts${queryString ? `?${queryString}` : ""}`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Recompute conflicts for a workspace.
 */
export async function recomputeConflicts(
  request: RecomputeConflictsRequest,
): Promise<RecomputeConflictsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/schedule/conflicts/recompute`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Incremental Planning API
// =============================================================================

export type PlanningMode = "from_scratch" | "incremental" | "repair";
export type LockPolicy = "respect_hard_only" | "respect_hard_and_soft";

// Repair mode specific types
export type RepairScope =
  | "workspace_horizon"
  | "satellite_subset"
  | "target_subset";
export type SoftLockPolicy = "allow_shift" | "allow_replace" | "freeze_soft";
export type RepairObjective =
  | "maximize_score"
  | "maximize_priority"
  | "minimize_changes";

export interface IncrementalPlanRequest {
  planning_mode: PlanningMode;
  horizon_from?: string;
  horizon_to?: string;
  workspace_id?: string;
  include_tentative?: boolean;
  lock_policy?: LockPolicy;
  imaging_time_s?: number;
  max_roll_rate_dps?: number;
  max_roll_accel_dps2?: number;
  max_pitch_rate_dps?: number;
  max_pitch_accel_dps2?: number;
  look_window_s?: number;
  value_source?: string;
}

export interface ExistingAcquisitionsSummary {
  count: number;
  by_state: Record<string, number>;
  by_satellite: Record<string, number>;
  acquisition_ids: string[];
  horizon_start?: string;
  horizon_end?: string;
}

export interface PlanItemPreview {
  opportunity_id: string;
  satellite_id: string;
  target_id: string;
  start_time: string;
  end_time: string;
  roll_angle_deg: number;
  pitch_angle_deg: number;
  value?: number;
  quality_score?: number;
  incidence_angle_deg?: number;
}

export interface CommitPreview {
  will_create: number;
  will_conflict_with: number;
  conflict_details: Array<{
    type: string;
    severity: string;
    description: string;
    acquisition_ids: string[];
    involves_new_item?: boolean;
  }>;
  warnings: string[];
}

export interface IncrementalPlanResponse {
  success: boolean;
  message: string;
  planning_mode: string;
  existing_acquisitions: ExistingAcquisitionsSummary;
  new_plan_items: PlanItemPreview[];
  conflicts_if_committed: Array<{
    type: string;
    severity: string;
    description: string;
    acquisition_ids: string[];
  }>;
  commit_preview: CommitPreview;
  algorithm_metrics: Record<string, unknown>;
  plan_id?: string;
  schedule_context: Record<string, unknown>;
}

/**
 * Create an incremental plan.
 * In incremental mode, plans around existing committed acquisitions.
 */
export async function createIncrementalPlan(
  request: IncrementalPlanRequest,
): Promise<IncrementalPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/schedule/plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Get schedule context for planning (existing acquisitions summary).
 * This is a quick way to show schedule context before running planning.
 */
export async function getScheduleContext(params: {
  workspace_id: string;
  from?: string;
  to?: string;
  include_tentative?: boolean;
}): Promise<{
  success: boolean;
  count: number;
  by_state: Record<string, number>;
  by_satellite: Record<string, number>;
  horizon: { start: string; end: string };
}> {
  const horizonResponse = await getScheduleHorizon({
    workspace_id: params.workspace_id,
    from: params.from,
    to: params.to,
    include_tentative: params.include_tentative,
  });

  return {
    success: horizonResponse.success,
    count: horizonResponse.statistics.total_acquisitions || 0,
    by_state: horizonResponse.statistics.by_state || {},
    by_satellite: horizonResponse.statistics.by_satellite || {},
    horizon: {
      start: horizonResponse.horizon.start || "",
      end: horizonResponse.horizon.end || "",
    },
  };
}

// =============================================================================
// Repair Planning API
// =============================================================================

export interface RepairPlanRequest {
  planning_mode: "repair";
  horizon_from?: string;
  horizon_to?: string;
  workspace_id?: string;
  include_tentative?: boolean;
  // Repair-specific
  repair_scope?: RepairScope;
  soft_lock_policy?: SoftLockPolicy;
  max_changes?: number;
  objective?: RepairObjective;
  // Scope filters
  satellite_subset?: string[];
  target_subset?: string[];
  // Planning parameters
  imaging_time_s?: number;
  max_roll_rate_dps?: number;
  max_roll_accel_dps2?: number;
  max_pitch_rate_dps?: number;
  max_pitch_accel_dps2?: number;
  look_window_s?: number;
  value_source?: string;
}

export interface MovedAcquisitionInfo {
  id: string;
  from_start: string;
  from_end: string;
  to_start: string;
  to_end: string;
  from_roll_deg?: number;
  to_roll_deg?: number;
}

export interface ChangeScore {
  num_changes: number;
  percent_changed: number;
}

export interface RepairDiff {
  kept: string[];
  dropped: string[];
  added: string[];
  moved: MovedAcquisitionInfo[];
  reason_summary: {
    dropped?: Array<{ id: string; reason: string }>;
    moved?: Array<{ id: string; reason: string }>;
  };
  change_score: ChangeScore;
  hard_lock_warnings?: string[];
}

export interface MetricsComparison {
  score_before: number;
  score_after: number;
  score_delta: number;
  mean_incidence_before?: number;
  mean_incidence_after?: number;
  conflicts_before: number;
  conflicts_after: number;
  acquisition_count_before: number;
  acquisition_count_after: number;
}

export interface RepairPlanResponse {
  success: boolean;
  message: string;
  planning_mode: "repair";
  // Schedule context
  existing_acquisitions: ExistingAcquisitionsSummary;
  fixed_count: number;
  flex_count: number;
  // Proposed schedule
  new_plan_items: PlanItemPreview[];
  // Repair diff (critical)
  repair_diff: RepairDiff;
  // Metrics comparison
  metrics_before: Record<string, unknown>;
  metrics_after: Record<string, unknown>;
  metrics_comparison: MetricsComparison;
  // Conflict prediction
  conflicts_if_committed: Array<{
    type: string;
    severity: string;
    description: string;
    acquisition_ids: string[];
    involves_new_item?: boolean;
  }>;
  // Commit preview
  commit_preview: CommitPreview;
  // Algorithm metrics
  algorithm_metrics: Record<string, unknown>;
  plan_id?: string;
  schedule_context: Record<string, unknown>;
}

/**
 * Create a repair plan.
 * Repair mode modifies existing schedule: keeps hard locks, optionally moves/replaces soft items.
 */
export async function createRepairPlan(
  request: RepairPlanRequest,
): Promise<RepairPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/schedule/repair`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Lock Management API
// =============================================================================

export type LockLevel = "none" | "soft" | "hard";

export interface UpdateLockResponse {
  success: boolean;
  message: string;
  acquisition_id: string;
  lock_level: LockLevel;
}

export interface BulkLockRequest {
  acquisition_ids: string[];
  lock_level: LockLevel;
}

export interface BulkLockResponse {
  success: boolean;
  message: string;
  updated: number;
  failed: string[];
  lock_level: LockLevel;
}

export interface HardLockCommittedResponse {
  success: boolean;
  message: string;
  updated: number;
  workspace_id: string;
}

/**
 * Update lock level for a single acquisition.
 */
export async function updateAcquisitionLock(
  acquisitionId: string,
  lockLevel: LockLevel,
): Promise<UpdateLockResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/schedule/acquisition/${acquisitionId}/lock?lock_level=${lockLevel}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Bulk update lock levels for multiple acquisitions.
 */
export async function bulkUpdateLocks(
  request: BulkLockRequest,
): Promise<BulkLockResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/schedule/acquisitions/bulk-lock`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Hard-lock all committed acquisitions in a workspace.
 */
export async function hardLockAllCommitted(
  workspaceId: string,
): Promise<HardLockCommittedResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/schedule/acquisitions/hard-lock-committed`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ workspace_id: workspaceId }),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// Repair Commit API
// =============================================================================

export interface RepairCommitRequest {
  plan_id: string;
  workspace_id: string;
  drop_acquisition_ids: string[];
  lock_level?: LockLevel;
  mode?: string;
  force?: boolean;
  notes?: string;
  score_before?: number;
  score_after?: number;
  conflicts_before?: number;
}

export interface RepairCommitResponse {
  success: boolean;
  message: string;
  plan_id: string;
  committed: number;
  dropped: number;
  audit_log_id: string;
  conflicts_after: number;
  warnings: string[];
}

/**
 * Commit a repair plan atomically.
 */
export async function commitRepairPlan(
  request: RepairCommitRequest,
): Promise<RepairCommitResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/schedule/repair/commit`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : error.detail?.message || `HTTP ${response.status}`,
    );
  }

  return response.json();
}

// =============================================================================
// Commit Audit Log API
// =============================================================================

export interface AuditLogEntry {
  id: string;
  created_at: string;
  plan_id: string;
  workspace_id?: string;
  committed_by?: string;
  commit_type: string;
  config_hash: string;
  repair_diff?: {
    dropped?: string[];
    created?: string[];
  };
  acquisitions_created: number;
  acquisitions_dropped: number;
  score_before?: number;
  score_after?: number;
  conflicts_before: number;
  conflicts_after: number;
  notes?: string;
}

export interface AuditLogListResponse {
  success: boolean;
  audit_logs: AuditLogEntry[];
  total: number;
}

/**
 * Get commit audit history.
 */
export async function getCommitHistory(params?: {
  workspace_id?: string;
  plan_id?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditLogListResponse> {
  const searchParams = new URLSearchParams();

  if (params?.workspace_id)
    searchParams.set("workspace_id", params.workspace_id);
  if (params?.plan_id) searchParams.set("plan_id", params.plan_id);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/schedule/commit-history${queryString ? `?${queryString}` : ""}`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// =============================================================================
// PS2.5 - Order Inbox & Batching API
// =============================================================================

export interface InboxOrder {
  order: Order;
  score: number;
  score_breakdown: Record<string, number>;
}

export interface InboxListResponse {
  success: boolean;
  orders: InboxOrder[];
  total: number;
  policy_id: string;
}

export interface BatchPolicy {
  id: string;
  name: string;
  description: string;
  weights: {
    priority_weight: number;
    deadline_weight: number;
    age_weight: number;
    quality_weight: number;
  };
  selection_rules: {
    max_orders_per_batch: number;
    horizon_hours: number;
    include_soft_lock_replace: boolean;
    min_priority: number;
  };
  repair_preset: string;
  planning_mode: string;
}

export interface PolicyListResponse {
  success: boolean;
  policies: BatchPolicy[];
  default_policy: string;
}

export interface BatchOrder {
  id: string;
  target_id: string;
  priority: number;
  status: string;
  due_time?: string;
  role: string;
  score?: number;
}

export interface Batch {
  id: string;
  workspace_id: string;
  created_at: string;
  updated_at: string;
  policy_id: string;
  horizon_from: string;
  horizon_to: string;
  status: string;
  plan_id?: string;
  notes?: string;
  metrics?: {
    orders_satisfied?: number;
    orders_unsatisfied?: number;
    unsatisfied_reasons?: Record<string, number>;
    acquisitions_planned?: number;
  };
  orders?: BatchOrder[];
}

export interface BatchListResponse {
  success: boolean;
  batches: Batch[];
  total: number;
}

export interface CreateBatchResponse {
  success: boolean;
  batch: Batch;
  selected_orders: number;
}

export interface PlanMetrics {
  orders_satisfied: number;
  orders_unsatisfied: number;
  unsatisfied_reasons: Record<string, number>;
  acquisitions_planned: number;
  acquisitions_dropped: number;
  conflicts_predicted: number;
  compute_time_ms: number;
}

export interface PlanBatchResponse {
  success: boolean;
  batch_id: string;
  plan_id: string;
  status: string;
  metrics: PlanMetrics;
  satisfied_order_ids: string[];
  unsatisfied_orders: Array<{ order_id: string; reason: string }>;
}

export interface CommitBatchResponse {
  success: boolean;
  batch_id: string;
  plan_id: string;
  acquisitions_created: number;
  acquisitions_dropped: number;
  orders_updated: number;
  audit_id?: string;
}

/**
 * Get orders inbox with scoring.
 */
export async function getOrdersInbox(params: {
  workspace_id: string;
  priority_min?: number;
  due_within_hours?: number;
  order_type?: string;
  tags?: string;
  policy_id?: string;
  limit?: number;
  offset?: number;
}): Promise<InboxListResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("workspace_id", params.workspace_id);

  if (params.priority_min)
    searchParams.set("priority_min", String(params.priority_min));
  if (params.due_within_hours)
    searchParams.set("due_within_hours", String(params.due_within_hours));
  if (params.order_type) searchParams.set("order_type", params.order_type);
  if (params.tags) searchParams.set("tags", params.tags);
  if (params.policy_id) searchParams.set("policy_id", params.policy_id);
  if (params.limit) searchParams.set("limit", String(params.limit));
  if (params.offset) searchParams.set("offset", String(params.offset));

  const url = `${API_BASE_URL}/api/v1/orders/inbox?${searchParams.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Import orders in bulk.
 */
export async function importOrders(params: {
  workspace_id: string;
  orders: Array<{
    target_id: string;
    priority?: number;
    constraints?: Record<string, unknown>;
    due_time?: string;
    tags?: string[];
    order_type?: string;
  }>;
}): Promise<{ success: boolean; imported_count: number; orders: Order[] }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/orders/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Reject an order with reason.
 */
export async function rejectOrder(
  orderId: string,
  reason: string,
): Promise<{ success: boolean; message: string; order?: Order }> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/orders/${orderId}/reject`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Defer an order.
 */
export async function deferOrder(
  orderId: string,
  params: { new_due_time?: string; defer_hours?: number; notes?: string },
): Promise<{ success: boolean; message: string; order?: Order }> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/orders/${orderId}/defer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * List available batch policies.
 */
export async function listPolicies(): Promise<PolicyListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/batches/policies`);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Create a new batch.
 */
export async function createBatch(params: {
  workspace_id: string;
  policy_id: string;
  horizon_hours?: number;
  order_ids?: string[];
  priority_min?: number;
  due_before?: string;
  max_orders?: number;
  notes?: string;
}): Promise<CreateBatchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/batches/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * List batches.
 */
export async function listBatches(params?: {
  workspace_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<BatchListResponse> {
  const searchParams = new URLSearchParams();

  if (params?.workspace_id)
    searchParams.set("workspace_id", params.workspace_id);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const queryString = searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/batches${queryString ? `?${queryString}` : ""}`;

  const response = await fetch(url);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Get batch details.
 */
export async function getBatch(batchId: string): Promise<CreateBatchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/batches/${batchId}`);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Plan a batch.
 */
export async function planBatch(
  batchId: string,
  params?: { use_repair_mode?: boolean; include_soft_lock_replace?: boolean },
): Promise<PlanBatchResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/batches/${batchId}/plan`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params || {}),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Commit a batch plan.
 */
export async function commitBatch(
  batchId: string,
  params?: { lock_level?: string; notes?: string },
): Promise<CommitBatchResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/batches/${batchId}/commit`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params || {}),
    },
  );

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Cancel a batch.
 */
export async function cancelBatch(
  batchId: string,
): Promise<{ success: boolean; batch_id: string; orders_returned: number }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/batches/${batchId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}
