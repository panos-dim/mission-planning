# PR_UI_040 Checklist

## Scope

This PR adds a recurring daily acquisition time window filter to feasibility analysis.
The filter is applied in the backend against each opportunity's off-nadir time
(`max_elevation_time`) across the full mission planning horizon.

## API Payload Example

```json
{
  "acquisition_time_window": {
    "enabled": true,
    "start_time": "15:00",
    "end_time": "17:00",
    "timezone": "UTC",
    "reference": "off_nadir_time"
  }
}
```

## Validation Rules

- Disabled window: no filtering is applied.
- Enabled window: `start_time` and `end_time` are required.
- Time format must be zero-padded `HH:MM`.
- The current Mission Parameters UI inherits UTC from the mission horizon inputs and sends `timezone: "UTC"` in the request payload.
- `reference` is fixed to `off_nadir_time` in v1.
- `start_time == end_time` is rejected in v1.
- Backend validation still requires `timezone` to be a valid IANA timezone name.

## Midnight-Crossing Behavior

- Standard window: `15:00` to `17:00` keeps only opportunities whose off-nadir time falls between those UTC times.
- Overnight window: `22:00` to `02:00` is treated as crossing midnight and keeps opportunities at or after `22:00`, or at or before `02:00`, in UTC.

## Screenshots

- Mission Parameters input:
  Pending capture after UI review.
- Results chip:
  Pending capture after UI review.
- Empty state:
  Pending capture after UI review.

## Manual Verification Results

1. Horizon = 24h, window disabled -> Pending manual verification.
2. Same horizon, window `15:00-17:00` -> Pending manual verification.
3. Window `22:00-02:00` -> Pending manual verification.
4. Window that excludes everything -> Pending manual verification.
5. Active chip appears in results when enabled -> Covered by frontend unit test; pending manual UI confirmation.
6. Filtering uses off-nadir time (`max_elevation_time`) rather than pass start/end text -> Covered by backend implementation and unit tests; pending manual end-to-end confirmation.
