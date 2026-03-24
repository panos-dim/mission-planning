import { beforeEach, describe, expect, it, vi } from 'vitest'

const loadFreshStore = async () => {
  vi.resetModules()
  const mod = await import('./visStore')
  return mod.useVisStore
}

describe('visStore', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('tracks one-shot left panel requests for workflow handoff', async () => {
    const useVisStore = await loadFreshStore()

    useVisStore.getState().openLeftPanel('planning')
    expect(useVisStore.getState().requestedLeftPanel).toBe('planning')

    useVisStore.getState().clearRequestedLeftPanel()
    expect(useVisStore.getState().requestedLeftPanel).toBeNull()
  })
})
