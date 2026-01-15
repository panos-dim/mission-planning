/**
 * Workspace API Client
 *
 * Provides functions for workspace CRUD operations:
 * - List, create, get, update, delete workspaces
 * - Save current mission state
 * - Export/Import workspaces
 */

import type {
  WorkspaceSummary,
  WorkspaceData,
  UIStateSnapshot,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "";

interface ApiResponse<T> {
  success: boolean;
  message?: string;
  error?: string;
  workspace?: T;
  workspaces?: T[];
  workspace_id?: string;
  total?: number;
  export?: WorkspaceData;
}

/**
 * List all workspaces
 */
export async function listWorkspaces(
  limit = 50,
  offset = 0
): Promise<{ workspaces: WorkspaceSummary[]; total: number }> {
  const response = await fetch(
    `${API_BASE}/api/v1/workspaces?limit=${limit}&offset=${offset}`
  );

  if (!response.ok) {
    throw new Error(`Failed to list workspaces: ${response.statusText}`);
  }

  const data: ApiResponse<WorkspaceSummary> = await response.json();

  if (!data.success) {
    throw new Error(data.message || "Failed to list workspaces");
  }

  return {
    workspaces: data.workspaces || [],
    total: data.total || 0,
  };
}

/**
 * Get a workspace by ID
 */
export async function getWorkspace(
  workspaceId: string,
  includeCzml = true
): Promise<WorkspaceData> {
  const response = await fetch(
    `${API_BASE}/api/v1/workspaces/${workspaceId}?include_czml=${includeCzml}`
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Workspace not found");
    }
    throw new Error(`Failed to get workspace: ${response.statusText}`);
  }

  const data: ApiResponse<WorkspaceData> = await response.json();

  if (!data.success || !data.workspace) {
    throw new Error(data.message || "Failed to get workspace");
  }

  return data.workspace;
}

/**
 * Create a new workspace
 */
export async function createWorkspace(params: {
  name: string;
  scenario_config?: Record<string, unknown>;
  analysis_state?: Record<string, unknown>;
  planning_state?: Record<string, unknown>;
  orders_state?: Record<string, unknown>;
  ui_state?: UIStateSnapshot;
  czml_data?: unknown[];
  mission_mode?: string;
  time_window_start?: string;
  time_window_end?: string;
}): Promise<{ workspaceId: string; workspace: WorkspaceSummary }> {
  const response = await fetch(`${API_BASE}/api/v1/workspaces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error(`Failed to create workspace: ${response.statusText}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.message || "Failed to create workspace");
  }

  return {
    workspaceId: data.workspace_id,
    workspace: data.workspace,
  };
}

/**
 * Update an existing workspace
 */
export async function updateWorkspace(
  workspaceId: string,
  params: {
    name?: string;
    scenario_config?: Record<string, unknown>;
    analysis_state?: Record<string, unknown>;
    planning_state?: Record<string, unknown>;
    orders_state?: Record<string, unknown>;
    ui_state?: UIStateSnapshot;
    czml_data?: unknown[];
    mission_mode?: string;
    time_window_start?: string;
    time_window_end?: string;
  }
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/workspaces/${workspaceId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Workspace not found");
    }
    throw new Error(`Failed to update workspace: ${response.statusText}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.message || "Failed to update workspace");
  }
}

/**
 * Delete a workspace
 */
export async function deleteWorkspace(workspaceId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/workspaces/${workspaceId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Workspace not found");
    }
    throw new Error(`Failed to delete workspace: ${response.statusText}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.message || "Failed to delete workspace");
  }
}

/**
 * Save current mission state as a new workspace
 */
export async function saveCurrentMission(
  name: string,
  options?: {
    uiState?: UIStateSnapshot;
    planningState?: {
      algorithm_runs?: Record<string, unknown>;
      selected_algorithm?: string;
    };
    ordersState?: {
      orders: unknown[];
    };
    missionData?: Record<string, unknown>;
  }
): Promise<{ workspaceId: string; workspace: WorkspaceSummary }> {
  const response = await fetch(`${API_BASE}/api/v1/workspaces/save-current`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      include_ui_state: !!options?.uiState,
      ui_state: options?.uiState,
      planning_state: options?.planningState,
      orders_state: options?.ordersState,
      mission_data: options?.missionData,
    }),
  });

  if (!response.ok) {
    if (response.status === 400) {
      const data = await response.json();
      throw new Error(data.detail || "No mission data available to save");
    }
    throw new Error(`Failed to save mission: ${response.statusText}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.message || "Failed to save mission");
  }

  return {
    workspaceId: data.workspace_id,
    workspace: data.workspace,
  };
}

/**
 * Export a workspace as portable JSON
 */
export async function exportWorkspace(
  workspaceId: string
): Promise<WorkspaceData> {
  const response = await fetch(
    `${API_BASE}/api/v1/workspaces/${workspaceId}/export`,
    {
      method: "POST",
    }
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Workspace not found");
    }
    throw new Error(`Failed to export workspace: ${response.statusText}`);
  }

  const data: ApiResponse<never> = await response.json();

  if (!data.success || !data.export) {
    throw new Error(data.message || "Failed to export workspace");
  }

  return data.export;
}

/**
 * Import a workspace from exported JSON
 */
export async function importWorkspace(
  exportData: WorkspaceData,
  newName?: string
): Promise<{ workspaceId: string; workspace: WorkspaceSummary }> {
  const response = await fetch(`${API_BASE}/api/v1/workspaces/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      data: exportData,
      new_name: newName,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to import workspace: ${response.statusText}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.message || "Failed to import workspace");
  }

  return {
    workspaceId: data.workspace_id,
    workspace: data.workspace,
  };
}

/**
 * Download workspace export as JSON file
 */
export async function downloadWorkspaceExport(
  workspaceId: string,
  filename?: string
): Promise<void> {
  const exportData = await exportWorkspace(workspaceId);

  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: "application/json",
  });

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `workspace-${exportData.name}-${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
