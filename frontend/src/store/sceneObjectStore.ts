import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type { SceneObject } from "../types";

interface SceneObjectState {
  sceneObjects: SceneObject[];
  selectedObjectId: string | null;
}

interface SceneObjectActions {
  addSceneObject: (object: SceneObject) => void;
  updateSceneObject: (id: string, updates: Partial<SceneObject>) => void;
  removeSceneObject: (id: string) => void;
  setSelectedObject: (id: string | null) => void;
  setSceneObjects: (objects: SceneObject[]) => void;
  clearSceneObjects: () => void;
}

export type SceneObjectStore = SceneObjectState & SceneObjectActions;

export const useSceneObjectStore = create<SceneObjectStore>()(
  devtools(
    (set) => ({
      // State
      sceneObjects: [],
      selectedObjectId: null,

      // Actions
      addSceneObject: (object) =>
        set(
          (state) => ({
            sceneObjects: [...state.sceneObjects, object],
          }),
          false,
          "addSceneObject",
        ),

      updateSceneObject: (id, updates) =>
        set(
          (state) => ({
            sceneObjects: state.sceneObjects.map((obj) =>
              obj.id === id ? { ...obj, ...updates } : obj,
            ),
          }),
          false,
          "updateSceneObject",
        ),

      removeSceneObject: (id) =>
        set(
          (state) => ({
            sceneObjects: state.sceneObjects.filter((obj) => obj.id !== id),
            selectedObjectId:
              state.selectedObjectId === id ? null : state.selectedObjectId,
          }),
          false,
          "removeSceneObject",
        ),

      setSelectedObject: (id) =>
        set({ selectedObjectId: id }, false, "setSelectedObject"),

      setSceneObjects: (objects) =>
        set({ sceneObjects: objects }, false, "setSceneObjects"),

      clearSceneObjects: () =>
        set(
          { sceneObjects: [], selectedObjectId: null },
          false,
          "clearSceneObjects",
        ),
    }),
    {
      name: "sceneObjectStore",
      enabled: import.meta.env?.DEV ?? false,
    },
  ),
);
