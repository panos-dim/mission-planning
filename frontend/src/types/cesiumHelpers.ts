import type { CzmlDataSource, JulianDate, Timeline, Viewer } from 'cesium'
import type { RefObject } from 'react'

export interface CesiumViewerRefValue {
  cesiumElement?: Viewer
}

export interface CesiumDataSourceRefValue {
  cesiumElement?: CzmlDataSource
}

export type CesiumViewerRef = RefObject<CesiumViewerRefValue | null>
export type CesiumDataSourceRef = RefObject<CesiumDataSourceRefValue | null>

export interface TimelineInternals extends Timeline {
  _startJulian?: JulianDate
  _endJulian?: JulianDate
  _makeTics?: () => void
  updateFromClock?: () => void
}
