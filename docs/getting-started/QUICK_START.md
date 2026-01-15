# Quick Start Guide

> Get your first mission analysis running in 5 minutes

## Prerequisites

Ensure you have:

- Node.js 22+ (via nvm)
- Python 3.11+
- PDM installed

## 1. Start the Application

```bash
cd mission-planning
./run_dev.sh
```

This starts both backend (port 8000) and frontend (port 5173).

Open: **http://localhost:5173**

## 2. Configure a Satellite

The application comes with pre-configured satellites. To use them:

1. Click **Admin Panel** (shield icon, bottom of left sidebar)
2. Go to **Satellites** tab
3. Select a satellite (e.g., ICEYE-X44)
4. Click **Set as Active**

## 3. Add Targets

In the **Mission Analysis** panel (left sidebar):

### Option A: Manual Entry

1. Enter target name (e.g., "Athens")
2. Enter coordinates: `37.9838, 23.7275`
3. Set priority (1-5)
4. Click **Add Target**

### Option B: Click on Map

1. Click **Add Target Mode** button
2. Click on the map to place targets
3. Enter name in the popup

### Option C: Upload File

1. Click **Upload** button
2. Select CSV or KML file with targets

## 4. Set Mission Parameters

Configure your mission:

| Parameter | Description | Example |
|-----------|-------------|---------|
| Start Time | Mission start (UTC) | Current time |
| End Time | Mission end (UTC) | +48 hours |
| Mission Type | Imaging or Communication | Imaging |
| Elevation Mask | Minimum elevation | 10° |

## 5. Run Analysis

Click **Analyze Mission**

The system will:

1. Propagate satellite orbit
2. Calculate visibility windows
3. Find imaging opportunities
4. Generate visualization

## 6. View Results

After analysis:

- **Map**: Shows satellite path, targets, coverage circles
- **Mission Results** (right sidebar): Lists all passes
- **Timeline**: Scrub through time to see satellite position

### Navigate Passes

- Click on a pass in results to jump to that time
- Use timeline controls to animate

## 7. Run Mission Planning

Switch to **Mission Planning** panel:

1. Configure spacecraft agility parameters
2. Select algorithms to compare
3. Click **Run All**
4. Compare results in the comparison table
5. Click **Accept This Plan** to create an order

## 8. Export Results

From the results panel:

- **Export CSV**: Schedule in spreadsheet format
- **Export JSON**: Full data for integration

---

## Example Mission

### Scenario: Monitor 5 Greek Cities

**Targets:**

| City | Lat | Lon | Priority |
|------|-----|-----|----------|
| Athens | 37.98 | 23.73 | 1 |
| Thessaloniki | 40.63 | 22.94 | 2 |
| Patras | 38.25 | 21.73 | 3 |
| Heraklion | 35.34 | 25.13 | 2 |
| Larissa | 39.64 | 22.42 | 3 |

**Settings:**

- Duration: 48 hours
- Mission Type: Optical Imaging
- Max Roll: 45°

**Expected Results:**

- ~10-15 passes total
- 80-100% target coverage with roll+pitch algorithms

---

## Troubleshooting

### "No opportunities found"

- Check elevation mask isn't too high
- Verify target coordinates are correct
- Ensure time window is long enough (24+ hours)

### Satellite not moving

- Click **Reset Timeline** button
- Check that mission data loaded successfully

### Map not loading

- Verify Cesium Ion token in `.env`
- Check browser console for errors

---

## Next Steps

- [Configure Ground Stations](./CONFIGURATION.md)
- [Understand Algorithms](../algorithms/ALGORITHM_OVERVIEW.md)
- [API Integration](../api/API_REFERENCE.md)
