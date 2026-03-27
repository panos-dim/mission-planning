import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import type { Workspace, SceneObject, MissionData, CZMLPacket } from "../types";

interface WorkspaceState {
  workspaces: Workspace[];
  activeWorkspace: string | null;
  activeWorkspaceName: string | null;
}

interface WorkspaceActions {
  saveWorkspace: (workspace: Workspace) => void;
  loadWorkspace: (id: string) => Workspace | undefined;
  deleteWorkspace: (id: string) => void;
  setActiveWorkspace: (id: string | null, name?: string | null) => void;
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
        activeWorkspaceName: null,

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
                activeWorkspaceName: workspace.name,
              };
            },
            false,
            "saveWorkspace"
          ),

        loadWorkspace: (id) => {
          const workspace = get().workspaces.find((w) => w.id === id);
          if (workspace) {
            set(
              {
                activeWorkspace: workspace.id,
                activeWorkspaceName: workspace.name,
              },
              false,
              "loadWorkspace"
            );
          }
          return workspace;
        },

        deleteWorkspace: (id) =>
          set(
            (state) => ({
              workspaces: state.workspaces.filter((w) => w.id !== id),
              activeWorkspace:
                state.activeWorkspace === id ? null : state.activeWorkspace,
              activeWorkspaceName:
                state.activeWorkspace === id ? null : state.activeWorkspaceName,
            }),
            false,
            "deleteWorkspace"
          ),

        setActiveWorkspace: (id, name = null) =>
          set(
            { activeWorkspace: id, activeWorkspaceName: id ? name : null },
            false,
            "setActiveWorkspace"
          ),

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
        version: 1,
        migrate: (persistedState) => {
          const state = persistedState as Partial<WorkspaceStore> | undefined

          return {
            workspaces: Array.isArray(state?.workspaces) ? state.workspaces : [],
            activeWorkspace:
              typeof state?.activeWorkspace === "string" ? state.activeWorkspace : null,
            activeWorkspaceName:
              typeof state?.activeWorkspaceName === "string"
                ? state.activeWorkspaceName
                : null,
          }
        },
        partialize: (state) => ({
          workspaces: state.workspaces,
          activeWorkspace: state.activeWorkspace,
          activeWorkspaceName: state.activeWorkspaceName,
        }),
        merge: (persistedState, currentState) => ({
          ...currentState,
          ...(persistedState as Partial<WorkspaceStore>),
        }),
      }
    ),
    {
      name: "WorkspaceStore",
      enabled: import.meta.env?.DEV ?? false,
    }
  )
);
