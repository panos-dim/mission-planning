import React, { useState } from 'react'
import { useMission } from '../context/MissionContext'
import { Calendar, Clock, Download, Activity, List, BarChart2, Map, Target } from 'lucide-react'
import ObjectMapViewer from './ObjectMapViewer'
import { formatDateTimeShort, formatDateDDMMYYYY } from '../utils/date'

const MissionSidebar: React.FC = () => {
  const { state, navigateToPassWindow } = useMission()
  const [activeSection, setActiveSection] = useState<
    'objects' | 'overview' | 'schedule' | 'timeline' | 'summary'
  >('objects')

  const downloadJSON = (data: unknown, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const downloadCSV = () => {
    if (!state.missionData) return

    const headers = [
      'Target',
      'Start Time (UTC)',
      'End Time (UTC)',
      'Max Elevation (°)',
      'Opportunity Type',
    ]
    const rows = state.missionData.passes.map((pass) => [
      pass.target,
      pass.start_time,
      pass.end_time,
      pass.max_elevation.toFixed(1),
      pass.pass_type,
    ])

    const csvContent = [headers, ...rows].map((row) => row.join(',')).join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mission_schedule_${state.missionData.satellite_name}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const sections = [
    { id: 'objects' as const, label: 'Objects', icon: Map },
    { id: 'overview' as const, label: 'Overview', icon: Activity },
    { id: 'schedule' as const, label: 'Schedule', icon: Calendar },
    { id: 'timeline' as const, label: 'Timeline', icon: Clock },
    { id: 'summary' as const, label: 'Summary', icon: BarChart2 },
  ]

  // Show Objects tab even without mission data
  const availableSections = state.missionData
    ? sections
    : [{ id: 'objects' as const, label: 'Objects', icon: Map }]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-white">
            {state.missionData ? 'Feasibility Results' : 'Mission Controls'}
          </h2>
          {state.missionData && (
            <div className="flex space-x-2">
              <button
                onClick={() =>
                  downloadJSON(
                    state.missionData,
                    `mission_data_${state.missionData?.satellite_name}.json`,
                  )
                }
                className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
                title="Download JSON"
              >
                <List className="w-4 h-4" />
              </button>
              <button
                onClick={downloadCSV}
                className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
                title="Download CSV"
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {state.missionData && (
          <div className="text-sm text-gray-400">
            <div className="flex items-center space-x-2">
              <Map className="w-4 h-4" />
              <span>{state.missionData.satellite_name}</span>
            </div>
          </div>
        )}
      </div>

      {/* Section Navigation */}
      <div className="flex border-b border-gray-700">
        {availableSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setActiveSection(section.id)}
            className={`flex-1 flex items-center justify-center space-x-1 py-2 px-2 text-xs font-medium transition-colors ${
              activeSection === section.id
                ? 'text-blue-400 border-b-2 border-blue-400 bg-blue-900/20'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            <section.icon className="w-3 h-3" />
            <span>{section.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeSection === 'objects' && <ObjectMapViewer />}
        {!state.missionData && activeSection !== 'objects' && (
          <div className="h-full flex items-center justify-center p-6">
            <div className="text-center">
              <Map className="w-12 h-12 text-gray-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-400 mb-2">No Mission Data</h3>
              <p className="text-sm text-gray-500">
                Configure your mission parameters and analyze to see results here.
              </p>
            </div>
          </div>
        )}
        {state.missionData && activeSection === 'overview' && (
          <div className="p-4 space-y-4">
            <div className="glass-panel rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Mission Overview</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Time window:</span>
                  <span className="text-white">
                    {(() => {
                      const start = new Date(state.missionData.start_time)
                      const end = new Date(state.missionData.end_time)
                      const hours = (end.getTime() - start.getTime()) / (1000 * 60 * 60)
                      return `${hours.toFixed(1)}h`
                    })()}
                  </span>
                </div>
                {/* Only show elevation mask for communication missions */}
                {state.missionData.mission_type === 'communication' &&
                  state.missionData.elevation_mask !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Elevation Mask:</span>
                      <span className="text-white">{state.missionData.elevation_mask}°</span>
                    </div>
                  )}
              </div>
            </div>

            <div className="glass-panel rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Targets</h3>
              <div className="space-y-2">
                {state.missionData.targets.map((target, index) => (
                  <div key={index} className="flex items-center space-x-2 text-sm">
                    <Target className="w-3 h-3 text-red-400" />
                    <span className="text-white">{target.name}</span>
                    <span className="text-gray-400 text-xs">
                      ({target.latitude.toFixed(2)}°, {target.longitude.toFixed(2)}°)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {state.missionData && activeSection === 'schedule' && (
          <div className="p-4">
            <div className="space-y-2">
              {state.missionData.passes.map((pass, index) => (
                <div
                  key={index}
                  className="glass-panel rounded-lg p-3 cursor-pointer hover:bg-gray-800/50 transition-colors"
                  onClick={() => {
                    console.log('Pass clicked:', index, pass)
                    navigateToPassWindow(index)
                  }}
                  title="Click to navigate to this imaging opportunity"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <div className="w-2 h-2 rounded-full bg-green-500"></div>
                      <span className="text-sm font-medium text-white">
                        Imaging Opportunity {index + 1}
                      </span>
                    </div>
                    {state.missionData?.mission_type !== 'imaging' && (
                      <span className="text-xs text-gray-400 capitalize">{pass.pass_type}</span>
                    )}
                  </div>

                  <div className="text-xs text-gray-400 mb-1">
                    <Target className="w-3 h-3 inline mr-1" />
                    {pass.target}
                  </div>

                  <div className="text-xs space-y-1">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Start:</span>
                      <span className="text-white">
                        {formatDateDDMMYYYY(pass.start_time)} {pass.start_time.substring(11, 16)}{' '}
                        UTC
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">End:</span>
                      <span className="text-white">
                        {formatDateDDMMYYYY(pass.end_time)} {pass.end_time.substring(11, 16)} UTC
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Max Elev:</span>
                      <span className="text-white">{pass.max_elevation.toFixed(1)}°</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {state.missionData && activeSection === 'timeline' && (
          <div className="p-4">
            <div className="glass-panel rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Mission Timeline</h3>
              <div className="space-y-3">
                <div className="text-xs">
                  <div className="flex justify-between mb-1">
                    <span className="text-gray-400">Start Time:</span>
                    <span className="text-white">
                      {formatDateTimeShort(state.missionData.start_time)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">End Time:</span>
                    <span className="text-white">
                      {formatDateTimeShort(state.missionData.end_time)}
                    </span>
                  </div>
                </div>

                <div className="relative">
                  <div className="absolute left-2 top-0 bottom-0 w-0.5 bg-gray-600"></div>
                  {state.missionData.passes.map((pass, index) => (
                    <div key={index} className="relative flex items-center space-x-3 py-2">
                      <div className="w-4 h-4 rounded-full bg-green-500 border-2 border-gray-900 z-10"></div>
                      <div className="flex-1">
                        <div className="text-xs text-white font-medium">{pass.target}</div>
                        <div className="text-xs text-gray-400">
                          {pass.start_time.substring(8, 10)}-{pass.start_time.substring(5, 7)}{' '}
                          {pass.start_time.substring(11, 16)} → {pass.end_time.substring(11, 16)}{' '}
                          UTC
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {state.missionData && activeSection === 'summary' && (
          <div className="p-4 space-y-4">
            <div className="glass-panel rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Statistics</h3>
              <div className="grid grid-cols-2 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-green-400">
                    {state.missionData.total_passes}
                  </div>
                  <div className="text-xs text-gray-400">Total Opportunities</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-blue-400">
                    {state.missionData.targets.length}
                  </div>
                  <div className="text-xs text-gray-400">Targets</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-yellow-400">
                    {(() => {
                      const totalSeconds = state.missionData.passes.reduce((sum, pass) => {
                        const start = new Date(pass.start_time).getTime()
                        const end = new Date(pass.end_time).getTime()
                        return sum + (end - start) / 1000
                      }, 0)
                      return totalSeconds.toFixed(0)
                    })()}
                    s
                  </div>
                  <div className="text-xs text-gray-400">Total Contact</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-blue-400">
                    {Math.max(...state.missionData.passes.map((p) => p.max_elevation)).toFixed(1)}°
                  </div>
                  <div className="text-xs text-gray-400">Max Elevation</div>
                </div>
              </div>
            </div>

            <div className="glass-panel rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Opportunity Distribution</h3>
              <div className="space-y-2">
                {state.missionData.targets.map((target) => {
                  const targetPasses = state.missionData!.passes.filter(
                    (p) => p.target === target.name,
                  )
                  return (
                    <div key={target.name} className="flex justify-between text-xs">
                      <span className="text-gray-400">{target.name}:</span>
                      <span className="text-white">{targetPasses.length} opportunities</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default MissionSidebar
