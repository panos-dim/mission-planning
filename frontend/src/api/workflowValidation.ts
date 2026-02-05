/**
 * Workflow Validation API Client
 *
 * Provides access to the deterministic workflow validation endpoints.
 * Used by debug/admin mode UI for running validation scenarios.
 */

import { apiClient } from "./client";

export interface WorkflowScenario {
  id: string;
  name: string;
  description?: string;
  tags: string[];
  num_satellites: number;
  num_targets: number;
  supports_workflow: boolean;
}

export interface InvariantResult {
  invariant: string;
  passed: boolean;
  message: string;
  details: Record<string, unknown>;
  violations: Array<Record<string, unknown>>;
}

export interface StageMetrics {
  stage: string;
  runtime_ms: number;
  success: boolean;
  error_message?: string;
  input_count: number;
  output_count: number;
  details: Record<string, unknown>;
}

export interface WorkflowCounts {
  opportunities: number;
  planned: number;
  committed: number;
  conflicts: number;
}

export interface WorkflowValidationReport {
  report_id: string;
  scenario_id: string;
  scenario_name: string;
  timestamp: string;
  config_hash: string;
  passed: boolean;
  total_invariants: number;
  passed_invariants: number;
  failed_invariants: number;
  stages: StageMetrics[];
  invariants: InvariantResult[];
  counts: WorkflowCounts;
  total_runtime_ms: number;
  report_hash: string;
  errors: string[];
}

export interface RunValidationRequest {
  scenario_id?: string;
  scenario?: Record<string, unknown>;
  dry_run?: boolean;
  previous_hash?: string;
}

/**
 * List available workflow validation scenarios
 */
export async function listWorkflowScenarios(): Promise<WorkflowScenario[]> {
  return apiClient.get<WorkflowScenario[]>(
    "/api/v1/validate/workflow/scenarios",
  );
}

/**
 * Run a workflow validation scenario
 */
export async function runWorkflowValidation(
  request: RunValidationRequest,
): Promise<WorkflowValidationReport> {
  return apiClient.post<WorkflowValidationReport>(
    "/api/v1/validate/run",
    request,
  );
}

/**
 * Get a stored validation report by ID
 */
export async function getValidationReport(
  reportId: string,
): Promise<WorkflowValidationReport> {
  return apiClient.get<WorkflowValidationReport>(
    `/api/v1/validate/report/${reportId}`,
  );
}
