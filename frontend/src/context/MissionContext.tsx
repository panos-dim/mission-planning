import React, {
  createContext,
  useContext,
  useReducer,
  ReactNode,
  useRef,
  useCallback,
} from "react";
import {
  Color,
  Cartesian3,
  HeightReference,
  LabelStyle,
  VerticalOrigin,
  Cartesian2,
  JulianDate,
  HeadingPitchRange,
  Viewer,
  Entity,
} from "cesium";
import {
  MissionState,
  MissionData,
  ValidationResponse,
  FormData,
  SceneObject,
  Workspace,
  CZMLPacket,
  TargetData,
} from "../types";
import { useVisStore } from "../store/visStore";
import { useExplorerStore } from "../store/explorerStore";
import debug from "../utils/debug";
import { missionApi, tleApi, configApi, getErrorMessage } from "../api";
import type { GroundStation } from "../api";

// Initial state
const initialState: MissionState = {
  isLoading: false,
  missionData: null,
  czmlData: [],
  error: null,
  validationResult: null,
  sceneObjects: [],
  selectedObjectId: null,
  workspaces: [],
  activeWorkspace: null,
};

// Action types
type MissionAction =
  | { type: "SET_LOADING"; payload: boolean }
  | {
      type: "SET_MISSION_DATA";
      payload: { missionData: MissionData; czmlData: CZMLPacket[] };
    }
  | { type: "SET_ERROR"; payload: string | null }
  | { type: "SET_VALIDATION_RESULT"; payload: ValidationResponse | null }
  | { type: "CLEAR_MISSION" }
  | { type: "ADD_SCENE_OBJECT"; payload: SceneObject }
  | {
      type: "UPDATE_SCENE_OBJECT";
      payload: { id: string; updates: Partial<SceneObject> };
    }
  | { type: "REMOVE_SCENE_OBJECT"; payload: string }
  | { type: "SET_SELECTED_OBJECT"; payload: string | null }
  | { type: "SET_SCENE_OBJECTS"; payload: SceneObject[] }
  | { type: "SAVE_WORKSPACE"; payload: Workspace }
  | { type: "LOAD_WORKSPACE"; payload: Workspace }
  | { type: "DELETE_WORKSPACE"; payload: string }
  | { type: "SET_ACTIVE_WORKSPACE"; payload: string | null };

// Reducer
function missionReducer(
  state: MissionState,
  action: MissionAction
): MissionState {
  switch (action.type) {
    case "SET_LOADING":
      return { ...state, isLoading: action.payload };
    case "SET_MISSION_DATA":
      return {
        ...state,
        missionData: action.payload.missionData,
        czmlData: action.payload.czmlData,
        isLoading: false,
        error: null,
      };
    case "SET_ERROR":
      return { ...state, error: action.payload, isLoading: false };
    case "SET_VALIDATION_RESULT":
      return { ...state, validationResult: action.payload };
    case "CLEAR_MISSION":
      return { ...initialState, workspaces: state.workspaces };
    case "ADD_SCENE_OBJECT":
      return {
        ...state,
        sceneObjects: [...state.sceneObjects, action.payload],
      };
    case "UPDATE_SCENE_OBJECT":
      return {
        ...state,
        sceneObjects: state.sceneObjects.map((obj) =>
          obj.id === action.payload.id
            ? { ...obj, ...action.payload.updates }
            : obj
        ),
      };
    case "REMOVE_SCENE_OBJECT":
      return {
        ...state,
        sceneObjects: state.sceneObjects.filter(
          (obj) => obj.id !== action.payload
        ),
        selectedObjectId:
          state.selectedObjectId === action.payload
            ? null
            : state.selectedObjectId,
      };
    case "SET_SELECTED_OBJECT":
      return { ...state, selectedObjectId: action.payload };
    case "SET_SCENE_OBJECTS":
      return { ...state, sceneObjects: action.payload };
    case "SAVE_WORKSPACE":
      const existingIndex = state.workspaces.findIndex(
        (w) => w.id === action.payload.id
      );
      const updatedWorkspaces =
        existingIndex >= 0
          ? state.workspaces.map((w) =>
              w.id === action.payload.id ? action.payload : w
            )
          : [...state.workspaces, action.payload];
      return {
        ...state,
        workspaces: updatedWorkspaces,
        activeWorkspace: action.payload.id,
      };
    case "LOAD_WORKSPACE":
      return {
        ...state,
        sceneObjects: action.payload.sceneObjects,
        missionData: action.payload.missionData,
        czmlData: action.payload.czmlData,
        activeWorkspace: action.payload.id,
      };
    case "DELETE_WORKSPACE":
      return {
        ...state,
        workspaces: state.workspaces.filter((w) => w.id !== action.payload),
        activeWorkspace:
          state.activeWorkspace === action.payload
            ? null
            : state.activeWorkspace,
      };
    case "SET_ACTIVE_WORKSPACE":
      return { ...state, activeWorkspace: action.payload };
    default:
      return state;
  }
}

