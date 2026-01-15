import React, { useState, useRef, useEffect } from "react";
import {
  Plus,
  Trash2,
  MapPin,
  Target,
  Upload,
  FileText,
  AlertCircle,
  CheckCircle,
  Map,
  Shuffle,
} from "lucide-react";
import { TargetData } from "../types";
import { useTargetAddStore } from "../store/targetAddStore";
import { usePreviewTargetsStore } from "../store/previewTargetsStore";
import { TargetDetailsSheet } from "./Targets/TargetDetailsSheet";

// Color presets for target markers (gradient from green to red)
const TARGET_COLORS = [
  { value: "#EF4444", label: "Red", tailwind: "bg-red-500" },
  { value: "#F97316", label: "Orange", tailwind: "bg-orange-500" },
  { value: "#EAB308", label: "Yellow", tailwind: "bg-yellow-500" },
  { value: "#22C55E", label: "Green", tailwind: "bg-green-500" },
];

interface TargetInputProps {
  targets: TargetData[];
  onChange: (targets: TargetData[]) => void;
  disabled?: boolean;
}

const TargetInput: React.FC<TargetInputProps> = ({
  targets,
  onChange,
  disabled = false,
}) => {
  const [newTarget, setNewTarget] = useState<TargetData>({
    name: "",
    latitude: 0,
    longitude: 0,
    description: "",
    priority: 1,
    color: "#EF4444", // Default red
  });
  const [coordinateInput, setCoordinateInput] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{
    type: "success" | "error" | null;
    message: string;
  }>({ type: null, message: "" });
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Map click target state
  const { isAddMode, toggleAddMode } = useTargetAddStore();

  // Preview targets store - sync targets to map display
  const { setTargets: setPreviewTargets } = usePreviewTargetsStore();

  // Sync targets to preview store whenever they change
  useEffect(() => {
    setPreviewTargets(targets);
  }, [targets, setPreviewTargets]);

  const addTarget = () => {
    if (
      !newTarget.name ||
      newTarget.latitude === 0 ||
      newTarget.longitude === 0
    ) {
      alert("Please provide target name and coordinates");
      return;
    }

    onChange([...targets, { ...newTarget }]);
    setNewTarget({
      name: "",
      latitude: 0,
      longitude: 0,
      description: "",
      priority: 1,
      color: "#EF4444",
    });
    setCoordinateInput("");
  };

  const parseCoordinates = async () => {
    if (!coordinateInput) return;

    try {
      const response = await fetch("/api/targets/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ coordinate_string: coordinateInput }),
      });

      const data = await response.json();
      if (response.ok) {
        setNewTarget({
          ...newTarget,
          latitude: data.latitude,
          longitude: data.longitude,
        });
        setUploadStatus({
          type: "success",
          message: `Parsed: ${data.latitude.toFixed(
            4
          )}°, ${data.longitude.toFixed(4)}°`,
        });
      } else {
        setUploadStatus({
          type: "error",
          message: data.error || "Failed to parse coordinates",
        });
      }
    } catch (error) {
      setUploadStatus({ type: "error", message: "Error parsing coordinates" });
    }
  };

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus({ type: null, message: "" });

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/targets/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (response.ok && data.targets) {
        const newTargets = data.targets.map((t: any) => ({
          name: t.name,
          latitude: t.latitude,
          longitude: t.longitude,
          description: t.description || "",
          priority: t.priority || 1, // Default priority to 1
        }));
        onChange([...targets, ...newTargets]);
        setUploadStatus({
          type: "success",
          message: `Successfully added ${newTargets.length} target(s) from ${file.name}`,
        });
      } else {
        setUploadStatus({
          type: "error",
          message: data.error || "Failed to upload file",
        });
      }
    } catch (error) {
      setUploadStatus({ type: "error", message: "Error uploading file" });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const removeTarget = (index: number) => {
    onChange(targets.filter((_, i) => i !== index));
  };

  const loadSampleTargets = () => {
    // Eastern Mediterranean scenario: 10 nearby targets to showcase algorithm differences
    // These targets are close enough (~200-500km apart) to create scheduling conflicts
    // and force algorithms to make tradeoff decisions between value, efficiency, and coverage
    const sampleTargets: TargetData[] = [
      {
        name: "Athens",
        latitude: 37.9838,
        longitude: 23.7275,
        description: "Greek Capital - High Priority",
        priority: 5, // Highest priority
      },
      {
        name: "Istanbul",
        latitude: 41.0082,
        longitude: 28.9784,
        description: "Turkey - Major City (~500km from Athens)",
        priority: 4, // Very high priority
      },
      {
        name: "Thessaloniki",
        latitude: 40.6401,
        longitude: 22.9444,
        description: "Northern Greece (~310km from Athens)",
        priority: 3, // High priority
      },
      {
        name: "Izmir",
        latitude: 38.4237,
        longitude: 27.1428,
        description: "Western Turkey (~280km from Athens)",
        priority: 3, // High priority
      },
      {
        name: "Nicosia",
        latitude: 35.1856,
        longitude: 33.3823,
        description: "Cyprus - Capital (~800km from Athens)",
        priority: 3, // High priority
      },
      {
        name: "Sofia",
        latitude: 42.6977,
        longitude: 23.3219,
        description: "Bulgaria - Capital (~550km from Athens)",
        priority: 2, // Medium priority
      },
      {
        name: "Rhodes",
        latitude: 36.4341,
        longitude: 28.2176,
        description: "Greek Island (~430km from Athens)",
        priority: 2, // Medium priority
      },
      {
        name: "Antalya",
        latitude: 36.8969,
        longitude: 30.7133,
        description: "Southern Turkey (~480km from Athens)",
        priority: 2, // Medium priority
      },
      {
        name: "Heraklion",
        latitude: 35.3387,
        longitude: 25.1442,
        description: "Crete, Greece (~380km from Athens)",
        priority: 1, // Lower priority
      },
      {
        name: "Patras",
        latitude: 38.2466,
        longitude: 21.7346,
        description: "Western Greece (~210km from Athens)",
        priority: 1, // Lower priority
      },
    ];
    onChange(sampleTargets);
  };

  // Handle target save from map click
  const handleMapTargetSave = (target: TargetData) => {
    onChange([...targets, target]);
    setUploadStatus({
      type: "success",
      message: `Added target "${
        target.name
      }" from map (${target.latitude.toFixed(4)}°, ${target.longitude.toFixed(
        4
      )}°)`,
    });
  };

  // Randomize all target colors (for testing)
  // Pattern: First 40 = Green, remaining split ~evenly among Red, Orange, Yellow
  const randomizeColors = () => {
    const greenCount = 40;
    const remaining = Math.max(0, targets.length - greenCount);
    const perColor = Math.ceil(remaining / 3);

    const updated = targets.map((target, index) => {
      let color: string;
      if (index < greenCount) {
        // First 40 are always green
        color = "#22C55E";
      } else {
        // Remaining split among Red, Orange, Yellow
        const remainingIndex = index - greenCount;
        if (remainingIndex < perColor) {
          color = "#F97316"; // Orange
        } else if (remainingIndex < perColor * 2) {
          color = "#EAB308"; // Yellow
        } else {
          color = "#EF4444"; // Red
        }
      }
      return { ...target, color };
    });
    onChange(updated);
    setUploadStatus({
      type: "success",
      message: `Colored ${targets.length} targets: ${greenCount} green, rest split among orange/yellow/red`,
    });
  };

  return (
    <div className={`space-y-4 ${disabled ? "opacity-60" : ""}`}>
      {!disabled && (
        <div className="flex items-center justify-end space-x-2">
          <button
            onClick={loadSampleTargets}
            disabled={disabled}
            className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-md text-xs font-medium transition-colors flex items-center space-x-1.5 border border-gray-700"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Load Samples</span>
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-md text-xs font-medium transition-colors flex items-center space-x-1.5 border border-gray-700"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload File</span>
          </button>
          <button
            onClick={toggleAddMode}
            disabled={disabled}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center space-x-1.5 border ${
              isAddMode
                ? "bg-green-600 hover:bg-green-700 text-white border-green-500"
                : "bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border-gray-700"
            }`}
          >
            <Map className="w-3.5 h-3.5" />
            <span>{isAddMode ? "Exit Map Mode" : "Add via Map"}</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".kml,.kmz,.json,.csv,.txt"
            onChange={handleFileUpload}
            className="hidden"
          />
        </div>
      )}

      {/* Randomize Colors Button - Testing Only */}
      {!disabled && targets.length > 0 && (
        <button
          onClick={randomizeColors}
          className="w-full px-3 py-1.5 bg-purple-700/50 hover:bg-purple-600/50 text-purple-200 rounded-md text-xs font-medium transition-colors flex items-center justify-center space-x-2 border border-purple-600/50"
          title="Randomize all target colors (testing)"
        >
          <Shuffle className="w-3.5 h-3.5" />
          <span>🎨 Randomize Colors (Testing)</span>
        </button>
      )}

      {/* Map Add Mode Helper */}
      {isAddMode && (
        <div className="glass-panel rounded-lg p-2 text-xs text-blue-300 flex items-center space-x-2">
          <MapPin className="w-3 h-3 flex-shrink-0" />
          <span>
            Click on the map to place a target. Press{" "}
            <kbd className="px-1 py-0.5 bg-white/10 rounded">Esc</kbd> to exit.
          </span>
        </div>
      )}

      {/* Upload Status */}
      {uploadStatus.type && (
        <div
          className={`flex items-start space-x-2 p-2 rounded-lg text-xs ${
            uploadStatus.type === "success"
              ? "bg-green-900/30 text-green-400"
              : "bg-red-900/30 text-red-400"
          }`}
        >
          {uploadStatus.type === "success" ? (
            <CheckCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
          )}
          <span>{uploadStatus.message}</span>
        </div>
      )}

      {/* Empty State - Show when no targets */}
      {targets.length === 0 && (
        <div className="text-center py-8 text-gray-500 glass-panel rounded-lg">
          <Target className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm font-medium text-gray-400">
            No targets added yet
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Add targets manually, via map, or upload a file
          </p>
        </div>
      )}

      {/* Existing Targets */}
      {targets.length > 0 && (
        <div className="space-y-2 overflow-visible">
          {targets.map((target, index) => (
            <div
              key={index}
              className="glass-panel rounded-lg p-3 overflow-visible relative"
              style={{ zIndex: targets.length - index }}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2 mb-1">
                    <Target
                      className="w-3 h-3 flex-shrink-0"
                      style={{ color: target.color || "#EF4444" }}
                    />
                    <span className="text-sm font-medium text-white">
                      {target.name}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400 mb-1">
                    <MapPin className="w-3 h-3 inline mr-1" />
                    {target.latitude.toFixed(4)}°, {target.longitude.toFixed(4)}
                    °
                  </div>
                  {target.description && (
                    <div className="text-xs text-gray-500">
                      {target.description}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  {disabled ? (
                    <>
                      {/* Read-only: Color indicator */}
                      <div
                        className="w-4 h-4 rounded-full border border-gray-600 shadow-sm flex-shrink-0"
                        style={{ backgroundColor: target.color || "#EF4444" }}
                        title={target.color || "Red"}
                      />
                      {/* Read-only: Priority indicator */}
                      <span
                        className="text-[10px] text-gray-400"
                        title="Priority"
                      >
                        P{target.priority || 1}
                      </span>
                    </>
                  ) : (
                    <>
                      {/* Color Picker - Compact color dots */}
                      <div className="relative group">
                        <button
                          className="w-5 h-5 rounded-full border-2 border-gray-600 hover:border-gray-400 transition-colors shadow-sm"
                          style={{ backgroundColor: target.color || "#EF4444" }}
                          title="Change color"
                        />
                        {/* Dropdown on hover - using pt-1 padding-top to bridge the gap */}
                        <div
                          className="absolute right-0 top-5 pt-2 hidden group-hover:block"
                          style={{ zIndex: 9999 }}
                        >
                          <div className="flex flex-wrap gap-1 p-2 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl w-[100px]">
                            {TARGET_COLORS.map((c) => (
                              <button
                                key={c.value}
                                onClick={() => {
                                  const updated = [...targets];
                                  updated[index] = {
                                    ...target,
                                    color: c.value,
                                  };
                                  onChange(updated);
                                }}
                                className={`w-5 h-5 rounded-full border-2 transition-all hover:scale-110 ${
                                  target.color === c.value
                                    ? "border-white"
                                    : "border-transparent hover:border-gray-500"
                                }`}
                                style={{ backgroundColor: c.value }}
                                title={c.label}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                      {/* Priority */}
                      <select
                        value={target.priority || 1}
                        onChange={(e) => {
                          const updated = [...targets];
                          updated[index] = {
                            ...target,
                            priority: parseInt(e.target.value),
                          };
                          onChange(updated);
                        }}
                        className="w-10 px-1 py-0.5 bg-gray-800 border border-gray-700 rounded text-[10px] text-white focus:border-blue-500 focus:outline-none"
                        title="Priority"
                      >
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                        <option value="5">5</option>
                      </select>
                      {/* Delete */}
                      <button
                        onClick={() => removeTarget(index)}
                        className="p-1 text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded transition-colors"
                        title="Remove target"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add New Target - Hidden when mission is analyzed */}
      {!disabled && (
        <div className="glass-panel rounded-lg p-3">
          <h4 className="text-xs font-medium text-gray-400 mb-3">
            Add New Target
          </h4>
          <div className="space-y-3">
            <div>
              <input
                type="text"
                value={newTarget.name}
                onChange={(e) =>
                  setNewTarget({ ...newTarget, name: e.target.value })
                }
                placeholder="Target name (e.g., Ground Station Alpha)"
                className="input-field w-full text-sm"
              />
            </div>

            {/* Flexible Coordinate Input */}
            <div>
              <label className="text-xs text-gray-500 mb-1 block">
                Coordinates (flexible format)
              </label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={coordinateInput}
                  onChange={(e) => setCoordinateInput(e.target.value)}
                  placeholder="e.g., 23.7 N, 45.2 W or -15.78, -47.93"
                  className="input-field flex-1 text-sm"
                  onBlur={parseCoordinates}
                />
                <button
                  onClick={parseCoordinates}
                  className="btn-secondary px-3 py-1 text-xs"
                >
                  Parse
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Supports: decimal degrees, DMS, hemisphere notation
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">
                  Latitude
                </label>
                <input
                  type="number"
                  value={newTarget.latitude || ""}
                  onChange={(e) =>
                    setNewTarget({
                      ...newTarget,
                      latitude: parseFloat(e.target.value) || 0,
                    })
                  }
                  placeholder="-90 to 90"
                  step="0.0001"
                  min="-90"
                  max="90"
                  className="input-field w-full text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">
                  Longitude
                </label>
                <input
                  type="number"
                  value={newTarget.longitude || ""}
                  onChange={(e) =>
                    setNewTarget({
                      ...newTarget,
                      longitude: parseFloat(e.target.value) || 0,
                    })
                  }
                  placeholder="-180 to 180"
                  step="0.0001"
                  min="-180"
                  max="180"
                  className="input-field w-full text-sm"
                />
              </div>
            </div>

            <div>
              <input
                type="text"
                value={newTarget.description}
                onChange={(e) =>
                  setNewTarget({ ...newTarget, description: e.target.value })
                }
                placeholder="Description (optional)"
                className="input-field w-full text-sm"
              />
            </div>

            <button
              onClick={addTarget}
              disabled={isUploading}
              className="btn-primary w-full text-sm disabled:opacity-50"
            >
              {isUploading ? (
                <>
                  <div className="loading-spinner w-4 h-4" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" />
                  <span>Add Target</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Target Details Sheet for map-click targets */}
      <TargetDetailsSheet onSave={handleMapTargetSave} />
    </div>
  );
};

export default TargetInput;
