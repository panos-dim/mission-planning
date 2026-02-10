import React, { useEffect, useRef, useState } from "react";
import { Viewer, CzmlDataSource } from "resium";
import {
  JulianDate,
  ClockRange,
  ShadowMode,
  Entity,
  ScreenSpaceEventType,
  ScreenSpaceEventHandler,
  defined,
  Ellipsoid,
  SceneMode as CesiumSceneMode,
  Math as CesiumMath,
  Cartesian2,
  OpenStreetMapImageryProvider,
  Cartesian3,
  Color,
  VerticalOrigin,
  HorizontalOrigin,
  LabelStyle,
} from "cesium";
import { useMission } from "../../context/MissionContext";
import { SceneObject } from "../../types";
import { SceneMode, useVisStore } from "../../store/visStore";
import { useTargetAddStore } from "../../store/targetAddStore";
import { usePreviewTargetsStore } from "../../store/previewTargetsStore";
import { useSwathStore } from "../../store/swathStore";
import { useMapClickToCartographic } from "../../hooks/useMapClickToCartographic";
import { useConflictMapHighlight } from "../../hooks/useConflictMapHighlight";
import { useRepairMapHighlight } from "../../hooks/useRepairMapHighlight";
import { useUnifiedMapHighlight } from "../../hooks/useUnifiedMapHighlight";
import SlewVisualizationLayer from "./SlewVisualizationLayer";
import { SlewCanvasOverlay } from "./SlewCanvasOverlay";
import SwathDebugOverlay from "./SwathDebugOverlay";
import debug from "../../utils/debug";

/**
 * Extract SAR swath properties from entity
 */
function extractSwathProperties(entity: Entity): {
  opportunityId: string | null;
  targetId: string | null;
  runId: string | null;
} | null {
  if (!entity.properties) return null;
  try {
    const entityType = entity.properties.entity_type?.getValue(null);
    if (entityType !== "sar_swath") return null;
    return {
      opportunityId: entity.properties.opportunity_id?.getValue(null) ?? null,
      targetId: entity.properties.target_id?.getValue(null) ?? null,
      runId: entity.properties.run_id?.getValue(null) ?? null,
    };
  } catch {
    return null;
  }
}

/**
 * Check if entity is a SAR swath
 */
function isSarSwathEntity(entity: Entity): boolean {
  if (!entity.id || typeof entity.id !== "string") return false;
  return entity.id.startsWith("sar_swath_");
}

interface GlobeViewportProps {
  mode: SceneMode;
  viewportId: "primary" | "secondary";
  sharedCzml?: any[]; // Optional shared CZML data
}

