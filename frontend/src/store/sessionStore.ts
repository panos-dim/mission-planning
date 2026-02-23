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

  // Actions
  saveMissionSession: (
    missionData: MissionData,
    czmlData: CZMLPacket[]
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

        saveMissionSession: (missionData, czmlData) =>
          set(
            {
              lastMissionData: missionData,
              lastCzmlData: czmlData,
              savedAt: new Date().toISOString(),
            },
            false,
            "saveMissionSession"
          ),

        clearSession: () =>
          set(
            { lastMissionData: null, lastCzmlData: [], savedAt: null },
            false,
            "clearSession"
          ),
      }),
      {
        name: "mission_session",
      }
    ),
    {
      name: "SessionStore",
      enabled: import.meta.env?.DEV ?? false,
    }
  )
);
