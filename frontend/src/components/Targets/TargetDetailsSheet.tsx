/**
 * TargetDetailsSheet — DEPRECATED
 *
 * PR-UI-036: Target editing after map-click now happens inline inside OrdersPanel
 * via EditableTargetRow. This component is kept as a no-op stub so existing
 * imports (e.g. TargetInput.tsx) compile without errors.
 */

import React from 'react'
import { TargetData } from '../../types'

interface TargetDetailsSheetProps {
  onSave: (target: TargetData) => void
  onCancel?: () => void
}

export const TargetDetailsSheet: React.FC<TargetDetailsSheetProps> = () => {
  // No-op — inline editing in OrdersPanel replaces this component
  return null
}