const GlobeViewport: React.FC<GlobeViewportProps> = ({
  mode,
  viewportId,
  sharedCzml,
}) => {
  const { state, addSceneObject, selectObject, setCesiumViewer } = useMission();
  const viewerRef = useRef<any>(null);
  const eventHandlerRef = useRef<any>(null);
  const clockConfiguredRef = useRef<string | null>(null);
  const lightingInitializedRef = useRef<string | null>(null);
  const [isUsingFallback, setIsUsingFallback] = useState(false);
  const imageryReplacedRef = useRef(false);

  // Create OSM provider immediately (needed as emergency fallback)
  const [osmProvider] = useState(() => {
    return new OpenStreetMapImageryProvider({
      url: "https://a.tile.openstreetmap.org/",
    });
  });

  // Target add mode state
  const { isAddMode, setPendingTarget, openDetailsSheet } = useTargetAddStore();
  const { pickCartographic } = useMapClickToCartographic();

  // Preview targets store for showing targets before mission analysis
  const {
    targets: previewTargets,
    hidePreview,
    setHidePreview,
  } = usePreviewTargetsStore();
  const previewEntitiesRef = useRef<string[]>([]);

  // Store hooks
  const {
    selectedOpportunityId,
    activeLayers,
    setTimeWindow,
    viewMode,
    clockTime,
    clockShouldAnimate,
    clockMultiplier,
    setClockState,
    setSelectedOpportunity,
  } = useVisStore();

  // Swath store for SAR swath selection and debug
  const { selectSwath, setHoveredSwath, updateDebugInfo, debugEnabled } =
    useSwathStore();

  // Conflict highlighting on map (PR-CONFLICT-UX-02)
  useConflictMapHighlight(viewerRef);

  // Repair diff highlighting on map (PR-REPAIR-UX-01)
  useRepairMapHighlight(viewerRef);

  // Unified map highlighting (PR-MAP-HIGHLIGHT-01)
  // Provides consistent entity ID resolution, ghost clone fallback, and timeline focus reliability
  useUnifiedMapHighlight(viewerRef);

  // Use shared CZML if provided, otherwise use state CZML
  const czmlData = sharedCzml || state.czmlData;
  const czmlDataSourceRef = useRef<any>(null);

  // Render preview targets on the map before mission analysis
  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer || !viewer.entities) return;

    // Hide preview targets when CZML data is loaded (mission analyzed)
    const hasCzmlData = czmlData && czmlData.length > 0;
    if (hasCzmlData && !hidePreview) {
      setHidePreview(true);
    } else if (!hasCzmlData && hidePreview) {
      setHidePreview(false);
    }

    // Remove old preview entities
    previewEntitiesRef.current.forEach((id) => {
      const entity = viewer.entities.getById(id);
      if (entity) {
        viewer.entities.remove(entity);
      }
    });
    previewEntitiesRef.current = [];

    // Don't show preview if CZML is loaded
    if (hasCzmlData) return;

    // Add preview target entities - matching backend CZML format
    previewTargets.forEach((target, index) => {
      const entityId = `preview_target_${index}`;

      // Calculate darker stroke color (same as backend)
      const hexColor = (target.color || "#EF4444").replace("#", "");
      const r = Math.max(0, parseInt(hexColor.substring(0, 2), 16) - 40);
      const g = Math.max(0, parseInt(hexColor.substring(2, 4), 16) - 40);
      const b = Math.max(0, parseInt(hexColor.substring(4, 6), 16) - 40);
      const strokeColor = `#${r.toString(16).padStart(2, "0")}${g
        .toString(16)
        .padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;

      // Create SVG billboard matching backend exactly
      const svgPin = `<svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">
        <path d="M16 0C9.4 0 4 5.4 4 12c0 8 12 28 12 28s12-20 12-28c0-6.6-5.4-12-12-12z"
              fill="${
                target.color || "#EF4444"
              }" stroke="${strokeColor}" stroke-width="2"/>
        <circle cx="16" cy="12" r="5" fill="#FFF"/>
      </svg>`;
      const svgBase64 = "data:image/svg+xml;base64," + btoa(svgPin);

      viewer.entities.add({
        id: entityId,
        name: target.name,
        position: Cartesian3.fromDegrees(target.longitude, target.latitude, 0),
        billboard: {
          image: svgBase64,
          width: 20,
          height: 25,
          verticalOrigin: VerticalOrigin.BOTTOM,
          // No heightReference, no scaleByDistance - matches backend CZML
        },
        label: {
          text: target.name,
          font: "14px sans-serif",
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 3,
          style: LabelStyle.FILL_AND_OUTLINE,
          horizontalOrigin: HorizontalOrigin.CENTER,
          verticalOrigin: VerticalOrigin.BOTTOM,
          pixelOffset: new Cartesian2(0, -30),
          // No scaleByDistance - matches backend CZML
        },
      });

      previewEntitiesRef.current.push(entityId);
    });

    // Force render
    viewer.scene.requestRender();
  }, [previewTargets, czmlData, hidePreview, setHidePreview]);

  // Smart fallback: Only use OSM if Cesium Ion actually fails
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      const viewer = viewerRef.current?.cesiumElement;

      if (!viewer?.imageryLayers || imageryReplacedRef.current) return;

      try {
        const baseLayer = viewer.imageryLayers.get(0);

        // Only switch to fallback if Ion has actual errors
        if (baseLayer && !baseLayer.ready && baseLayer.errorEvent) {
          console.warn(
            `[${viewportId}] Cesium Ion failed, switching to OSM fallback`,
          );
          imageryReplacedRef.current = true;
          viewer.imageryLayers.removeAll();
          viewer.imageryLayers.addImageryProvider(osmProvider);
          setIsUsingFallback(true);
        }
      } catch (error) {
        console.error(`[${viewportId}] Error checking imagery:`, error);
      }
    }, 8000); // 8 second timeout

    return () => clearTimeout(timeoutId);
  }, [viewportId, osmProvider]);

  // Initialize viewer with proper scene mode
  useEffect(() => {
    if (viewerRef.current?.cesiumElement) {
      const viewer = viewerRef.current.cesiumElement;

      // Wait for viewer to be fully initialized
      if (!viewer.scene || !viewer.scene.canvas) {
        return;
      }

      const cesiumMode =
        mode === "2D" ? CesiumSceneMode.SCENE2D : CesiumSceneMode.SCENE3D;
      // Check if morphTo method is available and scene mode needs changing
      if (viewer.scene.morphTo && viewer.scene.mode !== cesiumMode) {
        try {
          viewer.scene.morphTo(cesiumMode, 0); // Immediate morph

          // 2D-specific fixes after morphing
          if (mode === "2D" && viewer.scene.mapProjection) {
            // Force scene render after 2D morph to ensure proper coordinate projection
            requestAnimationFrame(() => {
              viewer.scene.requestRender();
            });
          }
        } catch (error) {
          console.warn(`[${viewportId}] Error morphing to ${mode}:`, error);
        }
      }

      try {
        // Configure camera controls based on mode
        if (mode === "2D") {
          // 2D specific configuration
          if (viewer.scene.screenSpaceCameraController) {
            viewer.scene.screenSpaceCameraController.enableRotate = false;
            viewer.scene.screenSpaceCameraController.enableTilt = false;
            viewer.scene.screenSpaceCameraController.minimumZoomDistance = 1;
            viewer.scene.screenSpaceCameraController.maximumZoomDistance = 100000000;
          }
        } else {
          // 3D specific configuration
          if (viewer.scene.screenSpaceCameraController) {
            viewer.scene.screenSpaceCameraController.enableRotate = true;
            viewer.scene.screenSpaceCameraController.enableTilt = true;
            viewer.scene.screenSpaceCameraController.minimumZoomDistance = 1;
            viewer.scene.screenSpaceCameraController.maximumZoomDistance = 100000000;
          }
        }
      } catch (error) {
        console.warn(
          `[${viewportId}] Error configuring camera controls:`,
          error,
        );
      }
    }
  }, [mode, viewportId]);

  // Register primary viewport's viewer with MissionContext for flyToObject
  // Use an interval to check for viewer readiness since it may not be available immediately
  useEffect(() => {
    if (viewportId !== "primary") return;

    let registered = false;
    const checkAndRegister = () => {
      if (registered) return;
      if (viewerRef.current?.cesiumElement) {
        const viewer = viewerRef.current.cesiumElement;
        if (viewer.scene && viewer.scene.canvas) {
          setCesiumViewer(viewerRef.current);
          registered = true;
          console.log(
            "[GlobeViewport] Registered primary viewer with MissionContext",
          );
        }
      }
    };

    // Try immediately
    checkAndRegister();

    // Also check after a short delay in case viewer isn't ready yet
    const timeoutId = setTimeout(checkAndRegister, 500);
    const intervalId = setInterval(checkAndRegister, 1000);

    // Stop checking after 5 seconds
    const cleanupId = setTimeout(() => {
      clearInterval(intervalId);
    }, 5000);

    // Cleanup on unmount
    return () => {
      clearTimeout(timeoutId);
      clearInterval(intervalId);
      clearTimeout(cleanupId);
      if (viewportId === "primary") {
        setCesiumViewer(null);
      }
    };
  }, [viewportId, setCesiumViewer]);

  // Clock synchronization - works in both single and split view
  // OPTIMIZED: Throttled updates to reduce CPU usage
  useEffect(() => {
    if (
      !viewerRef.current?.cesiumElement ||
      !czmlData ||
      czmlData.length === 0
    ) {
      return;
    }

    const viewer = viewerRef.current.cesiumElement;
    let lastUpdateTime = 0;
    let lastAnimateState = viewer.clock.shouldAnimate;
    let lastMultiplier = viewer.clock.multiplier;

    // Wait for viewer to be fully ready before setting up clock sync
    const setupClockSync = () => {
      // Primary viewport (or single view) drives the clock by sending complete state to store
      if (viewportId === "primary" || viewMode === "single") {
        debug.verbose(`[${viewportId}] Clock sync enabled as PRIMARY`);

        // Throttled clock handler - only update every 500ms or on state changes
        const clockUpdateHandler = () => {
          const now = Date.now();
          const animateChanged =
            viewer.clock.shouldAnimate !== lastAnimateState;
          const multiplierChanged = viewer.clock.multiplier !== lastMultiplier;

          // Only update if: state changed OR 500ms passed (for time scrubbing)
          if (
            animateChanged ||
            multiplierChanged ||
            now - lastUpdateTime > 500
          ) {
            lastUpdateTime = now;
            lastAnimateState = viewer.clock.shouldAnimate;
            lastMultiplier = viewer.clock.multiplier;

            setClockState(
              viewer.clock.currentTime,
              viewer.clock.shouldAnimate,
              viewer.clock.multiplier,
            );
          }
        };

        // Listen to clock tick but with throttling built-in
        viewer.clock.onTick.addEventListener(clockUpdateHandler);

        return () => {
          if (viewer && viewer.clock) {
            viewer.clock.onTick.removeEventListener(clockUpdateHandler);
          }
        };
      }
    };

    // Delay setup to ensure viewer is fully initialized
    const timer = setTimeout(setupClockSync, 1000);
    return () => clearTimeout(timer);
  }, [viewportId, viewMode, setClockState, czmlData]);

  // Secondary viewport syncs complete clock state from store
  useEffect(() => {
    if (
      !viewerRef.current?.cesiumElement ||
      viewportId === "primary" ||
      viewMode === "single"
    ) {
      return;
    }

    const viewer = viewerRef.current.cesiumElement;

    // Sync complete clock state from store to secondary viewport
    if (viewer.clock) {
      // Only log when animation state changes
      // Update all clock properties to match the primary viewport
      if (clockTime) {
        viewer.clock.currentTime = clockTime;
      }
      viewer.clock.shouldAnimate = clockShouldAnimate;
      viewer.clock.multiplier = clockMultiplier;

      // Silently sync clock state
    } else {
      debug.warn(
        `[${viewportId}] Cannot sync clock - viewer.clock not available`,
      );
    }
  }, [clockTime, clockShouldAnimate, clockMultiplier, viewportId, viewMode]);

  // 2D rendering fix - force proper entity positioning in 2D mode
  // OPTIMIZED: Reduced render calls, single timeout chain with proper cleanup
  useEffect(() => {
    if (!viewerRef.current?.cesiumElement || mode !== "2D") return;

    const timeouts: ReturnType<typeof setTimeout>[] = [];

    // Single render fix with minimal calls
    const applyRenderFix = () => {
      const v = viewerRef.current?.cesiumElement;
      if (!v?.scene) return;

      debug.verbose(`[${viewportId}] Applying 2D rendering fix`);
      v.scene.requestRender();

      // One delayed render after scene stabilizes
      const t1 = setTimeout(() => {
        const v2 = viewerRef.current?.cesiumElement;
        if (v2?.scene) {
          v2.scene.requestRender();
        }
      }, 500);
      timeouts.push(t1);
    };

    const timer = setTimeout(applyRenderFix, 300);
    timeouts.push(timer);

    return () => timeouts.forEach((t) => clearTimeout(t));
  }, [mode, czmlData, viewportId]);

  // External updates (like navigateToPass) for all viewports
  useEffect(() => {
    if (!viewerRef.current?.cesiumElement || !clockTime) return;

    const viewer = viewerRef.current.cesiumElement;

    // Update viewer clock when store clock changes from external sources
    if (viewer.clock) {
      const currentTime = viewer.clock.currentTime;
      // Only update if the time is actually different to avoid circular updates
      if (!clockTime.equals(currentTime)) {
        viewer.clock.currentTime = clockTime;
      }
    }
  }, [clockTime, viewportId]);

  // Layer visibility synchronization
  useEffect(() => {
    if (!viewerRef.current?.cesiumElement || !czmlDataSourceRef.current) return;

    const viewer = viewerRef.current.cesiumElement;
    const dataSource = czmlDataSourceRef.current;

    // Apply layer visibility
    if (dataSource && dataSource.entities) {
      dataSource.entities.values.forEach((entity: Entity) => {
        try {
          // Coverage areas
          if (entity.name?.includes("Coverage Area")) {
            entity.show = activeLayers.coverageAreas;
          }
          // Pointing cone
          else if (entity.id === "pointing_cone") {
            entity.show = activeLayers.pointingCone;
          }
          // Satellite entity - keep visible but control path separately
          else if (entity.id?.startsWith("sat_")) {
            // Always show the satellite point itself
            entity.show = true;
            // Path is hidden in CZML, using ground track polyline instead
          }
          // Ground track (dynamic path at ground level)
          else if (entity.id === "satellite_ground_track") {
            entity.show = true; // Always show entity
            if (entity.path) {
              (entity.path.show as any) = activeLayers.orbitLine;
            }
          }
          // Targets
          else if (
            entity.name?.includes("Target") ||
            entity.id?.startsWith("target_")
          ) {
            entity.show = activeLayers.targets;
            if (entity.label) {
              // Use type assertion to handle Cesium property system
              (entity.label.show as any) = activeLayers.labels;
            }
          }
          // Other labels
          else if (entity.label && !entity.name?.includes("Target")) {
            // Use type assertion to handle Cesium property system
            (entity.label.show as any) = activeLayers.labels;
          }
        } catch (error) {
          console.warn(
            `[${viewportId}] Error setting entity visibility for ${
              entity.name || entity.id
            }:`,
            error,
          );
        }
      });
    }

    // Day/night lighting
    if (viewer.scene.globe) {
      viewer.scene.globe.enableLighting = activeLayers.dayNightLighting;
      viewer.scene.globe.showGroundAtmosphere = activeLayers.atmosphere;
      if (viewer.scene.sun) {
        viewer.scene.sun.show = activeLayers.dayNightLighting;
      }

      // Atmosphere (sky dome)
      if (viewer.scene.skyAtmosphere) {
        viewer.scene.skyAtmosphere.show = activeLayers.atmosphere;
      }

      // Fog effect
      viewer.scene.fog.enabled = activeLayers.fog;
      viewer.scene.fog.density = 0.0002;

      // Grid lines (graticule) - uses imagery layer
      // Note: Grid lines would require a custom imagery provider
    }

    // Post-processing effects
    if (viewer.scene.postProcessStages) {
      // FXAA anti-aliasing
      if (viewer.scene.postProcessStages.fxaa) {
        viewer.scene.postProcessStages.fxaa.enabled = activeLayers.fxaa;
      }

      // Bloom effect
      if (viewer.scene.postProcessStages.bloom) {
        viewer.scene.postProcessStages.bloom.enabled = activeLayers.bloom;
        viewer.scene.postProcessStages.bloom.glowOnly = false;
        viewer.scene.postProcessStages.bloom.contrast = 128;
        viewer.scene.postProcessStages.bloom.brightness = -0.3;
        viewer.scene.postProcessStages.bloom.delta = 1.0;
        viewer.scene.postProcessStages.bloom.sigma = 3.78;
        viewer.scene.postProcessStages.bloom.stepSize = 5.0;
      }
    }
  }, [activeLayers, viewportId, mode]);

  // Initialize clock when mission data is available
  useEffect(() => {
    try {
      if (state.missionData && viewerRef.current?.cesiumElement) {
        const viewer = viewerRef.current.cesiumElement;
        const start = JulianDate.fromIso8601(state.missionData.start_time);
        const stop = JulianDate.fromIso8601(state.missionData.end_time);

        const missionId = `${state.missionData.start_time}_${state.missionData.end_time}`;
        if (clockConfiguredRef.current === missionId) {
          return;
        }
        clockConfiguredRef.current = missionId;

        // Apply touch-action CSS for performance
        if (viewer.scene && viewer.scene.canvas) {
          const canvas = viewer.scene.canvas;
          canvas.style.touchAction = "pan-x pan-y pinch-zoom";
          canvas.style.willChange = "transform";
        }

        // Configure clock
        requestIdleCallback(
          () => {
            try {
              if (!viewer.clock) {
                console.warn(
                  `[${viewportId}] Clock not available for configuration`,
                );
                return;
              }
              viewer.clock.startTime = start;
              viewer.clock.stopTime = stop;
              viewer.clock.currentTime = start;
              viewer.clock.clockRange = ClockRange.CLAMPED;
              viewer.clock.multiplier = 2; // Default 2x speed for better visualization
              viewer.clock.shouldAnimate = false;

              // Update store time window
              setTimeWindow(start, stop);

              // Synchronize timeline
              if (viewer.timeline) {
                viewer.timeline.zoomTo(start, stop);
                requestIdleCallback(
                  () => {
                    if (viewer.timeline) {
                      viewer.timeline.resize();
                    }
                  },
                  { timeout: 100 },
                );
              }

              // Resize animation widget
              if (viewer.animation) {
                requestIdleCallback(
                  () => {
                    if (viewer.animation && viewer.animation.resize) {
                      viewer.animation.resize();
                    }
                  },
                  { timeout: 100 },
                );
              }

              debug.verbose(`[${viewportId}] Clock configured`);
            } catch (error) {
              console.error(`[${viewportId}] Error configuring clock:`, error);
            }
          },
          { timeout: 150 },
        );
      }
    } catch (error) {
      console.error(`[${viewportId}] Error in clock setup:`, error);
    }
  }, [state.missionData, czmlData, viewportId, mode, setTimeWindow]);

  // Entity click handler (with target add mode support)
  useEffect(() => {
    if (viewerRef.current?.cesiumElement) {
      const viewer = viewerRef.current.cesiumElement;

      if (!viewer.scene || !viewer.scene.canvas) {
        return;
      }

      try {
        // Clean up existing handler
        if (eventHandlerRef.current && !eventHandlerRef.current.isDestroyed()) {
          eventHandlerRef.current.destroy();
          eventHandlerRef.current = null;
        }

        // Create new handler
        eventHandlerRef.current = new ScreenSpaceEventHandler(
          viewer.scene.canvas,
        );

        eventHandlerRef.current.setInputAction((click: any) => {
          // Handle target add mode
          if (isAddMode) {
            const windowPosition = new Cartesian2(
              click.position.x,
              click.position.y,
            );
            const clickedLocation = pickCartographic(viewer, windowPosition);

            if (clickedLocation) {
              debug.info(`Target placed: ${clickedLocation.formatted.decimal}`);

              // Create pending target
              const pendingTarget = {
                id: `pending-${Date.now()}`,
                latitude: clickedLocation.latitude,
                longitude: clickedLocation.longitude,
              };

              setPendingTarget(pendingTarget);
              openDetailsSheet();
            }
            return;
          }

          // Normal entity selection mode
          const pickedObject = viewer.scene.pick(click.position);

          if (defined(pickedObject) && pickedObject.id instanceof Entity) {
            const entity = pickedObject.id;

            // ===== SAR SWATH PICKING (deterministic selection) =====
            if (isSarSwathEntity(entity)) {
              const swathProps = extractSwathProperties(entity);
              if (swathProps?.opportunityId) {
                // Update debug info
                updateDebugInfo({
                  pickingHitType: "sar_swath",
                  lastPickTime: Date.now(),
                });

                // Select the swath in swath store
                selectSwath(entity.id, swathProps.opportunityId);

                // Sync with visStore for cross-panel sync
                setSelectedOpportunity(swathProps.opportunityId);

                debug.info(
                  `[SwathPicking] Selected swath: ${swathProps.opportunityId} (target: ${swathProps.targetId})`,
                );
              }
              return; // Don't process as regular entity
            }

            // Ignore non-interactive entities (visualization helpers, not mission objects)
            if (
              entity.name?.includes("Coverage Area") ||
              entity.id === "pointing_cone" ||
              entity.name === "Sensor Cone" ||
              entity.id?.includes("agility_envelope") ||
              entity.id?.includes("coverage") ||
              entity.id?.includes("ground_track") ||
              entity.id?.includes("footprint")
            ) {
              return;
            }

            debug.verbose(`Entity clicked: ${entity.name || entity.id}`);

            // Check for existing object
            const existingObject = state.sceneObjects.find((obj) => {
              if (obj.entityId === entity.id) return true;
              if (obj.name === entity.name) return true;
              if (obj.id === entity.id) return true;
              if (obj.id === `entity_${entity.id}`) return true;
              if (
                entity.id &&
                entity.id.startsWith("target_") &&
                obj.id === entity.id
              )
                return true;
              return false;
            });

            if (!existingObject) {
              // Create new scene object
              const newObject: SceneObject = {
                id: `entity_${entity.id}`,
                name: entity.name || entity.id || "Unknown Entity",
                type: entity.name?.includes("Satellite")
                  ? "satellite"
                  : "target",
                entityId: entity.id,
                visible: true,
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
              };

              // Extract position if available
              if (entity.position) {
                const position = entity.position.getValue(
                  viewer.clock.currentTime,
                );
                if (position) {
                  const cartographic =
                    Ellipsoid.WGS84.cartesianToCartographic(position);
                  newObject.position = {
                    latitude: CesiumMath.toDegrees(cartographic.latitude),
                    longitude: CesiumMath.toDegrees(cartographic.longitude),
                    altitude: cartographic.height,
                  };
                }
              }

              addSceneObject(newObject);
              selectObject(newObject.id);
            } else {
              // Select existing object
              selectObject(existingObject.id);
            }
          } else {
            // Clicked on empty space - deselect
            selectObject(null);
          }
        }, ScreenSpaceEventType.LEFT_CLICK);

        // Add mouse move handler for swath hover highlighting
        eventHandlerRef.current.setInputAction(
          (movement: { endPosition: Cartesian2 }) => {
            const pickedObject = viewer.scene.pick(movement.endPosition);

            if (defined(pickedObject) && pickedObject.id instanceof Entity) {
              const entity = pickedObject.id;
              if (isSarSwathEntity(entity)) {
                const swathProps = extractSwathProperties(entity);
                if (swathProps?.opportunityId) {
                  setHoveredSwath(entity.id, swathProps.opportunityId);
                  return;
                }
              }
            }
            // Clear hover when not over a swath
            setHoveredSwath(null, null);
          },
          ScreenSpaceEventType.MOUSE_MOVE,
        );
      } catch (error) {
        console.error(`[${viewportId}] Error setting up click handler:`, error);
      }

      return () => {
        if (eventHandlerRef.current && !eventHandlerRef.current.isDestroyed()) {
          try {
            eventHandlerRef.current.destroy();
            eventHandlerRef.current = null;
          } catch (error) {
            console.error(
              `[${viewportId}] Error cleaning up event handler:`,
              error,
            );
          }
        }
      };
    }
  }, [
    state.sceneObjects,
    addSceneObject,
    selectObject,
    viewportId,
    isAddMode,
    pickCartographic,
    setPendingTarget,
    openDetailsSheet,
    selectSwath,
    setSelectedOpportunity,
    setHoveredSwath,
    updateDebugInfo,
  ]);

  // Focus on opportunity when selected
  useEffect(() => {
    if (!selectedOpportunityId || !viewerRef.current?.cesiumElement) return;

    // Find the entity corresponding to the selected opportunity
    // This would need to be implemented based on your opportunity ID scheme
    // For now, we'll just log it
    debug.verbose(`Focus on opportunity: ${selectedOpportunityId}`);

    // Example: Focus on a location if we have coordinates
    // You would extract these from your opportunity data
    /*
    if (mode === '2D') {
      viewer.camera.setView({
        destination: Rectangle.fromDegrees(lon - 5, lat - 5, lon + 5, lat + 5)
      })
    } else {
      viewer.camera.flyTo({
        destination: Cartesian3.fromDegrees(lon, lat, 1000000),
        duration: 2.0
      })
    }
    */
  }, [selectedOpportunityId, viewportId, mode]);

  return (
    <div className="w-full h-full relative">
      <Viewer
        ref={viewerRef}
        full
        timeline={viewportId === "primary"} // Only show timeline on primary viewport
        animation={viewportId === "primary"} // Only show animation on primary viewport
        homeButton={false}
        sceneModePicker={false}
        navigationHelpButton={false}
        baseLayerPicker={false}
        geocoder={false}
        infoBox={false}
        selectionIndicator={true}
        shadows={false}
        terrainShadows={ShadowMode.DISABLED}
        requestRenderMode={true}
        maximumRenderTimeChange={0.0}
        automaticallyTrackDataSourceClocks={false}
        sceneMode={
          mode === "2D" ? CesiumSceneMode.SCENE2D : CesiumSceneMode.SCENE3D
        }
        onSelectedEntityChange={undefined}
      >
        {czmlData && czmlData.length > 0 && (
          <CzmlDataSource
            ref={czmlDataSourceRef}
            data={czmlData}
            onLoad={(dataSource) => {
              const missionId = state.missionData
                ? `${state.missionData.start_time}_${state.missionData.end_time}`
                : null;

              debug.verbose(`[${viewportId}] CZML loaded`);

              // Apply initial layer visibility
              if (dataSource && dataSource.entities) {
                dataSource.entities.values.forEach((entity: any) => {
                  // Hide coverage areas by default
                  if (entity.name && entity.name.includes("Coverage Area")) {
                    entity.show = false;
                  }

                  // Apply ground track path visibility from layer settings
                  if (entity.id === "satellite_ground_track" && entity.path) {
                    entity.path.show = activeLayers.orbitLine;
                  }
                });
              }

              // Enable lighting for imaging missions
              if (
                state.missionData?.mission_type === "imaging" &&
                viewerRef.current?.cesiumElement
              ) {
                const viewer = viewerRef.current.cesiumElement;

                if (missionId && lightingInitializedRef.current !== missionId) {
                  lightingInitializedRef.current = missionId;

                  viewer.scene.globe.enableLighting = true;
                  viewer.scene.globe.showGroundAtmosphere = true;
                  if (viewer.scene.sun) {
                    viewer.scene.sun.show = true;
                  }

                  viewer.scene.requestRender();

                  debug.verbose(
                    `[${viewportId}] Day/night lighting initialized`,
                  );
                }
              }

              // Clock configuration after CZML load
              if (
                viewerRef.current?.cesiumElement &&
                state.missionData &&
                missionId &&
                clockConfiguredRef.current !== missionId
              ) {
                const viewer = viewerRef.current.cesiumElement;
                clockConfiguredRef.current = missionId;

                // Force reconfigure clock after CZML load to ensure proper synchronization
                requestIdleCallback(
                  () => {
                    if (viewer.clock && state.missionData) {
                      const start = JulianDate.fromIso8601(
                        state.missionData.start_time.replace("+00:00", "Z"),
                      );
                      const stop = JulianDate.fromIso8601(
                        state.missionData.end_time.replace("+00:00", "Z"),
                      );

                      viewer.clock.startTime = start;
                      viewer.clock.stopTime = stop;
                      viewer.clock.currentTime = start;
                      viewer.clock.clockRange = ClockRange.CLAMPED;
                      viewer.clock.multiplier = 2; // Default 2x speed for better visualization
                      viewer.clock.shouldAnimate = false;

                      if (viewer.timeline) {
                        viewer.timeline.zoomTo(start, stop);
                        viewer.timeline.updateFromClock();
                      }
                    }
                  },
                  { timeout: 150 },
                );
              }
            }}
            onError={(_, error) => {
              console.error(`[${viewportId}] CZML DataSource error:`, error);
            }}
          />
        )}

        {/* Slew Visualization Layer - controls and metrics only */}
        {viewportId === "primary" && <SlewVisualizationLayer />}

        {/* Slew Canvas Overlay - 2D canvas rendering (no entities) */}
        {viewportId === "primary" && <SlewCanvasOverlay />}
      </Viewer>

      {/* Loading overlay */}
      {state.isLoading && viewportId === "primary" && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900/90 backdrop-blur-sm rounded-lg p-6 flex items-center space-x-3">
            <div className="loading-spinner"></div>
            <span className="text-white">Loading mission data...</span>
          </div>
        </div>
      )}

      {/* Fallback imagery notification */}
      {isUsingFallback && viewportId === "primary" && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-40">
          <div className="bg-blue-900/90 backdrop-blur-sm border border-blue-600 rounded-lg px-4 py-2 flex items-center space-x-2 shadow-lg">
            <svg
              className="w-5 h-5 text-blue-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-blue-100 text-sm font-medium">
              Using OpenStreetMap base layer due to Cesium Ion connectivity
              issues
            </span>
          </div>
        </div>
      )}

      {/* SAR Swath Debug Overlay (dev mode only) */}
      {viewportId === "primary" && debugEnabled && <SwathDebugOverlay />}
    </div>
  );
};

export default GlobeViewport;
