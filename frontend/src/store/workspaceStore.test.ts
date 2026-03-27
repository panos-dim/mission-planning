import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Workspace } from '../types'

const buildWorkspace = (id: string, name: string): Workspace => ({
  id,
  name,
  createdAt: '2026-03-24T00:00:00Z',
  sceneObjects: [],
  missionData: null,
  czmlData: [],
})

const loadFreshStore = async () => {
  vi.resetModules()
  const mod = await import('./workspaceStore')
  return mod.useWorkspaceStore
}

describe('workspaceStore', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.resetModules()
  })

  it('tracks both the active workspace id and name when set directly', async () => {
    const useWorkspaceStore = await loadFreshStore()

    useWorkspaceStore.getState().setActiveWorkspace('ws-gulf', 'Gulf Planning')

    expect(useWorkspaceStore.getState().activeWorkspace).toBe('ws-gulf')
    expect(useWorkspaceStore.getState().activeWorkspaceName).toBe('Gulf Planning')
  })

  it('restores the workspace name when loading a saved workspace', async () => {
    const useWorkspaceStore = await loadFreshStore()
    const workspace = buildWorkspace('ws-kuwait', 'Kuwait Repairs')

    useWorkspaceStore.getState().saveWorkspace(workspace)
    useWorkspaceStore.getState().setActiveWorkspace(null)

    const loaded = useWorkspaceStore.getState().loadWorkspace(workspace.id)

    expect(loaded?.name).toBe('Kuwait Repairs')
    expect(useWorkspaceStore.getState().activeWorkspace).toBe(workspace.id)
    expect(useWorkspaceStore.getState().activeWorkspaceName).toBe('Kuwait Repairs')
  })

  it('rehydrates the persisted active selection alongside the workspace list', async () => {
    const persistedWorkspace = buildWorkspace('ws-rome', 'Rome Demo')

    localStorage.setItem(
      'mission_workspaces',
      JSON.stringify({
        state: {
          workspaces: [persistedWorkspace],
          activeWorkspace: persistedWorkspace.id,
          activeWorkspaceName: persistedWorkspace.name,
        },
        version: 0,
      }),
    )

    const useWorkspaceStore = await loadFreshStore()
    await Promise.resolve()

    expect(useWorkspaceStore.getState().workspaces).toEqual([persistedWorkspace])
    expect(useWorkspaceStore.getState().activeWorkspace).toBe(persistedWorkspace.id)
    expect(useWorkspaceStore.getState().activeWorkspaceName).toBe(persistedWorkspace.name)

    const persisted = JSON.parse(localStorage.getItem('mission_workspaces') || '{}')
    expect(persisted.state.workspaces).toEqual([persistedWorkspace])
    expect(persisted.state.activeWorkspace).toBe(persistedWorkspace.id)
    expect(persisted.state.activeWorkspaceName).toBe(persistedWorkspace.name)
    expect(persisted.version).toBe(1)
  })
})
