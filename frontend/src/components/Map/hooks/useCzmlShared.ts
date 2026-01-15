import { useEffect, useState, useRef } from 'react'
import { useMission } from '../../../context/MissionContext'

interface CzmlCache {
  data: any[] | null
  timestamp: number
  missionId: string | null
}

// Singleton cache to share CZML data across viewports
let czmlCache: CzmlCache = {
  data: null,
  timestamp: 0,
  missionId: null
}

export const useCzmlShared = () => {
  const { state } = useMission()
  const [sharedCzml, setSharedCzml] = useState<any[] | null>(null)
  const lastMissionIdRef = useRef<string | null>(null)
  
  useEffect(() => {
    if (!state.missionData || !state.czmlData) {
      setSharedCzml(null)
      return
    }
    
    const currentMissionId = `${state.missionData.start_time}_${state.missionData.end_time}`
    
    // Check if we need to update the cache
    if (currentMissionId !== czmlCache.missionId || 
        !czmlCache.data || 
        state.czmlData !== czmlCache.data) {
      
      console.log('Updating shared CZML cache for mission:', currentMissionId)
      
      // Update the cache
      czmlCache = {
        data: state.czmlData,
        timestamp: Date.now(),
        missionId: currentMissionId
      }
      
      lastMissionIdRef.current = currentMissionId
    }
    
    // Always set the shared CZML from cache
    setSharedCzml(czmlCache.data)
    
  }, [state.missionData, state.czmlData])
  
  return {
    sharedCzml,
    isCached: czmlCache.missionId === lastMissionIdRef.current
  }
}

// Export a function to clear the cache when needed
export const clearCzmlCache = () => {
  czmlCache = {
    data: null,
    timestamp: 0,
    missionId: null
  }
  console.log('CZML cache cleared')
}
