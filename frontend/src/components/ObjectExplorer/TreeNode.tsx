/**
 * TreeNode Component
 *
 * Individual tree node with expand/collapse, selection, and context menu support.
 */

import React, { memo, useCallback } from "react";
import {
  ChevronRight,
  ChevronDown,
  Satellite,
  Target,
  Radio,
  MapPin,
  Settings,
  Eye,
  Gauge,
  Sliders,
  Play,
  BarChart2,
  Calendar,
  CheckCircle,
  Zap,
  FileText,
  Package,
  Upload,
  File,
  FolderOpen,
  Clock,
  Box,
} from "lucide-react";
import type {
  TreeNode as TreeNodeType,
  TreeNodeBadge,
} from "../../types/explorer";

// =============================================================================
// Icon Mapping
// =============================================================================

const ICON_COMPONENTS: Record<string, React.ElementType> = {
  FolderOpen,
  Clock,
  Box,
  Satellite,
  Radio,
  Target,
  MapPin,
  Settings,
  Eye,
  Gauge,
  Sliders,
  Play,
  BarChart2,
  Calendar,
  CheckCircle,
  Zap,
  FileText,
  ChevronRight,
  Package,
  Upload,
  File,
};

// =============================================================================
// Badge Component
// =============================================================================

interface BadgeProps {
  badge: TreeNodeBadge;
}

const Badge: React.FC<BadgeProps> = memo(({ badge }) => {
  const colorClasses: Record<string, string> = {
    blue: "bg-blue-500/20 text-blue-400",
    green: "bg-green-500/20 text-green-400",
    yellow: "bg-yellow-500/20 text-yellow-400",
    red: "bg-red-500/20 text-red-400",
    gray: "bg-gray-500/20 text-gray-400",
  };

  return (
    <span
      className={`ml-auto px-1.5 py-0.5 rounded text-xs font-medium ${
        colorClasses[badge.color || "gray"]
      }`}
    >
      {badge.count}
    </span>
  );
});

Badge.displayName = "Badge";

// =============================================================================
// TreeNode Component
// =============================================================================

interface TreeNodeProps {
  node: TreeNodeType;
  depth: number;
  isExpanded: boolean;
  isSelected: boolean;
  isFiltered: boolean;
  onToggle: (nodeId: string) => void;
  onSelect: (nodeId: string, nodeType: string) => void;
  onContextMenu: (
    e: React.MouseEvent,
    nodeId: string,
    nodeType: string
  ) => void;
  renderChildren?: () => React.ReactNode;
}

const TreeNodeComponent: React.FC<TreeNodeProps> = memo(
  ({
    node,
    depth,
    isExpanded,
    isSelected,
    isFiltered,
    onToggle,
    onSelect,
    onContextMenu,
    renderChildren,
  }) => {
    const hasChildren = node.children && node.children.length > 0;
    const isExpandable = node.isExpandable !== false && hasChildren;

    const handleToggle = useCallback(
      (e: React.MouseEvent) => {
        e.stopPropagation();
        if (isExpandable) {
          onToggle(node.id);
        }
      },
      [isExpandable, node.id, onToggle]
    );

    const handleSelect = useCallback(() => {
      onSelect(node.id, node.type);
    }, [node.id, node.type, onSelect]);

    const handleContextMenu = useCallback(
      (e: React.MouseEvent) => {
        e.preventDefault();
        onContextMenu(e, node.id, node.type);
      },
      [node.id, node.type, onContextMenu]
    );

    // Get icon component
    const IconComponent = node.icon ? ICON_COMPONENTS[node.icon] : Box;

    // Calculate padding based on depth
    const paddingLeft = 8 + depth * 16;

    // Hide if filtered out
    if (isFiltered) {
      return null;
    }

    return (
      <div className="select-none">
        {/* Node Row */}
        <div
          className={`
          flex items-center gap-1 px-2 py-1 cursor-pointer rounded-sm
          hover:bg-gray-800 transition-colors
          ${isSelected ? "bg-blue-900/40 border-l-2 border-blue-500" : ""}
        `}
          style={{ paddingLeft }}
          onClick={handleSelect}
          onContextMenu={handleContextMenu}
        >
          {/* Expand/Collapse Toggle */}
          <button
            className={`
            p-0.5 rounded hover:bg-gray-700 transition-colors
            ${isExpandable ? "visible" : "invisible"}
          `}
            onClick={handleToggle}
          >
            {isExpanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
            )}
          </button>

          {/* Icon */}
          {IconComponent && (
            <IconComponent className="w-4 h-4 text-gray-400 flex-shrink-0" />
          )}

          {/* Name */}
          <span className="flex-1 text-sm text-gray-300 truncate">
            {node.name}
          </span>

          {/* Badge */}
          {node.badge && <Badge badge={node.badge} />}
        </div>

        {/* Children */}
        {isExpanded && hasChildren && renderChildren && (
          <div className="relative">
            {/* Vertical line connector */}
            <div
              className="absolute top-0 bottom-0 border-l border-gray-700"
              style={{ left: paddingLeft + 11 }}
            />
            {renderChildren()}
          </div>
        )}
      </div>
    );
  }
);

TreeNodeComponent.displayName = "TreeNode";

export default TreeNodeComponent;
