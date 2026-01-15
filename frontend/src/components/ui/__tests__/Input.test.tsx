import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Input } from '../Input'

describe('Input', () => {
  it('renders with label', () => {
    render(<Input label="Email" />)
    expect(screen.getByText('Email')).toBeInTheDocument()
  })

  it('renders with placeholder', () => {
    render(<Input placeholder="Enter email" />)
    expect(screen.getByPlaceholderText('Enter email')).toBeInTheDocument()
  })

  it('handles value changes', () => {
    const handleChange = vi.fn()
    render(<Input onChange={handleChange} />)
    
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'test@example.com' } })
    
    expect(handleChange).toHaveBeenCalled()
  })

  it('displays error message', () => {
    render(<Input error="Invalid email" />)
    expect(screen.getByText('Invalid email')).toBeInTheDocument()
    expect(screen.getByText('Invalid email')).toHaveClass('text-red-400')
  })

  it('displays hint message', () => {
    render(<Input hint="Enter your email address" />)
    expect(screen.getByText('Enter your email address')).toBeInTheDocument()
  })

  it('renders with suffix', () => {
    render(<Input suffix="kg" />)
    expect(screen.getByText('kg')).toBeInTheDocument()
  })

  it('is disabled when disabled prop is true', () => {
    render(<Input disabled />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })

  it('applies size styles', () => {
    const { rerender } = render(<Input size="sm" />)
    expect(screen.getByRole('textbox')).toHaveClass('text-xs')

    rerender(<Input size="lg" />)
    expect(screen.getByRole('textbox')).toHaveClass('text-base')
  })
})
