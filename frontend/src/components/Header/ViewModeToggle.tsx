import React, { useState, useRef, useEffect } from 'react'
import { ChevronDown, Map, Globe, PanelLeftClose } from 'lucide-react'
import { useVisStore } from '../../store/visStore'

const ViewModeToggle: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  
  const { 
    viewMode, 
    sceneModePrimary, 
    sceneModeSecondary,
    setViewMode, 
    setSceneModePrimary,
    setSceneModeSecondary 
  } = useVisStore()
  
  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])
  
  const getCurrentModeLabel = () => {
    if (viewMode === 'split') {
      return 'Split View'
    }
    return sceneModePrimary === '2D' ? '2D View' : '3D View'
  }
  
  const getCurrentIcon = () => {
    if (viewMode === 'split') {
      return <PanelLeftClose className="w-4 h-4" />
    }
    return sceneModePrimary === '2D' ? <Map className="w-4 h-4" /> : <Globe className="w-4 h-4" />
  }
  
  const handleModeChange = (newViewMode: 'single' | 'split', primaryMode?: '2D' | '3D') => {
    setViewMode(newViewMode)
    if (primaryMode) {
      setSceneModePrimary(primaryMode)
    }
    setIsOpen(false)
  }
  
  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-300 hover:bg-gray-700 hover:text-white transition-colors text-sm"
      >
        {getCurrentIcon()}
        <span>{getCurrentModeLabel()}</span>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      
      {isOpen && (
        <div className="absolute top-full mt-2 right-0 w-48 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50">
          <div className="py-1">
            {/* Single view options */}
            <div className="px-3 py-1 text-xs text-gray-400 uppercase tracking-wide">Single View</div>
            
            <button
              onClick={() => handleModeChange('single', '2D')}
              className={`w-full px-3 py-2 text-left flex items-center space-x-2 hover:bg-gray-800 transition-colors ${
                viewMode === 'single' && sceneModePrimary === '2D' ? 'bg-gray-800 text-blue-400' : 'text-white'
              }`}
            >
              <Map className="w-4 h-4" />
              <span>2D View</span>
              {viewMode === 'single' && sceneModePrimary === '2D' && (
                <span className="ml-auto text-blue-400">✓</span>
              )}
            </button>
            
            <button
              onClick={() => handleModeChange('single', '3D')}
              className={`w-full px-3 py-2 text-left flex items-center space-x-2 hover:bg-gray-800 transition-colors ${
                viewMode === 'single' && sceneModePrimary === '3D' ? 'bg-gray-800 text-blue-400' : 'text-white'
              }`}
            >
              <Globe className="w-4 h-4" />
              <span>3D View</span>
              {viewMode === 'single' && sceneModePrimary === '3D' && (
                <span className="ml-auto text-blue-400">✓</span>
              )}
            </button>
            
            {/* Split view option */}
            <div className="border-t border-gray-700 mt-1 pt-1">
              <div className="px-3 py-1 text-xs text-gray-400 uppercase tracking-wide">Multi View</div>
              
              <button
                onClick={() => handleModeChange('split')}
                className={`w-full px-3 py-2 text-left flex items-center space-x-2 hover:bg-gray-800 transition-colors ${
                  viewMode === 'split' ? 'bg-gray-800 text-blue-400' : 'text-white'
                }`}
              >
                <PanelLeftClose className="w-4 h-4" />
                <span>Split 2D | 3D</span>
                {viewMode === 'split' && (
                  <span className="ml-auto text-blue-400">✓</span>
                )}
              </button>
            </div>
            
            {/* Split view configuration (when active) */}
            {viewMode === 'split' && (
              <div className="border-t border-gray-700 mt-1 pt-1 px-3 py-2">
                <div className="text-xs text-gray-400 mb-2">Split View Configuration</div>
                <div className="space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-300">Left:</span>
                    <div className="flex space-x-1">
                      <button
                        onClick={() => setSceneModePrimary('2D')}
                        className={`px-2 py-1 rounded ${
                          sceneModePrimary === '2D' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        2D
                      </button>
                      <button
                        onClick={() => setSceneModePrimary('3D')}
                        className={`px-2 py-1 rounded ${
                          sceneModePrimary === '3D' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        3D
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-300">Right:</span>
                    <div className="flex space-x-1">
                      <button
                        onClick={() => setSceneModeSecondary('2D')}
                        className={`px-2 py-1 rounded ${
                          sceneModeSecondary === '2D' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        2D
                      </button>
                      <button
                        onClick={() => setSceneModeSecondary('3D')}
                        className={`px-2 py-1 rounded ${
                          sceneModeSecondary === '3D' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        3D
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ViewModeToggle
