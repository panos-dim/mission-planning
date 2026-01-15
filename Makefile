# Mission Planning Tool - Development Commands
# Usage: make <target>

.PHONY: help install dev test lint format clean build

# Default target
help:
	@echo "Mission Planning Tool - Available Commands"
	@echo ""
	@echo "  make install     Install all dependencies (backend + frontend)"
	@echo "  make dev         Start development servers (backend + frontend)"
	@echo "  make test        Run all tests"
	@echo "  make lint        Run linters (Python + TypeScript)"
	@echo "  make format      Format code (Python + TypeScript)"
	@echo "  make typecheck   Run type checkers"
	@echo "  make clean       Clean build artifacts"
	@echo "  make build       Build for production"
	@echo ""
	@echo "Backend only:"
	@echo "  make backend     Start backend server only"
	@echo "  make test-py     Run Python tests"
	@echo "  make lint-py     Lint Python code"
	@echo "  make format-py   Format Python code"
	@echo ""
	@echo "Frontend only:"
	@echo "  make frontend    Start frontend server only"
	@echo "  make test-fe     Run frontend tests"
	@echo "  make lint-fe     Lint TypeScript code"
	@echo ""

# ============================================
# Full Stack Commands
# ============================================

install: install-py install-fe
	@echo "✅ All dependencies installed"

dev:
	@./run_dev.sh

test: test-py test-fe
	@echo "✅ All tests passed"

lint: lint-py lint-fe
	@echo "✅ All linting passed"

format: format-py
	@echo "✅ Code formatted"

typecheck: typecheck-py typecheck-fe
	@echo "✅ Type checking passed"

clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .mypy_cache/ .coverage htmlcov/
	@rm -rf frontend/dist/ frontend/node_modules/.cache/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"

build: build-fe
	@echo "✅ Build complete"

# ============================================
# Backend (Python) Commands
# ============================================

install-py:
	@echo "📦 Installing Python dependencies..."
	@python -m venv .venv 2>/dev/null || true
	@.venv/bin/pip install -e ".[dev]" -q

backend:
	@echo "🚀 Starting backend server..."
	@.venv/bin/python -m uvicorn backend.main:app --reload --port 8000

test-py:
	@echo "🧪 Running Python tests..."
	@.venv/bin/pytest tests/ -v

test-py-cov:
	@echo "🧪 Running Python tests with coverage..."
	@.venv/bin/pytest tests/ --cov=src/mission_planner --cov-report=html

lint-py:
	@echo "🔍 Linting Python code..."
	@.venv/bin/flake8 src/ backend/ --max-line-length=88 --extend-ignore=E203,W503

format-py:
	@echo "🎨 Formatting Python code..."
	@.venv/bin/black src/ backend/ tests/
	@.venv/bin/isort src/ backend/ tests/

typecheck-py:
	@echo "📝 Type checking Python..."
	@.venv/bin/mypy src/ --ignore-missing-imports

# ============================================
# Frontend (TypeScript) Commands
# ============================================

install-fe:
	@echo "📦 Installing frontend dependencies..."
	@cd frontend && npm install --silent

frontend:
	@echo "🚀 Starting frontend server..."
	@cd frontend && npm run dev

test-fe:
	@echo "🧪 Running frontend tests..."
	@cd frontend && npm run test:run

test-fe-watch:
	@echo "🧪 Running frontend tests (watch mode)..."
	@cd frontend && npm run test

lint-fe:
	@echo "🔍 Linting TypeScript code..."
	@cd frontend && npm run lint

typecheck-fe:
	@echo "📝 Type checking TypeScript..."
	@cd frontend && npx tsc --noEmit

build-fe:
	@echo "🏗️ Building frontend..."
	@cd frontend && npm run build

# ============================================
# Utility Commands
# ============================================

benchmark:
	@echo "📊 Running benchmarks..."
	@.venv/bin/python scripts/benchmark_adaptive.py

validate:
	@echo "✅ Running validation..."
	@.venv/bin/python scripts/validate_adaptive_stepping.py

# Quick checks before commit
precommit: format lint typecheck test
	@echo "✅ Pre-commit checks passed"
