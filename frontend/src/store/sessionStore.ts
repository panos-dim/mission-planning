/**
 * Session Persistence Store
 *
 * Zustand store with persist middleware that saves the last mission session
 * (missionData + czmlData) to localStorage. This allows the full mission state
 * (satellite orbits, CZML visualization, timeline) to survive page refreshes
 * without requiring the user to explicitly save a workspace.
 */

import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import type { MissionData, CZMLPacket } from "../types";

interface SessionState {
  /** Last mission analysis result — null if no analysis has been run */
  lastMissionData: MissionData | null;
  /** CZML packets for the last mission — empty if no analysis */
  lastCzmlData: CZMLPacket[];
  /** Timestamp of last save (ISO) */
  savedAt: string | null;
  /** Workspace that owns the saved session */
  workspaceId: string | null;

  // Actions
  saveMissionSession: (
    missionData: MissionData,
    czmlData: CZMLPacket[],
    workspaceId: string
  ) => void;
  clearSession: () => void;
}

export const useSessionStore = create<SessionState>()(
  devtools(
    persist(
      (set) => ({
        lastMissionData: null,
        lastCzmlData: [],
        savedAt: null,
        workspaceId: null,

        saveMissionSession: (missionData, czmlData, workspaceId) =>
          set(
            {
              lastMissionData: missionData,
              lastCzmlData: czmlData,
              savedAt: new Date().toISOString(),
              workspaceId,
            },
            false,
            "saveMissionSession"
          ),

        clearSession: () =>
          set(
            { lastMissionData: null, lastCzmlData: [], savedAt: null, workspaceId: null },
            false,
            "clearSession"
          ),
      }),
      {
        name: "mission_session",
        version: 2,
        migrate: (persistedState) => {
          const state = (persistedState as Partial<SessionState> | undefined) ?? {};
          return {
            lastMissionData: state.lastMissionData ?? null,
            lastCzmlData: state.lastCzmlData ?? [],
            savedAt: state.savedAt ?? null,
            workspaceId: state.workspaceId ?? null,
          };
        },
      }
    ),
    {
      name: "SessionStore",
      enabled: import.meta.env?.DEV ?? false,
    }
  )
);
