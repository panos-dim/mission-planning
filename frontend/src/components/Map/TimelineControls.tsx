/**
 * TimelineControls — STK-style mission timeline and animation controls
 *
 * Replaces Cesium's default animation widget and timeline bar with a
 * custom, themed control bar at the bottom of the viewport.
 * Rendered as a sibling of the Resium <Viewer> (same pattern as LockModeButton).
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  ChevronsLeft,
  ChevronsRight,
  RotateCcw,
} from 'lucide-react'
import { JulianDate, Viewer } from 'cesium'

interface TimelineControlsProps {
  viewerRef: React.RefObject<{ cesiumElement: Viewer | undefined } | null>
}

/** Speed presets (multiplier values) */
const SPEED_PRESETS = [0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600]

/** Format JulianDate to readable UTC string */
function formatTime(jd: JulianDate | null, style: 'full' | 'short' | 'date-time' = 'full'): string {
  if (!jd) return '--:--:--'
  try {
    const d = JulianDate.toDate(jd)
    if (style === 'short') {
      return d.toISOString().slice(11, 19) + 'Z'
    }
    if (style === 'date-time') {
      // Compact: "Feb 12 12:50Z"
      const months = [
        'Jan',
        'Feb',
        'Mar',
        'Apr',
        'May',
        'Jun',
        'Jul',
        'Aug',
        'Sep',
        'Oct',
        'Nov',
        'Dec',
      ]
      return `${months[d.getUTCMonth()]} ${d.getUTCDate()} ${d.toISOString().slice(11, 16)}Z`
    }
    return d.toISOString().slice(0, 10) + ' ' + d.toISOString().slice(11, 19) + ' UTC'
  } catch {
    return '--:--:--'
  }
}

