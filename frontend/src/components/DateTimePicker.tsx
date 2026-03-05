import React, { useState, useCallback, useEffect } from 'react'
import DatePicker from 'react-datepicker'
import 'react-datepicker/dist/react-datepicker.css'
import { Calendar } from 'lucide-react'

interface DateTimePickerProps {
  label: string
  value: string // ISO string format YYYY-MM-DDTHH:mm
  onChange: (value: string) => void
  minDate?: string
  icon?: React.ReactNode
  disabled?: boolean
  /** Intercept raw text input (e.g. '+1d' offsets). Return true if handled externally. */
  onRawInput?: (raw: string) => boolean
  placeholder?: string
}

// ---------------------------------------------------------------------------
// OffsetAwareInput — custom input for DatePicker that supports typing offsets
// When the user types text starting with '+', the input manages its own value
// and delegates parsing to onRawInput. On blur/Enter it resets to the
// resolved date value that DatePicker passes via props.
// ---------------------------------------------------------------------------
interface OffsetInputProps {
  value?: string
  onClick?: () => void
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void
  onRawInput?: (raw: string) => boolean
  className?: string
  placeholder?: string
  disabled?: boolean
}

const OffsetAwareInput = React.forwardRef<HTMLInputElement, OffsetInputProps>(
  ({ value = '', onClick, onChange, onRawInput, className, placeholder, disabled }, ref) => {
    const [isOffsetMode, setIsOffsetMode] = useState(false)
    const [rawText, setRawText] = useState('')

    // Exit offset mode when the parent value changes (offset was resolved)
    useEffect(() => {
      if (!isOffsetMode) return
      // Value changed → offset was resolved, stay in offset mode until blur
    }, [value, isOffsetMode])

    const handleChange = useCallback(
      (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value

        if (val.startsWith('+')) {
          // Offset mode: manage our own text, delegate parsing
          setIsOffsetMode(true)
          setRawText(val)
          onRawInput?.(val)
        } else {
          // Normal date text: pass through to DatePicker
          setIsOffsetMode(false)
          setRawText('')
          onChange?.(e)
        }
      },
      [onChange, onRawInput],
    )

    const exitOffsetMode = useCallback(() => {
      setIsOffsetMode(false)
      setRawText('')
    }, [])

    const handleKeyDown = useCallback(
      (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && isOffsetMode) {
          exitOffsetMode()
          ;(e.target as HTMLInputElement).blur()
        }
        if (e.key === 'Escape') {
          exitOffsetMode()
        }
      },
      [isOffsetMode, exitOffsetMode],
    )

    return (
      <input
        ref={ref}
        type="text"
        value={isOffsetMode ? rawText : value}
        onClick={isOffsetMode ? undefined : onClick}
        onChange={handleChange}
        onBlur={exitOffsetMode}
        onKeyDown={handleKeyDown}
        className={className}
        placeholder={placeholder}
        disabled={disabled}
      />
    )
  },
)
OffsetAwareInput.displayName = 'OffsetAwareInput'

const DateTimePicker: React.FC<DateTimePickerProps> = ({
  label,
  value,
  onChange,
  minDate,
  icon,
  disabled = false,
  onRawInput,
  placeholder,
}) => {
  // Convert ISO string to Date object
  const dateValue = value ? new Date(value) : new Date()

  // Convert minDate string to Date object if provided
  const minDateObj = minDate ? new Date(minDate) : undefined

  const handleChange = (date: Date | null) => {
    if (date) {
      // Validate that the selected date is not before minDate
      if (minDateObj && date < minDateObj) {
        // If selected time is before minimum, set it to minimum time
        date = minDateObj
      }

      // Format to YYYY-MM-DDTHH:mm for datetime-local compatibility
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')

      const formatted = `${year}-${month}-${day}T${hours}:${minutes}`
      onChange(formatted)
    }
  }

  // Filter time to only allow times after minDate on the same day
  const filterTime = (time: Date) => {
    if (!minDateObj) return true

    // Get the date components (without time) for comparison
    const timeDate = new Date(time)
    const minDate = new Date(minDateObj)

    // Reset hours/minutes/seconds for date-only comparison
    const timeDateOnly = new Date(timeDate.getFullYear(), timeDate.getMonth(), timeDate.getDate())
    const minDateOnly = new Date(minDate.getFullYear(), minDate.getMonth(), minDate.getDate())

    // If selected date is AFTER minDate (future day), allow all times
    if (timeDateOnly.getTime() > minDateOnly.getTime()) {
      return true
    }

    // If selected date is BEFORE minDate (past day), block all times
    if (timeDateOnly.getTime() < minDateOnly.getTime()) {
      return false
    }

    // Same day - only allow times after the minimum time
    return timeDate.getTime() >= minDate.getTime()
  }

  return (
    <div>
      {label && (
        <label className="block text-xs font-medium text-gray-400 mb-1">
          {icon === undefined ? <Calendar className="w-3 h-3 inline mr-1" /> : icon}
          {label}
        </label>
      )}
      <div className="relative">
        <DatePicker
          selected={dateValue}
          onChange={handleChange}
          showTimeSelect
          timeFormat="HH:mm"
          timeIntervals={15}
          dateFormat="dd-MM-yyyy HH:mm"
          minDate={minDateObj}
          {...(minDateObj && {
            minTime: minDateObj,
            maxTime: new Date(new Date().setHours(23, 45, 0, 0)),
          })}
          filterTime={filterTime}
          customInput={
            onRawInput ? (
              <OffsetAwareInput
                onRawInput={onRawInput}
                className={`input-field w-full text-sm ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                placeholder={placeholder || 'Select date and time'}
                disabled={disabled}
              />
            ) : undefined
          }
          className={`input-field w-full text-sm ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
          calendarClassName="datetime-picker-calendar"
          wrapperClassName="w-full"
          placeholderText={placeholder || 'Select date and time'}
          showPopperArrow={false}
          popperPlacement="bottom-start"
          disabled={disabled}
        />
      </div>
    </div>
  )
}

export default DateTimePicker
