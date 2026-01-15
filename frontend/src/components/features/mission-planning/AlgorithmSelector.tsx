import React from "react";
import { Card } from "../../ui";
import { ALGORITHMS } from "./usePlanningState";

interface AlgorithmSelectorProps {
  selectedAlgorithms: Set<string>;
  onToggle: (algorithmId: string) => void;
  disabled?: boolean;
}

export const AlgorithmSelector: React.FC<AlgorithmSelectorProps> = ({
  selectedAlgorithms,
  onToggle,
  disabled = false,
}) => {
  return (
    <Card
      title="Algorithm Selector"
      className={disabled ? "opacity-50 pointer-events-none" : ""}
    >
      <div className="space-y-2">
        {ALGORITHMS.map((algo) => (
          <div
            key={algo.id}
            className={`flex items-center gap-3 p-2.5 bg-gray-700 rounded cursor-pointer hover:bg-gray-650 transition-colors ${
              selectedAlgorithms.has(algo.id) ? "ring-1 ring-blue-500/50" : ""
            }`}
            onClick={() => onToggle(algo.id)}
          >
            <input
              type="checkbox"
              checked={selectedAlgorithms.has(algo.id)}
              onChange={() => onToggle(algo.id)}
              className="w-4 h-4 flex-shrink-0"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-white">{algo.name}</div>
              <div className="text-xs text-gray-400">{algo.description}</div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

AlgorithmSelector.displayName = "AlgorithmSelector";
