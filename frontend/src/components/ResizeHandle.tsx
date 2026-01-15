import { useState, useEffect, useRef } from 'react'

interface ResizeHandleProps {
  side: 'left' | 'right'
  onResize: (width: number) => void
  currentWidth: number
  minWidth?: number
  maxWidth?: number
}

export default function ResizeHandle({ 
  side, 
  onResize, 
  currentWidth,
  minWidth = 432,
  maxWidth = 864
}: ResizeHandleProps): JSX.Element {
  const [isDragging, setIsDragging] = useState(false)
  const startXRef = useRef<number>(0)
  const startWidthRef = useRef<number>(0)

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = side === 'left' ? e.clientX - startXRef.current : startXRef.current - e.clientX
      const newWidth = Math.min(Math.max(startWidthRef.current + deltaX, minWidth), maxWidth)
      onResize(newWidth)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      document.body.style.cursor = 'default'
      document.body.style.userSelect = 'auto'
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, side, onResize, minWidth, maxWidth])

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    startXRef.current = e.clientX
    startWidthRef.current = currentWidth
    document.body.style.cursor = side === 'left' ? 'ew-resize' : 'ew-resize'
    document.body.style.userSelect = 'none'
  }

  return (
    <div
      className={`absolute top-0 bottom-0 w-1 group cursor-ew-resize z-50 ${
        side === 'left' ? 'right-0' : 'left-0'
      }`}
      onMouseDown={handleMouseDown}
    >
      {/* Invisible wider hit area */}
      <div className="absolute inset-y-0 -inset-x-2" />
      
      {/* Visual indicator */}
      <div
        className={`absolute inset-0 transition-colors ${
          isDragging
            ? 'bg-blue-500'
            : 'bg-gray-600 group-hover:bg-blue-400'
        }`}
      />
      
      {/* Resize icon hint */}
      <div
        className={`absolute top-1/2 -translate-y-1/2 ${
          side === 'left' ? '-right-2' : '-left-2'
        } opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none`}
      >
        <div className="bg-gray-800 rounded px-1 py-2 shadow-lg border border-gray-600">
          <svg
            width="8"
            height="24"
            viewBox="0 0 8 24"
            fill="none"
            className="text-gray-400"
          >
            <circle cx="2" cy="8" r="1.5" fill="currentColor" />
            <circle cx="6" cy="8" r="1.5" fill="currentColor" />
            <circle cx="2" cy="12" r="1.5" fill="currentColor" />
            <circle cx="6" cy="12" r="1.5" fill="currentColor" />
            <circle cx="2" cy="16" r="1.5" fill="currentColor" />
            <circle cx="6" cy="16" r="1.5" fill="currentColor" />
          </svg>
        </div>
      </div>
    </div>
  )
}
