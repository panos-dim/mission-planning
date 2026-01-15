import React from 'react'
import { Modal } from './ui'
import { formatShortcut, APP_SHORTCUTS } from '../hooks/useKeyboardShortcuts'

interface KeyboardShortcutsHelpProps {
  isOpen: boolean
  onClose: () => void
}

const shortcutGroups = [
  {
    title: 'Navigation',
    shortcuts: [
      APP_SHORTCUTS.TOGGLE_LEFT_SIDEBAR,
      APP_SHORTCUTS.TOGGLE_RIGHT_SIDEBAR,
    ],
  },
  {
    title: 'Timeline',
    shortcuts: [
      APP_SHORTCUTS.PLAY_PAUSE,
      APP_SHORTCUTS.STEP_FORWARD,
      APP_SHORTCUTS.STEP_BACKWARD,
      APP_SHORTCUTS.RESET_TIMELINE,
    ],
  },
  {
    title: 'View',
    shortcuts: [
      APP_SHORTCUTS.TOGGLE_2D_3D,
      APP_SHORTCUTS.RESET_VIEW,
    ],
  },
  {
    title: 'Actions',
    shortcuts: [
      APP_SHORTCUTS.RUN_ANALYSIS,
      APP_SHORTCUTS.ESCAPE,
    ],
  },
]

export const KeyboardShortcutsHelp: React.FC<KeyboardShortcutsHelpProps> = ({
  isOpen,
  onClose,
}) => {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Keyboard Shortcuts"
      size="md"
    >
      <div className="space-y-6">
        {shortcutGroups.map((group) => (
          <div key={group.title}>
            <h3 className="text-sm font-semibold text-gray-300 mb-2">
              {group.title}
            </h3>
            <div className="space-y-2">
              {group.shortcuts.map((shortcut) => (
                <div
                  key={shortcut.description}
                  className="flex items-center justify-between py-1"
                >
                  <span className="text-sm text-gray-400">
                    {shortcut.description}
                  </span>
                  <kbd className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-xs text-gray-300 font-mono">
                    {formatShortcut(shortcut)}
                  </kbd>
                </div>
              ))}
            </div>
          </div>
        ))}
        
        <div className="pt-4 border-t border-gray-700">
          <p className="text-xs text-gray-500">
            Press <kbd className="px-1 py-0.5 bg-gray-700 border border-gray-600 rounded text-[10px]">?</kbd> to show this help at any time
          </p>
        </div>
      </div>
    </Modal>
  )
}

KeyboardShortcutsHelp.displayName = 'KeyboardShortcutsHelp'
