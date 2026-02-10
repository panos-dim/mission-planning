import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import type { Workspace, SceneObject, MissionData, CZMLPacket } from "../types";

interface WorkspaceState {
  workspaces: Workspace[];
  activeWorkspace: string | null;
}

interface WorkspaceActions {
  saveWorkspace: (workspace: Workspace) => void;
  loadWorkspace: (id: string) => Workspace | undefined;
  deleteWorkspace: (id: string) => void;
  setActiveWorkspace: (id: string | null) => void;
  createWorkspace: (
    name: string,
    sceneObjects: SceneObject[],
    missionData: MissionData | null,
    czmlData: CZMLPacket[]
  ) => Workspace;
}

export type WorkspaceStore = WorkspaceState & WorkspaceActions;

export const useWorkspaceStore = create<WorkspaceStore>()(
  devtools(
    persist(
      (set, get) => ({
        // State
        workspaces: [],
        activeWorkspace: null,

        // Actions
        saveWorkspace: (workspace) =>
          set(
            (state) => {
              const existingIndex = state.workspaces.findIndex(
                (w) => w.id === workspace.id
              );
              const updatedWorkspaces =
                existingIndex >= 0
                  ? state.workspaces.map((w) =>
                      w.id === workspace.id ? workspace : w
                    )
                  : [...state.workspaces, workspace];
              return {
                workspaces: updatedWorkspaces,
                activeWorkspace: workspace.id,
              };
            },
            false,
            "saveWorkspace"
          ),

        loadWorkspace: (id) => {
          const workspace = get().workspaces.find((w) => w.id === id);
          if (workspace) {
            set({ activeWorkspace: workspace.id }, false, "loadWorkspace");
          }
          return workspace;
        },

        deleteWorkspace: (id) =>
          set(
            (state) => ({
              workspaces: state.workspaces.filter((w) => w.id !== id),
              activeWorkspace:
                state.activeWorkspace === id ? null : state.activeWorkspace,
            }),
            false,
            "deleteWorkspace"
          ),

        setActiveWorkspace: (id) =>
          set({ activeWorkspace: id }, false, "setActiveWorkspace"),

        createWorkspace: (name, sceneObjects, missionData, czmlData) => {
          const workspace: Workspace = {
            id: `workspace_${Date.now()}`,
            name,
            createdAt: new Date().toISOString(),
            sceneObjects,
            missionData,
            czmlData,
          };
          get().saveWorkspace(workspace);
          return workspace;
        },
      }),
      {
        name: "mission_workspaces",
      }
    ),
    {
      name: "WorkspaceStore",
      enabled: import.meta.env?.DEV ?? false,
    }
  )
);