/** Format seconds into human-friendly duration */
function formatDuration(totalSec: number): string {
  const h = Math.floor(Math.abs(totalSec) / 3600)
  const m = Math.floor((Math.abs(totalSec) % 3600) / 60)
  const s = Math.floor(Math.abs(totalSec) % 60)
  if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}m`
  if (m > 0) return `${m}m ${s.toString().padStart(2, '0')}s`
  return `${s}s`
}

/** Get fraction of current time within the time window [0..1] */
function getProgress(current: JulianDate, start: JulianDate, stop: JulianDate): number {
  const total = JulianDate.secondsDifference(stop, start)
  if (total <= 0) return 0
  const elapsed = JulianDate.secondsDifference(current, start)
  return Math.max(0, Math.min(1, elapsed / total))
}

/** Format speed multiplier for display */
function formatSpeed(mult: number): string {
  if (mult >= 1) return `${mult}x`
  return `${mult}x`
}

const TimelineControls: React.FC<TimelineControlsProps> = ({ viewerRef }) => {
  const [isPlaying, setIsPlaying] = useState(false)
  const [multiplier, setMultiplier] = useState(2)
  const [progress, setProgress] = useState(0)
  const [currentTime, setCurrentTime] = useState<JulianDate | null>(null)
  const [startTime, setStartTime] = useState<JulianDate | null>(null)
  const [stopTime, setStopTime] = useState<JulianDate | null>(null)
  const [hasMission, setHasMission] = useState(false)
  const [speedMenuOpen, setSpeedMenuOpen] = useState(false)
  const [hoverFrac, setHoverFrac] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [remaining, setRemaining] = useState(0)
  const rafRef = useRef<number | null>(null)
  const timelineRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)

  const getViewer = useCallback(() => viewerRef.current?.cesiumElement ?? null, [viewerRef])

  // Sync state from Cesium clock at ~15fps
  useEffect(() => {
    const tick = () => {
      const v = getViewer()
      if (v?.clock) {
        const clock = v.clock
        const start = clock.startTime
        const stop = clock.stopTime
        const cur = clock.currentTime

        // Check if we have a valid mission time window
        const totalSec = JulianDate.secondsDifference(stop, start)
        const hasMissionData = totalSec > 0

        setHasMission(hasMissionData)
        setIsPlaying(clock.shouldAnimate)
        setMultiplier(clock.multiplier)
        setStartTime(start)
        setStopTime(stop)
        setCurrentTime(cur)

        if (hasMissionData && !isDraggingRef.current) {
          setProgress(getProgress(cur, start, stop))
        }

        // Elapsed / remaining
        if (hasMissionData) {
          setElapsed(JulianDate.secondsDifference(cur, start))
          setRemaining(JulianDate.secondsDifference(stop, cur))
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [getViewer])

  // Close speed menu on outside click
  useEffect(() => {
    if (!speedMenuOpen) return
    const close = () => setSpeedMenuOpen(false)
    document.addEventListener('click', close, { once: true })
    return () => document.removeEventListener('click', close)
  }, [speedMenuOpen])

  // ─── Playback controls ───

  const handlePlayPause = useCallback(() => {
    const v = getViewer()
    if (!v?.clock) return
    v.clock.shouldAnimate = !v.clock.shouldAnimate
    v.scene.requestRender()
  }, [getViewer])

  const handleReset = useCallback(() => {
    const v = getViewer()
    if (!v?.clock) return
    v.clock.currentTime = v.clock.startTime.clone()
    v.clock.shouldAnimate = false
    v.scene.requestRender()
  }, [getViewer])

  const handleStepBack = useCallback(() => {
    const v = getViewer()
    if (!v?.clock) return
    v.clock.shouldAnimate = false
    const step = Math.max(1, Math.abs(v.clock.multiplier))
    const newTime = JulianDate.addSeconds(v.clock.currentTime, -step, new JulianDate())
    if (JulianDate.greaterThanOrEquals(newTime, v.clock.startTime)) {
      v.clock.currentTime = newTime
    } else {
      v.clock.currentTime = v.clock.startTime.clone()
    }
    v.scene.requestRender()
  }, [getViewer])

  const handleStepForward = useCallback(() => {
    const v = getViewer()
    if (!v?.clock) return
    v.clock.shouldAnimate = false
    const step = Math.max(1, Math.abs(v.clock.multiplier))
    const newTime = JulianDate.addSeconds(v.clock.currentTime, step, new JulianDate())
    if (JulianDate.lessThanOrEquals(newTime, v.clock.stopTime)) {
      v.clock.currentTime = newTime
    } else {
      v.clock.currentTime = v.clock.stopTime.clone()
    }
    v.scene.requestRender()
  }, [getViewer])

  const handleSpeedChange = useCallback(
    (speed: number) => {
      const v = getViewer()
      if (!v?.clock) return
      v.clock.multiplier = speed
      setSpeedMenuOpen(false)
    },
    [getViewer],
  )

  const handleSlowerSpeed = useCallback(() => {
    const v = getViewer()
    if (!v?.clock) return
    const idx = SPEED_PRESETS.indexOf(v.clock.multiplier)
    if (idx > 0) {
      v.clock.multiplier = SPEED_PRESETS[idx - 1]
    } else if (idx === -1) {
      // Find the closest lower preset
      const lower = SPEED_PRESETS.filter((s) => s < v.clock.multiplier)
      if (lower.length > 0) v.clock.multiplier = lower[lower.length - 1]
    }
  }, [getViewer])

  const handleFasterSpeed = useCallback(() => {
    const v = getViewer()
    if (!v?.clock) return
    const idx = SPEED_PRESETS.indexOf(v.clock.multiplier)
    if (idx >= 0 && idx < SPEED_PRESETS.length - 1) {
      v.clock.multiplier = SPEED_PRESETS[idx + 1]
    } else if (idx === -1) {
      // Find the closest higher preset
      const higher = SPEED_PRESETS.filter((s) => s > v.clock.multiplier)
      if (higher.length > 0) v.clock.multiplier = higher[0]
    }
  }, [getViewer])

  // ─── Keyboard shortcuts ───
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      const v = getViewer()
      if (!v?.clock) return

      switch (e.key) {
        case ' ':
          e.preventDefault()
          v.clock.shouldAnimate = !v.clock.shouldAnimate
          v.scene.requestRender()
          break
        case 'ArrowLeft':
          e.preventDefault()
          handleStepBack()
          break
        case 'ArrowRight':
          e.preventDefault()
          handleStepForward()
          break
        case '+':
        case '=':
          handleFasterSpeed()
          break
        case '-':
        case '_':
          handleSlowerSpeed()
          break
      }
    }
    if (hasMission) {
      document.addEventListener('keydown', handler)
      return () => document.removeEventListener('keydown', handler)
    }
  }, [
    hasMission,
    getViewer,
    handleStepBack,
    handleStepForward,
    handleFasterSpeed,
    handleSlowerSpeed,
  ])

  // ─── Timeline scrubbing ───

  const scrubToPosition = useCallback(
    (clientX: number) => {
      const v = getViewer()
      const el = timelineRef.current
      if (!v?.clock || !el) return

      const rect = el.getBoundingClientRect()
      const frac = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
      setProgress(frac)

      const totalSec = JulianDate.secondsDifference(v.clock.stopTime, v.clock.startTime)
      const newTime = JulianDate.addSeconds(v.clock.startTime, frac * totalSec, new JulianDate())
      v.clock.currentTime = newTime
      v.scene.requestRender()
    },
    [getViewer],
  )

  const handleTimelineMouseDown = useCallback(
    (e: React.MouseEvent) => {
      isDraggingRef.current = true
      scrubToPosition(e.clientX)

      const handleMove = (ev: MouseEvent) => scrubToPosition(ev.clientX)
      const handleUp = () => {
        isDraggingRef.current = false
        document.removeEventListener('mousemove', handleMove)
        document.removeEventListener('mouseup', handleUp)
      }
      document.addEventListener('mousemove', handleMove)
      document.addEventListener('mouseup', handleUp)
    },
    [scrubToPosition],
  )

  // Don't render if no mission data loaded
  if (!hasMission) return null

  const btnCls =
    'flex items-center justify-center w-8 h-8 rounded-md transition-all duration-150 ' +
    'text-gray-300 hover:text-white hover:bg-gray-700/60 active:scale-95'

  return (
    <div
      className="absolute bottom-0 left-0 right-0 z-40 select-none"
      style={{ pointerEvents: 'auto' }}
    >
      {/* Timeline scrubber bar */}
      <div
        ref={timelineRef}
        className="relative h-6 cursor-pointer group mx-2"
        onMouseDown={handleTimelineMouseDown}
        onMouseMove={(e) => {
          const rect = timelineRef.current?.getBoundingClientRect()
          if (rect) setHoverFrac(Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width)))
        }}
        onMouseLeave={() => setHoverFrac(null)}
        title="Click or drag to scrub · Keyboard: Space=Play/Pause, ←→=Step, +/-=Speed"
      >
        {/* Track background */}
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-gray-700/80" />

        {/* Elapsed fill */}
        <div
          className="absolute top-1/2 -translate-y-1/2 left-0 h-1.5 rounded-full bg-blue-500/70 group-hover:bg-blue-400/80 transition-colors"
          style={{ width: `${progress * 100}%` }}
        />

        {/* Scrubber handle */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-blue-400 border-2 border-blue-300 shadow-lg shadow-blue-500/30 group-hover:scale-125 transition-transform"
          style={{ left: `calc(${progress * 100}% - 6px)` }}
        />

        {/* Tick marks — start / 25% / 50% / 75% / end */}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <div
            key={p}
            className="absolute top-1/2 -translate-y-1/2 w-px h-2.5 bg-gray-500/50"
            style={{ left: `${p * 100}%` }}
          />
        ))}

        {/* Hover time tooltip */}
        {hoverFrac !== null && startTime && stopTime && (
          <div
            className="absolute -top-7 -translate-x-1/2 px-1.5 py-0.5 rounded bg-gray-800/95 border border-gray-600/50 text-[9px] font-mono text-gray-300 whitespace-nowrap pointer-events-none"
            style={{ left: `${hoverFrac * 100}%` }}
          >
            {(() => {
              const totalSec = JulianDate.secondsDifference(stopTime, startTime)
              const hoverTime = JulianDate.addSeconds(
                startTime,
                hoverFrac * totalSec,
                new JulianDate(),
              )
              return formatTime(hoverTime, 'full')
            })()}
          </div>
        )}
      </div>

      {/* Control bar */}
      <div className="flex items-center gap-1 px-3 py-1.5 bg-gray-900/95 backdrop-blur-md border-t border-gray-700/50">
        {/* Start time label */}
        <span className="text-[10px] text-gray-500 font-mono whitespace-nowrap">
          {formatTime(startTime, 'date-time')}
        </span>

        {/* Elapsed indicator */}
        <span className="text-[9px] text-gray-600 font-mono ml-1" title="Elapsed">
          +{formatDuration(elapsed)}
        </span>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Speed slower */}
        <button onClick={handleSlowerSpeed} className={btnCls} title="Slower" aria-label="Slower">
          <ChevronsLeft className="w-4 h-4" />
        </button>

        {/* Step back */}
        <button
          onClick={handleStepBack}
          className={btnCls}
          title="Step Back"
          aria-label="Step Back"
        >
          <SkipBack className="w-4 h-4" />
        </button>

        {/* Play / Pause */}
        <button
          onClick={handlePlayPause}
          className={
            'flex items-center justify-center w-9 h-9 rounded-lg transition-all duration-150 ' +
            (isPlaying
              ? 'bg-blue-600/80 text-white hover:bg-blue-500/90'
              : 'bg-gray-700/60 text-gray-200 hover:bg-gray-600/80 hover:text-white') +
            ' active:scale-95'
          }
          title={isPlaying ? 'Pause' : 'Play'}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
        </button>

        {/* Step forward */}
        <button
          onClick={handleStepForward}
          className={btnCls}
          title="Step Forward"
          aria-label="Step Forward"
        >
          <SkipForward className="w-4 h-4" />
        </button>

        {/* Speed faster */}
        <button onClick={handleFasterSpeed} className={btnCls} title="Faster" aria-label="Faster">
          <ChevronsRight className="w-4 h-4" />
        </button>

        {/* Divider */}
        <div className="w-px h-5 bg-gray-700/60 mx-1" />

        {/* Reset */}
        <button
          onClick={handleReset}
          className={btnCls}
          title="Reset to Start"
          aria-label="Reset to Start"
        >
          <RotateCcw className="w-4 h-4" />
        </button>

        {/* Divider */}
        <div className="w-px h-5 bg-gray-700/60 mx-1" />

        {/* Speed multiplier button */}
        <div className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setSpeedMenuOpen(!speedMenuOpen)
            }}
            className={
              'flex items-center gap-1 px-2 py-1 rounded-md text-xs font-mono font-bold transition-all ' +
              'bg-gray-800/80 border border-gray-600/50 text-blue-400 hover:text-blue-300 hover:border-blue-500/50'
            }
            title="Playback Speed"
            aria-label="Playback Speed"
          >
            {formatSpeed(multiplier)}
          </button>

          {/* Speed dropdown */}
          {speedMenuOpen && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-800/95 backdrop-blur-md border border-gray-600/60 rounded-lg shadow-xl py-1 min-w-[64px] z-50">
              {SPEED_PRESETS.map((s) => (
                <button
                  key={s}
                  onClick={(e) => {
                    e.stopPropagation()
                    handleSpeedChange(s)
                  }}
                  className={
                    'block w-full text-center px-3 py-1 text-xs font-mono transition-colors ' +
                    (s === multiplier
                      ? 'text-blue-400 bg-blue-600/20 font-bold'
                      : 'text-gray-300 hover:text-white hover:bg-gray-700/60')
                  }
                >
                  {formatSpeed(s)}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Current time display */}
        <div className="ml-2 px-2 py-0.5 rounded bg-gray-800/60 border border-gray-700/40">
          <span className="text-[11px] font-mono text-green-400 tracking-tight">
            {formatTime(currentTime, 'full')}
          </span>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Remaining indicator */}
        <span className="text-[9px] text-gray-600 font-mono mr-1" title="Remaining">
          -{formatDuration(remaining)}
        </span>

        {/* End time label */}
        <span className="text-[10px] text-gray-500 font-mono whitespace-nowrap text-right">
          {formatTime(stopTime, 'date-time')}
        </span>
      </div>
    </div>
  )
}

export default TimelineControls
