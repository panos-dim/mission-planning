import React, { useEffect, useState, useMemo } from 'react'
import GlobeViewport from './GlobeViewport'
import { useVisStore } from '../../store/visStore'
import { useMission } from '../../context/MissionContext'
import { Maximize2, Minimize2 } from 'lucide-react'

const MultiViewContainer: React.FC = () => {
  const { state } = useMission()
  const { 
    viewMode, 
    sceneModePrimary, 
    sceneModeSecondary
  } = useVisStore()
  
  const [primaryExpanded, setPrimaryExpanded] = useState(false)
  const [secondaryExpanded, setSecondaryExpanded] = useState(false)
  
  // Cache CZML data to avoid re-parsing
  const cachedCzml = useMemo(() => {
    return state.czmlData
  }, [state.czmlData])
  
  // Reset expansion states when view mode changes
  useEffect(() => {
    setPrimaryExpanded(false)
    setSecondaryExpanded(false)
  }, [viewMode])
  
  if (viewMode === 'single') {
    return (
      <div className="w-full h-full">
        <GlobeViewport 
          mode={sceneModePrimary} 
          viewportId="primary"
          sharedCzml={cachedCzml}
        />
      </div>
    )
  }
  
  // Split view layout
  return (
    <div className="w-full h-full flex">
      {/* Primary viewport */}
      <div 
        className={`
          relative border-r border-gray-700 transition-all duration-300
          ${primaryExpanded ? 'flex-grow' : secondaryExpanded ? 'w-0 overflow-hidden' : 'w-1/2'}
        `}
      >
        {!secondaryExpanded && (
          <>
            <GlobeViewport 
              mode={sceneModePrimary} 
              viewportId="primary"
              sharedCzml={cachedCzml}
            />
            
            {/* Expand/Collapse button */}
            <button
              onClick={() => setPrimaryExpanded(!primaryExpanded)}
              className="absolute top-20 right-4 z-40 bg-gray-900/90 backdrop-blur-sm border border-gray-700 rounded-lg p-2 text-white hover:bg-gray-800/90 transition-colors"
              title={primaryExpanded ? "Restore split view" : "Expand primary view"}
            >
              {primaryExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
          </>
        )}
      </div>
      
      {/* Secondary viewport */}
      <div 
        className={`
          relative transition-all duration-300
          ${secondaryExpanded ? 'flex-grow' : primaryExpanded ? 'w-0 overflow-hidden' : 'w-1/2'}
        `}
      >
        {!primaryExpanded && (
          <>
            <GlobeViewport 
              mode={sceneModeSecondary} 
              viewportId="secondary"
              sharedCzml={cachedCzml}
            />
            
            {/* Expand/Collapse button */}
            <button
              onClick={() => setSecondaryExpanded(!secondaryExpanded)}
              className="absolute top-20 left-4 z-40 bg-gray-900/90 backdrop-blur-sm border border-gray-700 rounded-lg p-2 text-white hover:bg-gray-800/90 transition-colors"
              title={secondaryExpanded ? "Restore split view" : "Expand secondary view"}
            >
              {secondaryExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export default MultiViewContainer
