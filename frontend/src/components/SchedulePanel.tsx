/**
 * Schedule Panel Component
 * Unified panel for Committed Schedule (AcceptedOrders) and Timeline
 * Per UX_MINIMAL_SPEC.md Section 3.4
 */

import React, { useState, useMemo, useCallback } from 'react'
import { CheckSquare, History, Clock } from 'lucide-react'
import AcceptedOrders from './AcceptedOrders'
import ScheduleTimeline from './ScheduleTimeline'
import { useLockStore } from '../store/lockStore'
import { AcceptedOrder } from '../types'
import { SCHEDULE_TABS, SIMPLE_MODE_SCHEDULE_TABS } from '../constants/simpleMode'
import type { ScheduledAcquisition } from './ScheduleTimeline'

interface SchedulePanelProps {
  orders: AcceptedOrder[]
  onOrdersChange: (orders: AcceptedOrder[]) => void
  showHistoryTab?: boolean // Admin only
}

type TabId = (typeof SCHEDULE_TABS)[keyof typeof SCHEDULE_TABS]

interface Tab {
  id: TabId
  label: string
  icon: React.ElementType
  badge?: number
  badgeColor?: 'red' | 'yellow' | 'green'
}

const SchedulePanel: React.FC<SchedulePanelProps> = ({
  orders,
  onOrdersChange,
  showHistoryTab = false,
}) => {
  const [activeTab, setActiveTab] = useState<TabId>(SCHEDULE_TABS.COMMITTED)
  // PR-LOCK-OPS-01: Lock store for merging lock levels into timeline acquisitions
  const lockLevels = useLockStore((s) => s.levels)
  const toggleLock = useLockStore((s) => s.toggleLock)

  // PR-LOCK-OPS-01: Handle lock toggle from timeline
  const handleLockToggle = useCallback(
    (acquisitionId: string) => {
      toggleLock(acquisitionId)
    },
    [toggleLock],
  )

  // PR-OPS-REPAIR-DEFAULT-01: Convert orders to timeline acquisitions
  // PR-LOCK-OPS-01: Merge lock levels from lockStore
  const timelineAcquisitions = useMemo((): ScheduledAcquisition[] => {
    const acquisitions: ScheduledAcquisition[] = []
    const seen = new Set<string>()
    for (const order of orders) {
      for (const item of order.schedule || []) {
        const acqId = item.opportunity_id
        if (seen.has(acqId)) continue
        seen.add(acqId)
        acquisitions.push({
          id: acqId,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          start_time: item.start_time,
          end_time: item.end_time,
          lock_level: lockLevels.get(acqId) ?? 'none',
          state: 'committed',
          mode: undefined,
          has_conflict: false,
          order_id: order.order_id,
        })
      }
    }
    return acquisitions
  }, [orders, lockLevels])

  const tabs: Tab[] = [
    {
      id: SCHEDULE_TABS.COMMITTED,
      label: 'Committed',
      icon: CheckSquare,
      badge: orders.length > 0 ? orders.length : undefined,
      badgeColor: 'green',
    },
    // PR-OPS-REPAIR-DEFAULT-01: Added Timeline tab
    {
      id: SCHEDULE_TABS.TIMELINE,
      label: 'Timeline',
      icon: Clock,
      badge: timelineAcquisitions.length > 0 ? timelineAcquisitions.length : undefined,
      badgeColor: 'green',
    },
  ]

  // Add History tab for admins only
  if (showHistoryTab) {
    tabs.push({
      id: SCHEDULE_TABS.HISTORY,
      label: 'History',
      icon: History,
    })
  }

  // Filter tabs based on Simple Mode config
  const visibleTabs = showHistoryTab
    ? tabs
    : tabs.filter((tab) => (SIMPLE_MODE_SCHEDULE_TABS as readonly string[]).includes(tab.id))

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Tab Bar */}
      <div className="flex border-b border-gray-700 bg-gray-800">
        {visibleTabs.map((tab) => {
          const isActive = activeTab === tab.id
          const Icon = tab.icon

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-xs font-medium
                transition-colors relative
                ${
                  isActive
                    ? 'text-white border-b-2 border-blue-500 bg-gray-900'
                    : 'text-gray-400 hover:text-white hover:bg-gray-700'
                }
              `}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>

              {/* Badge */}
              {tab.badge !== undefined && tab.badge > 0 && (
                <span
                  className={`
                    min-w-[18px] h-[18px] flex items-center justify-center
                    text-[10px] font-bold rounded-full px-1
                    ${
                      tab.badgeColor === 'red'
                        ? 'bg-red-500 text-white'
                        : tab.badgeColor === 'yellow'
                          ? 'bg-yellow-500 text-black'
                          : 'bg-green-500 text-white'
                    }
                  `}
                >
                  {tab.badge > 99 ? '99+' : tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === SCHEDULE_TABS.COMMITTED && (
          <AcceptedOrders orders={orders} onOrdersChange={onOrdersChange} />
        )}

        {/* PR-OPS-REPAIR-DEFAULT-01: Timeline tab */}
        {activeTab === SCHEDULE_TABS.TIMELINE && (
          <ScheduleTimeline acquisitions={timelineAcquisitions} onLockToggle={handleLockToggle} />
        )}

        {activeTab === SCHEDULE_TABS.HISTORY && showHistoryTab && (
          <div className="p-4 text-center text-gray-500">
            <History className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <h3 className="text-sm font-medium text-gray-400 mb-1">Commit History</h3>
            <p className="text-xs text-gray-500">
              Audit log of schedule commits. Available in future release.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default SchedulePanel
