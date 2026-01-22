import React from "react";
import { Modal } from "./ui/Modal";
import { Button } from "./ui/Button";
import { AlertTriangle, CheckCircle, XCircle } from "lucide-react";

export interface ConflictInfo {
  type: "temporal_overlap" | "slew_infeasible" | "resource_conflict";
  description: string;
  satellite_id?: string;
  affected_acquisitions?: string[];
  severity: "warning" | "error";
}

export interface CommitPreview {
  new_items_count: number;
  conflicts_count: number;
  conflicts: ConflictInfo[];
  warnings: string[];
}

interface ConflictWarningModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  onCancel: () => void;
  preview: CommitPreview | null;
  isCommitting: boolean;
}

export const ConflictWarningModal: React.FC<ConflictWarningModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  onCancel,
  preview,
  isCommitting,
}) => {
  if (!preview) return null;

  const hasErrors = preview.conflicts.some((c) => c.severity === "error");
  const hasWarnings =
    preview.conflicts.some((c) => c.severity === "warning") ||
    preview.warnings.length > 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        hasErrors
          ? "⚠️ Conflicts Detected"
          : hasWarnings
            ? "⚠️ Warnings"
            : "✓ Ready to Commit"
      }
      size="lg"
      footer={
        <>
          <Button
            variant="secondary"
            onClick={onCancel}
            disabled={isCommitting}
          >
            Cancel
          </Button>
          <Button
            variant={hasErrors ? "danger" : "primary"}
            onClick={onConfirm}
            disabled={isCommitting}
          >
            {isCommitting
              ? "Committing..."
              : hasErrors
                ? "Commit Anyway"
                : "Commit Plan"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {/* Summary */}
        <div className="flex items-center gap-4 p-3 bg-gray-800 rounded-lg">
          <div className="flex-1">
            <div className="text-sm text-gray-400">New Items</div>
            <div className="text-2xl font-bold text-white">
              {preview.new_items_count}
            </div>
          </div>
          <div className="flex-1">
            <div className="text-sm text-gray-400">Conflicts</div>
            <div
              className={`text-2xl font-bold ${preview.conflicts_count > 0 ? "text-red-400" : "text-green-400"}`}
            >
              {preview.conflicts_count}
            </div>
          </div>
        </div>

        {/* No conflicts message */}
        {preview.conflicts_count === 0 && preview.warnings.length === 0 && (
          <div className="flex items-center gap-3 p-4 bg-green-900/30 border border-green-700 rounded-lg">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <div>
              <div className="font-medium text-green-300">
                No conflicts detected
              </div>
              <div className="text-sm text-green-400/80">
                The plan can be committed safely.
              </div>
            </div>
          </div>
        )}

        {/* Conflicts list */}
        {preview.conflicts.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-300">
              Conflicts ({preview.conflicts.length})
            </h4>
            <div className="max-h-48 overflow-y-auto space-y-2">
              {preview.conflicts.map((conflict, idx) => (
                <div
                  key={idx}
                  className={`flex items-start gap-3 p-3 rounded-lg ${
                    conflict.severity === "error"
                      ? "bg-red-900/30 border border-red-700"
                      : "bg-yellow-900/30 border border-yellow-700"
                  }`}
                >
                  {conflict.severity === "error" ? (
                    <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div
                      className={`font-medium ${conflict.severity === "error" ? "text-red-300" : "text-yellow-300"}`}
                    >
                      {conflict.type.replace(/_/g, " ").toUpperCase()}
                    </div>
                    <div className="text-sm text-gray-400">
                      {conflict.description}
                    </div>
                    {conflict.satellite_id && (
                      <div className="text-xs text-gray-500 mt-1">
                        Satellite: {conflict.satellite_id}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Warnings list */}
        {preview.warnings.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-300">
              Warnings ({preview.warnings.length})
            </h4>
            <div className="space-y-1">
              {preview.warnings.map((warning, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 text-sm text-yellow-400"
                >
                  <AlertTriangle className="w-4 h-4" />
                  {warning}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Warning message for errors */}
        {hasErrors && (
          <div className="p-3 bg-red-900/20 border border-red-800 rounded-lg">
            <div className="text-sm text-red-300">
              <strong>Warning:</strong> Committing with conflicts may cause
              scheduling issues. Review the conflicts above before proceeding.
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default ConflictWarningModal;
