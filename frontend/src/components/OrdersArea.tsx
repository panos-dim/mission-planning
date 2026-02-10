/**
 * OrdersArea Component (PS2.5)
 *
 * Enhanced orders management with:
 * - Inbox tab: View and score orders, reject/defer actions
 * - Batches tab: Create and manage order batches
 * - Schedule tab: View committed schedule
 */

import { useState, useEffect, useCallback } from "react";
import {
  InboxOrder,
  Batch,
  BatchPolicy,
  getOrdersInbox,
  listBatches,
  listPolicies,
  createBatch,
  planBatch,
  commitBatch,
  cancelBatch,
  rejectOrder,
  deferOrder,
  PlanBatchResponse,
} from "../api/scheduleApi";

type TabType = "inbox" | "batches" | "schedule";

interface OrdersAreaProps {
  workspaceId: string;
}

export default function OrdersArea({
  workspaceId,
}: OrdersAreaProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabType>("inbox");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Inbox state
  const [inboxOrders, setInboxOrders] = useState<InboxOrder[]>([]);
  const [selectedOrders, setSelectedOrders] = useState<Set<string>>(new Set());
  const [inboxPolicy, setInboxPolicy] = useState<string>("");

  // Batches state
  const [batches, setBatches] = useState<Batch[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<Batch | null>(null);
  const [planResult, setPlanResult] = useState<PlanBatchResponse | null>(null);

  // Policies state
  const [policies, setPolicies] = useState<BatchPolicy[]>([]);
  const [defaultPolicy, setDefaultPolicy] = useState<string>("");

  // Filters
  const [priorityFilter, setPriorityFilter] = useState<number | null>(null);
  const [dueWithinHours, setDueWithinHours] = useState<number | null>(null);

  const loadPolicies = useCallback(async () => {
    try {
      const result = await listPolicies();
      setPolicies(result.policies);
      setDefaultPolicy(result.default_policy);
      setInboxPolicy(result.default_policy);
    } catch (err) {
      console.error("Failed to load policies:", err);
    }
  }, []);

  const loadInbox = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getOrdersInbox({
        workspace_id: workspaceId,
        priority_min: priorityFilter ?? undefined,
        due_within_hours: dueWithinHours ?? undefined,
        policy_id: inboxPolicy || undefined,
      });
      setInboxOrders(result.orders);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inbox");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, priorityFilter, dueWithinHours, inboxPolicy]);

  const loadBatches = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listBatches({ workspace_id: workspaceId });
      setBatches(result.batches);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load batches");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  // Load policies on mount
  useEffect(() => {
    loadPolicies();
  }, [loadPolicies]);

  // Load data when tab changes
  useEffect(() => {
    if (activeTab === "inbox") {
      loadInbox();
    } else if (activeTab === "batches") {
      loadBatches();
    }
  }, [activeTab, loadInbox, loadBatches]);

  const handleSelectOrder = (orderId: string) => {
    setSelectedOrders((prev) => {
      const next = new Set(prev);
      if (next.has(orderId)) {
        next.delete(orderId);
      } else {
        next.add(orderId);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedOrders.size === inboxOrders.length) {
      setSelectedOrders(new Set());
    } else {
      setSelectedOrders(new Set(inboxOrders.map((o) => o.order.id)));
    }
  };

  const handleRejectOrder = async (orderId: string) => {
    const reason = prompt("Enter rejection reason:");
    if (!reason) return;

    try {
      await rejectOrder(orderId, reason);
      loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject order");
    }
  };

  const handleDeferOrder = async (orderId: string) => {
    const hours = prompt("Defer by how many hours?", "24");
    if (!hours) return;

    try {
      await deferOrder(orderId, { defer_hours: parseInt(hours, 10) });
      loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to defer order");
    }
  };

  const handleCreateBatch = async () => {
    if (selectedOrders.size === 0) {
      setError("Select orders to create a batch");
      return;
    }

    const policyId = inboxPolicy || defaultPolicy;
    if (!policyId) {
      setError("No policy selected");
      return;
    }

    try {
      const result = await createBatch({
        workspace_id: workspaceId,
        policy_id: policyId,
        order_ids: Array.from(selectedOrders),
      });
      setSelectedOrders(new Set());
      setActiveTab("batches");
      setSelectedBatch(result.batch);
      loadBatches();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create batch");
    }
  };

  const handlePlanBatch = async (batchId: string) => {
    setLoading(true);
    setPlanResult(null);
    try {
      const result = await planBatch(batchId);
      setPlanResult(result);
      loadBatches();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to plan batch");
    } finally {
      setLoading(false);
    }
  };

  const handleCommitBatch = async (batchId: string) => {
    if (
      !confirm(
        "Commit this batch? This will create acquisitions in the schedule.",
      )
    ) {
      return;
    }

    setLoading(true);
    try {
      await commitBatch(batchId, { lock_level: "none" });
      setPlanResult(null);
      setSelectedBatch(null);
      loadBatches();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to commit batch");
    } finally {
      setLoading(false);
    }
  };

  const handleCancelBatch = async (batchId: string) => {
    if (!confirm("Cancel this batch? Orders will be returned to the inbox.")) {
      return;
    }

    try {
      await cancelBatch(batchId);
      setSelectedBatch(null);
      setPlanResult(null);
      loadBatches();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel batch");
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "new":
      case "queued":
        return "bg-yellow-500/20 text-yellow-300";
      case "planned":
        return "bg-blue-500/20 text-blue-300";
      case "committed":
        return "bg-green-500/20 text-green-300";
      case "rejected":
        return "bg-red-500/20 text-red-300";
      case "draft":
        return "bg-gray-500/20 text-gray-300";
      default:
        return "bg-gray-500/20 text-gray-300";
    }
  };

  const getPriorityColor = (priority: number) => {
    if (priority >= 4) return "text-red-400";
    if (priority >= 3) return "text-yellow-400";
    return "text-gray-400";
  };

  return (
    <div className="h-full flex flex-col bg-gray-900 text-white">
      {/* Header with Tabs */}
      <div className="border-b border-gray-700 px-4">
        <div className="flex items-center justify-between py-3">
          <h2 className="text-lg font-semibold">Order Management</h2>
          <div className="flex gap-2">
            {(["inbox", "batches", "schedule"] as TabType[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-300 hover:bg-gray-700"
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-2 flex justify-between items-center">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-red-300 hover:text-white"
          >
            ×
          </button>
        </div>
      )}

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4">
        {activeTab === "inbox" && (
          <InboxTab
            orders={inboxOrders}
            selectedOrders={selectedOrders}
            policies={policies}
            currentPolicy={inboxPolicy}
            loading={loading}
            priorityFilter={priorityFilter}
            dueWithinHours={dueWithinHours}
            onSelectOrder={handleSelectOrder}
            onSelectAll={handleSelectAll}
            onReject={handleRejectOrder}
            onDefer={handleDeferOrder}
            onCreateBatch={handleCreateBatch}
            onPolicyChange={setInboxPolicy}
            onPriorityFilterChange={setPriorityFilter}
            onDueWithinHoursChange={setDueWithinHours}
            onRefresh={loadInbox}
            formatDate={formatDate}
            getStatusColor={getStatusColor}
            getPriorityColor={getPriorityColor}
          />
        )}

        {activeTab === "batches" && (
          <BatchesTab
            batches={batches}
            selectedBatch={selectedBatch}
            planResult={planResult}
            loading={loading}
            onSelectBatch={setSelectedBatch}
            onPlan={handlePlanBatch}
            onCommit={handleCommitBatch}
            onCancel={handleCancelBatch}
            onRefresh={loadBatches}
            formatDate={formatDate}
            getStatusColor={getStatusColor}
          />
        )}

        {activeTab === "schedule" && (
          <ScheduleTab workspaceId={workspaceId} formatDate={formatDate} />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Inbox Tab Component
// =============================================================================

interface InboxTabProps {
  orders: InboxOrder[];
  selectedOrders: Set<string>;
  policies: BatchPolicy[];
  currentPolicy: string;
  loading: boolean;
  priorityFilter: number | null;
  dueWithinHours: number | null;
  onSelectOrder: (id: string) => void;
  onSelectAll: () => void;
  onReject: (id: string) => void;
  onDefer: (id: string) => void;
  onCreateBatch: () => void;
  onPolicyChange: (id: string) => void;
  onPriorityFilterChange: (val: number | null) => void;
  onDueWithinHoursChange: (val: number | null) => void;
  onRefresh: () => void;
  formatDate: (s: string) => string;
  getStatusColor: (s: string) => string;
  getPriorityColor: (p: number) => string;
}

function InboxTab({
  orders,
  selectedOrders,
  policies,
  currentPolicy,
  loading,
  priorityFilter,
  dueWithinHours,
  onSelectOrder,
  onSelectAll,
  onReject,
  onDefer,
  onCreateBatch,
  onPolicyChange,
  onPriorityFilterChange,
  onDueWithinHoursChange,
  onRefresh,
  formatDate,
  getStatusColor,
  getPriorityColor,
}: InboxTabProps) {
  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-4 bg-gray-800 p-3 rounded-lg">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Policy:</label>
          <select
            value={currentPolicy}
            onChange={(e) => onPolicyChange(e.target.value)}
            className="bg-gray-700 text-white rounded px-2 py-1 text-sm"
          >
            {policies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Min Priority:</label>
          <select
            value={priorityFilter ?? ""}
            onChange={(e) =>
              onPriorityFilterChange(
                e.target.value ? parseInt(e.target.value) : null,
              )
            }
            className="bg-gray-700 text-white rounded px-2 py-1 text-sm"
          >
            <option value="">Any</option>
            {[1, 2, 3, 4, 5].map((p) => (
              <option key={p} value={p}>
                {p}+
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Due within:</label>
          <select
            value={dueWithinHours ?? ""}
            onChange={(e) =>
              onDueWithinHoursChange(
                e.target.value ? parseInt(e.target.value) : null,
              )
            }
            className="bg-gray-700 text-white rounded px-2 py-1 text-sm"
          >
            <option value="">Any</option>
            <option value="12">12 hours</option>
            <option value="24">24 hours</option>
            <option value="48">48 hours</option>
            <option value="72">72 hours</option>
          </select>
        </div>

        <div className="flex-1" />

        <button
          onClick={onRefresh}
          disabled={loading}
          className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>

        <button
          onClick={onCreateBatch}
          disabled={selectedOrders.size === 0}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-sm"
        >
          Create Batch ({selectedOrders.size})
        </button>
      </div>

      {/* Orders Table */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-700">
            <tr>
              <th className="px-3 py-2 text-left">
                <input
                  type="checkbox"
                  checked={
                    selectedOrders.size === orders.length && orders.length > 0
                  }
                  onChange={onSelectAll}
                  className="rounded"
                />
              </th>
              <th className="px-3 py-2 text-left">Score</th>
              <th className="px-3 py-2 text-left">Target</th>
              <th className="px-3 py-2 text-left">Priority</th>
              <th className="px-3 py-2 text-left">Due</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Created</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-gray-500">
                  No orders in inbox
                </td>
              </tr>
            ) : (
              orders.map(({ order, score }) => (
                <tr
                  key={order.id}
                  className="border-t border-gray-700 hover:bg-gray-750"
                >
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selectedOrders.has(order.id)}
                      onChange={() => onSelectOrder(order.id)}
                      className="rounded"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-blue-400">
                      {(score * 100).toFixed(0)}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-medium">{order.target_id}</td>
                  <td
                    className={`px-3 py-2 font-bold ${getPriorityColor(order.priority)}`}
                  >
                    P{order.priority}
                  </td>
                  <td className="px-3 py-2 text-gray-400">
                    {order.due_time ? formatDate(order.due_time) : "-"}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${getStatusColor(order.status)}`}
                    >
                      {order.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-400">
                    {formatDate(order.created_at)}
                  </td>
                  <td className="px-3 py-2 text-right space-x-2">
                    <button
                      onClick={() => onDefer(order.id)}
                      className="text-yellow-400 hover:text-yellow-300 text-xs"
                    >
                      Defer
                    </button>
                    <button
                      onClick={() => onReject(order.id)}
                      className="text-red-400 hover:text-red-300 text-xs"
                    >
                      Reject
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =============================================================================
// Batches Tab Component
// =============================================================================

interface BatchesTabProps {
  batches: Batch[];
  selectedBatch: Batch | null;
  planResult: PlanBatchResponse | null;
  loading: boolean;
  onSelectBatch: (batch: Batch | null) => void;
  onPlan: (batchId: string) => void;
  onCommit: (batchId: string) => void;
  onCancel: (batchId: string) => void;
  onRefresh: () => void;
  formatDate: (s: string) => string;
  getStatusColor: (s: string) => string;
}

function BatchesTab({
  batches,
  selectedBatch,
  planResult,
  loading,
  onSelectBatch,
  onPlan,
  onCommit,
  onCancel,
  onRefresh,
  formatDate,
  getStatusColor,
}: BatchesTabProps) {
  return (
    <div className="flex gap-4 h-full">
      {/* Batch List */}
      <div className="w-1/3 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Batches</h3>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
          >
            Refresh
          </button>
        </div>

        <div className="space-y-2">
          {batches.length === 0 ? (
            <div className="text-gray-500 text-center py-8">No batches</div>
          ) : (
            batches.map((batch) => (
              <div
                key={batch.id}
                onClick={() => onSelectBatch(batch)}
                className={`p-3 rounded-lg cursor-pointer transition-colors ${
                  selectedBatch?.id === batch.id
                    ? "bg-blue-900/50 border border-blue-600"
                    : "bg-gray-800 hover:bg-gray-750 border border-transparent"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-gray-400">
                    {batch.id}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${getStatusColor(batch.status)}`}
                  >
                    {batch.status}
                  </span>
                </div>
                <div className="mt-1 text-sm">
                  <span className="text-gray-400">Policy:</span>{" "}
                  {batch.policy_id}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {formatDate(batch.created_at)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Batch Details */}
      <div className="flex-1 bg-gray-800 rounded-lg p-4">
        {selectedBatch ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Batch Details</h3>
              <div className="space-x-2">
                {selectedBatch.status === "draft" && (
                  <button
                    onClick={() => onPlan(selectedBatch.id)}
                    disabled={loading}
                    className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-sm"
                  >
                    {loading ? "Planning..." : "Plan"}
                  </button>
                )}
                {selectedBatch.status === "planned" && (
                  <button
                    onClick={() => onCommit(selectedBatch.id)}
                    disabled={loading}
                    className="px-3 py-1 bg-green-600 hover:bg-green-500 rounded text-sm"
                  >
                    Commit
                  </button>
                )}
                {selectedBatch.status !== "committed" && (
                  <button
                    onClick={() => onCancel(selectedBatch.id)}
                    className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-sm"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-400">ID:</span>{" "}
                <span className="font-mono">{selectedBatch.id}</span>
              </div>
              <div>
                <span className="text-gray-400">Status:</span>{" "}
                <span
                  className={`px-2 py-0.5 rounded ${getStatusColor(selectedBatch.status)}`}
                >
                  {selectedBatch.status}
                </span>
              </div>
              <div>
                <span className="text-gray-400">Policy:</span>{" "}
                {selectedBatch.policy_id}
              </div>
              <div>
                <span className="text-gray-400">Created:</span>{" "}
                {formatDate(selectedBatch.created_at)}
              </div>
              <div>
                <span className="text-gray-400">Horizon:</span>{" "}
                {formatDate(selectedBatch.horizon_from)} -{" "}
                {formatDate(selectedBatch.horizon_to)}
              </div>
            </div>

            {/* Plan Result */}
            {planResult && (
              <div className="mt-4 p-3 bg-gray-700 rounded-lg">
                <h4 className="font-semibold mb-2">Plan Results</h4>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div className="bg-green-900/30 p-2 rounded">
                    <div className="text-green-400 text-lg font-bold">
                      {planResult.metrics.orders_satisfied}
                    </div>
                    <div className="text-gray-400 text-xs">Satisfied</div>
                  </div>
                  <div className="bg-red-900/30 p-2 rounded">
                    <div className="text-red-400 text-lg font-bold">
                      {planResult.metrics.orders_unsatisfied}
                    </div>
                    <div className="text-gray-400 text-xs">Unsatisfied</div>
                  </div>
                  <div className="bg-blue-900/30 p-2 rounded">
                    <div className="text-blue-400 text-lg font-bold">
                      {planResult.metrics.acquisitions_planned}
                    </div>
                    <div className="text-gray-400 text-xs">Acquisitions</div>
                  </div>
                </div>

                {planResult.unsatisfied_orders.length > 0 && (
                  <div className="mt-3">
                    <h5 className="text-sm font-medium mb-1">
                      Unsatisfied Orders:
                    </h5>
                    <div className="text-xs space-y-1">
                      {planResult.unsatisfied_orders.map((item) => (
                        <div
                          key={item.order_id}
                          className="flex justify-between text-gray-400"
                        >
                          <span className="font-mono">{item.order_id}</span>
                          <span className="text-red-400">{item.reason}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="mt-2 text-xs text-gray-500">
                  Computed in {planResult.metrics.compute_time_ms}ms
                </div>
              </div>
            )}

            {/* Orders in Batch */}
            {selectedBatch.orders && selectedBatch.orders.length > 0 && (
              <div className="mt-4">
                <h4 className="font-semibold mb-2">
                  Orders ({selectedBatch.orders.length})
                </h4>
                <div className="space-y-1 max-h-48 overflow-auto">
                  {selectedBatch.orders.map((order) => (
                    <div
                      key={order.id}
                      className="flex items-center justify-between text-sm bg-gray-700 px-2 py-1 rounded"
                    >
                      <span>{order.target_id}</span>
                      <span className="text-gray-400">P{order.priority}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            Select a batch to view details
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Schedule Tab Component
// =============================================================================

interface ScheduleTabProps {
  workspaceId: string;
  formatDate: (s: string) => string;
}

function ScheduleTab({
  workspaceId: _workspaceId,
  formatDate: _formatDate,
}: ScheduleTabProps) {
  return (
    <div className="text-center py-8 text-gray-500">
      <p>Schedule view - Shows committed acquisitions from batches</p>
      <p className="text-sm mt-2">
        Use the existing Schedule panel or integrate with the planning timeline
        view.
      </p>
    </div>
  );
}
