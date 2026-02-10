import React, { useState, useEffect } from "react";
import { Edit2, Save } from "lucide-react";
import type { SARMode } from "./types";

interface SarModesTabProps {
  onConfigUpdate?: () => void;
}

const SarModesTab: React.FC<SarModesTabProps> = ({ onConfigUpdate }) => {
  const [sarModes, setSarModes] = useState<Record<string, SARMode>>({});
  const [editingModeName, setEditingModeName] = useState<string | null>(null);
  const [editingModeData, setEditingModeData] = useState<SARMode | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [currentConfigHash, setCurrentConfigHash] = useState<string>("");

  useEffect(() => {
    fetchSarModes();
    fetchConfigHash();
  }, []);

  const fetchSarModes = async () => {
    try {
      const response = await fetch("/api/v1/config/sar-modes");
      const data = await response.json();
      if (data.success) {
        setSarModes(data.modes || {});
      }
    } catch (error) {
      console.error("Error fetching SAR modes:", error);
    }
  };

  const fetchConfigHash = async () => {
    try {
      const response = await fetch("/api/v1/config/snapshots");
      const data = await response.json();
      if (data.success) {
        setCurrentConfigHash(data.current_hash || "");
      }
    } catch (error) {
      console.error("Error fetching config hash:", error);
    }
  };

  const saveSarMode = async (modeName: string, modeData: SARMode) => {
    setIsSaving(true);
    try {
      const response = await fetch(`/api/v1/config/sar-modes/${modeName}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(modeData),
      });
      const data = await response.json();
      if (data.success) {
        await fetchSarModes();
        await fetchConfigHash();
        setEditingModeName(null);
        setEditingModeData(null);
        if (onConfigUpdate) onConfigUpdate();
      } else {
        console.error("Failed to save SAR mode:", data);
      }
    } catch (error) {
      console.error("Error saving SAR mode:", error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-gray-800 p-4 rounded-lg">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-white font-semibold">SAR Imaging Modes</h3>
          <div className="text-xs text-gray-400">
            Config Hash:{" "}
            {currentConfigHash.substring(0, 8) || "loading..."}
          </div>
        </div>
        <p className="text-gray-400 text-sm mb-4">
          Configure incidence angle ranges, scene dimensions, and quality
          parameters for each SAR imaging mode.
        </p>

        {Object.keys(sarModes).length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            Loading SAR modes...
          </p>
        ) : (
          <div className="space-y-4">
            {Object.entries(sarModes).map(([modeName, mode]) => (
              <div key={modeName} className="bg-gray-700 p-4 rounded-lg">
                {editingModeName === modeName && editingModeData ? (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h4 className="text-white font-medium capitalize">
                        {modeName}
                      </h4>
                      <div className="flex space-x-2">
                        <button
                          onClick={() =>
                            saveSarMode(modeName, editingModeData)
                          }
                          disabled={isSaving}
                          className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-sm flex items-center space-x-1"
                        >
                          <Save className="w-3 h-3" />
                          <span>{isSaving ? "Saving..." : "Save"}</span>
                        </button>
                        <button
                          onClick={() => {
                            setEditingModeName(null);
                            setEditingModeData(null);
                          }}
                          className="px-3 py-1 bg-gray-600 text-white rounded hover:bg-gray-500 text-sm"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>

                    {/* Incidence Angles */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-gray-300 text-xs block mb-1">
                          Recommended Min (°)
                        </label>
                        <input
                          type="number"
                          value={editingModeData.incidence_angle.recommended_min}
                          onChange={(e) =>
                            setEditingModeData({
                              ...editingModeData,
                              incidence_angle: {
                                ...editingModeData.incidence_angle,
                                recommended_min: parseFloat(e.target.value),
                              },
                            })
                          }
                          className="w-full bg-gray-600 text-white px-2 py-1 rounded text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-gray-300 text-xs block mb-1">
                          Recommended Max (°)
                        </label>
                        <input
                          type="number"
                          value={editingModeData.incidence_angle.recommended_max}
                          onChange={(e) =>
                            setEditingModeData({
                              ...editingModeData,
                              incidence_angle: {
                                ...editingModeData.incidence_angle,
                                recommended_max: parseFloat(e.target.value),
                              },
                            })
                          }
                          className="w-full bg-gray-600 text-white px-2 py-1 rounded text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-gray-300 text-xs block mb-1">
                          Absolute Min (°)
                        </label>
                        <input
                          type="number"
                          value={editingModeData.incidence_angle.absolute_min}
                          onChange={(e) =>
                            setEditingModeData({
                              ...editingModeData,
                              incidence_angle: {
                                ...editingModeData.incidence_angle,
                                absolute_min: parseFloat(e.target.value),
                              },
                            })
                          }
                          className="w-full bg-gray-600 text-white px-2 py-1 rounded text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-gray-300 text-xs block mb-1">
                          Absolute Max (°)
                        </label>
                        <input
                          type="number"
                          value={editingModeData.incidence_angle.absolute_max}
                          onChange={(e) =>
                            setEditingModeData({
                              ...editingModeData,
                              incidence_angle: {
                                ...editingModeData.incidence_angle,
                                absolute_max: parseFloat(e.target.value),
                              },
                            })
                          }
                          className="w-full bg-gray-600 text-white px-2 py-1 rounded text-sm"
                        />
                      </div>
                    </div>

                    {/* Scene Dimensions */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-gray-300 text-xs block mb-1">
                          Scene Width (km)
                        </label>
                        <input
                          type="number"
                          value={editingModeData.scene.width_km}
                          onChange={(e) =>
                            setEditingModeData({
                              ...editingModeData,
                              scene: {
                                ...editingModeData.scene,
                                width_km: parseFloat(e.target.value),
                              },
                            })
                          }
                          className="w-full bg-gray-600 text-white px-2 py-1 rounded text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-gray-300 text-xs block mb-1">
                          Scene Length (km)
                        </label>
                        <input
                          type="number"
                          value={editingModeData.scene.length_km}
                          onChange={(e) =>
                            setEditingModeData({
                              ...editingModeData,
                              scene: {
                                ...editingModeData.scene,
                                length_km: parseFloat(e.target.value),
                              },
                            })
                          }
                          className="w-full bg-gray-600 text-white px-2 py-1 rounded text-sm"
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h4 className="text-white font-medium">
                        {mode.display_name}
                      </h4>
                      <p className="text-gray-400 text-sm mt-1">
                        {mode.description}
                      </p>
                      <div className="grid grid-cols-2 gap-4 mt-3 text-xs text-gray-500">
                        <div>
                          <span className="text-gray-400">Incidence:</span>{" "}
                          {mode.incidence_angle.recommended_min}° -{" "}
                          {mode.incidence_angle.recommended_max}°
                          <span className="text-gray-600 ml-1">
                            (abs: {mode.incidence_angle.absolute_min}° -{" "}
                            {mode.incidence_angle.absolute_max}°)
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-400">Scene:</span>{" "}
                          {mode.scene.width_km}km × {mode.scene.length_km}km
                        </div>
                        <div>
                          <span className="text-gray-400">Resolution:</span>{" "}
                          {mode.collection.azimuth_resolution_m}m ×{" "}
                          {mode.collection.range_resolution_m}m
                        </div>
                        <div>
                          <span className="text-gray-400">
                            Optimal Incidence:
                          </span>{" "}
                          {mode.quality.optimal_incidence_deg}°
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setEditingModeName(modeName);
                        setEditingModeData({ ...mode });
                      }}
                      className="p-2 text-gray-400 hover:text-white"
                      title="Edit SAR mode"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SarModesTab;
