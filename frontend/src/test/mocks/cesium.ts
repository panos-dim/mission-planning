/**
 * Cesium Mock for Testing
 * 
 * Cesium requires browser APIs and WebGL that aren't available in jsdom.
 * This mock provides the necessary types for tests to compile and run.
 */

import { vi } from 'vitest'

export const JulianDate = {
  fromIso8601: vi.fn(() => ({ dayNumber: 0, secondsOfDay: 0 })),
  toIso8601: vi.fn(() => '2025-01-01T00:00:00Z'),
  now: vi.fn(() => ({ dayNumber: 0, secondsOfDay: 0 })),
  clone: vi.fn((date) => date),
  addSeconds: vi.fn(),
  secondsDifference: vi.fn(() => 0),
  compare: vi.fn(() => 0),
}

export const Cartesian3 = {
  fromDegrees: vi.fn(() => ({ x: 0, y: 0, z: 0 })),
  fromDegreesArray: vi.fn(() => []),
  magnitude: vi.fn(() => 0),
  normalize: vi.fn(),
  cross: vi.fn(),
  dot: vi.fn(() => 0),
}

export const Color = {
  fromCssColorString: vi.fn(() => ({ red: 1, green: 1, blue: 1, alpha: 1 })),
  RED: { red: 1, green: 0, blue: 0, alpha: 1 },
  GREEN: { red: 0, green: 1, blue: 0, alpha: 1 },
  BLUE: { red: 0, green: 0, blue: 1, alpha: 1 },
  WHITE: { red: 1, green: 1, blue: 1, alpha: 1 },
  BLACK: { red: 0, green: 0, blue: 0, alpha: 1 },
  YELLOW: { red: 1, green: 1, blue: 0, alpha: 1 },
  ORANGE: { red: 1, green: 0.5, blue: 0, alpha: 1 },
}

export const SceneMode = {
  SCENE2D: 2,
  SCENE3D: 3,
  COLUMBUS_VIEW: 1,
  MORPHING: 0,
}

export const Viewer = vi.fn().mockImplementation(() => ({
  scene: {
    mode: SceneMode.SCENE3D,
    morphTo2D: vi.fn(),
    morphTo3D: vi.fn(),
    globe: { enableLighting: false },
  },
  clock: {
    currentTime: JulianDate.now(),
    startTime: JulianDate.now(),
    stopTime: JulianDate.now(),
    shouldAnimate: false,
    multiplier: 1,
  },
  camera: {
    flyTo: vi.fn(),
    setView: vi.fn(),
    position: { x: 0, y: 0, z: 10000000 },
  },
  dataSources: {
    add: vi.fn(),
    remove: vi.fn(),
    removeAll: vi.fn(),
    get: vi.fn(),
    length: 0,
  },
  entities: {
    add: vi.fn(),
    remove: vi.fn(),
    removeAll: vi.fn(),
    getById: vi.fn(),
    values: [],
  },
  imageryLayers: {
    addImageryProvider: vi.fn(),
    removeAll: vi.fn(),
    get: vi.fn(() => ({ ready: true })),
    length: 1,
  },
  destroy: vi.fn(),
  isDestroyed: vi.fn(() => false),
}))

export const CzmlDataSource = {
  load: vi.fn(() => Promise.resolve({
    entities: { values: [] },
  })),
}

export const Ion = {
  defaultAccessToken: '',
}

export const IonImageryProvider = vi.fn()

export const OpenStreetMapImageryProvider = vi.fn()

export const ScreenSpaceEventHandler = vi.fn().mockImplementation(() => ({
  setInputAction: vi.fn(),
  removeInputAction: vi.fn(),
  destroy: vi.fn(),
}))

export const ScreenSpaceEventType = {
  LEFT_CLICK: 0,
  LEFT_DOUBLE_CLICK: 1,
  LEFT_DOWN: 2,
  LEFT_UP: 3,
  MOUSE_MOVE: 15,
  RIGHT_CLICK: 5,
}

export const defined = vi.fn((value) => value !== undefined && value !== null)

export const Math = {
  toDegrees: vi.fn((radians: number) => radians * (180 / 3.14159)),
  toRadians: vi.fn((degrees: number) => degrees * (3.14159 / 180)),
}

export default {
  JulianDate,
  Cartesian3,
  Color,
  SceneMode,
  Viewer,
  CzmlDataSource,
  Ion,
  IonImageryProvider,
  OpenStreetMapImageryProvider,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  defined,
  Math,
}
