declare global {
  interface Window {
    debug?: typeof import('../utils/debug').debug
    lightingInitializationInProgress?: boolean
  }
}

export {}
