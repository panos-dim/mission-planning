import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Card } from '../Card'

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Card content</Card>)
    expect(screen.getByText('Card content')).toBeInTheDocument()
  })

  it('renders with title', () => {
    render(<Card title="Card Title">Content</Card>)
    expect(screen.getByText('Card Title')).toBeInTheDocument()
  })

  it('renders with description', () => {
    render(<Card title="Title" description="Card description">Content</Card>)
    expect(screen.getByText('Card description')).toBeInTheDocument()
  })

  it('renders actions', () => {
    render(
      <Card 
        title="Title" 
        actions={<button>Action</button>}
      >
        Content
      </Card>
    )
    expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument()
  })

  it('renders footer', () => {
    render(<Card footer={<span>Footer content</span>}>Content</Card>)
    expect(screen.getByText('Footer content')).toBeInTheDocument()
  })

  it('handles collapsible state', () => {
    render(
      <Card title="Collapsible Card" collapsible>
        Hidden content
      </Card>
    )
    
    // Content should be visible by default
    expect(screen.getByText('Hidden content')).toBeInTheDocument()
    
    // Click to collapse
    fireEvent.click(screen.getByText('Collapsible Card'))
    
    // Content should be hidden
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument()
  })

  it('starts collapsed when defaultCollapsed is true', () => {
    render(
      <Card title="Collapsed Card" collapsible defaultCollapsed>
        Hidden content
      </Card>
    )
    
    // Content should be hidden by default
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument()
    
    // Click to expand
    fireEvent.click(screen.getByText('Collapsed Card'))
    
    // Content should now be visible
    expect(screen.getByText('Hidden content')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(<Card className="custom-class">Content</Card>)
    expect(container.firstChild).toHaveClass('custom-class')
  })
})
