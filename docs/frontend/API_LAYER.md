# API Layer Documentation

## Overview

The API layer provides a centralized, type-safe interface for all backend communication with automatic retry, timeout handling, and runtime validation.

## Directory Structure

```plaintext
src/api/
├── client.ts      # HTTP client with retry/timeout
├── config.ts      # API configuration
├── errors.ts      # Custom error classes
├── mission.ts     # Mission API endpoints
├── tle.ts         # TLE API endpoints
├── configApi.ts   # Config API endpoints
├── validate.ts    # Runtime validation utilities
├── schemas/       # Zod validation schemas
│   └── index.ts
└── index.ts       # Barrel export
```

## Configuration

### Environment Variables

```bash
# .env or .env.local
VITE_API_URL=http://localhost:8000
```

### API Configuration (`config.ts`)

```typescript
// Base URL with fallback
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Endpoints
export const API_ENDPOINTS = {
  MISSION_ANALYZE: '/api/mission/analyze',
  MISSION_PLAN: '/api/mission/plan',
  TLE_VALIDATE: '/api/tle/validate',
  TLE_SOURCES: '/api/tle/sources',
  CONFIG_GROUND_STATIONS: '/api/config/ground-stations',
  // ...
}

// Timeouts
export const TIMEOUTS = {
  DEFAULT: 30000,
  MISSION_ANALYSIS: 60000,
  TLE_SEARCH: 15000,
}

// Retry configuration
export const RETRY_CONFIG = {
  MAX_RETRIES: 3,
  RETRY_DELAY_MS: 1000,
  RETRY_BACKOFF_MULTIPLIER: 2,
}
```

## HTTP Client (`client.ts`)

The HTTP client provides a centralized fetch wrapper with:

- Automatic retry with exponential backoff
- Request timeout handling
- AbortController support
- Detailed error handling
- Debug logging integration

### Usage

```typescript
import { apiClient } from '@/api'

// GET request
const data = await apiClient.get<ResponseType>('/api/endpoint')

// POST request
const result = await apiClient.post<ResponseType, RequestType>(
  '/api/endpoint',
  requestData,
  { timeout: 60000 }
)

// With abort signal
const controller = new AbortController()
const result = await apiClient.get('/api/endpoint', {
  signal: controller.signal
})
// Cancel: controller.abort()
```

## Error Handling

### Custom Error Classes

```typescript
import { ApiError, NetworkError, TimeoutError, isApiError } from '@/api'

try {
  await missionApi.analyze(request)
} catch (error) {
  if (isApiError(error)) {
    if (error.isServerError) {
      console.log('Server error:', error.status)
    }
  }
}
```

### Error Types

| Class | Description |
|-------|-------------|
| `ApiError` | HTTP error (4xx, 5xx) |
| `NetworkError` | Network/connection failure |
| `TimeoutError` | Request timeout |
| `ValidationError` | Response validation failure |

### Error Utilities

```typescript
import { getErrorMessage, isApiError, isNetworkError, isTimeoutError } from '@/api'

// Get user-friendly message
const message = getErrorMessage(error)

// Type guards
if (isApiError(error)) { /* handle API error */ }
if (isNetworkError(error)) { /* handle network error */ }
if (isTimeoutError(error)) { /* handle timeout */ }
```

## API Modules

### Mission API (`mission.ts`)

```typescript
import { missionApi } from '@/api'

// Analyze mission
const result = await missionApi.analyze({
  tle: { name: 'SAT-1', line1: '...', line2: '...' },
  targets: [{ name: 'Target1', latitude: 25.0, longitude: 55.0 }],
  start_time: '2025-01-01T00:00:00Z',
  end_time: '2025-01-02T00:00:00Z',
  mission_type: 'imaging',
})

// Plan mission
const planResult = await missionApi.plan({
  opportunities: [...],
  algorithms: ['first_fit', 'best_fit'],
  // ...
})
```

### TLE API (`tle.ts`)

```typescript
import { tleApi } from '@/api'

// Validate TLE
const validation = await tleApi.validate({
  name: 'ISS',
  line1: '1 25544U...',
  line2: '2 25544...'
})

// Get Celestrak sources
const sources = await tleApi.getSources()

// Search satellites
const results = await tleApi.search('active', 'ISS')
```

### Config API (`configApi.ts`)

```typescript
import { configApi } from '@/api'

// Get ground stations
const { ground_stations } = await configApi.getGroundStations()

// Get mission settings
const { settings } = await configApi.getMissionSettings()
```

## Runtime Validation

### Zod Schemas

All API responses are validated at runtime using Zod schemas:

```typescript
// schemas/index.ts
export const MissionAnalyzeResponseSchema = z.object({
  success: z.boolean(),
  message: z.string().optional(),
  data: z.object({
    mission_data: MissionDataSchema,
    czml_data: z.array(CZMLPacketSchema),
  }).optional(),
})
```

### Validation Behavior

- **Development**: Logs warnings but returns data
- **Production**: Throws ValidationError on failure

```typescript
import { validateResponse } from '@/api'

// Manual validation
const validData = validateResponse(MySchema, response, 'context')
```

## TanStack Query Integration

The API layer integrates with TanStack Query for caching:

```typescript
// hooks/queries/useMissionQueries.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { missionApi } from '@/api'

export function useMissionAnalysis() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (request) => missionApi.analyze(request),
    onSuccess: (data) => {
      queryClient.setQueryData(['mission', 'current'], data)
    }
  })
}
```

### Query Hooks

```typescript
import { 
  useMissionAnalysis, 
  useTLEValidation,
  useGroundStations 
} from '@/hooks/queries'

// In component
const { mutate: analyze, isLoading } = useMissionAnalysis()
const { data: sources } = useTLESources()
const { data: groundStations } = useGroundStations()
```

## Best Practices

### 1. Always Use AbortController

```typescript
const abortRef = useRef<AbortController | null>(null)

const fetchData = async () => {
  abortRef.current?.abort()
  abortRef.current = new AbortController()
  
  await missionApi.analyze(request, {
    signal: abortRef.current.signal
  })
}

// Cleanup on unmount
useEffect(() => () => abortRef.current?.abort(), [])
```

### 2. Handle Errors Gracefully

```typescript
try {
  await missionApi.analyze(request)
} catch (error) {
  if (error instanceof Error && error.name === 'AbortError') {
    return // Request was cancelled, don't show error
  }
  setError(getErrorMessage(error))
}
```

### 3. Use Query Hooks for Caching

```typescript
// ❌ Direct API call (no caching)
const data = await configApi.getGroundStations()

// ✅ Query hook (with caching)
const { data } = useGroundStations()
```
