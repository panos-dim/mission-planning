import React, { useState, useEffect } from "react";
import { Edit2, Save, RefreshCw, AlertCircle } from "lucide-react";
import type { MissionSettingsConfig } from "./types";

interface SettingsTabProps {
  onConfigUpdate?: () => void;
}

const SettingsTab: React.FC<SettingsTabProps> = ({ onConfigUpdate }) => {
  const [missionSettings, setMissionSettings] =
    useState<MissionSettingsConfig | null>(null);
  const [isEditingSettings, setIsEditingSettings] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  useEffect(() => {
    fetchMissionSettings();
  }, []);

  const fetchMissionSettings = async () => {
    try {
      const response = await fetch("/api/v1/mission-settings");
      const data = await response.json();
      if (data.success) {
        setMissionSettings(data.settings);
      }
    } catch (error) {
      console.error("Error fetching mission settings:", error);
    }
  };

  const reloadMissionSettings = async () => {
    try {
      const response = await fetch("/api/v1/mission-settings/reload", {
        method: "POST",
      });
      if (response.ok) {
        await fetchMissionSettings();
      } else {
        console.error("Failed to reload mission settings");
      }
    } catch (error) {
      console.error("Error reloading mission settings:", error);
    }
  };

  const updateMissionSetting = async (
    section: string,
    key: string,
    value: string | number | boolean | Record<string, unknown>,
  ) => {
    if (!isEditingSettings) return;
    setHasUnsavedChanges(true);
    setMissionSettings((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        [section]: {
          ...(prev[section] as Record<string, unknown>),
          [key]: value,
        },
      };
    });
    try {
      const response = await fetch(
        `/api/v1/mission-settings/${section}/${key}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ value }),
        },
      );
      if (!response.ok) {
        console.error("Failed to update mission setting");
      }
    } catch (error) {
      console.error("Error updating mission setting:", error);
    }
  };

  return (
    <div className="space-y-4">
      {missionSettings && (
        <div className="space-y-4">
          {/* Edit/Save Controls */}
          <div className="bg-gray-800 p-4 rounded-lg flex justify-between items-center">
            <h3 className="text-white font-semibold">Mission Configuration</h3>
            <div className="flex space-x-2">
              {!isEditingSettings ? (
                <>
                  <button
                    onClick={() => setIsEditingSettings(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center space-x-2"
                  >
                    <Edit2 className="w-4 h-4" />
                    <span>Edit Settings</span>
                  </button>
                  <button
                    onClick={reloadMissionSettings}
                    className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 flex items-center space-x-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    <span>Reload</span>
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={async () => {
                      try {
                        const response = await fetch(
                          "/api/v1/config/mission-settings",
                          {
                            method: "POST",
                            headers: {
                              "Content-Type": "application/json",
                            },
                            body: JSON.stringify(missionSettings),
                          },
                        );
                        if (response.ok) {
                          setIsEditingSettings(false);
                          setHasUnsavedChanges(false);
                          if (onConfigUpdate) onConfigUpdate();
                        }
                      } catch (error) {
                        console.error(
                          "Failed to save mission settings:",
                          error,
                        );
                      }
                    }}
                    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center space-x-2"
                  >
                    <Save className="w-4 h-4" />
                    <span>Save Changes</span>
                  </button>
                  <button
                    onClick={() => {
                      setIsEditingSettings(false);
                      setHasUnsavedChanges(false);
                      fetchMissionSettings();
                    }}
                    className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                  >
                    Cancel
                  </button>
                </>
              )}
            </div>
          </div>
          {hasUnsavedChanges && (
            <div className="bg-yellow-900 text-yellow-200 p-3 rounded-lg flex items-center space-x-2">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">You have unsaved changes</span>
            </div>
          )}
          {/* Pass Durations */}
          <div className="bg-gray-800 p-4 rounded-lg">
            <h3 className="text-white font-semibold mb-4">
              Pass Duration Settings
            </h3>
            <div className="space-y-4">
              {Object.entries(missionSettings.pass_duration || {})
                .filter(([missionType]) => missionType !== "tracking")
                .map(([missionType, durations]) => (
                  <div
                    key={missionType}
                    className="border-l-4 border-blue-600 pl-4"
                  >
                    <h4 className="text-white capitalize mb-3">
                      {missionType}
                    </h4>
                    <div className="grid grid-cols-3 gap-3">
                      {Object.entries(durations as Record<string, number>).map(
                        ([durationType, value]) => (
                          <div key={durationType} className="space-y-2">
                            <label className="text-gray-300 text-sm capitalize">
                              {durationType.replace(/_/g, " ")}
                            </label>
                            <input
                              type="number"
                              value={String(value || "")}
                              onChange={(e) => {
                                const newValue = parseInt(e.target.value);
                                const updatedDurations = {
                                  ...(durations as Record<string, number>),
                                  [durationType]: newValue,
                                };
                                updateMissionSetting(
                                  "pass_duration",
                                  missionType,
                                  updatedDurations,
                                );
                              }}
                              disabled={!isEditingSettings}
                              className={`w-full bg-gray-700 text-white px-2 py-1 rounded text-sm ${
                                !isEditingSettings
                                  ? "opacity-60 cursor-not-allowed"
                                  : ""
                              }`}
                            />
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                ))}
            </div>
          </div>

          {/* Elevation Constraints */}
          <div className="bg-gray-800 p-4 rounded-lg">
            <h3 className="text-white font-semibold mb-4">
              Elevation Constraints
            </h3>
            <div className="space-y-4">
              {Object.entries(missionSettings.elevation_constraints || {})
                .filter(([missionType]) => missionType !== "tracking")
                .map(([missionType, constraints]) => (
                  <div
                    key={missionType}
                    className="border-l-4 border-green-600 pl-4"
                  >
                    <h4 className="text-white capitalize mb-3">
                      {missionType}
                    </h4>
                    <div className="grid grid-cols-3 gap-3">
                      {Object.entries(
                        constraints as Record<string, number>,
                      ).map(([constraintType, value]) => (
                        <div key={constraintType} className="space-y-2">
                          <label className="text-gray-300 text-sm capitalize">
                            {constraintType.replace(/_/g, " ")} (°)
                          </label>
                          <input
                            type="number"
                            value={String(value || "")}
                            onChange={(e) => {
                              const newValue = parseFloat(e.target.value);
                              const updatedConstraints = {
                                ...(constraints as Record<string, number>),
                                [constraintType]: newValue,
                              };
                              updateMissionSetting(
                                "elevation_constraints",
                                missionType,
                                updatedConstraints,
                              );
                            }}
                            disabled={!isEditingSettings}
                            className={`w-full bg-gray-700 text-white px-2 py-1 rounded text-sm ${
                              !isEditingSettings
                                ? "opacity-60 cursor-not-allowed"
                                : ""
                            }`}
                            step="0.1"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </div>

          {/* Planning Constraints */}
          <div className="bg-gray-800 p-4 rounded-lg">
            <h3 className="text-white font-semibold mb-4">
              Planning Constraints
            </h3>
            <div className="space-y-4">
              {Object.entries(missionSettings.planning_constraints || {}).map(
                ([constraintType, value]) => (
                  <div
                    key={constraintType}
                    className="flex items-center space-x-4"
                  >
                    <label className="text-gray-300 flex-1 capitalize">
                      {constraintType.replace(/_/g, " ")}
                    </label>
                    {constraintType === "weather" &&
                    typeof value === "object" ? (
                      <div className="flex space-x-4">
                        {Object.entries(value as Record<string, number>).map(
                          ([weatherKey, weatherValue]) => (
                            <div
                              key={weatherKey}
                              className="flex items-center space-x-2"
                            >
                              <label className="text-gray-400 text-sm capitalize">
                                {weatherKey.replace(/_/g, " ")}
                              </label>
                              <input
                                type="number"
                                value={String(weatherValue || "")}
                                onChange={(e) => {
                                  const updatedWeather = {
                                    ...(value as Record<string, number>),
                                    [weatherKey]: Number(e.target.value),
                                  };
                                  updateMissionSetting(
                                    "planning_constraints",
                                    constraintType,
                                    updatedWeather,
                                  );
                                }}
                                disabled={!isEditingSettings}
                                className={`bg-gray-700 text-white px-3 py-1 rounded text-sm w-24 ${
                                  !isEditingSettings
                                    ? "opacity-60 cursor-not-allowed"
                                    : ""
                                }`}
                              />
                            </div>
                          ),
                        )}
                      </div>
                    ) : (
                      <input
                        type={
                          typeof value === "boolean"
                            ? "checkbox"
                            : typeof value === "number"
                              ? "number"
                              : "text"
                        }
                        checked={
                          typeof value === "boolean"
                            ? (value as boolean)
                            : undefined
                        }
                        value={
                          typeof value === "number" || typeof value === "string"
                            ? String(value)
                            : undefined
                        }
                        onChange={(e) => {
                          const newValue =
                            typeof value === "boolean"
                              ? e.target.checked
                              : typeof value === "number"
                                ? Number(e.target.value)
                                : e.target.value;
                          updateMissionSetting(
                            "planning_constraints",
                            constraintType,
                            newValue,
                          );
                        }}
                        disabled={!isEditingSettings}
                        className={`${
                          typeof value === "boolean"
                            ? "h-4 w-4 rounded text-blue-600"
                            : "bg-gray-700 text-white px-3 py-1 rounded text-sm w-24"
                        } ${
                          !isEditingSettings
                            ? "opacity-60 cursor-not-allowed"
                            : ""
                        }`}
                      />
                    )}
                  </div>
                ),
              )}
            </div>
          </div>

          {/* Output Settings */}
          <div className="bg-gray-800 p-4 rounded-lg">
            <h3 className="text-white font-semibold mb-4">Output Settings</h3>
            <div className="space-y-4">
              {Object.entries(missionSettings.output_settings || {}).map(
                ([key, value]) => (
                  <div key={key} className="space-y-2">
                    <label className="text-gray-300 text-sm capitalize font-semibold">
                      {key.replace(/_/g, " ")}
                    </label>
                    {Array.isArray(value) ? (
                      <div className="bg-gray-700 p-3 rounded">
                        <div className="text-gray-300 text-sm">
                          {(value as string[]).join(", ")}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Array values (read-only)
                        </div>
                      </div>
                    ) : typeof value === "object" && value !== null ? (
                      <div className="bg-gray-700 p-3 rounded space-y-2">
                        {Object.entries(
                          value as Record<string, string | number | boolean>,
                        ).map(([subKey, subValue]) => (
                          <div
                            key={subKey}
                            className="flex items-center justify-between"
                          >
                            <span className="text-gray-300 text-sm capitalize">
                              {subKey.replace(/_/g, " ")}:
                            </span>
                            {typeof subValue === "boolean" ? (
                              <select
                                value={subValue.toString()}
                                onChange={(e) => {
                                  const updatedObj = {
                                    ...(value as Record<
                                      string,
                                      string | number | boolean
                                    >),
                                    [subKey]: e.target.value === "true",
                                  };
                                  updateMissionSetting(
                                    "output_settings",
                                    key,
                                    updatedObj,
                                  );
                                }}
                                disabled={!isEditingSettings}
                                className={`w-24 bg-gray-600 text-white px-2 py-1 rounded text-sm ${
                                  !isEditingSettings
                                    ? "opacity-60 cursor-not-allowed"
                                    : ""
                                }`}
                              >
                                <option value="true">Yes</option>
                                <option value="false">No</option>
                              </select>
                            ) : (
                              <input
                                type="text"
                                value={String(subValue || "")}
                                onChange={(e) => {
                                  const updatedObj = {
                                    ...(value as Record<
                                      string,
                                      string | number | boolean
                                    >),
                                    [subKey]: e.target.value,
                                  };
                                  updateMissionSetting(
                                    "output_settings",
                                    key,
                                    updatedObj,
                                  );
                                }}
                                disabled={!isEditingSettings}
                                className={`w-32 bg-gray-600 text-white px-2 py-1 rounded text-sm ${
                                  !isEditingSettings
                                    ? "opacity-60 cursor-not-allowed"
                                    : ""
                                }`}
                              />
                            )}
                          </div>
                        ))}
                      </div>
                    ) : typeof value === "boolean" ? (
                      <select
                        value={value.toString()}
                        onChange={(e) =>
                          updateMissionSetting(
                            "output_settings",
                            key,
                            e.target.value === "true",
                          )
                        }
                        disabled={!isEditingSettings}
                        className={`w-full bg-gray-700 text-white px-3 py-2 rounded ${
                          !isEditingSettings
                            ? "opacity-60 cursor-not-allowed"
                            : ""
                        }`}
                      >
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={String(value || "")}
                        onChange={(e) =>
                          updateMissionSetting(
                            "output_settings",
                            key,
                            e.target.value,
                          )
                        }
                        disabled={!isEditingSettings}
                        className={`w-full bg-gray-700 text-white px-3 py-2 rounded ${
                          !isEditingSettings
                            ? "opacity-60 cursor-not-allowed"
                            : ""
                        }`}
                      />
                    )}
                  </div>
                ),
              )}
            </div>
          </div>

          {/* Defaults Section */}
          <div className="bg-gray-800 p-4 rounded-lg">
            <h3 className="text-white font-semibold mb-4">Default Settings</h3>
            <div className="grid grid-cols-2 gap-4">
              {Object.entries(missionSettings.defaults || {}).map(
                ([key, value]) => (
                  <div key={key} className="space-y-2">
                    <label className="text-gray-300 text-sm capitalize">
                      {key.replace(/_/g, " ")}
                    </label>
                    {typeof value === "boolean" ? (
                      <select
                        value={value.toString()}
                        onChange={(e) =>
                          updateMissionSetting(
                            "defaults",
                            key,
                            e.target.value === "true",
                          )
                        }
                        disabled={!isEditingSettings}
                        className={`w-full bg-gray-700 text-white px-3 py-2 rounded ${
                          !isEditingSettings
                            ? "opacity-60 cursor-not-allowed"
                            : ""
                        }`}
                      >
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                      </select>
                    ) : typeof value === "number" ? (
                      <input
                        type="number"
                        value={String(value || "")}
                        onChange={(e) =>
                          updateMissionSetting(
                            "defaults",
                            key,
                            parseFloat(e.target.value),
                          )
                        }
                        disabled={!isEditingSettings}
                        className={`w-full bg-gray-700 text-white px-3 py-2 rounded ${
                          !isEditingSettings
                            ? "opacity-60 cursor-not-allowed"
                            : ""
                        }`}
                        step="0.1"
                      />
                    ) : (
                      <input
                        type="text"
                        value={String(value || "")}
                        onChange={(e) =>
                          updateMissionSetting("defaults", key, e.target.value)
                        }
                        disabled={!isEditingSettings}
                        className={`w-full bg-gray-700 text-white px-3 py-2 rounded ${
                          !isEditingSettings
                            ? "opacity-60 cursor-not-allowed"
                            : ""
                        }`}
                      />
                    )}
                  </div>
                ),
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettingsTab;
