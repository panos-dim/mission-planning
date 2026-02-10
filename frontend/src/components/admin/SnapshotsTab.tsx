import React, { useState, useEffect } from "react";
import { Download, RotateCcw, Trash2 } from "lucide-react";
import type { ConfigSnapshot } from "./types";

interface SnapshotsTabProps {
  onConfigUpdate?: () => void;
}

const SnapshotsTab: React.FC<SnapshotsTabProps> = ({ onConfigUpdate }) => {
  const [snapshots, setSnapshots] = useState<ConfigSnapshot[]>([]);
  const [currentConfigHash, setCurrentConfigHash] = useState<string>("");
  const [snapshotDescription, setSnapshotDescription] = useState("");
  const [isCreatingSnapshot, setIsCreatingSnapshot] = useState(false);
  const [isRestoringSnapshot, setIsRestoringSnapshot] = useState<string | null>(
    null,
  );

  useEffect(() => {
    fetchSnapshots();
  }, []);

  const fetchSnapshots = async () => {
    try {
      const response = await fetch("/api/v1/config/snapshots");
      const data = await response.json();
      if (data.success) {
        setSnapshots(data.snapshots || []);
        setCurrentConfigHash(data.current_hash || "");
      }
    } catch (error) {
      console.error("Error fetching snapshots:", error);
    }
  };

  const createSnapshot = async () => {
    setIsCreatingSnapshot(true);
    try {
      const response = await fetch("/api/v1/config/snapshots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: snapshotDescription || null }),
      });
      const data = await response.json();
      if (data.success) {
        await fetchSnapshots();
        setSnapshotDescription("");
      }
    } catch (error) {
      console.error("Error creating snapshot:", error);
    } finally {
      setIsCreatingSnapshot(false);
    }
  };

  const restoreSnapshot = async (snapshotId: string) => {
    setIsRestoringSnapshot(snapshotId);
    try {
      const response = await fetch(
        `/api/v1/config/snapshots/${snapshotId}/restore`,
        { method: "POST" },
      );
      const data = await response.json();
      if (data.success) {
        await fetchSnapshots();
        if (onConfigUpdate) onConfigUpdate();
        alert(
          `Config restored from snapshot. Backup created: ${data.backup_id}`,
        );
      }
    } catch (error) {
      console.error("Error restoring snapshot:", error);
    } finally {
      setIsRestoringSnapshot(null);
    }
  };

  const deleteSnapshot = async (snapshotId: string) => {
    if (!confirm(`Delete snapshot "${snapshotId}"?`)) return;
    try {
      const response = await fetch(`/api/v1/config/snapshots/${snapshotId}`, {
        method: "DELETE",
      });
      const data = await response.json();
      if (data.success) {
        await fetchSnapshots();
      }
    } catch (error) {
      console.error("Error deleting snapshot:", error);
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-gray-800 p-4 rounded-lg">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-white font-semibold">
            Configuration Snapshots
          </h3>
          <div className="text-xs text-gray-400">
            Current Hash:{" "}
            {currentConfigHash.substring(0, 8) || "loading..."}
          </div>
        </div>
        <p className="text-gray-400 text-sm mb-4">
          Create snapshots of your configuration to enable versioning and
          rollback capabilities.
        </p>

        {/* Create Snapshot */}
        <div className="bg-gray-700 p-4 rounded-lg mb-4">
          <h4 className="text-white font-medium mb-3">
            Create New Snapshot
          </h4>
          <div className="flex space-x-2">
            <input
              type="text"
              value={snapshotDescription}
              onChange={(e) => setSnapshotDescription(e.target.value)}
              placeholder="Optional description..."
              className="flex-1 bg-gray-600 text-white px-3 py-2 rounded"
            />
            <button
              onClick={createSnapshot}
              disabled={isCreatingSnapshot}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center space-x-2"
            >
              <Download className="w-4 h-4" />
              <span>
                {isCreatingSnapshot ? "Creating..." : "Create Snapshot"}
              </span>
            </button>
          </div>
        </div>

        {/* Snapshots List */}
        <div className="space-y-2">
          {snapshots.length === 0 ? (
            <p className="text-gray-500 text-center py-4">
              No snapshots yet. Create one to enable config versioning.
            </p>
          ) : (
            snapshots.map((snapshot) => (
              <div
                key={snapshot.id}
                className="bg-gray-700 p-3 rounded-lg flex justify-between items-center"
              >
                <div>
                  <div className="text-white font-medium text-sm">
                    {snapshot.id}
                  </div>
                  <div className="text-gray-400 text-xs">
                    {new Date(snapshot.timestamp).toLocaleString()}
                    {snapshot.description && (
                      <span className="ml-2">
                        - {snapshot.description}
                      </span>
                    )}
                  </div>
                  <div className="text-gray-500 text-xs mt-1">
                    Hash: {snapshot.config_hash.substring(0, 8)} | Files:{" "}
                    {snapshot.files.join(", ")}
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => restoreSnapshot(snapshot.id)}
                    disabled={isRestoringSnapshot === snapshot.id}
                    className="px-3 py-1 bg-yellow-600 text-white rounded hover:bg-yellow-700 text-sm flex items-center space-x-1"
                    title="Restore this snapshot"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>
                      {isRestoringSnapshot === snapshot.id
                        ? "Restoring..."
                        : "Restore"}
                    </span>
                  </button>
                  <button
                    onClick={() => deleteSnapshot(snapshot.id)}
                    className="p-1 text-gray-400 hover:text-red-400"
                    title="Delete snapshot"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default SnapshotsTab;
