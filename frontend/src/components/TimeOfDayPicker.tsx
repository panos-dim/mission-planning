import React from 'react'
import DatePicker from 'react-datepicker'
import 'react-datepicker/dist/react-datepicker.css'

interface TimeOfDayPickerProps {
  id: string
  value?: string | null
  onChange: (value: string | null) => void
  disabled?: boolean
  placeholder?: string
}

function parseTimeValue(value?: string | null): Date | null {
  if (!value) return null

  const match = value.match(/^([01]\d|2[0-3]):([0-5]\d)$/)
  if (!match) return null

  const hours = Number(match[1])
  const minutes = Number(match[2])
  return new Date(2000, 0, 1, hours, minutes, 0, 0)
}

function formatTimeValue(value: Date): string {
  const hours = String(value.getHours()).padStart(2, '0')
  const minutes = String(value.getMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

const TimeOfDayPicker: React.FC<TimeOfDayPickerProps> = ({
  id,
  value,
  onChange,
  disabled = false,
  placeholder = 'HH:MM',
}) => {
  return (
    <DatePicker
      id={id}
      selected={parseTimeValue(value)}
      onChange={(date) => onChange(date ? formatTimeValue(date) : null)}
      showTimeSelect
      showTimeSelectOnly
      timeFormat="HH:mm"
      timeIntervals={15}
      timeCaption="Time"
      dateFormat="HH:mm"
      strictParsing
      className={`input-field w-full py-1.5 text-sm tabular-nums ${
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
      }`}
      calendarClassName="time-only-picker"
      popperClassName="time-only-picker-popper"
      wrapperClassName="w-full"
      placeholderText={placeholder}
      showPopperArrow={false}
      popperPlacement="bottom-start"
      disabled={disabled}
      autoComplete="off"
    />
  )
}

export default TimeOfDayPicker
