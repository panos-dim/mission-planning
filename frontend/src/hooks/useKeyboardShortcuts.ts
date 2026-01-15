import { useEffect, useCallback } from 'react'

export interface KeyboardShortcut {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  meta?: boolean
  action: () => void
  description: string
}

interface UseKeyboardShortcutsOptions {
  enabled?: boolean
  preventDefault?: boolean
}

/**
 * Custom hook for handling keyboard shortcuts
 * 
 * @example
 * ```tsx
 * useKeyboardShortcuts([
 *   { key: 's', ctrl: true, action: handleSave, description: 'Save' },
 *   { key: 'Escape', action: handleClose, description: 'Close modal' },
 * ])
 * ```
 */
export function useKeyboardShortcuts(
  shortcuts: KeyboardShortcut[],
  options: UseKeyboardShortcutsOptions = {}
) {
  const { enabled = true, preventDefault = true } = options

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return

      // Don't trigger shortcuts when typing in form fields
      const target = event.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      ) {
        // Allow Escape in form fields
        if (event.key !== 'Escape') return
      }

      for (const shortcut of shortcuts) {
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase()
        const ctrlMatch = !!shortcut.ctrl === (event.ctrlKey || event.metaKey)
        const shiftMatch = !!shortcut.shift === event.shiftKey
        const altMatch = !!shortcut.alt === event.altKey

        if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
          if (preventDefault) {
            event.preventDefault()
          }
          shortcut.action()
          return
        }
      }
    },
    [shortcuts, enabled, preventDefault]
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])
}

/**
 * Format a shortcut for display
 */
export function formatShortcut(shortcut: Omit<KeyboardShortcut, 'action' | 'description'>): string {
  const parts: string[] = []
  
  const isMac = typeof navigator !== 'undefined' && navigator.platform.includes('Mac')
  
  if (shortcut.ctrl) parts.push(isMac ? '⌘' : 'Ctrl')
  if (shortcut.shift) parts.push(isMac ? '⇧' : 'Shift')
  if (shortcut.alt) parts.push(isMac ? '⌥' : 'Alt')
  
  // Format special keys
  const keyDisplay: Record<string, string> = {
    'escape': 'Esc',
    'enter': '↵',
    'arrowup': '↑',
    'arrowdown': '↓',
    'arrowleft': '←',
    'arrowright': '→',
    ' ': 'Space',
  }
  
  const formattedKey = keyDisplay[shortcut.key.toLowerCase()] || shortcut.key.toUpperCase()
  parts.push(formattedKey)
  
  return parts.join(isMac ? '' : '+')
}

/**
 * Pre-defined shortcuts for the application
 */
export const APP_SHORTCUTS = {
  // Navigation
  TOGGLE_LEFT_SIDEBAR: { key: '[', ctrl: true, description: 'Toggle left sidebar' },
  TOGGLE_RIGHT_SIDEBAR: { key: ']', ctrl: true, description: 'Toggle right sidebar' },
  
  // Timeline
  PLAY_PAUSE: { key: ' ', description: 'Play/pause timeline' },
  STEP_FORWARD: { key: 'ArrowRight', description: 'Step forward in time' },
  STEP_BACKWARD: { key: 'ArrowLeft', description: 'Step backward in time' },
  RESET_TIMELINE: { key: 'r', description: 'Reset timeline to start' },
  
  // View
  TOGGLE_2D_3D: { key: 'm', description: 'Toggle 2D/3D view' },
  RESET_VIEW: { key: 'h', description: 'Reset camera to home view' },
  
  // Actions
  RUN_ANALYSIS: { key: 'Enter', ctrl: true, description: 'Run mission analysis' },
  ESCAPE: { key: 'Escape', description: 'Close modal / Cancel action' },
  
  // Help
  SHOW_SHORTCUTS: { key: '?', shift: true, description: 'Show keyboard shortcuts' },
} as const
