/**
 * Convenience re-exports from auto-generated OpenAPI types.
 *
 * Generated with: npm run generate:api-types
 * Source: FastAPI backend OpenAPI schema at /openapi.json
 *
 * Usage:
 *   import type { ApiMissionRequest, ApiPlanningResponse } from '@/api/generated';
 */

export type { paths, components, operations } from "./api-types";

// ── Schema type aliases ──────────────────────────────────────────────
// These provide short, friendly names for generated component schemas.
// Pattern: components["schemas"]["SchemaName"]

import type { components } from "./api-types";

type Schemas = components["schemas"];

// Mission & Analysis
export type ApiMissionRequest = Schemas["MissionRequest"];
export type ApiMissionResponse = Schemas["MissionResponse"];
export type ApiSARInputParams = Schemas["SARInputParams"];
export type ApiTLEData = Schemas["TLEData"];
export type ApiTargetData = Schemas["TargetData"];

// Planning
export type ApiPlanningRequest = Schemas["PlanningRequest"];
export type ApiPlanningResponse = Schemas["PlanningResponse"];
export type ApiPlanningAuditMetadata = Schemas["PlanningAuditMetadata"];
export type ApiIncrementalPlanRequest = Schemas["IncrementalPlanRequest"];
export type ApiIncrementalPlanResponse = Schemas["IncrementalPlanResponse"];

// Schedule
export type ApiScheduleState = Schemas["ScheduleState"];
export type ApiScheduleStateResponse = Schemas["ScheduleStateResponse"];
export type ApiScheduleHorizonResponse = Schemas["ScheduleHorizonResponse"];
export type ApiDirectCommitRequest = Schemas["DirectCommitRequest"];
export type ApiDirectCommitResponse = Schemas["DirectCommitResponse"];
export type ApiCommitPlanRequest = Schemas["CommitPlanRequest"];
export type ApiCommitPlanResponse = Schemas["CommitPlanResponse"];

// Acquisitions & Locks
export type ApiAcquisitionSummary = Schemas["AcquisitionSummary"];
export type ApiBulkLockRequest = Schemas["BulkLockRequest"];
export type ApiBulkLockResponse = Schemas["BulkLockResponse"];
export type ApiUpdateLockResponse = Schemas["UpdateLockResponse"];

// Conflicts
export type ApiConflictResponse = Schemas["ConflictResponse"];
export type ApiConflictListResponse = Schemas["ConflictListResponse"];
export type ApiConflictsSummary = Schemas["ConflictsSummary"];

// Orders
export type ApiOrderResponse = Schemas["OrderResponse"];
export type ApiOrderListResponse = Schemas["OrderListResponse"];
export type ApiCreateOrderRequest = Schemas["CreateOrderRequest"];
export type ApiImportOrdersRequest = Schemas["ImportOrdersRequest"];
export type ApiImportOrdersResponse = Schemas["ImportOrdersResponse"];
export type ApiInboxOrderResponse = Schemas["InboxOrderResponse"];
export type ApiInboxListResponse = Schemas["InboxListResponse"];

// Batching
export type ApiCreateBatchRequest = Schemas["CreateBatchRequest"];
export type ApiCreateBatchResponse = Schemas["CreateBatchResponse"];
export type ApiBatchResponse = Schemas["BatchResponse"];
export type ApiBatchListResponse = Schemas["BatchListResponse"];
export type ApiPlanBatchRequest = Schemas["PlanBatchRequest"];
export type ApiPlanBatchResponse = Schemas["PlanBatchResponse"];
export type ApiPolicyResponse = Schemas["PolicyResponse"];

// Repair
export type ApiRepairPlanRequest = Schemas["RepairPlanRequestModel"];
export type ApiRepairPlanResponse = Schemas["RepairPlanResponseModel"];
export type ApiRepairCommitRequest = Schemas["RepairCommitRequest"];
export type ApiRepairCommitResponse = Schemas["RepairCommitResponse"];
export type ApiRepairDiffResponse = Schemas["RepairDiffResponse"];

// Audit
export type ApiAuditLogResponse = Schemas["AuditLogResponse"];
export type ApiAuditLogListResponse = Schemas["AuditLogListResponse"];

// Config & SAR Modes
export type ApiSARModeConfig = Schemas["SARModeConfig"];
export type ApiSARModeCollection = Schemas["SARModeCollection"];

// Satellites
export type ApiSatelliteCreateRequest = Schemas["SatelliteCreateRequest"];
export type ApiSatelliteUpdateRequest = Schemas["SatelliteUpdateRequest"];

// Workspace
export type ApiWorkspaceCreateRequest = Schemas["WorkspaceCreateRequest"];
export type ApiWorkspaceUpdateRequest = Schemas["WorkspaceUpdateRequest"];

// Pass Enrichment & Analysis
export type ApiPassEnrichmentRequest = Schemas["PassEnrichmentRequest"];
export type ApiEnrichedPassResponse = Schemas["EnrichedPassResponse"];
export type ApiPassGeometryResponse = Schemas["PassGeometryResponse"];
export type ApiPassLightingResponse = Schemas["PassLightingResponse"];
export type ApiPassQualityResponse = Schemas["PassQualityResponse"];

// Validation
export type ApiValidationError = Schemas["ValidationError"];
export type ApiHTTPValidationError = Schemas["HTTPValidationError"];
