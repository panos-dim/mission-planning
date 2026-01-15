# Satellite Mission Planning Web Application

A modern, interactive 3D web application for satellite mission planning with real-time orbital visualization using CesiumJS.

## Features

### 🛰️ **3D Visualization**
- Interactive 3D globe with CesiumJS/Resium
- Real-time satellite orbital tracks
- Animated satellite imaging opportunities with time controls
- Target markers and visibility areas
- CZML-based time-dynamic visualization

### 📡 **Mission Planning**
- TLE input and validation
- Multiple ground target support
- Communication and imaging mission types
- Configurable elevation masks and pointing angles
- Minimum imaging separation filtering

### 🎛️ **Modern UI**
- TypeScript React frontend with Tailwind CSS
- Responsive design with glass-morphism effects
- Real-time mission controls overlay
- Comprehensive mission results sidebar
- JSON/CSV export functionality

### 🔧 **Backend API**
- FastAPI REST API
- CZML generation for Cesium
- Integration with existing mission planner modules
- Real-time orbit propagation

## Architecture

```
mission-planning/
├── backend/                 # Python FastAPI backend
│   ├── main.py             # FastAPI application
│   ├── czml_generator.py   # CZML generation for Cesium
│   └── __init__.py
├── frontend/               # React TypeScript frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── context/        # React context for state management
│   │   ├── types/          # TypeScript type definitions
│   │   ├── App.tsx         # Main application component
│   │   └── main.tsx        # Application entry point
│   ├── package.json        # Frontend dependencies
│   ├── tsconfig.json       # TypeScript configuration
│   ├── tailwind.config.js  # Tailwind CSS configuration
│   └── vite.config.js      # Vite build configuration
├── src/mission_planner/    # Existing mission planner modules
└── pyproject.toml          # Python dependencies (updated)
```

## Quick Start

### 1. Install Dependencies

**Backend (Python):**
```bash
# Install Python dependencies
pdm install
```

**Frontend (Node.js):**
```bash
cd frontend
npm install
```

### 2. Start the Application

**Terminal 1 - Backend:**
```bash
# Start FastAPI backend
cd backend
python main.py
# Backend runs on http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
# Start React development server
cd frontend
npm run dev
# Frontend runs on http://localhost:3000
```

### 3. Access the Application

Open your browser and navigate to: **http://localhost:3000**

## Usage Guide

### 1. **Configure Mission**
- **TLE Data**: Input satellite TLE data or use sample (ICEYE-X44)
- **Targets**: Add ground targets with coordinates
- **Parameters**: Set mission type, duration, elevation mask

### 2. **Analyze Mission**
- Click "Analyze Mission" to compute satellite imaging opportunities
- View real-time 3D visualization on the globe
- Use time controls to animate the mission timeline

### 3. **Review Results**
- **Overview**: Mission summary and statistics
- **Schedule**: Detailed imaging opportunity information
- **Timeline**: Chronological mission events
- **Summary**: Mission statistics and metrics

### 4. **Export Data**
- Download mission data as JSON
- Export imaging opportunity schedule as CSV
- Compatible with existing CLI tool outputs

## API Endpoints

### `POST /api/validate-tle`
Validate TLE data and return satellite information.

### `POST /api/mission/analyze`
Analyze mission and return visibility windows with CZML data.

### `GET /api/mission/czml`
Get CZML data for current mission.

### `GET /api/mission/schedule`
Get mission schedule data.

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server
- **Existing modules**: orbit-predictor, cartopy, matplotlib

### Frontend
- **React 18**: Modern React with hooks
- **TypeScript**: Type-safe JavaScript
- **Vite**: Fast build tool and dev server
- **Tailwind CSS**: Utility-first CSS framework
- **CesiumJS**: 3D globe and geospatial visualization
- **Resium**: React components for CesiumJS
- **Lucide React**: Modern icon library

## Development

### Frontend Development
```bash
cd frontend
npm run dev     # Start development server
npm run build   # Build for production
npm run preview # Preview production build
```

### Backend Development
```bash
cd backend
python main.py  # Start development server
# Auto-reload enabled for development
```

### Type Checking
```bash
cd frontend
npx tsc --noEmit  # Check TypeScript types
```

## Production Deployment

### Build Frontend
```bash
cd frontend
npm run build
# Builds to frontend/dist/
```

### Serve Application
```bash
# Backend serves both API and static files
cd backend
python main.py
# Access at http://localhost:8000
```

## Integration with CLI Tool

The web application integrates seamlessly with the existing CLI mission planner:

- **Same core modules**: Uses existing `src/mission_planner/` modules
- **Compatible outputs**: Generates same JSON/CSV formats
- **Shared algorithms**: Same orbit propagation and visibility calculations
- **Enhanced visualization**: Adds 3D interactive visualization layer

## Troubleshooting

### Common Issues

1. **CORS Errors**: Ensure backend is running on port 8000
2. **Cesium Loading**: Check network connection for Cesium assets
3. **TLE Validation**: Verify TLE format and satellite name
4. **Build Errors**: Clear node_modules and reinstall dependencies

### Performance Tips

1. **Large missions**: Use shorter durations for better performance
2. **Multiple targets**: Limit to 5-10 targets for optimal visualization
3. **Time range**: Reduce time step for smoother animations

## Contributing

1. Follow existing code structure and patterns
2. Use TypeScript for all frontend code
3. Add proper error handling and validation
4. Test with various satellite TLEs and target locations
5. Maintain compatibility with existing CLI tool

## License

MIT License - Same as the original mission planning tool.