// Context type
interface MissionContextType {
  state: MissionState;
  dispatch: React.Dispatch<MissionAction>;
  validateTLE: (tle: {
    name: string;
    line1: string;
    line2: string;
  }) => Promise<void>;
  analyzeMission: (formData: FormData) => Promise<void>;
  clearMission: () => void;
  navigateToPassWindow: (passIndex: number) => void; // Mission Results: jump to pass start
  navigateToImagingTime: (passIndex: number) => void; // Mission Planning: jump to optimal imaging time
  setCesiumViewer: (viewer: Viewer | null) => void;
  addSceneObject: (object: SceneObject) => void;
  updateSceneObject: (id: string, updates: Partial<SceneObject>) => void;
  removeSceneObject: (id: string) => void;
  setSelectedObject: (id: string | null) => void;
  selectObject: (id: string | null) => void;
  updateObject: (id: string, updates: Partial<SceneObject>) => void;
  removeObject: (id: string) => void;
  saveWorkspace: (name: string) => void;
  loadWorkspace: (id: string) => void;
  deleteWorkspace: (id: string) => void;
  flyToObject: (objectId: string) => void;
  toggleEntityVisibility: (entityType: string, isVisible: boolean) => void;
}

// Create context
const MissionContext = createContext<MissionContextType | undefined>(undefined);

// Provider component
interface MissionProviderProps {
  children: ReactNode;
}

