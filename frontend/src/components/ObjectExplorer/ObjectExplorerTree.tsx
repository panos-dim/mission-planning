/**
 * ObjectExplorerTree Component
 *
 * STK-style hierarchical tree view for navigating workspace objects.
 * Features: expand/collapse, search filtering, badges, context menu.
 */

import React, { useMemo, useCallback, useRef, useEffect } from "react";
import { Search, ChevronDown, ChevronRight } from "lucide-react";
import TreeNodeComponent from "./TreeNode";
import { useExplorerStore } from "../../store/explorerStore";
import { usePlanningStore } from "../../store/planningStore";
import { useOrdersStore } from "../../store/ordersStore";
import { useMission } from "../../context/MissionContext";
import { buildObjectTree, filterTree } from "../../utils/treeBuilder";
import type { TreeNode } from "../../types/explorer";
import type { AlgorithmResult, AcceptedOrder } from "../../types";

// =============================================================================
// Context Menu Component
// =============================================================================

interface ContextMenuProps {
  x: number;
  y: number;
  nodeId: string;
  nodeType: string;
  onClose: () => void;
  onAction: (action: string) => void;
}

const ContextMenu: React.FC<ContextMenuProps> = ({
  x,
  y,
  nodeId: _nodeId,
  nodeType,
  onClose,
  onAction,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  // Determine available actions based on node type
  const getActions = () => {
    const actions = [];

    // Navigation actions
    if (
      [
        "satellite",
        "target",
        "ground_station",
        "opportunity",
        "plan_item",
      ].includes(nodeType)
    ) {
      actions.push({ id: "flyTo", label: "Fly To", icon: "Navigation" });
    }

    if (["opportunity", "plan_item"].includes(nodeType)) {
      actions.push({ id: "jumpToTime", label: "Jump to Time", icon: "Clock" });
    }

    // Filter actions
    if (nodeType === "target") {
      actions.push({
        id: "filterOpportunities",
        label: "Filter Opportunities",
        icon: "Filter",
      });
    }

    // Plan actions
    if (nodeType === "plan") {
      actions.push({
        id: "setActive",
        label: "Set as Active Plan",
        icon: "CheckCircle",
      });
      actions.push({ id: "export", label: "Export Plan", icon: "Download" });
    }

    // Order actions
    if (nodeType === "order") {
      actions.push({ id: "loadOrder", label: "Load Order", icon: "Upload" });
      actions.push({
        id: "exportOrder",
        label: "Export Order",
        icon: "Download",
      });
    }

    // Delete action for user-created items
    if (["target", "order"].includes(nodeType)) {
      actions.push({
        id: "delete",
        label: "Delete",
        icon: "Trash2",
        danger: true,
      });
    }

    return actions;
  };

  const actions = getActions();

  if (actions.length === 0) {
    return null;
  }

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-gray-800 border border-gray-700 rounded-lg shadow-xl py-1 min-w-[160px]"
      style={{ left: x, top: y }}
    >
      {actions.map((action) => (
        <button
          key={action.id}
          onClick={() => {
            onAction(action.id);
            onClose();
          }}
          className={`
            w-full px-3 py-2 text-left text-sm flex items-center gap-2
            ${
              action.danger
                ? "text-red-400 hover:bg-red-900/30"
                : "text-gray-300 hover:bg-gray-700"
            }
          `}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
};

// =============================================================================
// Main ObjectExplorerTree Component
// =============================================================================

interface ObjectExplorerTreeProps {
  algorithmResults?: Record<string, AlgorithmResult>;
  acceptedOrders?: AcceptedOrder[];
  onNodeSelect?: (
    nodeId: string,
    nodeType: string,
    metadata?: Record<string, unknown>
  ) => void;
}

const ObjectExplorerTree: React.FC<ObjectExplorerTreeProps> = ({
  algorithmResults: propAlgorithmResults = {},
  acceptedOrders = [],
  onNodeSelect,
}) => {
  const { state, flyToObject, navigateToImagingTime } = useMission();
  const planningResults = usePlanningStore((s) => s.results);
  const setActiveAlgorithm = usePlanningStore((s) => s.setActiveAlgorithm);
  const { removeOrder } = useOrdersStore();
  const {
    expandedNodes,
    selectedNodeId,
    searchQuery,
    filterByTarget,
    toggleNode,
    selectNode,
    setSearchQuery,
    expandAll,
    collapseAll,
    setExpandedNodes,
    setActivePlan,
    setFilterByTarget,
  } = useExplorerStore();

  // Use planning store results if available, otherwise use prop
  const algorithmResults = planningResults || propAlgorithmResults;

  // Context menu state
  const [contextMenu, setContextMenu] = React.useState<{
    x: number;
    y: number;
    nodeId: string;
    nodeType: string;
  } | null>(null);

  // Build tree data from mission state
  const treeData = useMemo(() => {
    return buildObjectTree({
      missionData: state.missionData,
      sceneObjects: state.sceneObjects,
      algorithmResults,
      acceptedOrders,
      analysisRuns: [],
      planningRuns: [],
      filterByTarget,
    });
  }, [
    state.missionData,
    state.sceneObjects,
    algorithmResults,
    acceptedOrders,
    filterByTarget,
  ]);

  // Filter tree based on search query
  const filteredNodeIds = useMemo(() => {
    if (!searchQuery.trim()) return null;
    return filterTree(treeData, searchQuery);
  }, [treeData, searchQuery]);

  // Auto-expand filtered nodes
  useEffect(() => {
    if (filteredNodeIds && filteredNodeIds.size > 0) {
      setExpandedNodes(
        new Set([...Array.from(expandedNodes), ...Array.from(filteredNodeIds)])
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filteredNodeIds, setExpandedNodes]);

  // Handle node selection
  const handleSelect = useCallback(
    (nodeId: string, nodeType: string) => {
      selectNode(nodeId, nodeType as Parameters<typeof selectNode>[1]);

      // Find node metadata
      const findNode = (node: TreeNode): TreeNode | null => {
        if (node.id === nodeId) return node;
        if (node.children) {
          for (const child of node.children) {
            const found = findNode(child);
            if (found) return found;
          }
        }
        return null;
      };

      const node = findNode(treeData);
      if (onNodeSelect) {
        onNodeSelect(nodeId, nodeType, node?.metadata);
      }
    },
    [selectNode, treeData, onNodeSelect]
  );

  // Handle context menu
  const handleContextMenu = useCallback(
    (e: React.MouseEvent, nodeId: string, nodeType: string) => {
      e.preventDefault();
      setContextMenu({
        x: e.clientX,
        y: e.clientY,
        nodeId,
        nodeType,
      });
    },
    []
  );

  // Handle context menu actions
  const handleContextAction = useCallback(
    (action: string) => {
      if (!contextMenu) return;

      const { nodeId, nodeType } = contextMenu;
      console.log(
        `[ContextMenu] Action: ${action} on node ${nodeId} (${nodeType})`
      );

      switch (action) {
        case "flyTo":
          flyToObject(nodeId);
          break;

        case "jumpToTime": {
          const passIndex = extractPassIndex(nodeId);
          if (passIndex !== null) {
            navigateToImagingTime(passIndex);
          }
          break;
        }

        case "filterOpportunities": {
          const targetName = extractTargetName(nodeId);
          if (targetName) {
            setFilterByTarget(targetName);
          }
          break;
        }

        case "setActive": {
          const algorithm = extractAlgorithmFromNodeId(nodeId);
          if (algorithm) {
            setActivePlan(nodeId);
            setActiveAlgorithm(algorithm);
          }
          break;
        }

        case "export": {
          if (nodeType === "plan") {
            const algo = extractAlgorithmFromNodeId(nodeId);
            if (algo && algorithmResults && algorithmResults[algo]) {
              const result = algorithmResults[algo];
              downloadJson(
                {
                  algorithm: algo,
                  exported_at: new Date().toISOString(),
                  schedule: result.schedule,
                  metrics: result.metrics,
                },
                `plan_${algo}_${Date.now()}.json`
              );
            }
          }
          break;
        }

        case "loadOrder":
          console.log("[ContextMenu] Load order:", nodeId);
          break;

        case "exportOrder": {
          const orderId = nodeId.replace(/^order_/, "");
          const order = acceptedOrders.find((o) => o.order_id === orderId);
          if (order) {
            downloadJson(
              order,
              `order_${order.name.replace(/\s+/g, "_")}_${Date.now()}.json`
            );
          }
          break;
        }

        case "delete": {
          if (nodeType === "order") {
            const orderId = nodeId.replace(/^order_/, "");
            if (window.confirm("Are you sure you want to delete this order?")) {
              removeOrder(orderId);
            }
          }
          break;
        }
      }
    },
    [
      contextMenu,
      flyToObject,
      navigateToImagingTime,
      setFilterByTarget,
      setActivePlan,
      setActiveAlgorithm,
      algorithmResults,
      acceptedOrders,
      removeOrder,
    ]
  );

  // Helper functions for context menu
  function extractPassIndex(nodeId: string): number | null {
    const match = nodeId.match(/opportunity_(\d+)_|plan_item_\w+_(\d+)/);
    return match ? parseInt(match[1] || match[2], 10) : null;
  }

  function extractTargetName(nodeId: string): string | null {
    const match = nodeId.match(/target_(?:mission_)?(?:\d+_)?(.+)$/);
    return match ? match[1] : null;
  }

  function extractAlgorithmFromNodeId(nodeId: string): string | null {
    const match = nodeId.match(/^plan_(.+)$/);
    return match ? match[1] : null;
  }

  function downloadJson(data: unknown, filename: string): void {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // Get flattened list of visible nodes for keyboard navigation
  const getVisibleNodes = useCallback((): TreeNode[] => {
    const visible: TreeNode[] = [];

    function traverse(node: TreeNode) {
      // Skip filtered nodes
      if (filteredNodeIds !== null && !filteredNodeIds.has(node.id)) {
        return;
      }
      visible.push(node);
      // Only traverse children if expanded
      if (node.children && expandedNodes.has(node.id)) {
        node.children.forEach(traverse);
      }
    }

    traverse(treeData);
    return visible;
  }, [treeData, expandedNodes, filteredNodeIds]);

  // Find parent node
  const findParentNode = useCallback(
    (nodeId: string): TreeNode | null => {
      function findParent(
        node: TreeNode,
        parentNode: TreeNode | null
      ): TreeNode | null {
        if (node.id === nodeId) return parentNode;
        if (node.children) {
          for (const child of node.children) {
            const found = findParent(child, node);
            if (found !== null) return found;
          }
        }
        return null;
      }
      return findParent(treeData, null);
    },
    [treeData]
  );

  // Keyboard navigation handler
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const visibleNodes = getVisibleNodes();
      if (visibleNodes.length === 0) return;

      const currentIndex = selectedNodeId
        ? visibleNodes.findIndex((n) => n.id === selectedNodeId)
        : -1;
      const currentNode = currentIndex >= 0 ? visibleNodes[currentIndex] : null;

      switch (e.key) {
        case "ArrowDown": {
          e.preventDefault();
          const nextIndex =
            currentIndex < visibleNodes.length - 1 ? currentIndex + 1 : 0;
          const nextNode = visibleNodes[nextIndex];
          selectNode(nextNode.id, nextNode.type);
          break;
        }

        case "ArrowUp": {
          e.preventDefault();
          const prevIndex =
            currentIndex > 0 ? currentIndex - 1 : visibleNodes.length - 1;
          const prevNode = visibleNodes[prevIndex];
          selectNode(prevNode.id, prevNode.type);
          break;
        }

        case "ArrowRight": {
          e.preventDefault();
          if (currentNode) {
            if (currentNode.children && currentNode.children.length > 0) {
              if (!expandedNodes.has(currentNode.id)) {
                // Expand if collapsed
                toggleNode(currentNode.id);
              } else {
                // Already expanded, go to first child
                const firstChild = currentNode.children[0];
                selectNode(firstChild.id, firstChild.type);
              }
            }
          }
          break;
        }

        case "ArrowLeft": {
          e.preventDefault();
          if (currentNode) {
            if (
              expandedNodes.has(currentNode.id) &&
              currentNode.children?.length
            ) {
              // Collapse if expanded
              toggleNode(currentNode.id);
            } else {
              // Go to parent
              const parent = findParentNode(currentNode.id);
              if (parent) {
                selectNode(parent.id, parent.type);
              }
            }
          }
          break;
        }

        case "Enter": {
          e.preventDefault();
          if (currentNode) {
            // Trigger flyTo for actionable nodes
            if (
              [
                "satellite",
                "target",
                "ground_station",
                "opportunity",
                "plan_item",
              ].includes(currentNode.type)
            ) {
              flyToObject(currentNode.id);
            }
            // Toggle expansion for container nodes
            if (currentNode.children && currentNode.children.length > 0) {
              toggleNode(currentNode.id);
            }
          }
          break;
        }

        case "Home": {
          e.preventDefault();
          if (visibleNodes.length > 0) {
            const firstNode = visibleNodes[0];
            selectNode(firstNode.id, firstNode.type);
          }
          break;
        }

        case "End": {
          e.preventDefault();
          if (visibleNodes.length > 0) {
            const lastNode = visibleNodes[visibleNodes.length - 1];
            selectNode(lastNode.id, lastNode.type);
          }
          break;
        }
      }
    },
    [
      getVisibleNodes,
      selectedNodeId,
      selectNode,
      expandedNodes,
      toggleNode,
      findParentNode,
      flyToObject,
    ]
  );

  // Recursive tree renderer
  const renderNode = useCallback(
    (node: TreeNode, depth: number = 0): React.ReactNode => {
      const isExpanded = expandedNodes.has(node.id);
      const isSelected = selectedNodeId === node.id;
      const isFiltered =
        filteredNodeIds !== null && !filteredNodeIds.has(node.id);

      return (
        <TreeNodeComponent
          key={node.id}
          node={node}
          depth={depth}
          isExpanded={isExpanded}
          isSelected={isSelected}
          isFiltered={isFiltered}
          onToggle={toggleNode}
          onSelect={handleSelect}
          onContextMenu={handleContextMenu}
          renderChildren={
            node.children
              ? () =>
                  node.children!.map((child) => renderNode(child, depth + 1))
              : undefined
          }
        />
      );
    },
    [
      expandedNodes,
      selectedNodeId,
      filteredNodeIds,
      toggleNode,
      handleSelect,
      handleContextMenu,
    ]
  );

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Search Bar */}
      <div className="p-2 border-b border-gray-700">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search objects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-md
              text-sm text-gray-300 placeholder-gray-500
              focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Expand/Collapse Controls */}
        <div className="flex items-center gap-1 mt-2">
          <button
            onClick={expandAll}
            className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400
              hover:text-white hover:bg-gray-800 rounded transition-colors"
          >
            <ChevronDown className="w-3 h-3" />
            Expand All
          </button>
          <button
            onClick={collapseAll}
            className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400
              hover:text-white hover:bg-gray-800 rounded transition-colors"
          >
            <ChevronRight className="w-3 h-3" />
            Collapse
          </button>
        </div>
      </div>

      {/* Tree View */}
      <div
        className="flex-1 overflow-y-auto py-1 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
        tabIndex={0}
        onKeyDown={handleKeyDown}
        role="tree"
        aria-label="Object Explorer"
      >
        {renderNode(treeData)}
      </div>

      {/* Target Filter Indicator */}
      {filterByTarget && (
        <div className="px-3 py-2 border-t border-gray-700 flex items-center justify-between bg-blue-900/30">
          <span className="text-xs text-blue-300">
            Filtering: <strong>{filterByTarget}</strong>
          </span>
          <button
            onClick={() => setFilterByTarget(null)}
            className="text-xs text-blue-400 hover:text-white px-2 py-0.5 rounded hover:bg-blue-800/50"
          >
            Clear
          </button>
        </div>
      )}

      {/* Search Results Count */}
      {filteredNodeIds && (
        <div className="px-3 py-2 border-t border-gray-700 text-xs text-gray-500">
          {filteredNodeIds.size} items match &ldquo;{searchQuery}&rdquo;
        </div>
      )}

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          nodeId={contextMenu.nodeId}
          nodeType={contextMenu.nodeType}
          onClose={() => setContextMenu(null)}
          onAction={handleContextAction}
        />
      )}
    </div>
  );
};

export default ObjectExplorerTree;
