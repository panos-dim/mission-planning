# UI Component Library

> Shared UI primitives for consistent styling across the application

## Overview

The UI component library is located in `frontend/src/components/ui/` and provides:

- **Consistent styling** using Tailwind CSS
- **Accessibility** with proper ARIA attributes
- **Type safety** with TypeScript interfaces
- **Variants** for different use cases

## Components

### Button

```tsx
import { Button } from '@/components/ui'

// Variants
<Button variant="primary">Primary Action</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="danger">Delete</Button>
<Button variant="success">Confirm</Button>

// Sizes
<Button size="sm">Small</Button>
<Button size="md">Medium</Button>
<Button size="lg">Large</Button>

// With icon
<Button icon={<Save />}>Save Changes</Button>
<Button icon={<Trash />} iconPosition="right">Delete</Button>

// Loading state
<Button loading>Processing...</Button>
```

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| variant | `'primary' \| 'secondary' \| 'ghost' \| 'danger' \| 'success'` | `'primary'` | Visual style |
| size | `'sm' \| 'md' \| 'lg'` | `'md'` | Button size |
| loading | `boolean` | `false` | Show loading spinner |
| icon | `ReactNode` | - | Icon element |
| iconPosition | `'left' \| 'right'` | `'left'` | Icon placement |
| disabled | `boolean` | `false` | Disable button |

---

### Input

```tsx
import { Input } from '@/components/ui'

// Basic
<Input label="Email" placeholder="you@example.com" />

// With error
<Input label="Password" error="Password is required" />

// With hint
<Input label="API Key" hint="Found in settings" />

// With suffix
<Input label="Angle" suffix="°" type="number" />

// With icons
<Input leftIcon={<Search />} placeholder="Search..." />
<Input rightIcon={<Check />} />
```

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| label | `string` | - | Label text |
| error | `string` | - | Error message (red) |
| hint | `string` | - | Hint text (gray) |
| suffix | `string` | - | Right-side text suffix |
| leftIcon | `ReactNode` | - | Left icon |
| rightIcon | `ReactNode` | - | Right icon |
| size | `'sm' \| 'md' \| 'lg'` | `'md'` | Input size |

---

### Select

```tsx
import { Select } from '@/components/ui'

const options = [
  { value: 'optical', label: 'Optical Imaging' },
  { value: 'sar', label: 'SAR Imaging' },
  { value: 'communication', label: 'Communication' }
]

<Select
  label="Mission Type"
  options={options}
  placeholder="Select type..."
/>
```

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| label | `string` | - | Label text |
| options | `SelectOption[]` | Required | Array of options |
| placeholder | `string` | - | Placeholder text |
| error | `string` | - | Error message |
| hint | `string` | - | Hint text |

---

### Card

```tsx
import { Card } from '@/components/ui'

// Basic
<Card title="Mission Parameters">
  <p>Content goes here</p>
</Card>

// With description
<Card 
  title="Results" 
  description="Algorithm comparison"
>
  {/* content */}
</Card>

// Collapsible
<Card title="Advanced Settings" collapsible defaultCollapsed>
  {/* hidden by default */}
</Card>

// With actions
<Card 
  title="Schedule" 
  actions={<Button size="sm">Export</Button>}
>
  {/* content */}
</Card>

// With footer
<Card title="Form" footer={<Button>Submit</Button>}>
  {/* form fields */}
</Card>
```

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| title | `string` | - | Card header title |
| description | `string` | - | Subtitle text |
| children | `ReactNode` | Required | Card body content |
| footer | `ReactNode` | - | Footer content |
| actions | `ReactNode` | - | Header action buttons |
| collapsible | `boolean` | `false` | Allow collapse |
| defaultCollapsed | `boolean` | `false` | Start collapsed |

---

### Modal

```tsx
import { Modal } from '@/components/ui'

<Modal
  isOpen={showModal}
  onClose={() => setShowModal(false)}
  title="Confirm Action"
  description="Are you sure you want to proceed?"
  footer={
    <>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button onClick={onConfirm}>Confirm</Button>
    </>
  }
>
  <p>This action cannot be undone.</p>
</Modal>
```

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| isOpen | `boolean` | Required | Visibility state |
| onClose | `() => void` | Required | Close handler |
| title | `string` | - | Modal title |
| description | `string` | - | Subtitle |
| size | `'sm' \| 'md' \| 'lg' \| 'xl' \| 'full'` | `'md'` | Modal width |
| showCloseButton | `boolean` | `true` | Show X button |
| closeOnOverlayClick | `boolean` | `true` | Close on backdrop click |
| closeOnEscape | `boolean` | `true` | Close on Esc key |

---

### Tabs

```tsx
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'

<Tabs defaultValue="overview">
  <TabsList>
    <TabsTrigger value="overview">Overview</TabsTrigger>
    <TabsTrigger value="details">Details</TabsTrigger>
    <TabsTrigger value="history">History</TabsTrigger>
  </TabsList>
  
  <TabsContent value="overview">
    Overview content
  </TabsContent>
  <TabsContent value="details">
    Details content
  </TabsContent>
  <TabsContent value="history">
    History content
  </TabsContent>
</Tabs>
```

---

### Badge

```tsx
import { Badge } from '@/components/ui'

<Badge>Default</Badge>
<Badge variant="success">Completed</Badge>
<Badge variant="warning">Pending</Badge>
<Badge variant="error">Failed</Badge>
<Badge variant="info">Processing</Badge>

// With icon
<Badge variant="success" icon={<Check size={12} />}>
  Verified
</Badge>
```

---

### Spinner

```tsx
import { Spinner } from '@/components/ui'

<Spinner />
<Spinner size="sm" />
<Spinner size="lg" />
```

---

### ProgressBar

```tsx
import { ProgressBar } from '@/components/ui'

<ProgressBar value={75} />
<ProgressBar value={50} variant="success" showLabel />
<ProgressBar value={30} label="Processing..." animated />
```

---

### Tooltip

```tsx
import { Tooltip } from '@/components/ui'

<Tooltip content="Click to save">
  <Button icon={<Save />} />
</Tooltip>

<Tooltip content="More info" position="bottom" delay={500}>
  <span>Hover me</span>
</Tooltip>
```

---

## Utility: cn()

The `cn()` function merges class names with conditional support:

```tsx
import { cn } from '@/components/ui'

<div className={cn(
  'base-class',
  isActive && 'active-class',
  isDisabled && 'opacity-50 cursor-not-allowed'
)}>
  Content
</div>
```

---

## Import Pattern

```tsx
// Named imports (recommended)
import { Button, Input, Card } from '@/components/ui'

// Individual imports
import { Button } from '@/components/ui/Button'
```

---

## Styling Convention

All components use Tailwind CSS with the following patterns:

### Color Palette
- **Primary**: `blue-600` (actions, links)
- **Success**: `green-600` (confirmations)
- **Warning**: `yellow-600` (cautions)
- **Error**: `red-600` (errors, destructive)
- **Surface**: `gray-700`/`gray-800` (backgrounds)
- **Border**: `gray-600`/`gray-700`

### Focus States
```css
focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900
```

### Transitions
```css
transition-colors duration-200
```
