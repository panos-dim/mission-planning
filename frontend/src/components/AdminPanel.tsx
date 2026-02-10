import React, { useState, useEffect } from "react";
import {
  X,
  Plus,
  Edit2,
  Trash2,
  Save,
  RefreshCw,
  Download,
  Satellite,
  Globe,
  Settings,
  Upload,
  AlertCircle,
  Radio,
  History,
  RotateCcw,
  FlaskConical,
  CheckCircle,
  XCircle,
  Play,
} from "lucide-react";
import {
  listWorkflowScenarios,
  runWorkflowValidation,
  WorkflowScenario,
  WorkflowValidationReport,
} from "../api/workflowValidation";
import * as yaml from "js-yaml";
import debug from "../utils/debug";

// SAR Mode interfaces
interface SARModeIncidence {
  recommended_min: number;
  recommended_max: number;
  absolute_min: number;
  absolute_max: number;
}

interface SARModeScene {
  width_km: number;
  length_km: number;
  max_length_km?: number;
}

interface SARModeCollection {
  duration_s?: number;
  azimuth_resolution_m: number;
  range_resolution_m: number;
}

interface SARModeQuality {
  optimal_incidence_deg: number;
  quality_model: string;
}

interface SARMode {
  display_name: string;
  description: string;
  incidence_angle: SARModeIncidence;
  scene: SARModeScene;
  collection: SARModeCollection;
  quality: SARModeQuality;
}

interface ConfigSnapshot {
  id: string;
  timestamp: string;
  description: string | null;
  config_hash: string;
  files: string[];
}

interface GroundStation {
  name: string;
  latitude: number;
  longitude: number;
  altitude_km: number;
  elevation_mask: number;
  active: boolean;
  description: string;
  capabilities: string[];
}

// Form state allows string values for numeric fields during editing
interface EditableGroundStation {
  name: string;
  latitude: number | string;
  longitude: number | string;
  altitude_km: number | string;
  elevation_mask: number | string;
  active: boolean;
  description: string;
  capabilities: string[];
}

interface MissionSettings {
  default_elevation_mask: number;
  min_duration_seconds: number;
}

interface Config {
  ground_stations: GroundStation[];
  defaults: {
    elevation_mask: number;
    altitude_km: number;
    active: boolean;
    capabilities: string[];
  };
  mission_settings: {
    imaging?: MissionSettings;
    communication?: MissionSettings;
  };
}

interface TLESource {
  id: string;
  name: string;
  description?: string;
  url?: string;
}

interface TLESearchResult {
  name: string;
  line1: string;
  line2: string;
  norad_id?: string;
}

interface SatelliteConfig {
  id: string;
  name: string;
  tle_line1?: string;
  tle_line2?: string;
  line1?: string;
  line2?: string;
  imaging_type?: string;
  max_spacecraft_roll_deg?: number;
  sensor_fov_half_angle_deg?: number;
  satellite_agility?: number;
  sar_mode?: string;
  description?: string;
  active?: boolean;
  tle_updated_at?: string;
}

interface MissionSettingsConfig {
  defaults?: Record<string, unknown>;
  elevation_constraints?: Record<string, unknown>;
  mission_planning?: Record<string, unknown>;
  [key: string]: unknown;
}

interface AdminPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onConfigUpdate?: () => void;
}

