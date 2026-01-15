/**
 * Production-safe logging utility
 * 
 * Wraps console methods to only log in development mode,
 * except for errors which always log.
 */

const isDev = import.meta.env.DEV

type LogArgs = unknown[]

export const logger = {
  /**
   * Log general information (dev only)
   */
  log: (...args: LogArgs): void => {
    if (isDev) console.log(...args)
  },

  /**
   * Log warnings (dev only)
   */
  warn: (...args: LogArgs): void => {
    if (isDev) console.warn(...args)
  },

  /**
   * Log errors (always, for production debugging)
   */
  error: (...args: LogArgs): void => {
    console.error(...args)
  },

  /**
   * Log info messages (dev only)
   */
  info: (...args: LogArgs): void => {
    if (isDev) console.info(...args)
  },

  /**
   * Log debug messages (dev only)
   */
  debug: (...args: LogArgs): void => {
    if (isDev) console.debug(...args)
  },

  /**
   * Group console logs (dev only)
   */
  group: (label: string): void => {
    if (isDev) console.group(label)
  },

  /**
   * End console group (dev only)
   */
  groupEnd: (): void => {
    if (isDev) console.groupEnd()
  },

  /**
   * Log with custom styling (dev only)
   */
  styled: (message: string, style: string): void => {
    if (isDev) console.log(`%c${message}`, style)
  }
}

export default logger
