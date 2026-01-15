import React from 'react'
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
}

const DateTimePicker: React.FC<DateTimePickerProps> = ({ 
  label, 
  value, 
  onChange, 
  minDate,
  icon,
  disabled = false 
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
      <label className="block text-xs font-medium text-gray-400 mb-1">
        {icon || <Calendar className="w-3 h-3 inline mr-1" />}
        {label}
      </label>
      <div className="relative">
        <DatePicker
          selected={dateValue}
          onChange={handleChange}
          showTimeSelect
          timeFormat="HH:mm"
          timeIntervals={15}
          dateFormat="yyyy-MM-dd HH:mm"
          minDate={minDateObj}
          {...(minDateObj && {
            minTime: minDateObj,
            maxTime: new Date(new Date().setHours(23, 45, 0, 0))
          })}
          filterTime={filterTime}
          className={`input-field w-full text-sm ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
          calendarClassName="datetime-picker-calendar"
          wrapperClassName="w-full"
          placeholderText="Select date and time"
          showPopperArrow={false}
          popperPlacement="bottom-start"
          disabled={disabled}
        />
      </div>
    </div>
  )
}

export default DateTimePicker