export function MissionProvider({
  children,
}: MissionProviderProps): JSX.Element {
  const [state, dispatch] = useReducer(missionReducer, initialState);
  const [cesiumViewer, setCesiumViewer] = React.useState<any>(null);
  const { setClockTime } = useVisStore();

  // AbortController refs for cancellable requests
  const analyzeAbortRef = useRef<AbortController | null>(null);
  const validateAbortRef = useRef<AbortController | null>(null);

  const validateTLE = useCallback(
    async (tle: { name: string; line1: string; line2: string }) => {
      // Cancel any pending validation
      validateAbortRef.current?.abort();
      validateAbortRef.current = new AbortController();

      dispatch({ type: "SET_LOADING", payload: true });
      try {
        const result = await tleApi.validate(tle, {
          signal: validateAbortRef.current.signal,
        });

        dispatch({ type: "SET_VALIDATION_RESULT", payload: result });

        if (!result.valid && result.error) {
          dispatch({ type: "SET_ERROR", payload: result.error });
        }
      } catch (error) {
        // Don't report aborted requests as errors
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        dispatch({
          type: "SET_ERROR",
          payload: `TLE validation failed: ${getErrorMessage(error)}`,
        });
      } finally {
        dispatch({ type: "SET_LOADING", payload: false });
      }
    },
    []
  );

  const analyzeMission = useCallback(async (formData: FormData) => {
    // Cancel any pending analysis
    analyzeAbortRef.current?.abort();
    analyzeAbortRef.current = new AbortController();

    dispatch({ type: "SET_LOADING", payload: true });
    try {
      // Handle the datetime-local format and ensure it's treated as UTC
      let startTimeUTC: string;
      let endTimeUTC: string;

      if (formData.startTime && formData.startTime.includes("T")) {
        // The datetime-local input gives us YYYY-MM-DDTHH:mm format
        // Append seconds and Z to make it a valid ISO string for UTC
        startTimeUTC = formData.startTime + ":00Z";
      } else {
        // Fallback to current time if invalid format
        console.warn("Invalid start time format, using current time");
        startTimeUTC = new Date().toISOString();
      }

      if (formData.endTime && formData.endTime.includes("T")) {
        // Same format handling for end time
        endTimeUTC = formData.endTime + ":00Z";
      } else {
        // Fallback to 24 hours after start time
        console.warn("Invalid end time format, using 24 hours after start");
        const start = new Date(startTimeUTC);
        endTimeUTC = new Date(
          start.getTime() + 24 * 60 * 60 * 1000
        ).toISOString();
      }

      // Build mission request with constellation support (2025 best practice)
      // Use satellites array for multiple satellites, fall back to tle for single satellite
      const hasSatellitesArray =
        formData.satellites && formData.satellites.length > 0;

      const missionRequest = {
        // NEW: Constellation support - use satellites array if available
        ...(hasSatellitesArray
          ? { satellites: formData.satellites }
          : { tle: formData.tle }),
        targets: formData.targets,
        start_time: startTimeUTC,
        end_time: endTimeUTC,
        mission_type: formData.missionType,
        // Only include elevation_mask for communication missions
        ...(formData.missionType === "communication" && {
          elevation_mask: formData.elevationMask,
        }),
        max_spacecraft_roll_deg:
          formData.pointingAngle > 0 ? formData.pointingAngle : undefined,
        ground_station_name: formData.groundStationName,
        imaging_type: formData.imagingType,
        // Map frontend SAR mode names to backend API names
        // Frontend: spot, strip, scan, dwell → Backend: spotlight, stripmap, scan
        sar_mode: (() => {
          const mode = formData.sar?.imaging_mode || formData.sarMode;
          const modeMap: Record<string, string> = {
            spot: "spotlight",
            strip: "stripmap",
            scan: "scan",
            dwell: "scan", // dwell maps to scan for backend
            stripmap: "stripmap",
            spotlight: "spotlight",
          };
          return modeMap[mode || "stripmap"] || "stripmap";
        })() as "stripmap" | "spotlight" | "scan",
      };

      debug.section("MISSION ANALYSIS");

      const result = await missionApi.analyze(missionRequest, {
        signal: analyzeAbortRef.current.signal,
      });

      if (result.success && result.data) {
        // Log response with summary
        const passes = result.data.mission_data?.passes || [];
        debug.apiResponse("POST /api/mission/analyze", result.data, {
          summary: `✅ ${passes.length} opportunities found, ${
            result.data.czml_data?.length || 0
          } CZML packets`,
        });

        // Log opportunities in clean table format
        if (passes.length > 0) {
          debug.opportunities(passes);
        }

        dispatch({
          type: "SET_MISSION_DATA",
          payload: {
            missionData: result.data.mission_data,
            czmlData: result.data.czml_data,
          },
        });

        // Track analysis run in explorer store
        useExplorerStore.getState().addAnalysisRun({
          id: `analysis_${Date.now()}`,
          timestamp: new Date().toISOString(),
          opportunitiesCount: passes.length,
          missionMode:
            result.data.mission_data?.mission_type?.toUpperCase() || "UNKNOWN",
        });

        // Auto-populate scene objects with satellite and targets
        const missionData = result.data.mission_data;
        const newObjects: SceneObject[] = [];

        // Extract satellite from CZML data and add to object tree
        if (result.data.czml_data) {
          const satellitePacket = result.data.czml_data.find(
            (packet: CZMLPacket) => packet.id?.startsWith("sat_")
          );
          if (satellitePacket) {
            // Extract position data from CZML if available
            let position = undefined;
            if (satellitePacket.position?.cartographicDegrees) {
              const posArray = satellitePacket.position.cartographicDegrees;
              // Position array format: [time, lon, lat, alt, time, lon, lat, alt, ...]
              // Get the first position (after epoch time)
              if (posArray.length >= 4) {
                const longitude = posArray[1];
                const latitude = posArray[2];
                const altitude = posArray[3] * 1000; // Convert km to meters
                position = { latitude, longitude, altitude };
              }
            }

            // Get satellite name with fallback for constellation support
            const satName =
              satellitePacket.name || missionData.satellite_name || "Satellite";

            newObjects.push({
              id: satellitePacket.id,
              name: satName,
              type: "satellite",
              position: position,
              visible: true,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            });
            debug.verbose(`Added satellite: ${satellitePacket.id}`);
          }
        }

        // Add targets
        missionData.targets?.forEach((target: TargetData, index: number) => {
          newObjects.push({
            id: `target_${index}_${target.name}`,
            name: target.name,
            type: "target",
            position: {
              latitude: target.latitude,
              longitude: target.longitude,
              altitude: 0, // Ground level for targets
            },
            visible: true,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          });
        });

        // Add all objects to state
        newObjects.forEach((obj) => {
          dispatch({ type: "ADD_SCENE_OBJECT", payload: obj });
        });

        // Load ground stations with visibility enabled
        setTimeout(async () => {
          await loadGroundStations(true); // Pass true to force visibility
        }, 600); // Small delay to ensure CZML data is loaded
      } else {
        dispatch({
          type: "SET_ERROR",
          payload: result.message || "Mission analysis failed",
        });
      }
    } catch (error) {
      // Don't report aborted requests as errors
      if (error instanceof Error && error.name === "AbortError") {
        return;
      }
      console.error("Mission analysis error:", {
        message: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
        name: error instanceof Error ? error.name : typeof error,
      });
      dispatch({
        type: "SET_ERROR",
        payload: `Mission analysis failed: ${getErrorMessage(error)}`,
      });
    } finally {
      dispatch({ type: "SET_LOADING", payload: false });
    }
  }, []);

  const clearMission = useCallback(() => {
    // Cancel any pending requests
    analyzeAbortRef.current?.abort();
    validateAbortRef.current?.abort();
    dispatch({ type: "CLEAR_MISSION" });
  }, []);

  const navigateToPassWindow = useCallback(
    (passIndex: number) => {
      if (!state.missionData) return;

      const pass = state.missionData.passes[passIndex];
      if (!pass) return;

      debug.verbose(`Navigating to pass ${passIndex + 1}`);

      try {
        // Jump to pass window start (for Mission Results)
        const targetTime = pass.start_time;

        // Convert timezone offset format (+00:00) to Z format for Cesium
        let utcTimeString = targetTime;
        if (utcTimeString.includes("+00:00")) {
          utcTimeString = utcTimeString.replace("+00:00", "Z");
        } else if (!utcTimeString.endsWith("Z")) {
          utcTimeString = utcTimeString + "Z";
        }

        const jumpTime = JulianDate.fromIso8601(utcTimeString);
        setClockTime(jumpTime);
      } catch (error: unknown) {
        console.error("Error in navigateToPassWindow:", error);
      }
    },
    [state.missionData, setClockTime]
  );

  const navigateToImagingTime = useCallback(
    (passIndex: number) => {
      if (!state.missionData) return;

      const pass = state.missionData.passes[passIndex];
      if (!pass) return;

      debug.verbose(`Navigating to imaging time for pass ${passIndex + 1}`);

      try {
        // Jump to optimal imaging time (for Mission Planning Schedule)
        const isImagingMission = state.missionData.mission_type === "imaging";
        const targetTime =
          isImagingMission && pass.max_elevation_time
            ? pass.max_elevation_time
            : pass.start_time;

        // Convert timezone offset format (+00:00) to Z format for Cesium
        let utcTimeString = targetTime;
        if (utcTimeString.includes("+00:00")) {
          utcTimeString = utcTimeString.replace("+00:00", "Z");
        } else if (!utcTimeString.endsWith("Z")) {
          utcTimeString = utcTimeString + "Z";
        }

        const jumpTime = JulianDate.fromIso8601(utcTimeString);
        setClockTime(jumpTime);
      } catch (error: unknown) {
        console.error("Error in navigateToImagingTime:", error);
      }
    },
    [state.missionData, setClockTime]
  );

  const addSceneObject = useCallback((object: SceneObject) => {
    dispatch({ type: "ADD_SCENE_OBJECT", payload: object });
  }, []);

  const updateSceneObject = useCallback(
    (id: string, updates: Partial<SceneObject>) => {
      dispatch({ type: "UPDATE_SCENE_OBJECT", payload: { id, updates } });
    },
    []
  );

  const removeSceneObject = useCallback((id: string) => {
    dispatch({ type: "REMOVE_SCENE_OBJECT", payload: id });
  }, []);

  const setSelectedObject = useCallback((id: string | null) => {
    dispatch({ type: "SET_SELECTED_OBJECT", payload: id });
  }, []);

  const saveWorkspace = (name: string) => {
    const workspace: Workspace = {
      id: `workspace_${Date.now()}`,
      name,
      createdAt: new Date().toISOString(),
      sceneObjects: state.sceneObjects,
      missionData: state.missionData,
      czmlData: state.czmlData,
    };
    dispatch({ type: "SAVE_WORKSPACE", payload: workspace });
    // Save to localStorage
    const workspaces = JSON.parse(
      localStorage.getItem("mission_workspaces") || "[]"
    );
    workspaces.push(workspace);
    localStorage.setItem("mission_workspaces", JSON.stringify(workspaces));
  };

  const loadWorkspace = (id: string) => {
    const workspace = state.workspaces.find((w) => w.id === id);
    if (workspace) {
      dispatch({ type: "LOAD_WORKSPACE", payload: workspace });
    }
  };

  const deleteWorkspace = (id: string) => {
    dispatch({ type: "DELETE_WORKSPACE", payload: id });
    // Remove from localStorage
    const workspaces = JSON.parse(
      localStorage.getItem("mission_workspaces") || "[]"
    );
    const filtered = workspaces.filter((w: Workspace) => w.id !== id);
    localStorage.setItem("mission_workspaces", JSON.stringify(filtered));
  };

  const flyToObject = (objectId: string) => {
    debug.verbose(`Flying to object: ${objectId}`);

    if (!cesiumViewer || !cesiumViewer.cesiumElement) {
      console.warn("[flyToObject] No cesiumViewer available");
      return;
    }

    const viewer = cesiumViewer.cesiumElement;
    let entity: Entity | null = null;

    // Map object IDs to entity IDs
    let searchId = objectId;

    // Handle satellite IDs from tree: satellite_sat_ICEYE-X67 -> sat_ICEYE-X67
    if (objectId.startsWith("satellite_sat_")) {
      searchId = objectId.replace("satellite_", "");
    }
    // Handle satellite IDs: keep sat_ prefix for direct match with CZML entities
    else if (objectId.startsWith("sat_")) {
      searchId = objectId; // Keep the original ID for direct match
    }
    // Handle entity-generated IDs: entity_sat_Satellite -> sat_Satellite
    else if (objectId.startsWith("entity_sat_")) {
      searchId = objectId.replace("entity_", "");
    }
    // Handle target IDs from tree: target_target_Athens or target_mission_0_Athens -> target_0 or search by name
    else if (objectId.startsWith("target_")) {
      // Try to extract target name for searching
      const nameMatch = objectId.match(/target_(?:target_|mission_\d+_)?(.+)$/);
      if (nameMatch) {
        searchId = nameMatch[1]; // Use just the target name
      }
      // Also try numeric target ID format
      const numMatch = objectId.match(/target_(\d+)/);
      if (numMatch) {
        searchId = `target_${numMatch[1]}`;
      }
    }

    // First, check regular entities collection
    entity = viewer.entities.getById(searchId);

    // If not found, search through all data sources (CZML entities)
    if (!entity && viewer.dataSources && viewer.dataSources.length > 0) {
      for (let i = 0; i < viewer.dataSources.length; i++) {
        const dataSource = viewer.dataSources.get(i);
        if (dataSource && dataSource.entities) {
          // Try to find by mapped searchId
          entity = dataSource.entities.getById(searchId);
          if (entity) break;

          // Also try searching by entity name for targets
          if (!entity && objectId.startsWith("target_")) {
            const entities = dataSource.entities.values;
            for (const e of entities) {
              if (e.name && e.name === searchId) {
                entity = e;
                break;
              }
            }
          }
          if (entity) break;
        }
      }
    }

    if (entity) {
      // Unlock previous tracked entity
      if (viewer.trackedEntity) {
        viewer.trackedEntity = undefined;
      }

      // Determine appropriate viewing distance based on entity type
      let distance = 500000; // Default 500km for satellites

      // Adjust distance based on entity type or ID patterns
      if (objectId.includes("ground_station") || objectId.includes("target")) {
        distance = 300000; // 300km for ground targets
      } else if (objectId.includes("coverage")) {
        distance = 5000000; // 5000km for coverage circles
      } else if (objectId === "satellite" || objectId.includes("satellite")) {
        distance = 800000; // 800km for satellites
      }

      // Fly to entity with nadir view (straight down)
      viewer
        .flyTo(entity, {
          duration: 1.5,
          offset: new HeadingPitchRange(0, -Math.PI / 2, distance), // Nadir looking
        })
        .then(() => {
          // Only select the entity, don't use trackedEntity to avoid camera jumps
          viewer.selectedEntity = entity;
        })
        .catch((error: unknown) => {
          console.error("[flyToObject] Failed to fly to entity:", error);
        });
    } else {
      console.warn(
        `[flyToObject] Entity with ID '${objectId}' not found in viewer or data sources`
      );
    }
  };

  const toggleEntityVisibility = async (
    entityType: string,
    isVisible: boolean
  ) => {
    if (!cesiumViewer || !cesiumViewer.cesiumElement) return;

    const viewer = cesiumViewer.cesiumElement;

    // Check all data sources (including CZML)
    if (viewer.dataSources && viewer.dataSources.length > 0) {
      for (let i = 0; i < viewer.dataSources.length; i++) {
        const dataSource = viewer.dataSources.get(i);
        if (dataSource && dataSource.entities && dataSource.entities.values) {
          dataSource.entities.values.forEach((entity: Entity) => {
            // Toggle based on entity ID patterns or name
            if (entityType === "satellite" && entity.id.startsWith("sat_")) {
              entity.show = isVisible;
            } else if (
              entityType === "target" &&
              entity.id.startsWith("target_") &&
              !entity.id.includes("coverage")
            ) {
              entity.show = isVisible;
            } else if (entityType === "coverage") {
              // Check both ID and name for coverage areas
              if (
                entity.id.includes("coverage") ||
                (entity.name && entity.name.includes("Coverage Area"))
              ) {
                entity.show = isVisible;
              }
            } else if (
              entityType === "pointing_cone" &&
              entity.id === "pointing_cone"
            ) {
              entity.show = isVisible;
            }
          });
        }
      }
    }

    // Handle day/night lighting toggle
    if (entityType === "day_night_lighting") {
      // Prevent lighting toggles during initialization
      if ((window as any).lightingInitializationInProgress) {
        return;
      }

      // Only change lighting if it's actually different to prevent unnecessary toggles
      const currentLighting = viewer.scene.globe.enableLighting;
      const currentAtmosphere = viewer.scene.globe.showGroundAtmosphere;

      if (currentLighting !== isVisible || currentAtmosphere !== isVisible) {
        if (isVisible) {
          // Toggle ON: Show realistic day/night terminator
          viewer.scene.globe.enableLighting = true;
          viewer.scene.globe.showGroundAtmosphere = true;
          // Reset lighting to normal
          viewer.scene.globe.dynamicAtmosphereLighting = true;
          viewer.scene.globe.dynamicAtmosphereLightingFromSun = true;
          if (viewer.scene.skyAtmosphere) {
            viewer.scene.skyAtmosphere.show = true;
          }
        } else {
          // Toggle OFF: Return to default Cesium state (uniform bright lighting)
          viewer.scene.globe.enableLighting = false; // This gives uniform brightness
          viewer.scene.globe.showGroundAtmosphere = true; // Keep atmosphere for visual appeal
          // Reset dynamic atmosphere to defaults
          viewer.scene.globe.dynamicAtmosphereLighting = true;
          viewer.scene.globe.dynamicAtmosphereLightingFromSun = true;
          if (viewer.scene.skyAtmosphere) {
            viewer.scene.skyAtmosphere.show = true;
          }
          // Ensure HDR doesn't interfere with brightness
          viewer.scene.highDynamicRange = false;
        }

        // Force render to update lighting immediately
        viewer.scene.requestRender();

        console.log(
          `Day/night lighting ${isVisible ? "enabled" : "disabled"}`,
          {
            previousLighting: currentLighting,
            newLighting: isVisible,
            previousAtmosphere: currentAtmosphere,
            newAtmosphere: isVisible,
          }
        );
      }

      // Keep sun always visible - don't control sun visibility with lighting toggle
      if (viewer.scene.sun) {
        viewer.scene.sun.show = true; // Always keep sun visible
      }
    }

    // Handle ground stations specially - they need to be loaded from config
    if (entityType === "ground_station") {
      const entities = viewer.entities.values;
      const groundStations = entities.filter(
        (e: Entity) => e.id && e.id.toString().includes("ground_station")
      );

      if (isVisible) {
        // If toggling on and no ground stations exist, load them
        if (groundStations.length === 0) {
          await loadGroundStations();
        } else {
          // If they exist, just show them
          groundStations.forEach((entity: Entity) => {
            entity.show = true;
          });
        }
      } else {
        // Hide existing ground stations
        groundStations.forEach((entity: Entity) => {
          entity.show = false;
        });
      }
    }
  };

  const loadGroundStations = useCallback(
    async (forceVisible: boolean = true) => {
      if (!cesiumViewer || !cesiumViewer.cesiumElement) return;

      try {
        const data = await configApi.getGroundStations();

        if (data.success && data.ground_stations) {
          const viewer = cesiumViewer.cesiumElement;

          console.log(
            `Loading ${data.ground_stations.length} ground stations...`
          );

          // First, remove any existing ground stations to avoid duplicates
          const existingStations = viewer.entities.values.filter(
            (e: Entity) => e.id && e.id.toString().includes("ground_station")
          );
          existingStations.forEach((entity: Entity) => {
            viewer.entities.remove(entity);
          });

          // Create all ground station entities
          data.ground_stations.forEach((station: GroundStation) => {
            // Determine color based on station type
            const stationColor =
              station.type === "Primary" ? Color.GOLD : Color.ORANGE;

            viewer.entities.add({
              id: `ground_station_${
                station.id || station.name.toLowerCase().replace(/\s+/g, "_")
              }`,
              name: station.name,
              show: forceVisible, // Use the forceVisible parameter
              position: Cartesian3.fromDegrees(
                station.longitude,
                station.latitude,
                0
              ),
              billboard: {
                image:
                  "data:image/svg+xml;base64," +
                  btoa(`
                <svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
                  <!-- Ground Station Dish Icon -->
                  <circle cx="16" cy="26" r="5" fill="${
                    station.type === "Primary" ? "#FFD700" : "#FFA500"
                  }" stroke="#000" stroke-width="1.5"/>
                  <rect x="15" y="21" width="2" height="10" fill="#000"/>
                  <path d="M 16 21 Q 8 16 8 8 Q 16 13 24 8 Q 24 16 16 21" fill="${
                    station.type === "Primary" ? "#FFD700" : "#FFA500"
                  }" stroke="#000" stroke-width="1.5"/>
                  <circle cx="16" cy="14" r="2" fill="#FFF"/>
                </svg>
              `),
                width: 28,
                height: 28,
                heightReference: HeightReference.CLAMP_TO_GROUND,
                verticalOrigin: VerticalOrigin.BOTTOM,
              },
              point: {
                pixelSize: 10,
                color: stationColor,
                outlineColor: Color.BLACK,
                outlineWidth: 2,
                heightReference: HeightReference.CLAMP_TO_GROUND,
                show: false, // Show billboard instead of point
              },
              label: {
                text: station.name,
                font: "14px sans-serif",
                fillColor: Color.WHITE,
                outlineColor: Color.BLACK,
                outlineWidth: 3,
                style: LabelStyle.FILL_AND_OUTLINE,
                verticalOrigin: VerticalOrigin.BOTTOM,
                pixelOffset: new Cartesian2(0, -35),
                heightReference: HeightReference.CLAMP_TO_GROUND,
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
              },
              description: `
              <div style="background: rgba(17, 24, 39, 0.9); padding: 10px; border-radius: 5px;">
                <h3 style="color: #FFD700; margin: 0 0 10px 0;">${
                  station.name
                }</h3>
                <p style="color: #FFF; margin: 5px 0;"><strong>Type:</strong> ${
                  station.type || "Ground Station"
                }</p>
                <p style="color: #FFF; margin: 5px 0;"><strong>Location:</strong> ${station.latitude.toFixed(
                  4
                )}°, ${station.longitude.toFixed(4)}°</p>
                <p style="color: #FFF; margin: 5px 0;"><strong>Description:</strong> ${
                  station.description || "Communication ground station"
                }</p>
              </div>
            `,
            });
          });

          console.log(
            `${data.ground_stations.length} ground stations loaded successfully`
          );

          // Force render and visibility update using multiple strategies
          viewer.scene.requestRender();

          // Strategy 1: Immediate visibility update
          const groundStations = viewer.entities.values.filter(
            (e: Entity) => e.id && e.id.toString().includes("ground_station")
          );
          groundStations.forEach((entity: Entity) => {
            entity.show = forceVisible;
          });

          // Strategy 2: Force update via entity collection change
          viewer.entities.suspendEvents();
          viewer.entities.resumeEvents();

          // Strategy 3: Multiple render requests with delays
          viewer.scene.requestRender();
          requestAnimationFrame(() => {
            viewer.scene.requestRender();
            setTimeout(() => {
              groundStations.forEach((entity: Entity) => {
                entity.show = forceVisible;
              });
              viewer.scene.requestRender();
            }, 100);
          });
        }
      } catch (error) {
        console.error("Failed to load ground stations:", {
          message: error instanceof Error ? error.message : String(error),
          stack: error instanceof Error ? error.stack : undefined,
          name: error instanceof Error ? error.name : typeof error,
        });
      }
    },
    [cesiumViewer]
  );

  React.useEffect(() => {
    // Load workspaces from localStorage on mount
    const savedWorkspaces = JSON.parse(
      localStorage.getItem("mission_workspaces") || "[]"
    );
    savedWorkspaces.forEach((workspace: Workspace) => {
      dispatch({ type: "SAVE_WORKSPACE", payload: workspace });
    });
  }, []);

  const value: MissionContextType = {
    state,
    dispatch,
    validateTLE,
    analyzeMission,
    clearMission,
    navigateToPassWindow,
    navigateToImagingTime,
    setCesiumViewer,
    addSceneObject,
    updateSceneObject,
    removeSceneObject,
    setSelectedObject,
    selectObject: setSelectedObject, // Alias for consistency
    updateObject: updateSceneObject, // Alias for consistency
    removeObject: removeSceneObject, // Alias for consistency
    saveWorkspace,
    loadWorkspace,
    deleteWorkspace,
    flyToObject,
    toggleEntityVisibility,
  };

  return (
    <MissionContext.Provider value={value}>{children}</MissionContext.Provider>
  );
}

// Hook to use the context
export function useMission(): MissionContextType {
  const context = useContext(MissionContext);
  if (context === undefined) {
    throw new Error("useMission must be used within a MissionProvider");
  }
  return context;
}
