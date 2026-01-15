#!/usr/bin/env python3
"""
Startup script for the Satellite Mission Planning Web Application.

This script starts both the FastAPI backend and provides instructions
for starting the React frontend development server.
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        print("✅ Backend dependencies found")
    except ImportError as e:
        print(f"❌ Missing backend dependencies: {e}")
        print("Run: pdm install")
        return False
    
    frontend_dir = Path(__file__).parent / "frontend"
    if not (frontend_dir / "node_modules").exists():
        print("❌ Frontend dependencies not installed")
        print("Run: cd frontend && npm install")
        return False
    
    print("✅ Frontend dependencies found")
    return True

def start_backend():
    """Start the FastAPI backend server"""
    backend_dir = Path(__file__).parent / "backend"
    os.chdir(backend_dir)
    
    print("🚀 Starting FastAPI backend on http://localhost:8000")
    
    try:
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Backend server stopped")
    except Exception as e:
        print(f"❌ Failed to start backend: {e}")

def print_instructions():
    """Print startup instructions"""
    print("\n" + "="*60)
    print("🛰️  SATELLITE MISSION PLANNING WEB APPLICATION")
    print("="*60)
    print()
    print("📋 STARTUP INSTRUCTIONS:")
    print()
    print("1. Backend (FastAPI) - Terminal 1:")
    print("   cd backend")
    print("   python main.py")
    print("   → Runs on http://localhost:8000")
    print()
    print("2. Frontend (React) - Terminal 2:")
    print("   cd frontend")
    print("   npm run dev")
    print("   → Runs on http://localhost:3000")
    print()
    print("3. Open your browser:")
    print("   → http://localhost:3000")
    print()
    print("🎯 FEATURES:")
    print("   • 3D Interactive Globe with CesiumJS")
    print("   • Real-time Satellite Tracking")
    print("   • Mission Planning Controls")
    print("   • TLE Input & Validation")
    print("   • Target Management")
    print("   • Mission Results & Export")
    print()
    print("📚 Documentation: README_WEBAPP.md")
    print("="*60)

def main():
    """Main startup function"""
    print_instructions()
    
    if not check_dependencies():
        print("\n❌ Please install missing dependencies first")
        sys.exit(1)
    
    print("\n🔄 Starting backend server...")
    print("💡 Start the frontend in another terminal: cd frontend && npm run dev")
    print()
    
    # Start backend server
    start_backend()

if __name__ == "__main__":
    main()