const AdminPanel: React.FC<AdminPanelProps> = ({
  isOpen,
  onClose,
  onConfigUpdate,
}) => {
  const [activeTab, setActiveTab] = useState<
    | "ground-stations"
    | "satellites"
    | "sar-modes"
    | "settings"
    | "snapshots"
    | "validation"
  >("ground-stations");
  // Validation state (PR-VALIDATION-01)
  const [validationScenarios, setValidationScenarios] = useState<
    WorkflowScenario[]
  >([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [isRunningValidation, setIsRunningValidation] = useState(false);
  const [validationReport, setValidationReport] =
    useState<WorkflowValidationReport | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [editingStation, setEditingStation] =
    useState<EditableGroundStation | null>(null);
  const [isAddingStation, setIsAddingStation] = useState(false);
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<TLESearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    station: GroundStation | null;
    isOpen: boolean;
  }>({ station: null, isOpen: false });
  const [tleSources, setTleSources] = useState<TLESource[]>([]);
  const [satellites, setSatellites] = useState<SatelliteConfig[]>([]);
  const [editingSatellite, setEditingSatellite] =
    useState<SatelliteConfig | null>(null);
  const [isAddingSatellite, setIsAddingSatellite] = useState(false);
  const [missionSettings, setMissionSettings] =
    useState<MissionSettingsConfig | null>(null);
  const [isEditingSettings, setIsEditingSettings] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [refreshingSatelliteId, setRefreshingSatelliteId] = useState<
    string | null
  >(null);
  // SAR Modes state
  const [sarModes, setSarModes] = useState<Record<string, SARMode>>({});
  const [editingSarMode, setEditingSarMode] = useState<string | null>(null);
  const [editingSarModeData, setEditingSarModeData] = useState<SARMode | null>(
    null,
  );
  const [isSavingSarMode, setIsSavingSarMode] = useState(false);
  // Config snapshots state
  const [snapshots, setSnapshots] = useState<ConfigSnapshot[]>([]);
  const [currentConfigHash, setCurrentConfigHash] = useState<string>("");
  const [snapshotDescription, setSnapshotDescription] = useState("");
  const [isCreatingSnapshot, setIsCreatingSnapshot] = useState(false);
  const [isRestoringSnapshot, setIsRestoringSnapshot] = useState<string | null>(
    null,
  );
  // Multi-satellite selection for constellation support
  const [selectedSatelliteIds, setSelectedSatelliteIds] = useState<string[]>(
    () => {
      // Load selected satellites from localStorage on mount
      const stored = localStorage.getItem("selectedSatelliteIds");
      return stored ? JSON.parse(stored) : [];
    },
  );

  useEffect(() => {
    if (isOpen) {
      fetchConfig();
      fetchTleSources();
      fetchSatellites();
      fetchMissionSettings();
      fetchSarModes();
      fetchSnapshots();
      fetchValidationScenarios();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const fetchValidationScenarios = async () => {
    try {
      const scenarios = await listWorkflowScenarios();
      setValidationScenarios(scenarios);
      if (scenarios.length > 0 && !selectedScenarioId) {
        setSelectedScenarioId(scenarios[0].id);
      }
    } catch (error) {
      console.error("Error fetching validation scenarios:", error);
    }
  };

  const handleRunValidation = async () => {
    if (!selectedScenarioId) return;

    setIsRunningValidation(true);
    setValidationError(null);
    setValidationReport(null);

    try {
      const report = await runWorkflowValidation({
        scenario_id: selectedScenarioId,
        dry_run: true,
      });
      setValidationReport(report);
    } catch (error) {
      setValidationError(
        error instanceof Error ? error.message : "Validation failed",
      );
    } finally {
      setIsRunningValidation(false);
    }
  };

  const fetchConfig = async () => {
    try {
      const response = await fetch("/api/config/full");
      const data = await response.json();
      if (data.success) {
        setConfig(data.config);
      }
    } catch (error) {
      console.error("Error fetching config:", error);
    }
  };

  const fetchTleSources = async () => {
    try {
      const response = await fetch("/api/tle/sources");
      const data = await response.json();
      if (data.sources && data.sources.length > 0) {
        setTleSources(data.sources);
        setSelectedSource(data.sources[0].id);
      }
    } catch (error) {
      console.error("Error fetching TLE sources:", error);
    }
  };

  const fetchSatellites = async () => {
    try {
      const response = await fetch("/api/satellites");
      const data = await response.json();
      if (data.success) {
        const fetchedSatellites = data.satellites || [];
        setSatellites(fetchedSatellites);

        // If no satellites are selected yet, auto-select the first active one
        if (selectedSatelliteIds.length === 0 && fetchedSatellites.length > 0) {
          const firstActive = fetchedSatellites.find(
            (s: SatelliteConfig) => s.active,
          );
          if (firstActive) {
            handleToggleSatellite(firstActive);
          }
        } else if (selectedSatelliteIds.length > 0) {
          // Sync localStorage with current satellite data for selected IDs
          // This ensures MissionControls gets the full TLE data
          const selectedSats = fetchedSatellites
            .filter((s: SatelliteConfig) => selectedSatelliteIds.includes(s.id))
            .map((s: SatelliteConfig) => ({
              name: s.name,
              line1: s.line1,
              line2: s.line2,
              sensor_fov_half_angle_deg: s.sensor_fov_half_angle_deg,
              imaging_type: s.imaging_type,
            }));
          localStorage.setItem(
            "selectedSatellites",
            JSON.stringify(selectedSats),
          );
          debug.info(
            `Synced constellation to localStorage: ${selectedSats.length} satellites`,
          );
        }
      }
    } catch (error) {
      console.error("Error fetching satellites:", error);
    }
  };

  const fetchMissionSettings = async () => {
    try {
      const response = await fetch("/api/mission-settings");
      const data = await response.json();
      if (data.success) {
        setMissionSettings(data.settings);
      }
    } catch (error) {
      console.error("Error fetching mission settings:", error);
    }
  };

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

  const saveSarMode = async (modeName: string, modeData: SARMode) => {
    setIsSavingSarMode(true);
    try {
      const response = await fetch(`/api/v1/config/sar-modes/${modeName}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(modeData),
      });
      const data = await response.json();
      if (data.success) {
        await fetchSarModes();
        await fetchSnapshots();
        setEditingSarMode(null);
        setEditingSarModeData(null);
        if (onConfigUpdate) onConfigUpdate();
      } else {
        console.error("Failed to save SAR mode:", data);
      }
    } catch (error) {
      console.error("Error saving SAR mode:", error);
    } finally {
      setIsSavingSarMode(false);
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
        {
          method: "POST",
        },
      );
      const data = await response.json();
      if (data.success) {
        await fetchSnapshots();
        await fetchSarModes();
        await fetchMissionSettings();
        await fetchSatellites();
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
      const response = await fetch(`/api/mission-settings/${section}/${key}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ value }),
      });

      if (response.ok) {
        // Update local state
      } else {
        console.error("Failed to update mission setting");
      }
    } catch (error) {
      console.error("Error updating mission setting:", error);
    }
  };

  const reloadMissionSettings = async () => {
    try {
      const response = await fetch("/api/mission-settings/reload", {
        method: "POST",
      });

      if (response.ok) {
        // Refresh mission settings from backend
        await fetchMissionSettings();
      } else {
        console.error("Failed to reload mission settings");
      }
    } catch (error) {
      console.error("Error reloading mission settings:", error);
    }
  };

  const saveGroundStation = async (
    station: EditableGroundStation,
    isNew: boolean = false,
  ) => {
    try {
      // Convert form values to proper numeric types for API
      const latValue = station.latitude === "" ? 0 : Number(station.latitude);
      const lonValue = station.longitude === "" ? 0 : Number(station.longitude);
      const altValue =
        station.altitude_km === "" ? 0 : Number(station.altitude_km);
      const elevValue =
        station.elevation_mask === "" ? 10 : Number(station.elevation_mask);

      const stationData: GroundStation = {
        name: station.name,
        latitude: isNaN(latValue) ? 0 : latValue,
        longitude: isNaN(lonValue) ? 0 : lonValue,
        altitude_km: isNaN(altValue) ? 0 : altValue,
        elevation_mask: isNaN(elevValue) ? 10 : elevValue,
        active: station.active,
        description: station.description,
        capabilities: station.capabilities,
      };

      const url = isNew
        ? "/api/config/ground-stations"
        : `/api/config/ground-stations/${encodeURIComponent(station.name)}`;

      const response = await fetch(url, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(stationData),
      });

      if (response.ok) {
        await fetchConfig();
        setEditingStation(null);
        setIsAddingStation(false);
        if (onConfigUpdate) onConfigUpdate();
      }
    } catch (error) {
      console.error("Error saving ground station:", error);
    }
  };

  const handleDeleteStation = (station: GroundStation) => {
    setDeleteConfirmation({ station, isOpen: true });
  };

  const confirmDelete = async () => {
    if (!deleteConfirmation.station) return;

    try {
      const response = await fetch(
        `/api/config/ground-stations/${encodeURIComponent(
          deleteConfirmation.station.name,
        )}`,
        { method: "DELETE" },
      );

      if (response.ok) {
        debug.info(
          `Deleted ground station: ${deleteConfirmation.station?.name}`,
        );
        await fetchConfig();
        if (onConfigUpdate) onConfigUpdate();
      }
    } catch (error) {
      console.error("Error deleting ground station:", error);
    }

    setDeleteConfirmation({ station: null, isOpen: false });
  };

  const cancelDelete = () => {
    setDeleteConfirmation({ station: null, isOpen: false });
  };

  const reloadConfig = async () => {
    try {
      const response = await fetch("/api/config/reload", { method: "POST" });
      if (response.ok) {
        await fetchConfig();
        if (onConfigUpdate) onConfigUpdate();
      }
    } catch (error) {
      console.error("Error reloading config:", error);
    }
  };

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/config/upload", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        await fetchConfig();
        if (onConfigUpdate) onConfigUpdate();
      } else {
        const error = await response.json();
        alert(`Upload failed: ${error.detail}`);
      }
    } catch (error) {
      console.error("Error uploading config:", error);
      alert("Failed to upload configuration file");
    }
  };

  const downloadConfig = () => {
    if (!config) return;

    const dataStr = JSON.stringify(config, null, 2);
    const dataUri =
      "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);

    const exportFileDefaultName = "ground_stations_config.json";

    const linkElement = document.createElement("a");
    linkElement.setAttribute("href", dataUri);
    linkElement.setAttribute("download", exportFileDefaultName);
    linkElement.click();
  };

  const downloadYaml = () => {
    const yamlConfig = {
      ground_stations: config?.ground_stations || [],
      defaults: {
        elevation_mask: 10,
        altitude_km: 0,
        active: true,
        capabilities: ["communication"],
      },
      mission_settings: {
        imaging: {
          default_elevation_mask: 45,
          min_duration_seconds: 30,
        },
        communication: {
          default_elevation_mask: 10,
          min_duration_seconds: 60,
        },
      },
    };
    const yamlContent = yaml.dump(yamlConfig);
    const blob = new Blob([yamlContent], { type: "text/yaml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ground_stations.yaml";
    a.click();
    URL.revokeObjectURL(url);
  };

  const searchSatellites = async () => {
    if (!searchTerm.trim()) return;

    setIsSearching(true);
    try {
      const response = await fetch("/api/tle/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchTerm,
          source: selectedSource,
        }),
      });

      const data = await response.json();
      setSearchResults(data.satellites || []);
    } catch (error) {
      console.error("Error searching satellites:", error);
      setSearchResults([]);
    }
    setIsSearching(false);
  };

  const selectSatellite = async (satellite: TLESearchResult) => {
    // Add satellite to managed list with default parameters via API
    try {
      const response = await fetch("/api/satellites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: satellite.name,
          line1: satellite.line1,
          line2: satellite.line2,
          imaging_type: "optical",
          satellite_agility: 1.0,
          sar_mode: "stripmap",
          description: `Satellite: ${satellite.name}`,
          active: true,
        }),
      });

      if (response.ok) {
        await fetchSatellites(); // Refresh satellite list
        setSearchResults([]);
        setSearchTerm("");
      } else {
        console.error("Failed to add satellite");
      }
    } catch (error) {
      console.error("Error adding satellite:", error);
    }
  };

  const saveSatellite = async (satellite: SatelliteConfig) => {
    try {
      const response = await fetch(`/api/satellites/${satellite.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: satellite.name,
          line1: satellite.line1,
          line2: satellite.line2,
          imaging_type: satellite.imaging_type,
          sensor_fov_half_angle_deg: satellite.sensor_fov_half_angle_deg,
          satellite_agility: satellite.satellite_agility,
          sar_mode: satellite.sar_mode,
          description: satellite.description,
          active: satellite.active,
        }),
      });

      if (response.ok) {
        await fetchSatellites(); // Refresh satellite list
        setEditingSatellite(null);
      } else {
        console.error("Failed to update satellite");
      }
    } catch (error) {
      console.error("Error updating satellite:", error);
    }
  };

  const removeSatellite = async (satelliteId: string) => {
    try {
      const response = await fetch(`/api/satellites/${satelliteId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        // If the deleted satellite was selected, remove it from selection
        if (selectedSatelliteIds.includes(satelliteId)) {
          const newIds = selectedSatelliteIds.filter(
            (id) => id !== satelliteId,
          );
          setSelectedSatelliteIds(newIds);
          localStorage.setItem("selectedSatelliteIds", JSON.stringify(newIds));
          updateSelectedSatellitesStorage(newIds);
        }
        await fetchSatellites(); // Refresh satellite list
      } else {
        console.error("Failed to delete satellite");
      }
    } catch (error) {
      console.error("Error deleting satellite:", error);
    }
  };

  // Toggle satellite selection for constellation
  const handleToggleSatellite = (satellite: SatelliteConfig) => {
    const isSelected = selectedSatelliteIds.includes(satellite.id);
    let newIds: string[];

    if (isSelected) {
      // Remove from selection
      newIds = selectedSatelliteIds.filter((id) => id !== satellite.id);
    } else {
      // Add to selection
      newIds = [...selectedSatelliteIds, satellite.id];
    }

    setSelectedSatelliteIds(newIds);
    localStorage.setItem("selectedSatelliteIds", JSON.stringify(newIds));
    updateSelectedSatellitesStorage(newIds);

    debug.info(`Constellation updated: ${newIds.length} satellites selected`);
  };

  // Update localStorage with full satellite TLE data for selected satellites
  const updateSelectedSatellitesStorage = (ids: string[]) => {
    const selectedSats = satellites
      .filter((s) => ids.includes(s.id))
      .map((s) => ({
        name: s.name,
        line1: s.line1,
        line2: s.line2,
        sensor_fov_half_angle_deg: s.sensor_fov_half_angle_deg,
        imaging_type: s.imaging_type,
      }));
    localStorage.setItem("selectedSatellites", JSON.stringify(selectedSats));

    // Dispatch custom event to notify MissionControls
    window.dispatchEvent(
      new CustomEvent("constellationSelectionChanged", {
        detail: { satellites: selectedSats },
      }),
    );
  };

  const getTleAgeDays = (tleUpdatedAt: string): number => {
    if (!tleUpdatedAt) return 0;
    const tleDate = new Date(tleUpdatedAt);
    const currentDate = new Date();
    const diffTime = Math.abs(currentDate.getTime() - tleDate.getTime());
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const getTleAgeColor = (days: number): string => {
    if (days <= 1) {
      return "bg-green-900 text-green-200";
    } else if (days <= 3) {
      return "bg-green-800 text-green-200";
    } else if (days <= 5) {
      return "bg-yellow-900 text-yellow-200";
    } else if (days <= 7) {
      return "bg-orange-900 text-orange-200";
    } else if (days <= 14) {
      return "bg-orange-800 text-orange-200";
    } else {
      return "bg-red-900 text-red-200";
    }
  };

  const getTleAgeTooltip = (days: number): string => {
    if (days <= 1) {
      return "TLE data is fresh and highly accurate";
    } else if (days <= 3) {
      return "TLE data is recent and accurate";
    } else if (days <= 5) {
      return "TLE data is acceptable but consider refreshing";
    } else if (days <= 7) {
      return "TLE data is getting stale, refresh recommended";
    } else if (days <= 14) {
      return "TLE data is stale, refresh strongly recommended";
    } else {
      return "TLE data is expired, immediate refresh required";
    }
  };

  const refreshSatelliteTle = async (satelliteId: string) => {
    setRefreshingSatelliteId(satelliteId);

    debug.section("TLE REFRESH");
    debug.apiRequest(`POST /api/satellites/${satelliteId}/refresh-tle`, {
      satelliteId,
    });

    try {
      const response = await fetch(
        `/api/satellites/${satelliteId}/refresh-tle`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        },
      );

      if (response.ok) {
        const data = await response.json();
        debug.apiResponse(
          `POST /api/satellites/${satelliteId}/refresh-tle`,
          data,
          {
            summary: `✅ TLE updated for ${data.satellite?.name}`,
          },
        );
        await fetchSatellites(); // Refresh satellite list
      } else {
        const errorData = await response.json().catch(() => ({}));
        debug.apiError(
          `POST /api/satellites/${satelliteId}/refresh-tle`,
          errorData,
        );
      }
    } catch (error) {
      debug.error("Failed to refresh TLE", error);
    } finally {
      setRefreshingSatelliteId(null);
    }
  };

  const handleAddStation = () => {
    setIsAddingStation(true);
    setEditingStation({
      name: "",
      latitude: "",
      longitude: "",
      altitude_km: "",
      elevation_mask: "",
      description: "",
      active: true,
      capabilities: ["communication"],
    });
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={(e) => {
        // Prevent closing on background click during delete
        e.stopPropagation();
      }}
    >
      <div
        className="bg-gray-900 rounded-lg w-full max-w-6xl h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center space-x-2">
            <Settings className="w-5 h-5 text-blue-400" />
            <h2 className="text-xl font-semibold text-white">Admin Panel</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex space-x-1 p-2 bg-gray-800 border-b border-gray-700">
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === "ground-stations"
                ? "bg-blue-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
            onClick={() => setActiveTab("ground-stations")}
          >
            <Globe className="w-4 h-4" />
            <span>Ground Stations</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === "satellites"
                ? "bg-blue-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
            onClick={() => setActiveTab("satellites")}
          >
            <Satellite className="w-4 h-4" />
            <span>Satellites</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === "sar-modes"
                ? "bg-blue-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
            onClick={() => setActiveTab("sar-modes")}
          >
            <Radio className="w-4 h-4" />
            <span>SAR Modes</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === "settings"
                ? "bg-blue-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
            onClick={() => setActiveTab("settings")}
          >
            <Settings className="w-4 h-4" />
            <span>Mission Settings</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === "snapshots"
                ? "bg-blue-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
            onClick={() => setActiveTab("snapshots")}
          >
            <History className="w-4 h-4" />
            <span>Snapshots</span>
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center space-x-2 ${
              activeTab === "validation"
                ? "bg-blue-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
            onClick={() => setActiveTab("validation")}
          >
            <FlaskConical className="w-4 h-4" />
            <span>Validation</span>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {activeTab === "ground-stations" && (
            <div className="space-y-4">
              {/* Actions Bar */}
              <div className="flex justify-between items-center">
                <div className="flex space-x-2">
                  <button
                    onClick={handleAddStation}
                    className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center space-x-2"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Add Station</span>
                  </button>

                  <button
                    onClick={reloadConfig}
                    className="px-3 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 flex items-center space-x-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    <span>Reload</span>
                  </button>

                  <label className="px-3 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 flex items-center space-x-2 cursor-pointer">
                    <Upload className="w-4 h-4" />
                    <span>Upload Config</span>
                    <input
                      type="file"
                      accept=".yaml,.yml,.json"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                  </label>

                  <button
                    onClick={downloadConfig}
                    className="px-3 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 flex items-center space-x-2"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download JSON</span>
                  </button>
                  <button
                    onClick={downloadYaml}
                    className="px-3 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 flex items-center space-x-2"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download YAML</span>
                  </button>
                </div>
              </div>

              {/* Ground Stations List */}
              <div className="space-y-2">
                {config?.ground_stations.map((station) => (
                  <div
                    key={station.name}
                    className="bg-gray-800 p-4 rounded-lg"
                  >
                    {editingStation?.name === station.name &&
                    !isAddingStation ? (
                      <div className="space-y-3">
                        <input
                          type="text"
                          value={editingStation.name || ""}
                          onChange={(e) =>
                            setEditingStation({
                              ...editingStation,
                              name: e.target.value,
                            })
                          }
                          className="w-full bg-gray-700 text-white px-3 py-2 rounded"
                          placeholder="Station Name"
                        />
                        <div className="grid grid-cols-2 gap-3">
                          <input
                            type="number"
                            value={
                              editingStation.latitude === 0 ||
                              editingStation.latitude === ""
                                ? ""
                                : editingStation.latitude
                            }
                            onChange={(e) =>
                              setEditingStation({
                                ...editingStation,
                                latitude: e.target.value,
                              })
                            }
                            className="bg-gray-700 text-white px-3 py-2 rounded"
                            placeholder="Latitude"
                            step="0.0001"
                          />
                          <input
                            type="number"
                            value={
                              editingStation.longitude === 0 ||
                              editingStation.longitude === ""
                                ? ""
                                : editingStation.longitude
                            }
                            onChange={(e) =>
                              setEditingStation({
                                ...editingStation,
                                longitude: e.target.value,
                              })
                            }
                            className="bg-gray-700 text-white px-3 py-2 rounded"
                            placeholder="Longitude"
                            step="0.0001"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <input
                            type="number"
                            value={
                              editingStation.elevation_mask === 10 ||
                              editingStation.elevation_mask === ""
                                ? ""
                                : editingStation.elevation_mask
                            }
                            onChange={(e) =>
                              setEditingStation({
                                ...editingStation,
                                elevation_mask: e.target.value,
                              })
                            }
                            className="bg-gray-700 text-white px-3 py-2 rounded"
                            placeholder="Elevation Mask (degrees)"
                            min="0"
                            max="90"
                          />
                          <input
                            type="number"
                            value={
                              editingStation.altitude_km === 0 ||
                              editingStation.altitude_km === ""
                                ? ""
                                : editingStation.altitude_km
                            }
                            onChange={(e) =>
                              setEditingStation({
                                ...editingStation,
                                altitude_km: e.target.value,
                              })
                            }
                            className="bg-gray-700 text-white px-3 py-2 rounded"
                            placeholder="Altitude (km)"
                            step="0.001"
                          />
                        </div>
                        <textarea
                          value={editingStation.description}
                          onChange={(e) =>
                            setEditingStation({
                              ...editingStation,
                              description: e.target.value,
                            })
                          }
                          className="w-full bg-gray-700 text-white px-3 py-2 rounded"
                          placeholder="Description"
                          rows={2}
                        />
                        <div className="flex space-x-2">
                          <button
                            onClick={() => saveGroundStation(editingStation)}
                            className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                          >
                            <Save className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setEditingStation(null)}
                            className="px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="text-white font-semibold">
                            {station.name}
                          </h3>
                          <p className="text-gray-400 text-sm">
                            {station.description}
                          </p>
                          <p className="text-gray-500 text-xs mt-1">
                            {station.latitude.toFixed(4)}°,{" "}
                            {station.longitude.toFixed(4)}° | Elevation Mask:{" "}
                            {station.elevation_mask}° | Alt:{" "}
                            {station.altitude_km}km
                          </p>
                          <div className="flex space-x-2 mt-2">
                            {station.capabilities.map((cap) => (
                              <span
                                key={cap}
                                className="px-2 py-1 bg-blue-600/20 text-blue-400 text-xs rounded"
                              >
                                {cap}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="flex space-x-2">
                          <button
                            onClick={() => setEditingStation(station)}
                            className="p-2 text-gray-400 hover:text-white"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteStation(station)}
                            className="p-2 text-gray-400 hover:text-red-400"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {/* Add New Station Form */}
                {isAddingStation && editingStation && (
                  <div className="bg-gray-800 p-4 rounded-lg space-y-3">
                    <input
                      type="text"
                      value={editingStation.name || ""}
                      onChange={(e) =>
                        setEditingStation({
                          ...editingStation,
                          name: e.target.value,
                        })
                      }
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded"
                      placeholder="Station Name"
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <input
                        type="number"
                        value={
                          editingStation.latitude === 0 ||
                          editingStation.latitude === ""
                            ? ""
                            : editingStation.latitude
                        }
                        onChange={(e) =>
                          setEditingStation({
                            ...editingStation,
                            latitude: e.target.value,
                          })
                        }
                        className="bg-gray-700 text-white px-3 py-2 rounded"
                        placeholder="Latitude"
                        step="0.0001"
                      />
                      <input
                        type="number"
                        value={
                          editingStation.longitude === 0 ||
                          editingStation.longitude === ""
                            ? ""
                            : editingStation.longitude
                        }
                        onChange={(e) =>
                          setEditingStation({
                            ...editingStation,
                            longitude: e.target.value,
                          })
                        }
                        className="bg-gray-700 text-white px-3 py-2 rounded"
                        placeholder="Longitude"
                        step="0.0001"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <input
                        type="number"
                        value={
                          editingStation.elevation_mask === 10 ||
                          editingStation.elevation_mask === ""
                            ? ""
                            : editingStation.elevation_mask
                        }
                        onChange={(e) =>
                          setEditingStation({
                            ...editingStation,
                            elevation_mask: e.target.value,
                          })
                        }
                        className="bg-gray-700 text-white px-3 py-2 rounded"
                        placeholder="Elevation Mask (degrees)"
                        min="0"
                        max="90"
                      />
                      <input
                        type="number"
                        value={
                          editingStation.altitude_km === 0 ||
                          editingStation.altitude_km === ""
                            ? ""
                            : editingStation.altitude_km
                        }
                        onChange={(e) =>
                          setEditingStation({
                            ...editingStation,
                            altitude_km: e.target.value,
                          })
                        }
                        className="bg-gray-700 text-white px-3 py-2 rounded"
                        placeholder="Altitude (km)"
                        step="0.001"
                      />
                    </div>
                    <textarea
                      value={editingStation.description}
                      onChange={(e) =>
                        setEditingStation({
                          ...editingStation,
                          description: e.target.value,
                        })
                      }
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded"
                      placeholder="Description"
                      rows={2}
                    />
                    <div className="flex space-x-2">
                      <button
                        onClick={() => saveGroundStation(editingStation, true)}
                        className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center space-x-2"
                      >
                        <Save className="w-4 h-4" />
                        <span>Save</span>
                      </button>
                      <button
                        onClick={() => {
                          setIsAddingStation(false);
                          setEditingStation(null);
                        }}
                        className="px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "satellites" && (
            <div className="space-y-4">
              {/* Managed Satellites List */}
              <div className="bg-gray-800 p-4 rounded-lg">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-white font-semibold">
                    Managed Satellites
                  </h3>
                  <button
                    onClick={() => setIsAddingSatellite(true)}
                    className="flex items-center space-x-2 px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Add from Catalog</span>
                  </button>
                </div>

                {/* Info about constellation selection */}
                <div className="mb-4 p-3 bg-blue-900/30 border border-blue-700 rounded-lg">
                  <p className="text-blue-300 text-sm">
                    <strong>
                      Selected Constellation ({selectedSatelliteIds.length}):
                    </strong>{" "}
                    {selectedSatelliteIds.length > 0
                      ? satellites
                          .filter((s) => selectedSatelliteIds.includes(s.id))
                          .map((s) => s.name)
                          .join(", ")
                      : "None selected"}
                  </p>
                  <p className="text-gray-400 text-xs mt-1">
                    Select multiple satellites to form a constellation. Click
                    checkboxes to add/remove satellites.
                  </p>
                </div>

                <div className="space-y-3">
                  {satellites.map((satellite) => (
                    <div
                      key={satellite.id}
                      className={`p-3 rounded-lg transition-all ${
                        selectedSatelliteIds.includes(satellite.id)
                          ? "bg-blue-900/50 border-2 border-blue-500"
                          : "bg-gray-700 border-2 border-transparent"
                      }`}
                    >
                      {editingSatellite?.id === satellite.id ? (
                        <div className="space-y-3">
                          <input
                            type="text"
                            value={editingSatellite.name}
                            onChange={(e) =>
                              setEditingSatellite({
                                ...editingSatellite,
                                name: e.target.value,
                              })
                            }
                            className="w-full bg-gray-600 text-white px-3 py-2 rounded"
                            placeholder="Satellite Name"
                          />
                          <div className="grid grid-cols-2 gap-3">
                            <select
                              value={editingSatellite.imaging_type}
                              onChange={(e) => {
                                const imagingType = e.target.value;
                                setEditingSatellite({
                                  ...editingSatellite,
                                  imaging_type: imagingType,
                                  // Auto-set default FOV based on imaging type
                                  sensor_fov_half_angle_deg:
                                    imagingType === "sar" ? 30.0 : 1.0,
                                });
                              }}
                              className="bg-gray-600 text-white px-3 py-2 rounded"
                            >
                              <option value="optical">Optical</option>
                              <option value="sar" disabled>
                                SAR (Coming Soon)
                              </option>
                            </select>
                            <input
                              type="number"
                              value={editingSatellite.satellite_agility}
                              onChange={(e) =>
                                setEditingSatellite({
                                  ...editingSatellite,
                                  satellite_agility: parseFloat(e.target.value),
                                })
                              }
                              className="bg-gray-600 text-white px-3 py-2 rounded"
                              placeholder="Agility (deg/s)"
                              step="0.1"
                              min="0.1"
                              max="5.0"
                            />
                          </div>
                          <div>
                            <label className="block text-gray-300 text-sm mb-1">
                              Sensor FOV (half-angle °)
                            </label>
                            <input
                              type="number"
                              value={
                                editingSatellite.sensor_fov_half_angle_deg ||
                                (editingSatellite.imaging_type === "sar"
                                  ? 30.0
                                  : 1.0)
                              }
                              onChange={(e) =>
                                setEditingSatellite({
                                  ...editingSatellite,
                                  sensor_fov_half_angle_deg: parseFloat(
                                    e.target.value,
                                  ),
                                })
                              }
                              className="w-full bg-gray-600 text-white px-3 py-2 rounded"
                              placeholder="Sensor FOV"
                              step="0.1"
                              min="0.1"
                              max="90"
                            />
                            <p className="text-xs text-gray-400 mt-1">
                              {editingSatellite.imaging_type === "sar"
                                ? "SAR default: 30°"
                                : "Optical default: 1°"}{" "}
                              (±
                              {(editingSatellite.sensor_fov_half_angle_deg ||
                                (editingSatellite.imaging_type === "sar"
                                  ? 30.0
                                  : 1.0)) * 2}
                              ° total)
                            </p>
                          </div>
                          {editingSatellite.imaging_type === "sar" && (
                            <select
                              value={editingSatellite.sar_mode}
                              onChange={(e) =>
                                setEditingSatellite({
                                  ...editingSatellite,
                                  sar_mode: e.target.value,
                                })
                              }
                              className="w-full bg-gray-600 text-white px-3 py-2 rounded"
                            >
                              <option value="stripmap">Stripmap</option>
                              <option value="spotlight">Spotlight</option>
                              <option value="scan">ScanSAR</option>
                            </select>
                          )}
                          <textarea
                            value={editingSatellite.description}
                            onChange={(e) =>
                              setEditingSatellite({
                                ...editingSatellite,
                                description: e.target.value,
                              })
                            }
                            className="w-full bg-gray-600 text-white px-3 py-2 rounded"
                            placeholder="Description"
                            rows={2}
                          />
                          <div className="flex space-x-2">
                            <button
                              onClick={() => saveSatellite(editingSatellite)}
                              className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center space-x-2"
                            >
                              <Save className="w-4 h-4" />
                              <span>Save</span>
                            </button>
                            <button
                              onClick={() => setEditingSatellite(null)}
                              className="px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <h4 className="text-white font-semibold">
                              {satellite.name}
                            </h4>
                            <p className="text-gray-400 text-sm">
                              {satellite.description}
                            </p>
                            <div className="flex space-x-4 mt-2 text-xs text-gray-500">
                              <span>Type: {satellite.imaging_type}</span>
                              {satellite.sensor_fov_half_angle_deg && (
                                <span>
                                  FOV: {satellite.sensor_fov_half_angle_deg}° (±
                                  {satellite.sensor_fov_half_angle_deg * 2}°
                                  total)
                                </span>
                              )}
                              <span>
                                Agility: {satellite.satellite_agility}°/s
                              </span>
                              {satellite.imaging_type === "sar" && (
                                <span>Mode: {satellite.sar_mode}</span>
                              )}
                            </div>
                            {satellite.tle_updated_at && (
                              <div className="flex items-center space-x-2 mt-2">
                                <span className="text-xs text-gray-500">
                                  TLE Updated:{" "}
                                  {new Date(
                                    satellite.tle_updated_at,
                                  ).toLocaleDateString()}
                                </span>
                                <div className="relative group">
                                  <span
                                    className={`text-xs px-2 py-1 rounded font-medium ${getTleAgeColor(
                                      getTleAgeDays(satellite.tle_updated_at),
                                    )}`}
                                  >
                                    {getTleAgeDays(satellite.tle_updated_at)}{" "}
                                    {getTleAgeDays(satellite.tle_updated_at) ===
                                    1
                                      ? "day"
                                      : "days"}{" "}
                                    old
                                  </span>
                                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-1 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                                    {getTleAgeTooltip(
                                      getTleAgeDays(satellite.tle_updated_at),
                                    )}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                          <div className="flex flex-col items-end space-y-2">
                            {/* Toggle constellation selection */}
                            <button
                              onClick={() => handleToggleSatellite(satellite)}
                              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                                selectedSatelliteIds.includes(satellite.id)
                                  ? "bg-blue-600 text-white"
                                  : "bg-gray-600 text-gray-300 hover:bg-blue-600 hover:text-white"
                              }`}
                            >
                              {selectedSatelliteIds.includes(satellite.id)
                                ? "✓ In Constellation"
                                : "Add to Constellation"}
                            </button>
                            <div className="flex space-x-2">
                              <button
                                onClick={() =>
                                  refreshSatelliteTle(satellite.id)
                                }
                                className={`p-2 ${
                                  refreshingSatelliteId === satellite.id
                                    ? "text-blue-400"
                                    : "text-gray-400 hover:text-blue-400"
                                }`}
                                title={
                                  refreshingSatelliteId === satellite.id
                                    ? "Refreshing TLE..."
                                    : "Refresh TLE data"
                                }
                                disabled={refreshingSatelliteId !== null}
                              >
                                <RefreshCw
                                  className={`w-4 h-4 ${
                                    refreshingSatelliteId === satellite.id
                                      ? "animate-spin"
                                      : ""
                                  }`}
                                />
                              </button>
                              <button
                                onClick={() => setEditingSatellite(satellite)}
                                className="p-2 text-gray-400 hover:text-white"
                                title="Edit satellite"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => removeSatellite(satellite.id)}
                                className="p-2 text-gray-400 hover:text-red-400"
                                title="Remove satellite"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Satellite Catalog Search */}
              {isAddingSatellite && (
                <div className="bg-gray-800 p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-white font-semibold">
                      Satellite Catalog Search
                    </h3>
                    <button
                      onClick={() => {
                        setIsAddingSatellite(false);
                        setSearchResults([]);
                        setSearchTerm("");
                      }}
                      className="text-gray-400 hover:text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="space-y-3">
                    <select
                      value={selectedSource}
                      onChange={(e) => setSelectedSource(e.target.value)}
                      className="w-full bg-gray-700 text-white px-3 py-2 rounded"
                    >
                      {tleSources.map((source) => (
                        <option key={source.id} value={source.id}>
                          {source.name}
                        </option>
                      ))}
                    </select>

                    <div className="flex space-x-2">
                      <input
                        type="text"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        onKeyPress={(e) =>
                          e.key === "Enter" && searchSatellites()
                        }
                        className="flex-1 bg-gray-700 text-white px-3 py-2 rounded"
                        placeholder="Search satellites (e.g., ICEYE, ISS)"
                      />
                      <button
                        onClick={searchSatellites}
                        disabled={isSearching}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-600"
                      >
                        {isSearching ? "Searching..." : "Search"}
                      </button>
                    </div>

                    {searchResults.length > 0 && (
                      <div className="max-h-96 overflow-y-auto space-y-2">
                        {searchResults.map((sat, idx) => (
                          <div
                            key={idx}
                            onClick={() => selectSatellite(sat)}
                            className="bg-gray-700 p-3 rounded cursor-pointer hover:bg-gray-600"
                          >
                            <h4 className="text-white font-medium">
                              {sat.name}
                            </h4>
                            <pre className="text-gray-400 text-xs mt-1 font-mono">
                              {sat.line1.substring(0, 50)}...
                            </pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "settings" && (
            <div className="space-y-4">
              {missionSettings && (
                <div className="space-y-4">
                  {/* Edit/Save Controls */}
                  <div className="bg-gray-800 p-4 rounded-lg flex justify-between items-center">
                    <h3 className="text-white font-semibold">
                      Mission Configuration
                    </h3>
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
                                  "/api/config/mission-settings",
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
                              {Object.entries(
                                durations as Record<string, number>,
                              ).map(([durationType, value]) => (
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
                                        ...(durations as Record<
                                          string,
                                          number
                                        >),
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
                              ))}
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
                      {Object.entries(
                        missionSettings.elevation_constraints || {},
                      )
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
                                      const newValue = parseFloat(
                                        e.target.value,
                                      );
                                      const updatedConstraints = {
                                        ...(constraints as Record<
                                          string,
                                          number
                                        >),
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
                      {Object.entries(
                        missionSettings.planning_constraints || {},
                      ).map(([constraintType, value]) => (
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
                              {Object.entries(
                                value as Record<string, number>,
                              ).map(([weatherKey, weatherValue]) => (
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
                              ))}
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
                                typeof value === "number" ||
                                typeof value === "string"
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
                      ))}
                    </div>
                  </div>

                  {/* Output Settings */}
                  <div className="bg-gray-800 p-4 rounded-lg">
                    <h3 className="text-white font-semibold mb-4">
                      Output Settings
                    </h3>
                    <div className="space-y-4">
                      {Object.entries(
                        missionSettings.output_settings || {},
                      ).map(([key, value]) => (
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
                                value as Record<
                                  string,
                                  string | number | boolean
                                >,
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
                      ))}
                    </div>
                  </div>

                  {/* Defaults Section */}
                  <div className="bg-gray-800 p-4 rounded-lg">
                    <h3 className="text-white font-semibold mb-4">
                      Default Settings
                    </h3>
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
                                  updateMissionSetting(
                                    "defaults",
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
                </div>
              )}
            </div>
          )}

          {/* SAR Modes Tab */}
          {activeTab === "sar-modes" && (
            <div className="space-y-4">
              <div className="bg-gray-800 p-4 rounded-lg">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-white font-semibold">
                    SAR Imaging Modes
                  </h3>
                  <div className="text-xs text-gray-400">
                    Config Hash:{" "}
                    {currentConfigHash.substring(0, 8) || "loading..."}
                  </div>
                </div>
                <p className="text-gray-400 text-sm mb-4">
                  Configure incidence angle ranges, scene dimensions, and
                  quality parameters for each SAR imaging mode.
                </p>

                {Object.keys(sarModes).length === 0 ? (
                  <p className="text-gray-500 text-center py-8">
                    Loading SAR modes...
                  </p>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(sarModes).map(([modeName, mode]) => (
                      <div
                        key={modeName}
                        className="bg-gray-700 p-4 rounded-lg"
                      >
                        {editingSarMode === modeName && editingSarModeData ? (
                          <div className="space-y-4">
                            <div className="flex justify-between items-center">
                              <h4 className="text-white font-medium capitalize">
                                {modeName}
                              </h4>
                              <div className="flex space-x-2">
                                <button
                                  onClick={() =>
                                    saveSarMode(modeName, editingSarModeData)
                                  }
                                  disabled={isSavingSarMode}
                                  className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-sm flex items-center space-x-1"
                                >
                                  <Save className="w-3 h-3" />
                                  <span>
                                    {isSavingSarMode ? "Saving..." : "Save"}
                                  </span>
                                </button>
                                <button
                                  onClick={() => {
                                    setEditingSarMode(null);
                                    setEditingSarModeData(null);
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
                                  value={
                                    editingSarModeData.incidence_angle
                                      .recommended_min
                                  }
                                  onChange={(e) =>
                                    setEditingSarModeData({
                                      ...editingSarModeData,
                                      incidence_angle: {
                                        ...editingSarModeData.incidence_angle,
                                        recommended_min: parseFloat(
                                          e.target.value,
                                        ),
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
                                  value={
                                    editingSarModeData.incidence_angle
                                      .recommended_max
                                  }
                                  onChange={(e) =>
                                    setEditingSarModeData({
                                      ...editingSarModeData,
                                      incidence_angle: {
                                        ...editingSarModeData.incidence_angle,
                                        recommended_max: parseFloat(
                                          e.target.value,
                                        ),
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
                                  value={
                                    editingSarModeData.incidence_angle
                                      .absolute_min
                                  }
                                  onChange={(e) =>
                                    setEditingSarModeData({
                                      ...editingSarModeData,
                                      incidence_angle: {
                                        ...editingSarModeData.incidence_angle,
                                        absolute_min: parseFloat(
                                          e.target.value,
                                        ),
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
                                  value={
                                    editingSarModeData.incidence_angle
                                      .absolute_max
                                  }
                                  onChange={(e) =>
                                    setEditingSarModeData({
                                      ...editingSarModeData,
                                      incidence_angle: {
                                        ...editingSarModeData.incidence_angle,
                                        absolute_max: parseFloat(
                                          e.target.value,
                                        ),
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
                                  value={editingSarModeData.scene.width_km}
                                  onChange={(e) =>
                                    setEditingSarModeData({
                                      ...editingSarModeData,
                                      scene: {
                                        ...editingSarModeData.scene,
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
                                  value={editingSarModeData.scene.length_km}
                                  onChange={(e) =>
                                    setEditingSarModeData({
                                      ...editingSarModeData,
                                      scene: {
                                        ...editingSarModeData.scene,
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
                                  <span className="text-gray-400">
                                    Incidence:
                                  </span>{" "}
                                  {mode.incidence_angle.recommended_min}° -{" "}
                                  {mode.incidence_angle.recommended_max}°
                                  <span className="text-gray-600 ml-1">
                                    (abs: {mode.incidence_angle.absolute_min}° -{" "}
                                    {mode.incidence_angle.absolute_max}°)
                                  </span>
                                </div>
                                <div>
                                  <span className="text-gray-400">Scene:</span>{" "}
                                  {mode.scene.width_km}km ×{" "}
                                  {mode.scene.length_km}km
                                </div>
                                <div>
                                  <span className="text-gray-400">
                                    Resolution:
                                  </span>{" "}
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
                                setEditingSarMode(modeName);
                                setEditingSarModeData({ ...mode });
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
          )}

          {/* Snapshots Tab */}
          {activeTab === "snapshots" && (
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
                  Create snapshots of your configuration to enable versioning
                  and rollback capabilities.
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
                            Hash: {snapshot.config_hash.substring(0, 8)} |
                            Files: {snapshot.files.join(", ")}
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
          )}

          {/* Validation Tab Content (PR-VALIDATION-01) */}
          {activeTab === "validation" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
                  <FlaskConical className="w-5 h-5" />
                  <span>Workflow Validation</span>
                </h3>
                <span className="text-xs text-gray-500">Debug/Admin Mode</span>
              </div>

              <p className="text-gray-400 text-sm">
                Run deterministic validation scenarios to verify mission
                analysis → planning → commit workflows.
              </p>

              {/* Scenario Selection */}
              <div className="bg-gray-800 p-4 rounded-lg space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">
                    Select Scenario
                  </label>
                  <select
                    value={selectedScenarioId}
                    onChange={(e) => setSelectedScenarioId(e.target.value)}
                    className="w-full bg-gray-700 text-white rounded px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none"
                  >
                    {validationScenarios.length === 0 ? (
                      <option value="">No scenarios available</option>
                    ) : (
                      validationScenarios.map((scenario) => (
                        <option key={scenario.id} value={scenario.id}>
                          {scenario.name} ({scenario.num_satellites} satellites,{" "}
                          {scenario.num_targets} targets)
                        </option>
                      ))
                    )}
                  </select>
                </div>

                <button
                  onClick={handleRunValidation}
                  disabled={isRunningValidation || !selectedScenarioId}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                >
                  {isRunningValidation ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Running...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      <span>Run Validation</span>
                    </>
                  )}
                </button>
              </div>

              {/* Error Display */}
              {validationError && (
                <div className="bg-red-900/50 border border-red-600 rounded-lg p-4 flex items-start space-x-3">
                  <XCircle className="w-5 h-5 text-red-400 mt-0.5" />
                  <div>
                    <h4 className="text-red-200 font-medium">
                      Validation Failed
                    </h4>
                    <p className="text-red-300 text-sm mt-1">
                      {validationError}
                    </p>
                  </div>
                </div>
              )}

              {/* Report Display */}
              {validationReport && (
                <div
                  className={`border rounded-lg p-4 ${
                    validationReport.passed
                      ? "bg-green-900/30 border-green-600"
                      : "bg-red-900/30 border-red-600"
                  }`}
                >
                  <div className="flex items-center space-x-3 mb-4">
                    {validationReport.passed ? (
                      <CheckCircle className="w-6 h-6 text-green-400" />
                    ) : (
                      <XCircle className="w-6 h-6 text-red-400" />
                    )}
                    <h4
                      className={`text-lg font-medium ${
                        validationReport.passed
                          ? "text-green-200"
                          : "text-red-200"
                      }`}
                    >
                      {validationReport.passed
                        ? "Validation Passed"
                        : "Validation Failed"}
                    </h4>
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-400">Scenario:</span>
                      <span className="text-white ml-2">
                        {validationReport.scenario_name}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Runtime:</span>
                      <span className="text-white ml-2">
                        {validationReport.total_runtime_ms.toFixed(0)}ms
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Invariants:</span>
                      <span className="text-white ml-2">
                        {validationReport.passed_invariants}/
                        {validationReport.total_invariants} passed
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Report Hash:</span>
                      <span className="text-white ml-2 font-mono text-xs">
                        {validationReport.report_hash}
                      </span>
                    </div>
                  </div>

                  {/* Counts */}
                  <div className="mt-4 pt-4 border-t border-gray-700">
                    <h5 className="text-gray-300 text-sm font-medium mb-2">
                      Counts
                    </h5>
                    <div className="grid grid-cols-4 gap-2 text-sm">
                      <div className="bg-gray-800 rounded p-2 text-center">
                        <div className="text-xl font-bold text-white">
                          {validationReport.counts.opportunities}
                        </div>
                        <div className="text-gray-400 text-xs">
                          Opportunities
                        </div>
                      </div>
                      <div className="bg-gray-800 rounded p-2 text-center">
                        <div className="text-xl font-bold text-white">
                          {validationReport.counts.planned}
                        </div>
                        <div className="text-gray-400 text-xs">Planned</div>
                      </div>
                      <div className="bg-gray-800 rounded p-2 text-center">
                        <div className="text-xl font-bold text-white">
                          {validationReport.counts.committed}
                        </div>
                        <div className="text-gray-400 text-xs">Committed</div>
                      </div>
                      <div className="bg-gray-800 rounded p-2 text-center">
                        <div className="text-xl font-bold text-white">
                          {validationReport.counts.conflicts}
                        </div>
                        <div className="text-gray-400 text-xs">Conflicts</div>
                      </div>
                    </div>
                  </div>

                  {/* Invariants */}
                  {validationReport.invariants.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-700">
                      <h5 className="text-gray-300 text-sm font-medium mb-2">
                        Invariant Checks
                      </h5>
                      <div className="space-y-2">
                        {validationReport.invariants.map((inv, idx) => (
                          <div
                            key={idx}
                            className={`flex items-center space-x-2 text-sm ${
                              inv.passed ? "text-green-300" : "text-red-300"
                            }`}
                          >
                            {inv.passed ? (
                              <CheckCircle className="w-4 h-4" />
                            ) : (
                              <XCircle className="w-4 h-4" />
                            )}
                            <span className="font-mono text-xs">
                              {inv.invariant}
                            </span>
                            <span className="text-gray-400">-</span>
                            <span>{inv.message}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Report ID for reference */}
                  <div className="mt-4 pt-4 border-t border-gray-700 text-xs text-gray-500">
                    Report ID: {validationReport.report_id}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteConfirmation.isOpen && (
        <div className="fixed inset-0 bg-black/70 z-[60] flex items-center justify-center p-4">
          <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-white mb-4">
              Confirm Deletion
            </h3>
            <p className="text-gray-300 mb-6">
              Are you sure you want to delete the ground station &quot;
              {deleteConfirmation.station?.name}&quot;? This action cannot be
              undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={cancelDelete}
                className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;
