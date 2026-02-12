import { useState, useEffect } from 'react'
import { Orbit, Clock } from 'lucide-react'
import { Ion } from 'cesium'
import { QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { queryClient } from './lib/queryClient'
import { LazyAdminPanel, LazyMultiViewContainer } from './components/lazy'
import SuspenseWrapper from './components/SuspenseWrapper'
import ViewModeToggle from './components/Header/ViewModeToggle'
import UIModeToggle from './components/Header/UIModeToggle'
import LeftSidebar from './components/LeftSidebar'
import RightSidebar from './components/RightSidebar'
import ErrorBoundary from './components/ErrorBoundary'
import { MissionProvider } from './context/MissionContext'
import { useVisStore } from './store/visStore'
import { useTargetAddStore } from './store/targetAddStore'
import { useSwathStore } from './store/swathStore'
import { useSelectionStore } from './store/selectionStore'
import { useLockModeStore } from './store/lockModeStore'
import LockToastContainer from './components/LockToast'
import './App.css'

// Set Cesium Ion access token from environment variable
const cesiumToken = import.meta.env.VITE_CESIUM_ION_TOKEN
if (cesiumToken) {
  Ion.defaultAccessToken = cesiumToken
  console.log('Cesium Ion token configured')
} else {
  console.warn('No Cesium Ion token found in environment variables')
}

function AppContent(): JSX.Element {
  const [adminPanelOpen, setAdminPanelOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [displayTime, setDisplayTime] = useState<string>('--:--:-- UTC')
  const { leftSidebarOpen, rightSidebarOpen, leftSidebarWidth, rightSidebarWidth } = useVisStore()
  const { disableAddMode } = useTargetAddStore()
  const { debugEnabled, setDebugEnabled } = useSwathStore()
  const { clearSelection } = useSelectionStore()
  const { disableLockMode } = useLockModeStore()

  // Keyboard handler for Esc key to exit add mode/clear selection and Ctrl+Shift+D for debug toggle
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        // Don't clear if user is typing in an input
        const target = event.target as HTMLElement
        if (
          target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable
        ) {
          return
        }
        disableAddMode()
        disableLockMode()
        clearSelection()
      }
      // Ctrl+Shift+D to toggle SAR swath debug overlay
      if (event.ctrlKey && event.shiftKey && event.key === 'D') {
        event.preventDefault()
        setDebugEnabled(!debugEnabled)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [disableAddMode, disableLockMode, debugEnabled, setDebugEnabled, clearSelection])

  // Update UTC time display based on browser system time (independent of Cesium clock)
  useEffect(() => {
    let animationFrameId: number

    const updateTime = () => {
      // Always use browser system time in UTC
      const now = new Date()
      const hours = now.getUTCHours().toString().padStart(2, '0')
      const minutes = now.getUTCMinutes().toString().padStart(2, '0')
      const seconds = now.getUTCSeconds().toString().padStart(2, '0')
      setDisplayTime(`${hours}:${minutes}:${seconds} UTC`)

      animationFrameId = requestAnimationFrame(updateTime)
    }

    animationFrameId = requestAnimationFrame(updateTime)
    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId)
      }
    }
  }, [])

  return (
    <div className="h-screen bg-space-blue text-white flex flex-col overflow-hidden">
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-700 h-16 flex-shrink-0 z-50 shadow-lg">
        <div className="px-6 h-full flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-gray-800 rounded-lg">
              <Orbit className="w-5 h-5 text-blue-500" />
            </div>
            <h1 className="text-lg font-semibold text-white">
              <span className="text-white font-bold">COSMOS</span>
              <span className="text-blue-400 font-bold">42</span>
              <span className="text-gray-400 font-normal text-sm ml-2">
                Complete Orbital Mission Scheduling & Optimization System
              </span>
            </h1>
          </div>

          <div className="flex items-center space-x-4">
            <UIModeToggle />
            <ViewModeToggle />
            <div
              className="flex items-center space-x-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700"
              title="System Time (UTC)"
            >
              <Clock className="w-4 h-4 text-blue-400" />
              <span className="font-mono text-sm text-gray-300">{displayTime}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 relative overflow-hidden">
        <ErrorBoundary>
          <LeftSidebar onAdminPanelOpen={() => setAdminPanelOpen(true)} refreshKey={refreshKey} />
        </ErrorBoundary>

        {/* Canvas Container with Dynamic Padding */}
        <div
          className="absolute inset-0 transition-all duration-300"
          style={{
            left: leftSidebarOpen ? `${leftSidebarWidth + 48}px` : '48px',
            right: rightSidebarOpen ? `${rightSidebarWidth + 48}px` : '48px',
          }}
        >
          <SuspenseWrapper>
            <LazyMultiViewContainer />
          </SuspenseWrapper>
        </div>

        <ErrorBoundary>
          <RightSidebar />
        </ErrorBoundary>
      </div>

      {/* Admin Panel Modal */}
      {adminPanelOpen && (
        <SuspenseWrapper>
          <LazyAdminPanel
            isOpen={adminPanelOpen}
            onClose={() => setAdminPanelOpen(false)}
            onConfigUpdate={() => {
              // Trigger refresh of ground stations
              setRefreshKey((prev) => prev + 1)
            }}
          />
        </SuspenseWrapper>
      )}

      {/* PR-LOCK-OPS-01: Global lock operation toast notifications */}
      <LockToastContainer />
    </div>
  )
}

function App(): JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <MissionProvider>
        <AppContent />
      </MissionProvider>
      {/* React Query Devtools - only in development */}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  )
}

export default App
